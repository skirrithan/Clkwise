"""
Robust data schemas for timing analysis LLM pipeline
Defines strict contracts for LLM input/output with Pydantic validation
"""

from typing import List, Literal, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
import json

# ---- LLM Input Schema (distilled prompt JSON per violation) ----

class WorstCell(BaseModel):
    """Single cell in critical path with timing data"""
    inst: str = Field(..., description="Instance name")
    type: str = Field(..., description="Cell type (LUT6, DSP48E2, etc.)")
    delay_ns: float = Field(..., ge=0.0, description="Cell delay in nanoseconds")

class WorstNet(BaseModel):
    """Single net in critical path with routing data"""
    net: str = Field(..., description="Net name")
    delay_ns: float = Field(..., ge=0.0, description="Net delay in nanoseconds")
    routing_pct: int = Field(..., ge=0, le=100, description="Percentage of delay from routing")

class ViolationPrompt(BaseModel):
    """Structured input to LLM for single violation analysis"""
    model_config = ConfigDict(extra='forbid')  # Strict schema
    
    clock: str = Field(..., description="Clock domain name")
    slack_ns: float = Field(..., lt=0.0, description="Negative slack in nanoseconds")
    startpoint: str = Field(..., description="Path startpoint (e.g., ff_reg/Q)")
    endpoint: str = Field(..., description="Path endpoint (e.g., ff_reg/D)")
    levels_of_logic: int = Field(..., ge=0, description="Number of logic levels")
    worst_cells: List[WorstCell] = Field(default_factory=list, max_length=5)
    worst_nets: List[WorstNet] = Field(default_factory=list, max_length=5)
    hints: List[str] = Field(default_factory=list, description="Human-readable analysis hints")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for LLM consumption"""
        return self.model_dump()

# ---- LLM Output Schema (strict contract with validation) ----

class Culprit(BaseModel):
    """Node identified as contributing to timing violation"""
    name: str = Field(..., description="Instance or net name")
    kind: Literal["cell", "net", "clock", "constraint"] = Field(..., description="Type of culprit")

class Fix(BaseModel):
    """Specific fix suggestion with implementation details"""
    type: Literal[
        "retime_or_pipeline",
        "floorplan", 
        "replicate_driver",
        "constraint_update",
        "logic_refactor",
        "clocking_change"
    ] = Field(..., description="Category of fix")
    scope: str = Field(..., description="Module/instance scope for the fix")
    detail: str = Field(..., description="Specific implementation instructions")
    
    def to_markdown(self) -> str:
        """Convert to readable markdown for UI display"""
        type_emoji = {
            "retime_or_pipeline": "⏱️",
            "floorplan": "📍", 
            "replicate_driver": "🔀",
            "constraint_update": "⚙️",
            "logic_refactor": "🔧",
            "clocking_change": "🕐"
        }
        emoji = type_emoji.get(self.type, "🔧")
        return f"{emoji} **{self.type.replace('_', ' ').title()}** in `{self.scope}`\n   {self.detail}"

class LlmResult(BaseModel):
    """Complete LLM analysis result with strict validation"""
    model_config = ConfigDict(extra='forbid')
    
    issue_class: Literal["setup", "hold", "uncertain"] = Field(..., description="Type of timing violation")
    probable_root_cause: List[str] = Field(..., min_length=1, max_length=4, description="Root cause analysis")
    culprit_nodes: List[Culprit] = Field(..., min_length=1, max_length=5, description="Key problematic nodes")
    suggested_fixes: List[Fix] = Field(..., min_length=1, max_length=5, description="Ranked fix suggestions")
    expected_effect_ns: float = Field(..., gt=-1000, lt=1000, description="Expected slack improvement")
    risk_notes: List[str] = Field(default_factory=list, max_length=3, description="Implementation risks")
    verify_steps: List[str] = Field(default_factory=list, max_length=4, description="Verification checklist")
    
    # Metadata fields
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Analysis confidence")
    processing_time_ms: float = Field(default=0.0, ge=0.0, description="LLM processing time")
    model_used: str = Field(default="unknown", description="LLM model identifier")
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary for web UI consumption"""
        return {
            "issue_class": self.issue_class,
            "root_causes": self.probable_root_cause,
            "fixes": [f.to_markdown() for f in self.suggested_fixes],
            "expected_improvement_ns": self.expected_effect_ns,
            "confidence": self.confidence_score,
            "risks": self.risk_notes,
            "verification": self.verify_steps,
            "processing_ms": self.processing_time_ms
        }

# ---- Parser Output Schema (from .rpt files) ----

class PathEndpoint(BaseModel):
    """Timing path endpoint details"""
    name: str = Field(..., description="Signal name")
    type: str = Field(default="FF", description="Node type (FF, LATCH, etc.)")
    clock_edge: Literal["rising", "falling"] = Field(default="rising")

class CellArc(BaseModel):
    """Individual cell in timing path"""
    inst: str = Field(..., description="Instance name")
    type: str = Field(..., description="Cell type")
    delay_ns: float = Field(..., ge=0.0, description="Cell delay")

class NetArc(BaseModel):
    """Individual net in timing path"""
    net: str = Field(..., description="Net name")
    est_route_pct: int = Field(..., ge=0, le=100, description="Estimated routing percentage")
    delay_ns: float = Field(..., ge=0.0, description="Net delay")

