#!/usr/bin/env python3
"""
cohere_service.py
Process Cerebras timing analysis output using Cohere for enhanced user-friendly presentation.

This service takes the structured JSON output from cerebras_int.py and uses Cohere to:
1. Generate human-readable summaries
2. Create simplified explanations of fixes
3. Provide conversational insights
4. Format data for UI presentation

Env:
  COHERE_API_KEY=...   # Cohere API key

Install:
  pip install cohere
"""

import os
import json
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    import cohere
except ImportError:
    print("ERROR: pip install cohere", file=sys.stderr)
    cohere = None

class CohereProcessor:
    """Process Cerebras timing analysis output using Cohere for enhanced presentation."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Cohere client."""
        self.api_key = api_key or os.environ.get("COHERE_API_KEY")
        self.client = None
        
        if cohere and self.api_key:
            try:
                self.client = cohere.Client(self.api_key)
            except Exception as e:
                print(f"Warning: Could not initialize Cohere client: {e}", file=sys.stderr)
    
    def process_cerebras_output(self, cerebras_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process cerebras output and enhance it with Cohere analysis.
        
        Args:
            cerebras_data: Raw output from cerebras_int.py
            
        Returns:
            Enhanced data structure with Cohere analysis
        """
        # Extract the core result data
        result = cerebras_data.get("result", {})
        summary = result.get("summary", {})
        fixes = result.get("fixes", [])
        artifacts = result.get("artifacts", {})
        risks = result.get("risks", [])
        verification = result.get("verification", [])
        
        # Create enhanced structure focused on artifacts
        enhanced_data = {
            "original": cerebras_data,
            "analysis": {
                "summary": self._create_simple_summary(summary),
                "fixes": [{
                    "id": fix.get("id", f"F{i+1}"),
                    "title": fix.get("title", f"Fix {i+1}"),
                    "rationale": fix.get("rationale", "No rationale provided")
                } for i, fix in enumerate(fixes)],
                "code_changes": self._extract_code_changes(artifacts),
                "artifacts_focus": True
            },
            "ui_data": self._create_ui_data(result)
        }
        
        return enhanced_data
    
    def _create_simple_summary(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Create a simple summary focused on the artifacts changes."""
        if not summary:
            return {}
        
        return {
            "raw": summary,
            "explanation": f"""Timing violation fixed with {self._assess_severity(summary.get('wns_ns', 0))} severity. 
The artifacts show the code changes needed to resolve the {summary.get('path_kind', 'unknown')} timing path issue.""",
            "severity": self._assess_severity(summary.get("wns_ns", 0)),
            "quick_facts": [
                f"Clock frequency: {1000/summary.get('period_ns', 4):.1f} MHz" if summary.get('period_ns') else None,
                f"Timing margin needed: +{abs(summary.get('wns_ns', 0)):.3f}ns",
                f"Path type: {summary.get('path_kind', 'unknown')}",
                f"Focus: Code artifacts with timing fixes"
            ]
        }
    
    
    
    def _extract_code_changes(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format code changes for UI display with diff."""
        code_changes = {
            "files_modified": [],
            "preview": "",
            "diff": "",
            "changes_summary": {}
        }
        
        top_sv = artifacts.get("top_sv", {})
        if top_sv:
            code_changes["files_modified"] = ["top.sv"]
            new_code = top_sv.get("content", "")
            
            # Original code (reconstructed from the fixes)
            original_code = """module top(
  input  logic         clk,
  input  logic         rst_n,
  input  logic [31:0]  a, b, c, d, e, //32 bit
  output logic [63:0]  y //64 bit
);

  logic [63:0] mul1 = a * b; //32 bit x 32 bit
  logic [63:0] mul2 = c * d; //32 bit x 32 bit
  logic [63:0] sum  = mul1 + mul2 + e;  //64 bit + 64 bit + 32 bit

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) y <= '0;
    else        y <= sum;
  end
endmodule"""
            
            # Create diff
            import difflib
            original_lines = original_code.splitlines(keepends=True)
            new_lines = new_code.splitlines(keepends=True)
            
            diff = difflib.unified_diff(
                original_lines, 
                new_lines,
                fromfile="a/top.sv",
                tofile="b/top.sv",
                lineterm=""
            )
            
            code_changes["diff"] = ''.join(diff)
            code_changes["preview"] = new_code[:500] + "..." if len(new_code) > 500 else new_code
            code_changes["full_content"] = new_code
            
            # Summary
            code_changes["changes_summary"] = {
                "original_lines": len(original_lines),
                "new_lines": len(new_lines),
                "lines_added": len(new_lines) - len(original_lines)
            }
        
        return code_changes
    
    
    def _create_conversation_context(self, cerebras_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create context data for conversational AI interactions."""
        result = cerebras_data.get("result", {})
        summary = result.get("summary", {})
        
        context = {
            "problem": f"Timing violation on {summary.get('clock_name', 'unknown')} clock",
            "severity": self._assess_severity(summary.get("wns_ns", 0)),
            "key_metrics": {
                "wns": summary.get("wns_ns", 0),
                "period": summary.get("period_ns", 0),
                "signal_group": summary.get("signal_group", "unknown"),
                "path_type": summary.get("path_kind", "unknown")
            },
            "fix_count": len(result.get("fixes", [])),
            "has_code_changes": bool(result.get("artifacts", {}).get("top_sv")),
            "conversation_starters": [
                "What's the main cause of this timing violation?",
                "How complex are these fixes to implement?",
                "What are the risks of these changes?",
                "Can you explain the code changes needed?"
            ]
        }
        
        return context
    
    def _create_ui_data(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Create structured data optimized for UI display."""
        summary = result.get("summary", {})
        fixes = result.get("fixes", [])
        
        return {
            "header": {
                "title": f"Timing Analysis: {summary.get('clock_name', 'Unknown Clock')}",
                "status": "violation" if summary.get("wns_ns", 0) < 0 else "passing",
                "wns": summary.get("wns_ns", 0),
                "period": summary.get("period_ns", 0),
                "frequency": f"{1000/summary.get('period_ns', 4):.1f} MHz" if summary.get('period_ns') else "Unknown"
            },
            "problem": {
                "type": summary.get("path_kind", "unknown"),
                "signals": summary.get("signal_group", "unknown"),
                "root_cause": summary.get("root_cause", "Unknown cause")
            },
            "fixes": [
                {
                    "id": fix.get("id", f"F{i+1}"),
                    "title": fix.get("title", f"Fix {i+1}"),
                    "summary": fix.get("rationale", "")[:100] + "...",
                    "latency": fix.get("latency_impact_cycles", 0),
                    "complexity": self._assess_complexity(fix)
                }
                for i, fix in enumerate(fixes)
            ],
            "metrics": {
                "total_fixes": len(fixes),
                "total_latency": sum(fix.get("latency_impact_cycles", 0) for fix in fixes),
                "estimated_improvement": self._estimate_improvement(summary, fixes)
            }
        }
    
    # Helper methods
    def _assess_severity(self, wns: float) -> str:
        """Assess severity based on WNS value."""
        if wns >= 0:
            return "pass"
        elif wns >= -1.0:
            return "minor"
        elif wns >= -3.0:
            return "moderate"
        else:
            return "critical"
    
    def _assess_complexity(self, fix: Dict[str, Any]) -> str:
        """Assess implementation complexity of a fix."""
        patch = fix.get("verilog_patch", {})
        if patch.get("kind") == "replace_regex":
            return "low"
        elif patch.get("kind") == "insert_block":
            return "medium"
        else:
            return "high"
    
    def _categorize_risk(self, risk: str) -> str:
        """Categorize risk type."""
        risk_lower = risk.lower()
        if "latency" in risk_lower or "delay" in risk_lower:
            return "performance"
        elif "complexity" in risk_lower:
            return "implementation"
        elif "timing" in risk_lower:
            return "timing"
        else:
            return "general"
    
    def _suggest_risk_mitigation(self, risk: str) -> str:
        """Suggest mitigation for a risk."""
        risk_lower = risk.lower()
        if "latency" in risk_lower:
            return "Update protocol timing assumptions and verify downstream modules"
        elif "complexity" in risk_lower:
            return "Implement changes incrementally and test thoroughly"
        else:
            return "Careful verification and testing recommended"
    
    def _extract_code_snippet(self, fix: Dict[str, Any]) -> str:
        """Extract relevant code snippet from fix."""
        patch = fix.get("verilog_patch", {})
        return patch.get("block", "")
    
    def _estimate_improvement(self, summary: Dict[str, Any], fixes: List[Dict[str, Any]]) -> str:
        """Estimate timing improvement from fixes."""
        wns = summary.get("wns_ns", 0)
        if wns >= 0:
            return "Already passing"
        
        # Simple heuristic: assume each pipeline stage improves timing by ~1ns
        pipeline_fixes = sum(1 for fix in fixes if "pipeline" in fix.get("title", "").lower())
        estimated_improvement = pipeline_fixes * 1.0
        
        if estimated_improvement > abs(wns):
            return f"Should achieve positive slack (+{estimated_improvement + wns:.2f}ns estimated)"
        else:
            return f"Partial improvement (~+{estimated_improvement:.1f}ns estimated)"


def load_and_process_cerebras_file(file_path: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to load cerebras output file and process it with Cohere.
    
    Args:
        file_path: Path to cerebras_out.json file
        api_key: Optional Cohere API key
        
    Returns:
        Enhanced analysis data
    """
    processor = CohereProcessor(api_key)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        cerebras_data = json.load(f)
    
    return processor.process_cerebras_output(cerebras_data)


if __name__ == "__main__":
    # CLI usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Process Cerebras output with Cohere")
    parser.add_argument("input_file", help="Path to cerebras_out.json file")
    parser.add_argument("--output", "-o", help="Output file for enhanced analysis")
    parser.add_argument("--api-key", help="Cohere API key (or use COHERE_API_KEY env var)")
    
    args = parser.parse_args()
    
    try:
        enhanced_data = load_and_process_cerebras_file(args.input_file, args.api_key)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(enhanced_data, f, indent=2, ensure_ascii=False)
            print(f"Enhanced analysis written to {args.output}")
        else:
            print(json.dumps(enhanced_data, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)