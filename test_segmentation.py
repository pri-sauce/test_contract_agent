"""Quick test script to verify segmentation improvements"""

from ingestion.parser import parser
from ingestion.segmenter import segmenter
from pathlib import Path

# Test with the contract
contract_path = Path("data/uploads/contract_2026-03-04.txt")

print(f"Testing segmentation on: {contract_path.name}")
print("=" * 60)

# Parse
doc = parser.parse(contract_path)
print(f"✓ Parsed: {doc.word_count} words")

# Segment
clauses = segmenter.segment(doc)
print(f"✓ Found {len(clauses)} clauses\n")

# Show what was found
print("Clauses detected:")
print("-" * 60)
for i, clause in enumerate(clauses, 1):
    heading = clause.heading or clause.clause_type or "No heading"
    print(f"{i}. [{clause.number}] {heading[:60]}")
    print(f"   Type: {clause.clause_type} | Length: {len(clause.text)} chars")
    print()

print("=" * 60)
print(f"Summary: {len(clauses)} clauses successfully segmented")
