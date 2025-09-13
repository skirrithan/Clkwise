"""
Rox AI Agent for Messy Data Handling
Advanced system for processing unstructured timing reports, incomplete datasets, 
conflicting sources, and noisy data in real-world FPGA environments.

Competes for Rox's $10K prize with techniques for:
- Data cleaning and validation
- Multi-source resolution  
- Intelligent error handling
- Robust decision-making under uncertainty
"""

import re
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from app.schemas import TimingViolation, LlmResult, ViolationPrompt
from app.llm_clients import orchestrator

class DataQuality(Enum):
    """Data quality assessment levels"""
    EXCELLENT = 5    # Complete, consistent, validated
    GOOD = 4        # Minor gaps, mostly consistent  
    FAIR = 3        # Some inconsistencies, usable
    POOR = 2        # Major gaps, conflicts present
    UNUSABLE = 1    # Corrupted, incomplete, conflicting

@dataclass
class DataSource:
    """Represents a timing data source with quality metadata"""
    name: str
    content: str
    tool: str  # vivado, quartus, synplify, etc.
    version: str = "unknown"
    quality: DataQuality = DataQuality.FAIR
    confidence: float = 0.5
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    checksum: str = field(init=False)
    
    def __post_init__(self):
        """Calculate content checksum for deduplication"""
        self.checksum = hashlib.md5(self.content.encode()).hexdigest()

@dataclass
class ConflictResolution:
    """Resolution strategy for conflicting data"""
    conflict_type: str
    sources: List[str] 
    resolution_strategy: str
    chosen_value: Any
    confidence: float
    reasoning: str

