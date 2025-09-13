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
    Cerebras client using official SDK for ultra-fast timing analysis
    Uses Cerebras Cloud SDK with streaming support for real-time responses
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "qwen-3-235b-a22b-instruct-2507"):
        self.api_key = api_key or os.environ.get('CEREBRAS_API_KEY', '')
        self.model = model
        self.timeout = 15  # Cerebras is fast, but allow reasonable timeout
        
        # Initialize Cerebras client
        if self.api_key:
            try:
                from cerebras.cloud.sdk import Cerebras
                self.client = Cerebras(api_key=self.api_key)
            except ImportError:
                print("⚠️ Cerebras SDK not installed. Run: pip install cerebras-cloud-sdk")
                self.client = None
        else:
            self.client = None
        
        # Optimized parameters for timing analysis
        self.default_params = {
            'temperature': 0.2,  # Low for consistent technical advice
            'max_completion_tokens': 1500,  # Enough for detailed analysis
            'top_p': 0.8,
            'stream': False  # Non-streaming for JSON validation
        }
    
    def is_available(self) -> bool:
        """Check if Cerebras API is configured and client is ready"""
        return bool(self.api_key and self.client)
    
    def get_model_name(self) -> str:
        """Get model identifier"""
        return f"cerebras-{self.model}"
    
    def json_chat(self, system: str, user_content: str) -> str:
        """
        Send chat request to Cerebras using official SDK
        Optimized for structured JSON output
        """
        if not self.is_available():
            raise ValueError("Cerebras API key not configured or client not initialized")
        
        # Enhanced system prompt for JSON compliance
        enhanced_system = f"""{system}

CRITICAL: You must respond with valid JSON only. No markdown, no code blocks, no explanations outside the JSON structure. The JSON must exactly match the required schema."""
        
        try:
            # Use Cerebras SDK for chat completion
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': enhanced_system},
                    {'role': 'user', 'content': user_content}
                ],
                **self.default_params
            )
            
            # Extract content from response
            content = response.choices[0].message.content.strip()
            
            # Clean common formatting issues
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            return content.strip()
            
        except Exception as e:
            # Handle various SDK errors
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                raise TimeoutError(f"Cerebras API timeout: {error_msg}")
            elif "unauthorized" in error_msg.lower() or "401" in error_msg:
                raise ValueError(f"Cerebras API authentication failed: {error_msg}")
            else:
                raise ConnectionError(f"Cerebras API error: {error_msg}")

class GroqClient(LlmClient):
    """
    Groq client for ultra-fast inference using world-record speed LLM inference
    Delivers up to 3,000 tokens per second for real-time timing analysis
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.environ.get('GROQ_API_KEY', '')
        self.base_url = 'https://api.groq.com/openai/v1'
        self.model = model
        self.timeout = 10  # Groq is extremely fast, short timeout
        
        # Initialize Groq client
        if self.api_key:
            try:
                import groq
                self.client = groq.Groq(api_key=self.api_key)
            except ImportError:
                print("⚠️ Groq SDK not installed. Run: pip install groq")
                self.client = None
        else:
            self.client = None
        
        # Optimized for ultra-fast, consistent output
        self.default_params = {
            'temperature': 0.1,  # Low for technical consistency
            'max_tokens': 1200,  # Reasonable for detailed analysis
            'top_p': 0.85,
            'stream': False,
        }
    
    def is_available(self) -> bool:
        """Check if Groq API is configured and client is ready"""
        return bool(self.api_key and self.client)
    
    def get_model_name(self) -> str:
        """Get model identifier"""
        return f"groq-{self.model}"
    
    def json_chat(self, system: str, user_content: str) -> str:
        """
        Send chat request to Groq using official SDK
        Leverages world-record inference speed for real-time analysis
        """
        if not self.is_available():
            raise ValueError("Groq API key not configured or client not initialized")
        
        # Enhanced system prompt for JSON compliance
        enhanced_system = f"""{system}

