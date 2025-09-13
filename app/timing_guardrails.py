"""
Enhanced Guardrails and Heuristic Analysis for Timing Violations
Provides rule-based analysis and validation of LLM suggestions
"""

from typing import List, Dict, Any, Optional, Tuple
from app.schemas import ViolationPrompt, LlmResult, Fix, Culprit

class TimingGuardrails:
    """
    Rule-based guardrails for timing analysis
    Validates and enhances LLM suggestions with expert heuristics
    """
    
    def __init__(self):
        # Thresholds for different violation characteristics
        self.HIGH_LOGIC_THRESHOLD = 8
        self.MEDIUM_LOGIC_THRESHOLD = 5
        self.HIGH_ROUTING_THRESHOLD = 60  # percentage
        self.MEDIUM_ROUTING_THRESHOLD = 40
        self.SEVERE_SLACK_THRESHOLD = -2.0  # ns
        self.MODERATE_SLACK_THRESHOLD = -0.5
        
        # Common fix patterns
        self.fix_patterns = {
            'deep_logic': {
                'type': 'retime_or_pipeline',
                'priority': 1,
                'description': 'Insert pipeline registers to break deep combinational paths'
            },
            'high_routing': {
                'type': 'floorplan',
                'priority': 2,
                'description': 'Add placement constraints to reduce routing delays'
            },
            'high_fanout': {
                'type': 'replicate_driver',
                'priority': 3,
                'description': 'Replicate high-fanout signals to reduce loading'
            },
            'clock_domain': {
                'type': 'constraint_update',
                'priority': 4,
                'description': 'Review clock domain crossing constraints'
            },
            'logic_optimization': {
                'type': 'logic_refactor',
                'priority': 5,
                'description': 'Optimize logic structure for better timing'
            }
        }
    
    def analyze_violation_characteristics(self, prompt: ViolationPrompt) -> Dict[str, Any]:
        """
        Analyze violation characteristics and identify key issues
        Returns structured analysis for validation and enhancement
        """
        characteristics = {
            'severity': self._classify_severity(prompt.slack_ns),
            'logic_analysis': self._analyze_logic_complexity(prompt),
            'routing_analysis': self._analyze_routing_issues(prompt),
            'fanout_analysis': self._analyze_fanout_issues(prompt),
            'clock_analysis': self._analyze_clock_issues(prompt),
            'recommended_fixes': [],
            'risk_factors': [],
            'confidence_factors': []
        }
        
        # Generate recommended fixes based on characteristics
        characteristics['recommended_fixes'] = self._generate_heuristic_fixes(prompt, characteristics)
        
        return characteristics
    
    def validate_llm_suggestions(self, llm_result: LlmResult, prompt: ViolationPrompt) -> Tuple[bool, List[str]]:
        """
        Validate LLM suggestions against expert heuristics
        Returns (is_valid, list_of_warnings)
        """
        warnings = []
        is_valid = True
        
        characteristics = self.analyze_violation_characteristics(prompt)
        
        # Check if critical fixes are missing
        if characteristics['logic_analysis']['needs_pipelining'] and not self._has_pipeline_fix(llm_result):
            warnings.append("Missing pipeline fix for high logic levels")
            
        if characteristics['routing_analysis']['needs_floorplan'] and not self._has_floorplan_fix(llm_result):
            warnings.append("Missing floorplan constraints for high routing delay")
            
        if characteristics['fanout_analysis']['needs_replication'] and not self._has_replication_fix(llm_result):
            warnings.append("Missing driver replication for high fanout")
        
        # Validate expected improvement is reasonable
        if llm_result.expected_effect_ns <= 0:
            warnings.append("Expected improvement should be positive")
            is_valid = False
            
        if llm_result.expected_effect_ns > abs(prompt.slack_ns) * 2:
            warnings.append("Expected improvement seems unrealistically high")
        
        # Check for missing risk assessment on critical changes
        pipeline_fixes = [f for f in llm_result.suggested_fixes if f.type == 'retime_or_pipeline']
        if pipeline_fixes and not any('latency' in note.lower() for note in llm_result.risk_notes):
            warnings.append("Missing latency impact assessment for pipelining")
        
        return is_valid, warnings
    
    def enhance_llm_result(self, llm_result: LlmResult, prompt: ViolationPrompt) -> LlmResult:
        """
        Enhance LLM result with additional heuristic insights
        """
        characteristics = self.analyze_violation_characteristics(prompt)
        
        # Add missing critical fixes
        missing_fixes = self._identify_missing_fixes(llm_result, characteristics)
        for fix in missing_fixes:
            if len(llm_result.suggested_fixes) < 5:  # Don't exceed schema limits
                llm_result.suggested_fixes.append(fix)
        
        # Enhance risk notes
        additional_risks = self._generate_risk_notes(llm_result, characteristics)
        for risk in additional_risks:
            if len(llm_result.risk_notes) < 3:  # Don't exceed schema limits
                llm_result.risk_notes.append(risk)
        
        # Add verification steps
        additional_verifications = self._generate_verification_steps(llm_result, characteristics)
        for verification in additional_verifications:
            if len(llm_result.verify_steps) < 4:
                llm_result.verify_steps.append(verification)
        
        return llm_result
    
    def _classify_severity(self, slack_ns: float) -> str:
        """Classify violation severity based on slack"""
        if slack_ns < self.SEVERE_SLACK_THRESHOLD:
            return 'critical'
        elif slack_ns < self.MODERATE_SLACK_THRESHOLD:
            return 'moderate'
        else:
            return 'minor'
    
    def _analyze_logic_complexity(self, prompt: ViolationPrompt) -> Dict[str, Any]:
        """Analyze logic complexity and pipelining needs"""
        return {
            'levels': prompt.levels_of_logic,
            'is_high': prompt.levels_of_logic >= self.HIGH_LOGIC_THRESHOLD,
            'is_medium': prompt.levels_of_logic >= self.MEDIUM_LOGIC_THRESHOLD,
            'needs_pipelining': prompt.levels_of_logic >= self.HIGH_LOGIC_THRESHOLD,
            'pipeline_stages_needed': max(1, prompt.levels_of_logic // 4),
            'logic_cells': [cell.type for cell in prompt.worst_cells]
        }
    
    def _analyze_routing_issues(self, prompt: ViolationPrompt) -> Dict[str, Any]:
        """Analyze routing delays and placement needs"""
        high_routing_nets = [n for n in prompt.worst_nets if n.routing_pct >= self.HIGH_ROUTING_THRESHOLD]
        medium_routing_nets = [n for n in prompt.worst_nets if n.routing_pct >= self.MEDIUM_ROUTING_THRESHOLD]
        
        return {
            'high_routing_nets': len(high_routing_nets),
            'medium_routing_nets': len(medium_routing_nets),
            'worst_routing_pct': max([n.routing_pct for n in prompt.worst_nets]) if prompt.worst_nets else 0,
            'needs_floorplan': len(high_routing_nets) > 0,
            'placement_critical': len(high_routing_nets) > 1,
            'cross_die_hints': [hint for hint in prompt.hints if 'slr' in hint.lower() or 'cross' in hint.lower()]
        }
    
    def _analyze_fanout_issues(self, prompt: ViolationPrompt) -> Dict[str, Any]:
        """Analyze fanout and driver replication needs"""
        fanout_hints = [hint for hint in prompt.hints if 'fanout' in hint.lower() or 'load' in hint.lower()]
        
        return {
            'fanout_hints': len(fanout_hints),
            'needs_replication': len(fanout_hints) > 0,
            'high_fanout_nets': [hint for hint in prompt.hints if 'high fanout' in hint.lower()]
        }
    
    def _analyze_clock_issues(self, prompt: ViolationPrompt) -> Dict[str, Any]:
        """Analyze clock domain and constraint issues"""
        clock_hints = [hint for hint in prompt.hints if 'clock' in hint.lower() or 'cdc' in hint.lower()]
        
        return {
            'clock_domain': prompt.clock,
            'has_clock_issues': len(clock_hints) > 0,
            'clock_hints': clock_hints,
            'needs_constraint_review': 'uncertain' in ' '.join(prompt.hints).lower()
        }
    
    def _generate_heuristic_fixes(self, prompt: ViolationPrompt, characteristics: Dict[str, Any]) -> List[Fix]:
        """Generate fixes based on heuristic analysis"""
        fixes = []
        
        # High logic levels → pipelining
        if characteristics['logic_analysis']['needs_pipelining']:
            fixes.append(Fix(
                type='retime_or_pipeline',
                scope=self._extract_scope_from_path(prompt.startpoint, prompt.endpoint),
                detail=f"Insert {characteristics['logic_analysis']['pipeline_stages_needed']} pipeline stage(s) to reduce {prompt.levels_of_logic} logic levels. Consider retiming in synthesis."
            ))
        
        # High routing → floorplan
        if characteristics['routing_analysis']['needs_floorplan']:
            worst_net = max(prompt.worst_nets, key=lambda x: x.routing_pct) if prompt.worst_nets else None
            detail = f"Add pblock constraints to co-locate logic. Focus on net '{worst_net.net}' with {worst_net.routing_pct}% routing delay." if worst_net else "Add pblock constraints to reduce routing delays."
            
            fixes.append(Fix(
                type='floorplan',
                scope='placement',
                detail=detail
            ))
        
        # High fanout → replication
        if characteristics['fanout_analysis']['needs_replication']:
            fixes.append(Fix(
                type='replicate_driver',
                scope='high_fanout_signals',
                detail="Replicate high-fanout control signals to reduce loading. Consider local enables or distributed control."
            ))
        
        # Clock issues → constraints
        if characteristics['clock_analysis']['needs_constraint_review']:
            fixes.append(Fix(
                type='constraint_update',
                scope=prompt.clock,
                detail=f"Review timing constraints for {prompt.clock}. Consider multicycle paths or false paths if appropriate."
            ))
        
        return fixes
    
    def _extract_scope_from_path(self, startpoint: str, endpoint: str) -> str:
        """Extract module scope from path endpoints"""
        # Simple heuristic: find common prefix
        start_parts = startpoint.split('/')
        end_parts = endpoint.split('/')
        
        common_parts = []
        for i, (s, e) in enumerate(zip(start_parts, end_parts)):
            if s == e:
                common_parts.append(s)
            else:
                break
        
        if common_parts:
            return '/'.join(common_parts)
        else:
            return 'top'
    
    def _has_pipeline_fix(self, result: LlmResult) -> bool:
        """Check if result contains pipelining fix"""
        return any(f.type == 'retime_or_pipeline' for f in result.suggested_fixes)
    
    def _has_floorplan_fix(self, result: LlmResult) -> bool:
        """Check if result contains floorplan fix"""
        return any(f.type == 'floorplan' for f in result.suggested_fixes)
    
    def _has_replication_fix(self, result: LlmResult) -> bool:
        """Check if result contains replication fix"""
        return any(f.type == 'replicate_driver' for f in result.suggested_fixes)
    
    def _identify_missing_fixes(self, result: LlmResult, characteristics: Dict[str, Any]) -> List[Fix]:
        """Identify critical fixes missing from LLM result"""
        missing = []
        recommended = characteristics['recommended_fixes']
        
        for fix in recommended:
            if fix.type == 'retime_or_pipeline' and not self._has_pipeline_fix(result):
                missing.append(fix)
            elif fix.type == 'floorplan' and not self._has_floorplan_fix(result):
                missing.append(fix)
            elif fix.type == 'replicate_driver' and not self._has_replication_fix(result):
                missing.append(fix)
        
        return missing
    
    def _generate_risk_notes(self, result: LlmResult, characteristics: Dict[str, Any]) -> List[str]:
        """Generate additional risk notes based on analysis"""
        risks = []
        
        pipeline_fixes = [f for f in result.suggested_fixes if f.type == 'retime_or_pipeline']
        if pipeline_fixes and not any('latency' in note.lower() for note in result.risk_notes):
            risks.append("Pipeline changes will add clock cycle latency - update protocol timing")
        
        floorplan_fixes = [f for f in result.suggested_fixes if f.type == 'floorplan']
        if floorplan_fixes and characteristics['routing_analysis']['placement_critical']:
            risks.append("Aggressive placement constraints may impact other timing paths")
        
        if characteristics['severity'] == 'critical':
            risks.append("Critical violation may require multiple iterations to close")
        
        return risks
    
    def _generate_verification_steps(self, result: LlmResult, characteristics: Dict[str, Any]) -> List[str]:
        """Generate verification steps based on fix types"""
        steps = []
        
        fix_types = {f.type for f in result.suggested_fixes}
        
        if 'retime_or_pipeline' in fix_types:
            steps.append("Verify functional correctness with updated pipeline depth")
        
        if 'floorplan' in fix_types:
            steps.append("Check utilization and congestion in constrained regions")
        
        if 'replicate_driver' in fix_types:
            steps.append("Validate signal integrity with increased driver count")
        
        if characteristics['severity'] == 'critical':
            steps.append("Run full timing analysis across all process corners")
        
        return steps

# Global guardrails instance
guardrails = TimingGuardrails()