class RoxMessyDataAgent:
    """
    Advanced AI agent for handling messy, real-world FPGA timing data
    
    Key capabilities:
    - Parse corrupted/incomplete timing reports from multiple tools
    - Resolve conflicts between different analysis runs
    - Clean and validate noisy data
    - Make robust decisions with incomplete information
    - Learn from historical patterns to improve accuracy
    """
    
    def __init__(self):
        self.data_sources: List[DataSource] = []
        self.conflict_resolutions: List[ConflictResolution] = []
        self.learned_patterns: Dict[str, float] = {}
        
        # Regex patterns for extracting data from corrupted reports
        self.pattern_library = {
            'vivado_wns': [
                r'Worst Negative Slack\s*:\s*([-\d\.]+)',
                r'WNS\s*=\s*([-\d\.]+)',
                r'setup.*slack\s*([-\d\.]+)',
                r'negative.*slack.*?([-\d\.]+)'  # Fallback pattern
            ],
            'vivado_violation': [
                r'Path #\d+.*?slack\s*([-\d\.]+).*?endpoint\s*(\S+)',
                r'Timing.*violation.*slack\s*([-\d\.]+)',
                r'Failed.*path.*?([-\d\.]+)ns'
            ],
            'quartus_timing': [
                r'Timing Analyzer.*Slack\s*([-\d\.]+)',
                r'Setup.*relationship.*?([-\d\.]+)\s*ns',
                r'Critical.*path.*delay.*?([\d\.]+)'
            ]
        }
    
    def ingest_messy_data(self, content: str, source_name: str, tool_hint: str = "") -> DataSource:
        """
        Ingest potentially corrupted, incomplete, or malformed timing data
        Applies intelligent parsing and error recovery
        """
        # Detect tool type if not provided
        if not tool_hint:
            tool_hint = self._detect_tool_type(content)
        
        # Clean and normalize content
        cleaned_content = self._clean_raw_content(content)
        
        # Assess data quality  
        quality, errors, warnings = self._assess_data_quality(cleaned_content, tool_hint)
        
        # Create data source
        source = DataSource(
            name=source_name,
            content=cleaned_content,
            tool=tool_hint,
            quality=quality,
            errors=errors,
            warnings=warnings
        )
        
        # Check for duplicates
        if not self._is_duplicate_source(source):
            self.data_sources.append(source)
            print(f"✅ Ingested {source_name}: Quality={quality.name}, Tool={tool_hint}")
        else:
            print(f"⚠️ Duplicate source detected: {source_name}")
        
        return source
    
    def _detect_tool_type(self, content: str) -> str:
        """Intelligently detect EDA tool from content patterns"""
        content_lower = content.lower()
        
        # Tool signature patterns
        signatures = {
            'vivado': ['xilinx', 'vivado', 'timing summary', 'design checkpoint'],
            'quartus': ['intel', 'altera', 'quartus', 'timequest'],
            'synplify': ['synplify', 'synopsys', 'synthesis report'],
            'diamond': ['lattice', 'diamond', 'timing analysis'],
            'ise': ['xilinx ise', 'map report', 'par report']
        }
        
        scores = {}
        for tool, keywords in signatures.items():
            scores[tool] = sum(1 for keyword in keywords if keyword in content_lower)
        
        # Return tool with highest score, default to 'unknown'
        detected_tool = max(scores.items(), key=lambda x: x[1])
        return detected_tool[0] if detected_tool[1] > 0 else 'unknown'
    
    def _clean_raw_content(self, content: str) -> str:
        """Clean and normalize messy content for analysis"""
        # Remove common corruptions
        content = re.sub(r'\x00+', '', content)  # Null bytes
        content = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', '', content)  # Control chars
        
        # Normalize whitespace and line endings
        content = re.sub(r'\r\n|\r', '\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)  # Multiple blank lines
        
        # Fix common encoding issues
        content = content.replace('\u00a0', ' ')  # Non-breaking space
        content = content.replace('\u2010', '-')  # Hyphen variations
        
        return content.strip()
    
    def _assess_data_quality(self, content: str, tool: str) -> Tuple[DataQuality, List[str], List[str]]:
        """Assess data quality and identify issues"""
        errors = []
        warnings = []
        quality_score = 5  # Start with excellent
        
        # Check for completeness
        if len(content) < 100:
            errors.append("Content too short - likely incomplete")
            quality_score -= 2
        
        # Check for timing data presence
        timing_keywords = ['slack', 'delay', 'timing', 'setup', 'hold', 'violation']
        found_keywords = sum(1 for keyword in timing_keywords if keyword.lower() in content.lower())
        
        if found_keywords < 2:
            errors.append("Missing key timing analysis keywords")
            quality_score -= 2
        elif found_keywords < 4:
            warnings.append("Limited timing analysis content detected")
            quality_score -= 1
        
        # Check for structural integrity
        if tool == 'vivado':
            required_sections = ['timing summary', 'critical paths', 'design timing summary']
            found_sections = sum(1 for section in required_sections 
                               if section.lower() in content.lower())
            if found_sections == 0:
                errors.append("No recognizable Vivado timing sections found")
                quality_score -= 2
        
        # Check for numerical data corruption
        number_pattern = r'[-+]?(?:\d*\.\d+|\d+)'
        numbers = re.findall(number_pattern, content)
        if len(numbers) < 10:
            warnings.append("Very few numerical values found")
            quality_score -= 1
        
        # Check for common corruption patterns
        if '???' in content or '###' in content:
            warnings.append("Potential character corruption detected")
            quality_score -= 1
        
        # Truncation detection
        if content.endswith(('...', '..', 'TRUNCATED', 'CUT OFF')):
            errors.append("Content appears to be truncated")
            quality_score -= 2
        
        # Convert score to enum
        quality_score = max(1, quality_score)  # Minimum quality
        quality = DataQuality(quality_score)
        
        return quality, errors, warnings
    
    def _is_duplicate_source(self, new_source: DataSource) -> bool:
        """Check if source is duplicate based on content similarity"""
        for existing in self.data_sources:
            if (existing.checksum == new_source.checksum or 
                self._content_similarity(existing.content, new_source.content) > 0.95):
                return True
        return False
    
    def _content_similarity(self, content1: str, content2: str) -> float:
        """Calculate content similarity using simple metrics"""
        if not content1 or not content2:
            return 0.0
        
        # Simple word-based similarity
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def extract_robust_violations(self) -> List[Dict[str, Any]]:
        """
        Extract timing violations from multiple messy sources
        Handles conflicts, missing data, and inconsistencies
        """
        violations_by_source = {}
        
        # Extract from each source
        for source in self.data_sources:
            source_violations = self._extract_violations_from_source(source)
            violations_by_source[source.name] = source_violations
        
        # Resolve conflicts and merge
        merged_violations = self._resolve_violation_conflicts(violations_by_source)
        
        # Validate and clean results
        validated_violations = self._validate_violations(merged_violations)
        
        return validated_violations
    
    def _extract_violations_from_source(self, source: DataSource) -> List[Dict[str, Any]]:
        """Extract violations from a single source with error handling"""
        violations = []
        content = source.content
        
        # Use tool-specific patterns
        patterns = self.pattern_library.get(f'{source.tool}_violation', [])
        
        for pattern in patterns:
            try:
                matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    violation_data = self._build_violation_from_match(match, source)
                    if violation_data:
                        violations.append(violation_data)
            except Exception as e:
                print(f"Pattern matching error in {source.name}: {e}")
                continue
        
        # Fallback extraction for unrecognized formats
        if not violations and source.quality.value >= DataQuality.FAIR.value:
            violations = self._fallback_violation_extraction(content, source)
        
        return violations
    
    def _build_violation_from_match(self, match, source: DataSource) -> Optional[Dict[str, Any]]:
        """Build violation dictionary from regex match"""
        try:
            groups = match.groups()
            if not groups:
                return None
            
            # Extract slack (always first group)
            slack = float(groups[0]) if groups[0] else None
            if slack is None or slack >= 0:  # Not a violation
                return None
            
            violation = {
                'slack': slack,
                'source': source.name,
                'tool': source.tool,
                'confidence': source.confidence,
                'endpoint': groups[1] if len(groups) > 1 else 'unknown',
                'startpoint': 'unknown',  # Will be refined later
                'levels_of_logic': 0,  # Default
                'data_quality': source.quality.name.lower()
            }
            
            return violation
            
        except (ValueError, IndexError) as e:
            print(f"Error building violation from match: {e}")
            return None
    
    def _fallback_violation_extraction(self, content: str, source: DataSource) -> List[Dict[str, Any]]:
        """Fallback extraction using more general patterns"""
        violations = []
        
        # Look for any negative numbers that might be slack values
        negative_numbers = re.findall(r'-([\d\.]+)', content)
        
        for i, num_str in enumerate(negative_numbers[:5]):  # Limit to first 5
            try:
                slack = -float(num_str)
                if slack < -0.001:  # Significant violation
                    violations.append({
                        'slack': slack,
                        'source': source.name,
                        'tool': source.tool,
                        'confidence': 0.3,  # Low confidence for fallback
                        'endpoint': f'fallback_path_{i}',
                        'startpoint': 'unknown',
                        'levels_of_logic': 0,
                        'data_quality': 'fallback_extraction'
                    })
            except ValueError:
                continue
        
        return violations
    
    def _resolve_violation_conflicts(self, violations_by_source: Dict[str, List]) -> List[Dict[str, Any]]:
        """Resolve conflicts between multiple sources"""
        all_violations = []
        conflict_groups = []
        
        # Flatten all violations
        for source_name, violations in violations_by_source.items():
            all_violations.extend(violations)
        
        if len(violations_by_source) == 1:
            # No conflicts to resolve
            return all_violations
        
        # Group similar violations for conflict resolution
        grouped_violations = self._group_similar_violations(all_violations)
        
        resolved_violations = []
        for group in grouped_violations:
            if len(group) == 1:
                resolved_violations.append(group[0])
            else:
                # Resolve conflict within group
                resolved = self._resolve_violation_group_conflict(group)
                resolved_violations.append(resolved)
        
        return resolved_violations
    
    def _group_similar_violations(self, violations: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group violations that likely refer to the same timing path"""
        groups = []
        
        for violation in violations:
            added_to_group = False
            
            for group in groups:
                # Check if violation is similar to any in this group
                for existing in group:
                    if self._violations_similar(violation, existing):
                        group.append(violation)
                        added_to_group = True
                        break
                
                if added_to_group:
                    break
            
            if not added_to_group:
                groups.append([violation])
        
        return groups
    
    def _violations_similar(self, v1: Dict[str, Any], v2: Dict[str, Any]) -> bool:
        """Check if two violations likely refer to the same path"""
        # Slack values within 10% or 0.1ns
        slack_diff = abs(v1.get('slack', 0) - v2.get('slack', 0))
        slack_threshold = min(0.1, abs(v1.get('slack', 0)) * 0.1)
        
        if slack_diff > slack_threshold:
            return False
        
        # Endpoint similarity
        ep1 = v1.get('endpoint', '').lower()
        ep2 = v2.get('endpoint', '').lower()
        
        if ep1 and ep2 and ep1 != 'unknown' and ep2 != 'unknown':
            # Simple string similarity check
            return ep1 == ep2 or (len(ep1) > 5 and len(ep2) > 5 and 
                                 (ep1 in ep2 or ep2 in ep1))
        
        return True  # Conservative - assume similar if can't determine
    
    def _resolve_violation_group_conflict(self, group: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve conflicts within a group of similar violations"""
        if not group:
            return {}
        
        # Strategy: Choose violation from highest quality source
        # with preference for higher confidence
        best_violation = max(group, key=lambda v: (
            DataQuality[v.get('data_quality', 'fair').upper()].value,
            v.get('confidence', 0.0)
        ))
        
        # Record conflict resolution
        sources = [v.get('source', 'unknown') for v in group]
        slack_values = [v.get('slack', 0) for v in group]
        
        resolution = ConflictResolution(
            conflict_type='violation_slack',
            sources=sources,
            resolution_strategy='highest_quality_source',
            chosen_value=best_violation.get('slack'),
            confidence=best_violation.get('confidence', 0.0),
            reasoning=f"Selected from {len(group)} conflicting sources based on data quality"
        )
        self.conflict_resolutions.append(resolution)
        
        # Enhance chosen violation with conflict metadata
        best_violation['resolved_conflict'] = True
        best_violation['conflicting_values'] = slack_values
        best_violation['confidence'] = min(1.0, best_violation.get('confidence', 0.5) + 0.1)
        
        return best_violation
    
    def _validate_violations(self, violations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Final validation and cleaning of extracted violations"""
        validated = []
        
        for violation in violations:
            # Basic sanity checks
            slack = violation.get('slack')
            if slack is None or slack >= 0:
                continue  # Not a real violation
            
            if slack < -1000:  # Unrealistic slack value
                violation['warnings'] = violation.get('warnings', [])
                violation['warnings'].append('Suspicious slack value - may be incorrect units')
                violation['confidence'] *= 0.5  # Reduce confidence
            
            # Ensure required fields have defaults
            violation.setdefault('endpoint', 'unknown')
            violation.setdefault('startpoint', 'unknown')
            violation.setdefault('levels_of_logic', 0)
            violation.setdefault('confidence', 0.5)
            
            validated.append(violation)
        
        return validated
    
    def generate_robust_analysis(self, task_description: str) -> Dict[str, Any]:
        """
        Generate comprehensive analysis that operates effectively 
        despite messy, incomplete, or conflicting data
        """
        # Extract violations with conflict resolution
        violations = self.extract_robust_violations()
        
        # Assess overall data quality
        overall_quality = self._assess_overall_data_quality()
        
        # Generate analysis context for LLM
        context = {
            'violations': violations[:10],  # Top 10 violations
            'data_sources': [s.name for s in self.data_sources],
            'quality_assessment': overall_quality,
            'conflicts_resolved': len(self.conflict_resolutions),
            'total_sources': len(self.data_sources)
        }
        
        # Use LLM with robust prompting
        if violations:
            # Analyze worst violation with uncertainty quantification
            worst_violation = min(violations, key=lambda v: v.get('slack', 0))
            
            # Build robust prompt that acknowledges data quality issues
            prompt = ViolationPrompt(
                clock=worst_violation.get('clock', 'unknown_clk'),
                slack_ns=float(worst_violation.get('slack', -1.0)),
                startpoint=worst_violation.get('startpoint', 'unknown'),
                endpoint=worst_violation.get('endpoint', 'unknown'),
                levels_of_logic=int(worst_violation.get('levels_of_logic', 5)),
                worst_cells=[],  # Will be filled by heuristics
                worst_nets=[],
                hints=[
                    f"Data quality: {overall_quality}",
                    f"Source: {worst_violation.get('source', 'unknown')}",
                    f"Confidence: {worst_violation.get('confidence', 0.5):.2f}",
                    f"Extracted from potentially messy/incomplete data"
                ]
            )
            
            try:
                llm_result = orchestrator.analyze_violation(prompt)
                
                # Enhance with uncertainty quantification
                uncertainty_factor = 1.0 - overall_quality
                llm_result.confidence_score *= (1.0 - uncertainty_factor)
                
                # Add robust decision-making notes
                if uncertainty_factor > 0.3:
                    llm_result.risk_notes.append(
                        f"Analysis based on {overall_quality:.1%} quality data - verify results carefully"
                    )
                
                analysis_result = {
                    'llm_analysis': llm_result.to_summary_dict(),
                    'data_context': context,
                    'robustness_metrics': {
                        'data_quality': overall_quality,
                        'sources_processed': len(self.data_sources),
                        'conflicts_resolved': len(self.conflict_resolutions),
                        'uncertainty_factor': uncertainty_factor
                    }
                }
                
            except Exception as e:
                # Fallback analysis when LLM fails
                analysis_result = self._generate_fallback_analysis(violations, context, str(e))
        
        else:
            # No violations found - might be data quality issue
            analysis_result = {
                'message': 'No timing violations detected in provided data',
                'data_context': context,
                'recommendations': [
                    'Check if timing reports contain actual violation data',
                    'Verify report completeness and tool version compatibility',
                    'Consider running timing analysis with stricter constraints'
                ]
            }
        
        return analysis_result
    
    def _assess_overall_data_quality(self) -> float:
        """Assess overall quality across all data sources"""
        if not self.data_sources:
            return 0.0
        
        # Weighted average based on confidence and quality
        total_weight = 0
        weighted_quality = 0
        
        for source in self.data_sources:
            weight = source.confidence
            quality_score = source.quality.value / 5.0  # Normalize to 0-1
            
            weighted_quality += quality_score * weight
            total_weight += weight
        
        return weighted_quality / total_weight if total_weight > 0 else 0.0
    
    def _generate_fallback_analysis(self, violations: List[Dict], context: Dict, error: str) -> Dict[str, Any]:
        """Generate analysis when LLM pipeline fails"""
        if violations:
            worst = min(violations, key=lambda v: v.get('slack', 0))
            
            # Heuristic analysis
            recommendations = []
            if worst.get('slack', 0) < -0.5:
                recommendations.append("Critical timing violation - requires immediate attention")
            if len(violations) > 10:
                recommendations.append("Multiple violations - systematic optimization needed")
            
            return {
                'fallback_analysis': {
                    'worst_slack_ns': worst.get('slack'),
                    'violation_count': len(violations),
                    'primary_source': worst.get('source'),
                    'recommendations': recommendations
                },
                'data_context': context,
                'error': f"LLM analysis failed: {error}",
                'robustness_metrics': {
                    'fallback_mode': True,
                    'data_quality': self._assess_overall_data_quality()
                }
            }
        
        return {
            'error': 'No usable timing data found',
            'data_context': context
        }

# Global agent instance
rox_agent = RoxMessyDataAgent()