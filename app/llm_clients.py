"""
LLM Client Adapters for Timing Analysis
Provides unified interface for Cerebras and Cohere APIs with error handling
"""

import os
import time
import json
import requests
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from app.schemas import ViolationPrompt, LlmResult, validate_llm_output, create_fallback_result

class LlmClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    def json_chat(self, system: str, user_content: str) -> str:
        """Send structured prompt and get raw JSON response"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if client is properly configured"""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get model identifier for metadata"""
        pass

class CerebrasClient(LlmClient):
    """
    Cerebras client optimized for ultra-fast timing analysis
    Uses OpenAI-compatible API with millisecond latency
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama3.1-70b"):
        self.api_key = api_key or os.environ.get('CEREBRAS_API_KEY', '')
        self.base_url = 'https://api.cerebras.ai/v1'
        self.model = model
        self.timeout = 15  # Cerebras is fast, but allow reasonable timeout
        
        # Optimized parameters for timing analysis
        self.default_params = {
            'temperature': 0.2,  # Low for consistent technical advice
            'max_tokens': 1200,  # Enough for detailed analysis
            'top_p': 0.9
        }
    
    def is_available(self) -> bool:
        """Check if Cerebras API is configured"""
        return bool(self.api_key)
    
    def get_model_name(self) -> str:
        """Get model identifier"""
        return f"cerebras-{self.model}"
    
    def json_chat(self, system: str, user_content: str) -> str:
        """
        Send chat request to Cerebras API
        Optimized for structured JSON output
        """
        if not self.is_available():
            raise ValueError("Cerebras API key not configured")
        
        # Enhanced system prompt for JSON compliance
        enhanced_system = f"""{system}

CRITICAL: You must respond with valid JSON only. No markdown, no code blocks, no explanations outside the JSON structure. The JSON must exactly match the required schema."""
        
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': enhanced_system},
                {'role': 'user', 'content': user_content}
            ],
            **self.default_params
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                
                # Clean common formatting issues
                if content.startswith('```json'):
                    content = content[7:]
                if content.endswith('```'):
                    content = content[:-3]
                
                return content.strip()
            else:
                error_detail = response.text[:200] if response.text else "No error details"
                raise requests.HTTPError(f"Cerebras API error {response.status_code}: {error_detail}")
                
        except requests.Timeout:
            raise TimeoutError(f"Cerebras API timeout after {self.timeout}s")
        except requests.RequestException as e:
            raise ConnectionError(f"Cerebras API connection error: {str(e)}")

class CohereClient(LlmClient):
    """
    Cohere client optimized for structured output and reliability  
    Excellent for JSON schema compliance and consistent results
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "command-r-plus"):
        self.api_key = api_key or os.environ.get('COHERE_API_KEY', '')
        self.base_url = 'https://api.cohere.ai/v1'
        self.model = model
        self.timeout = 30  # Cohere may be slower but very reliable
        
        # Optimized for structured output
        self.default_params = {
            'temperature': 0.1,  # Very low for maximum consistency
            'max_tokens': 1000,
            'k': 0,
            'p': 0.75
        }
    
    def is_available(self) -> bool:
        """Check if Cohere API is configured"""
        return bool(self.api_key)
    
    def get_model_name(self) -> str:
        """Get model identifier"""
        return f"cohere-{self.model}"
    
    def json_chat(self, system: str, user_content: str) -> str:
        """
        Send chat request to Cohere API
        Uses chat endpoint with preamble for system instructions
        """
        if not self.is_available():
            raise ValueError("Cohere API key not configured")
        
        payload = {
            'model': self.model,
            'message': user_content,
            'preamble': system,
            **self.default_params
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/chat',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('text', '').strip()
                
                # Clean Cohere-specific formatting
                if content.startswith('```json'):
                    content = content[7:]
                if content.endswith('```'):
                    content = content[:-3]
                    
                return content.strip()
            else:
                error_detail = response.text[:200] if response.text else "No error details"
                raise requests.HTTPError(f"Cohere API error {response.status_code}: {error_detail}")
                
        except requests.Timeout:
            raise TimeoutError(f"Cohere API timeout after {self.timeout}s")
        except requests.RequestException as e:
            raise ConnectionError(f"Cohere API connection error: {str(e)}")

class LlmOrchestrator:
    """
    Orchestrates LLM calls with validation, retries, and fallbacks
    Implements the robust pipeline with schema validation
    """
    
    def __init__(self, primary_client: LlmClient, fallback_client: Optional[LlmClient] = None):
        self.primary_client = primary_client
        self.fallback_client = fallback_client
        
        # Expert system prompt for timing analysis
        self.system_prompt = """You are an elite FPGA timing closure expert with 20+ years of experience.
You specialize in Xilinx Vivado, Intel Quartus, and advanced timing optimization techniques.

Your expertise includes:
- Critical path analysis and optimization
- Clock domain crossing (CDC) design  
- Pipeline architecture and retiming
- DSP48/DSP58 block utilization
- Placement and routing optimization
- Multi-cycle path constraints
- False path identification
- Clock skew and jitter analysis