class TimingViolation(BaseModel):
    """Single timing violation from parser"""
    path_id: str = Field(..., description="Unique path identifier")
    slack_ns: float = Field(..., description="Timing slack (negative for violations)")
    clock: str = Field(..., description="Clock domain")
    path_group: str = Field(..., description="Timing group")
    startpoint: PathEndpoint = Field(..., description="Path start")
    endpoint: PathEndpoint = Field(..., description="Path end")
    levels_of_logic: int = Field(..., ge=0, description="Logic levels")
    arrival_ns: float = Field(..., ge=0.0, description="Arrival time")
    required_ns: float = Field(..., ge=0.0, description="Required time")
    cell_arcs: List[CellArc] = Field(default_factory=list, description="Cell timing arcs")
    net_arcs: List[NetArc] = Field(default_factory=list, description="Net timing arcs") 
    notes: List[str] = Field(default_factory=list, description="Analysis notes")
    
    def to_prompt(self) -> ViolationPrompt:
        """Convert to LLM prompt format"""
        # Extract worst cells (highest delay)
        worst_cells = sorted(self.cell_arcs, key=lambda x: x.delay_ns, reverse=True)[:3]
        worst_nets = sorted(self.net_arcs, key=lambda x: x.delay_ns, reverse=True)[:3]
        
        return ViolationPrompt(
            clock=self.clock,
            slack_ns=self.slack_ns,
            startpoint=self.startpoint.name,
            endpoint=self.endpoint.name,
            levels_of_logic=self.levels_of_logic,
            worst_cells=[
                WorstCell(inst=c.inst, type=c.type, delay_ns=c.delay_ns) 
                for c in worst_cells
            ],
            worst_nets=[
                WorstNet(net=n.net, delay_ns=n.delay_ns, routing_pct=n.est_route_pct)
                for n in worst_nets
            ],
            hints=self.notes
        )

class ReportMetadata(BaseModel):
    """Timing report metadata"""
    tool: str = Field(default="Unknown", description="EDA tool name and version")
    design: str = Field(default="Unknown", description="Top-level design name")
    device: str = Field(default="Unknown", description="Target device")

class TimingReport(BaseModel):
    """Complete timing report structure"""
    report_meta: ReportMetadata = Field(default_factory=ReportMetadata)
    violations: List[TimingViolation] = Field(default_factory=list)
    
    def get_worst_violations(self, limit: int = 10) -> List[TimingViolation]:
        """Get worst violations sorted by slack"""
        return sorted(self.violations, key=lambda x: x.slack_ns)[:limit]

# ---- Utility functions ----

def validate_llm_output(raw_json: str) -> LlmResult:
    """Validate and parse LLM output with detailed error reporting"""
    try:
        return LlmResult.model_validate_json(raw_json)
    except Exception as e:
        # Enhanced error context for debugging
        try:
            parsed = json.loads(raw_json)
            error_context = {
                "validation_error": str(e),
                "raw_keys": list(parsed.keys()) if isinstance(parsed, dict) else "not_dict",
                "raw_preview": str(raw_json)[:200] + "..." if len(raw_json) > 200 else raw_json
            }
        except:
            error_context = {"parsing_error": "Invalid JSON", "raw_preview": raw_json[:100]}
        
        raise ValueError(f"LLM output validation failed: {error_context}")

def create_fallback_result(violation_prompt: ViolationPrompt, error_msg: str) -> LlmResult:
    """Create minimal fallback result when LLM fails"""
    # Heuristic analysis based on prompt data
    fixes = []
    root_causes = []
    
    # High logic levels → pipeline
    if violation_prompt.levels_of_logic >= 8:
        fixes.append(Fix(
            type="retime_or_pipeline",
            scope="critical_path", 
            detail=f"Insert pipeline registers to reduce {violation_prompt.levels_of_logic} logic levels"
        ))
        root_causes.append("deep combinational logic")
    
    # High routing delay → floorplan
    high_routing_nets = [n for n in violation_prompt.worst_nets if n.routing_pct >= 50]
    if high_routing_nets:
        fixes.append(Fix(
            type="floorplan",
            scope="placement",
            detail=f"Add pblock constraints to reduce routing delay on {high_routing_nets[0].net}"
        ))
        root_causes.append("excessive routing delay")
    
    # Fallback fix if no heuristics match
    if not fixes:
        fixes.append(Fix(
            type="constraint_update",
            scope="timing",
            detail="Review timing constraints and add multicycle paths if appropriate"
        ))
        root_causes.append("constraint or analysis issue")
    
    return LlmResult(
        issue_class="uncertain",
        probable_root_cause=root_causes or ["analysis failed"],
        culprit_nodes=[Culprit(name="unknown", kind="cell")],
        suggested_fixes=fixes,
        expected_effect_ns=abs(violation_prompt.slack_ns) * 0.5,  # Conservative estimate
        risk_notes=[f"Fallback analysis due to: {error_msg}"],
        verify_steps=["Re-run timing analysis", "Validate functional correctness"],
        confidence_score=0.3,  # Low confidence for fallback
        model_used="heuristic_fallback"
    )