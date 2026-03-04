import re

# Test patterns
patterns = [
    r"^\*?\*?(\d{1,2}\.\d{2})\*?\*?\s*[.:]?\s*\*?\*?([A-Z][^\n]+?)\*?\*?\s*:?\s*$",
    r"^\*?\*?(\d{1,2}(?:\.\d{1,2}){0,3})\*?\*?\s*[.)]\s+\*?\*?([A-Z][^\n]+?)\*?\*?\s*:?\s*$",
]

test_lines = [
    "1. **Definitions**: (If needed, include definitions for key terms used in the agreement.)",
    "3.01 **Effective Date and Term**: This Agreement becomes effective",
    "4.01 **Confidentiality**: (Insert standard confidentiality clause.)",
    "**10.01 Code of Conduct**: (Insert clause regarding compliance)",
]

print("Testing clause header detection:")
print("=" * 70)

for line in test_lines:
    print(f"\nLine: {line[:60]}...")
    matched = False
    for i, pattern in enumerate(patterns):
        match = re.match(pattern, line)
        if match:
            print(f"  ✓ Pattern {i+1} matched: {match.groups()}")
            matched = True
            break
    if not matched:
        print("  ✗ No match")

print("\n" + "=" * 70)
