#!/usr/bin/env python3
"""
test_parsing.py
Test script to validate cerebras JSON parsing functionality
"""

import json
import sys
from pathlib import Path

# Add backend app to Python path
backend_dir = Path(__file__).parent / "backend" / "app" / "llm_integration"
sys.path.insert(0, str(backend_dir))

from cohere_service import load_and_process_cerebras_file

def test_parsing(json_file):
    """Test parsing and return validation results."""
    print(f"🔍 Testing parsing of: {json_file}")
    print("=" * 50)
    
    try:
        # Load and process the file
        enhanced_data = load_and_process_cerebras_file(json_file)
        
        # Validate key components
        results = {
            "file_loaded": True,
            "has_original": "original" in enhanced_data,
            "has_analysis": "analysis" in enhanced_data,
            "has_ui_data": "ui_data" in enhanced_data,
            "fixes_count": len(enhanced_data.get("analysis", {}).get("fixes", [])),
            "code_changes_exist": bool(enhanced_data.get("analysis", {}).get("code_changes", {}).get("files_modified")),
            "severity": enhanced_data.get("analysis", {}).get("summary", {}).get("severity"),
            "clock_info": enhanced_data.get("ui_data", {}).get("header", {}),
            "diff_generated": bool(enhanced_data.get("analysis", {}).get("code_changes", {}).get("diff"))
        }
        
        # Print validation results
        print("✅ Parsing Results:")
        print(f"   • File loaded successfully: {results['file_loaded']}")
        print(f"   • Original data preserved: {results['has_original']}")
        print(f"   • Analysis structure created: {results['has_analysis']}")
        print(f"   • UI data structure created: {results['has_ui_data']}")
        print(f"   • Number of fixes parsed: {results['fixes_count']}")
        print(f"   • Code changes detected: {results['code_changes_exist']}")
        print(f"   • Timing severity: {results['severity']}")
        print(f"   • Clock frequency: {results['clock_info'].get('frequency', 'N/A')}")
        print(f"   • Diff generated: {results['diff_generated']}")
        
        # Show timing metrics
        original = enhanced_data.get("original", {})
        wns = original.get("result", {}).get("summary", {}).get("wns_ns", 0)
        period = original.get("result", {}).get("summary", {}).get("period_ns", 0)
        print(f"   • WNS (Worst Negative Slack): {wns}ns")
        print(f"   • Clock period: {period}ns")
        
        # Show fix details
        fixes = enhanced_data.get("analysis", {}).get("fixes", [])
        if fixes:
            print(f"\n📋 Fix Summary:")
            for i, fix in enumerate(fixes, 1):
                title = fix.get("title", f"Fix {i}")
                print(f"   {i}. {title}")
        
        return True, results
        
    except Exception as e:
        print(f"❌ Error during parsing: {e}")
        return False, {"error": str(e)}

if __name__ == "__main__":
    # Test files
    test_files = [
        "/Users/raiya/Clkwise-2/cerebras_out1.json",
        "/Users/raiya/Clkwise-2/backend/data/llm_out/cerebras_out.json"
    ]
    
    all_passed = True
    
    for test_file in test_files:
        if Path(test_file).exists():
            success, results = test_parsing(test_file)
            all_passed &= success
            print()
        else:
            print(f"⚠️  File not found: {test_file}")
            print()
    
    if all_passed:
        print("🎉 All parsing tests passed!")
    else:
        print("❌ Some parsing tests failed!")
        sys.exit(1)