CRITICAL: You must respond with valid JSON only. No markdown, no code blocks, no explanations outside the JSON structure. The JSON must exactly match the required schema."""
        
        try:
            # Use Groq SDK for ultra-fast chat completion
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': enhanced_system},
                    {'role': 'user', 'content': user_content}
                ],
                **self.default_params
            )
            
            # Extract content from response
            content = response.choices[0].message.content.strip()
            
            # Clean common formatting issues
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            return content.strip()
            
        except Exception as e:
            # Handle various SDK errors
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                raise TimeoutError(f"Groq API timeout: {error_msg}")
            elif "unauthorized" in error_msg.lower() or "401" in error_msg:
                raise ValueError(f"Groq API authentication failed: {error_msg}")
            elif "rate_limit" in error_msg.lower() or "429" in error_msg:
                raise ConnectionError(f"Groq API rate limit: {error_msg}")
            else:
                raise ConnectionError(f"Groq API error: {error_msg}")

class CohereClient(LlmClient):
    """
    Cohere client with multimodal intelligence and agentic workflows
    Features document analysis, image interpretation, and advanced reasoning
    Enhanced for Cohere's 2025 hackathon with multimodal capabilities
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "command-r-plus"):
        self.api_key = api_key or os.environ.get('COHERE_API_KEY', '')
        self.base_url = 'https://api.cohere.ai/v1'  # Use stable v1 API
        self.model = model
        self.timeout = 30  # Cohere may be slower but very reliable
        
        # Enhanced for multimodal and agentic workflows
        self.default_params = {
            'temperature': 0.1,  # Very low for maximum consistency
            'max_tokens': 1500,  # Increased for detailed multimodal analysis
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
        Send chat request to Cohere API v1 with system preamble
        Uses chat endpoint with preamble for system instructions
        """
        if not self.is_available():
            raise ValueError("Cohere API key not configured")
        
        # Use v1 format with preamble
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
                # v1 format uses 'text' field
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
    
    def analyze_document(self, document_content: str, analysis_type: str = "timing_report") -> Dict[str, Any]:
        """
        Advanced document analysis using Cohere's multimodal intelligence
        Specialized for timing reports, constraint files, and HDL code
        """
        if not self.is_available():
            raise ValueError("Cohere API key not configured")
        
        system_prompt = f"""You are an expert document analysis agent for FPGA timing closure.
Specialized in analyzing: timing reports, constraint files, HDL code, and synthesis logs.

For timing reports: extract violations, performance metrics, and critical paths.
For constraint files: identify timing constraints, clock definitions, and I/O standards.
For HDL code: analyze pipeline structure, clock domains, and timing-critical logic.

Provide structured analysis as JSON with key findings and actionable insights."""
        
        user_prompt = f"""Analyze this {analysis_type} document and extract key information:

{document_content[:4000]}  {"..." if len(document_content) > 4000 else ""}

Return analysis as JSON with:
- document_type: detected document type
- key_findings: list of important discoveries
- violations: list of timing issues (if any)
- recommendations: list of actionable suggestions
- confidence: analysis confidence score"""
        
        try:
            raw_response = self.json_chat(system_prompt, user_prompt)
            return json.loads(raw_response)
        except Exception as e:
            # Fallback structured response
            return {
                "document_type": analysis_type,
                "key_findings": [f"Document analysis failed: {str(e)}"],
                "violations": [],
                "recommendations": ["Manual analysis required"],
                "confidence": 0.0
            }
    
    def create_agentic_workflow(self, task_description: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Generate agentic workflow for complex timing closure tasks
        Chains multiple analysis and action steps with live data integration
        """
        if not self.is_available():
            raise ValueError("Cohere API key not configured")
        
        system_prompt = """You are an agentic workflow orchestrator for FPGA timing closure.
You create step-by-step workflows that chain analysis tasks with actionable remediation.

Generate workflows as JSON array of steps:
[{"step": 1, "action": "analyze_timing", "tool": "vivado_sta", "params": {...}}, ...]

Available tools: vivado_sta, quartus_timing, constraint_writer, hdl_analyzer, placement_optimizer
Each step should build on previous results and include verification."""
        
        user_prompt = f"""Create an agentic workflow for: {task_description}

Context:
{json.dumps(context, indent=2)[:2000]}

Return workflow as JSON array where each step has:
- step: step number
- action: specific action to take
- tool: tool/command to use  
- params: parameters for the tool
- expected_output: what this step should produce
- verification: how to verify success"""
        
        try:
            raw_response = self.json_chat(system_prompt, user_prompt)
            workflow_steps = json.loads(raw_response)
            return workflow_steps if isinstance(workflow_steps, list) else []
        except Exception as e:
            # Fallback basic workflow
            return [{
                "step": 1,
                "action": "manual_analysis",
                "tool": "vivado_gui",
                "params": {"task": task_description},
                "expected_output": "Manual analysis results",
                "verification": f"Workflow generation failed: {str(e)}"
            }]

class GeminiClient(LlmClient):
    """
    Google Gemini client for natural language understanding and summarization
    Excellent for complex report summarization and conversational AI
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-pro"):
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY', '')
        self.base_url = 'https://generativelanguage.googleapis.com/v1beta'
        self.model = model
        self.timeout = 30
        
        # Optimized for natural language tasks
        self.default_params = {
            'temperature': 0.3,  # Balanced creativity and consistency
            'maxOutputTokens': 2048,
            'topP': 0.8,
            'topK': 40
        }
    
    def is_available(self) -> bool:
        """Check if Gemini API is configured"""
        return bool(self.api_key)
    
    def get_model_name(self) -> str:
        """Get model identifier"""
        return f"gemini-{self.model}"
    
    def json_chat(self, system: str, user_content: str) -> str:
        """
        Send chat request to Gemini API
        Uses generateContent endpoint with system instruction
        """
        if not self.is_available():
            raise ValueError("Gemini API key not configured")
        
        # Gemini request format
        payload = {
            'contents': [{
                'parts': [{'text': f"{system}\n\n{user_content}"}]
            }],
            'generationConfig': self.default_params
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/models/{self.model}:generateContent',
                headers={'Content-Type': 'application/json'},
                params={'key': self.api_key},
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                candidates = result.get('candidates', [])
                if candidates:
                    content = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '').strip()
                    
                    # Clean Gemini formatting
                    if content.startswith('```json'):
                        content = content[7:]
                    if content.endswith('```'):
                        content = content[:-3]
                        
                    return content.strip()
                else:
                    raise ValueError("No content generated by Gemini")
            else:
                error_detail = response.text[:200] if response.text else "No error details"
                raise requests.HTTPError(f"Gemini API error {response.status_code}: {error_detail}")
                
        except requests.Timeout:
            raise TimeoutError(f"Gemini API timeout after {self.timeout}s")
        except requests.RequestException as e:
            raise ConnectionError(f"Gemini API connection error: {str(e)}")
    
    def summarize_timing_report(self, report_content: str, focus_areas: List[str] = None) -> Dict[str, Any]:
        """
        Specialized timing report summarization using Gemini's natural language capabilities
        """
        if not self.is_available():
            raise ValueError("Gemini API key not configured")
        
        focus_text = ""
        if focus_areas:
            focus_text = f"\nFocus particularly on: {', '.join(focus_areas)}"
        
        system_prompt = f"""
You are an expert FPGA timing analysis summarizer. Create a clear, concise summary of timing reports that helps engineers quickly understand the key issues and next steps.

Provide your summary in this JSON format:
{{
  "executive_summary": "One paragraph overview of timing status",
  "key_metrics": {{
    "worst_slack_ns": float_value_or_null,
    "total_violations": integer_count,
    "critical_paths": integer_count
  }},
  "main_issues": ["issue1", "issue2", "issue3"],
  "recommendations": ["rec1", "rec2", "rec3"],
  "urgency_level": "low|medium|high|critical"
}}{focus_text}
"""
        
        user_prompt = f"""Analyze this timing report and provide a structured summary:

{report_content[:4000]}{'...' if len(report_content) > 4000 else ''}

Return the summary as JSON according to the specified format."""
        
        try:
            raw_response = self.json_chat(system_prompt, user_prompt)
            return json.loads(raw_response)
        except Exception as e:
            # Fallback summary
            return {
                "executive_summary": f"Unable to analyze timing report automatically: {str(e)}",
                "key_metrics": {"worst_slack_ns": None, "total_violations": 0, "critical_paths": 0},
                "main_issues": ["Analysis failed - manual review required"],
                "recommendations": ["Review report manually", "Check data format and completeness"],
                "urgency_level": "unknown"
            }

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

def create_cerebras_client(api_key: Optional[str] = None, model: str = "qwen-3-235b-a22b-instruct-2507") -> CerebrasClient:
    """Create configured Cerebras client"""
    return CerebrasClient(api_key, model)

def create_groq_client(api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile") -> GroqClient:
    """Create configured Groq client for ultra-fast inference"""
    return GroqClient(api_key, model)

def create_gemini_client(api_key: Optional[str] = None, model: str = "gemini-1.5-pro") -> GeminiClient:
    """Create configured Gemini client for natural language processing"""
    return GeminiClient(api_key, model)

def create_cohere_client(api_key: Optional[str] = None, model: str = "command-r-plus") -> CohereClient:
    """Create configured Cohere client"""
    return CohereClient(api_key, model)

def create_orchestrator(prefer_speed: bool = True) -> LlmOrchestrator:
    """
    Create orchestrator with speed-first priority: Groq > Cerebras > Cohere
    This maximizes demo impact with ultra-fast real-time responses
    """
    groq = create_groq_client()
    cerebras = create_cerebras_client()
    cohere = create_cohere_client()
    
    # Speed-first priority for real-time demos
    if prefer_speed and groq.is_available():
        # Groq primary for world-record speed, Cerebras fallback for quality
        primary = groq
        fallback = cerebras if cerebras.is_available() else (cohere if cohere.is_available() else None)
    elif cerebras.is_available():
        # Cerebras primary, Groq fallback for speed
        primary = cerebras  
        fallback = groq if groq.is_available() else (cohere if cohere.is_available() else None)
    elif cohere.is_available():
        # Cohere primary, Groq fallback
        primary = cohere
        fallback = groq if groq.is_available() else None
    else:
        # No APIs available - orchestrator will use heuristic fallbacks
        primary, fallback = groq, None  # Will fail gracefully to heuristics
    
    return LlmOrchestrator(primary, fallback)

# Global orchestrator instance with speed-first priority for demos
orchestrator = create_orchestrator(prefer_speed=True)
