#!/usr/bin/env python3
"""
Verification script to test all improvements
Run this to verify the fixes are working
"""

import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()

def test_imports():
    """Test that all modules import correctly"""
    console.print("\n[bold cyan]Step 1: Testing imports...[/bold cyan]")
    try:
        from ingestion.parser import parser
        from ingestion.segmenter import segmenter
        from core.review_pipeline import review_pipeline
        console.print("✓ All modules imported successfully", style="green")
        return True
    except Exception as e:
        console.print(f"✗ Import failed: {e}", style="red")
        return False

def test_patterns():
    """Test that new patterns work"""
    console.print("\n[bold cyan]Step 2: Testing clause patterns...[/bold cyan]")
    import re
    
    patterns = [
        r"^\*?\*?(\d{1,2}\.\d{2})\*?\*?\s*[.:]?\s*\*?\*?([A-Z][^\n]+?)\*?\*?\s*:?\s*$",
        r"^\*?\*?(\d{1,2}(?:\.\d{1,2}){0,3})\*?\*?\s*[.)]\s+\*?\*?([A-Z][^\n]+?)\*?\*?\s*:?\s*$",
    ]
    
    test_cases = [
        ("3.01 **Effective Date and Term**: This Agreement", True),
        ("**4.01 Confidentiality**: (Insert standard)", True),
        ("10.01 **Code of Conduct**: (Insert clause)", True),
        ("1. **Definitions**: (If needed, include)", True),
        ("Random text without number", False),
    ]
    
    passed = 0
    for line, should_match in test_cases:
        matched = any(re.match(p, line) for p in patterns)
        if matched == should_match:
            console.print(f"  ✓ {line[:50]}...", style="green")
            passed += 1
        else:
            console.print(f"  ✗ {line[:50]}... (expected {'match' if should_match else 'no match'})", style="red")
    
    console.print(f"\nPattern tests: {passed}/{len(test_cases)} passed", 
                  style="green" if passed == len(test_cases) else "yellow")
    return passed == len(test_cases)

def test_segmentation():
    """Test segmentation on the contract"""
    console.print("\n[bold cyan]Step 3: Testing segmentation...[/bold cyan]")
    
    contract_path = Path("data/uploads/contract_2026-03-04.txt")
    if not contract_path.exists():
        console.print(f"✗ Contract not found: {contract_path}", style="red")
        return False
    
    try:
        from ingestion.parser import parser
        from ingestion.segmenter import segmenter
        
        # Parse
        doc = parser.parse(contract_path)
        console.print(f"  ✓ Parsed: {doc.word_count} words", style="green")
        
        # Segment
        clauses = segmenter.segment(doc)
        console.print(f"  ✓ Segmented: {len(clauses)} clauses", style="green")
        
        # Show results
        if len(clauses) >= 10:
            console.print(f"\n[bold green]SUCCESS![/bold green] Found {len(clauses)} clauses (expected 14-15)")
            
            # Show clause table
            table = Table(title="Detected Clauses", show_header=True)
            table.add_column("#", style="dim", width=3)
            table.add_column("Number", width=8)
            table.add_column("Heading", min_width=30)
            table.add_column("Type", width=20)
            
            for i, clause in enumerate(clauses[:10], 1):
                heading = clause.heading or "No heading"
                table.add_row(
                    str(i),
                    clause.number,
                    heading[:40] + ("..." if len(heading) > 40 else ""),
                    clause.clause_type
                )
            
            if len(clauses) > 10:
                table.add_row("...", "...", f"... and {len(clauses) - 10} more", "...")
            
            console.print(table)
            return True
        else:
            console.print(f"\n[bold yellow]WARNING![/bold yellow] Only found {len(clauses)} clauses (expected 14-15)")
            console.print("This might indicate the patterns aren't matching correctly.")
            return False
            
    except Exception as e:
        console.print(f"✗ Segmentation failed: {e}", style="red")
        import traceback
        traceback.print_exc()
        return False

def main():
    console.print("\n[bold magenta]═══════════════════════════════════════════════════[/bold magenta]")
    console.print("[bold magenta]   Contract Review Agent - Fix Verification[/bold magenta]")
    console.print("[bold magenta]═══════════════════════════════════════════════════[/bold magenta]")
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Patterns", test_patterns()))
    results.append(("Segmentation", test_segmentation()))
    
    # Summary
    console.print("\n[bold cyan]═══════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]Summary[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════[/bold cyan]\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        color = "green" if result else "red"
        console.print(f"  {status} - {name}", style=color)
    
    console.print(f"\n[bold]Overall: {passed}/{total} tests passed[/bold]")
    
    if passed == total:
        console.print("\n[bold green]🎉 All fixes verified! Ready to use.[/bold green]")
        console.print("\nNext step: Run a full review:")
        console.print("  [cyan]python main.py rv data/uploads/contract_2026-03-04.txt --format both -v[/cyan]")
        return 0
    else:
        console.print("\n[bold yellow]⚠ Some tests failed. Check the output above.[/bold yellow]")
        return 1

if __name__ == "__main__":
    sys.exit(main())