Given a timing violation in JSON format, provide analysis as valid JSON matching this exact schema:
{
  "issue_class": "setup|hold|uncertain",
  "probable_root_cause": ["cause1", "cause2"],
  "culprit_nodes": [{"name": "node_name", "kind": "cell|net|clock|constraint"}],
  "suggested_fixes": [{"type": "retime_or_pipeline|floorplan|replicate_driver|constraint_update|logic_refactor|clocking_change", "scope": "module_name", "detail": "specific_instructions"}],
  "expected_effect_ns": 1.5,
  "risk_notes": ["risk1", "risk2"],
  "verify_steps": ["step1", "step2"]
}

Be specific and actionable. Focus on the highest-impact fixes first."""

    def analyze_violation(self, violation_prompt: ViolationPrompt) -> LlmResult:
        """
        Analyze single violation with validation and fallbacks
        Returns structured LlmResult with metadata
        """
        start_time = time.time()
        
        # Convert prompt to JSON string for LLM
        prompt_json = json.dumps(violation_prompt.to_dict(), indent=2)
        
        # Try primary client first
        if self.primary_client.is_available():
            try:
                raw_response = self.primary_client.json_chat(self.system_prompt, prompt_json)
                result = self._validate_and_enhance(raw_response, violation_prompt)
                result.model_used = self.primary_client.get_model_name()
                result.processing_time_ms = round((time.time() - start_time) * 1000, 2)
                return result
            except Exception as e:
                print(f"Primary client ({self.primary_client.get_model_name()}) failed: {e}")
                
                # Try one-shot repair before fallback
                try:
                    repair_response = self._attempt_repair(raw_response if 'raw_response' in locals() else "", str(e))
                    if repair_response:
                        result = self._validate_and_enhance(repair_response, violation_prompt)
                        result.model_used = f"{self.primary_client.get_model_name()}-repaired"
                        result.processing_time_ms = round((time.time() - start_time) * 1000, 2)
                        return result
                except Exception:
                    pass  # Continue to fallback
        
        # Try fallback client
        if self.fallback_client and self.fallback_client.is_available():
            try:
                raw_response = self.fallback_client.json_chat(self.system_prompt, prompt_json)
                result = self._validate_and_enhance(raw_response, violation_prompt)
                result.model_used = self.fallback_client.get_model_name()
                result.processing_time_ms = round((time.time() - start_time) * 1000, 2)
                return result
            except Exception as e:
                print(f"Fallback client ({self.fallback_client.get_model_name()}) failed: {e}")
        
        # Final fallback to heuristics
        result = create_fallback_result(violation_prompt, "All LLM clients failed")
        result.processing_time_ms = round((time.time() - start_time) * 1000, 2)
        return result
    
    def _validate_and_enhance(self, raw_json: str, violation_prompt: ViolationPrompt) -> LlmResult:
        """Validate JSON and enhance with confidence scoring"""
        result = validate_llm_output(raw_json)
        
        # Calculate confidence score based on data quality and response completeness
        confidence = 0.5  # Base confidence
        
        # Data quality factors
        if violation_prompt.worst_cells:
            confidence += 0.1
        if violation_prompt.worst_nets:
            confidence += 0.1
        if violation_prompt.hints:
            confidence += 0.1
        
        # Response quality factors  
        if len(result.suggested_fixes) >= 2:
            confidence += 0.1
        if result.expected_effect_ns > 0:
            confidence += 0.1
        if result.risk_notes:
            confidence += 0.1
            
        result.confidence_score = min(1.0, confidence)
        return result
    
    def _attempt_repair(self, invalid_json: str, error_msg: str) -> Optional[str]:
        """Attempt one-shot repair of invalid JSON"""
        if not invalid_json or not self.primary_client.is_available():
            return None
            
        repair_prompt = f"""The following JSON is invalid and needs to be fixed:

Invalid JSON:
{invalid_json[:500]}

Error:
{error_msg}

Please return ONLY the corrected JSON that matches the required schema. No explanations."""

        try:
            return self.primary_client.json_chat("Fix this JSON to match the timing analysis schema:", repair_prompt)
        except Exception:
            return None

# ---- Factory Functions ----

def create_cerebras_client(api_key: Optional[str] = None, model: str = "llama3.1-70b") -> CerebrasClient:
    """Create configured Cerebras client"""
    return CerebrasClient(api_key, model)

def create_cohere_client(api_key: Optional[str] = None, model: str = "command-r-plus") -> CohereClient:
    """Create configured Cohere client"""
    return CohereClient(api_key, model)

def create_orchestrator(prefer_cerebras: bool = True) -> LlmOrchestrator:
    """
    Create orchestrator with Cerebras primary, Cohere fallback
    This matches your recommended architecture
    """
    cerebras = create_cerebras_client()
    cohere = create_cohere_client()
    
    if prefer_cerebras and cerebras.is_available():
        primary, fallback = cerebras, cohere if cohere.is_available() else None
    elif cohere.is_available():
        primary, fallback = cohere, cerebras if cerebras.is_available() else None
    else:
        # No APIs available - orchestrator will use heuristic fallbacks
        primary, fallback = cerebras, None  # Will fail gracefully
    
    return LlmOrchestrator(primary, fallback)

# Global orchestrator instance
orchestrator = create_orchestrator(prefer_cerebras=True)