# Segmentation & Parsing Improvements

## What Was Fixed

### 1. Enhanced Clause Pattern Recognition

The segmenter now recognizes these additional numbering formats:

- **Leading zeros**: `3.01`, `10.01`, `15.01` (your contract uses this format!)
- **Markdown bold**: `**3.01 Heading**` or `3.01 **Heading**`
- **Colon separators**: `1: Title`, `2.1: Subtitle`
- **Mixed formats**: Handles contracts with inconsistent numbering

### 2. Improved Pattern Matching

Added 3 new regex patterns specifically for:
```python
# Pattern 1: Leading zeros with optional markdown
r"^\*?\*?(\d{1,2}\.\d{2})\*?\*?\s*[.:]?\s*\*?\*?([A-Z][^\n]+?)\*?\*?\s*:?\s*$"

# Pattern 2: Standard numbered with markdown support
r"^\*?\*?(\d{1,2}(?:\.\d{1,2}){0,3})\*?\*?\s*[.)]\s+\*?\*?([A-Z][^\n]+?)\*?\*?\s*:?\s*$"

# Pattern 3: Colon-separated with markdown
r"^\*?\*?(\d{1,2}(?:\.\d{1,2})?)\*?\*?\s*:\s*\*?\*?([A-Z][^\n]+?)\*?\*?\s*$"
```

### 3. Better Signature Block Detection

Now filters out:
- `ACKNOWLEDGEMENT AND ACCEPTANCE`
- `EMPLOYEE SIGNATURE PAGE`
- `EMPLOYER SIGNATURE PAGE`
- Lines with multiple signature artifacts

### 4. Enhanced Clause Type Classification

Added new clause types:
- `code_of_conduct`
- `acknowledgement`
- `payment and financial terms`
- `non-solicitation`

## Testing Instructions

### Step 1: Test Pattern Recognition

Run this to verify patterns work:
```bash
python quick_test.py
```

Expected output: All 4 test lines should match

### Step 2: Test Full Segmentation

Run this to see clause detection:
```bash
python test_segmentation.py
```

Expected output: Should find **15 clauses** (not 1!)

### Step 3: Run Full Review

```bash
python main.py rv data/uploads/contract_2026-03-04.txt --format both -v
```

Expected results:
- 15 clauses detected
- Each clause properly numbered (1, 2, 3.01, 3.02, 4.01, etc.)
- Proper headings extracted
- Signature blocks filtered out

## What Your Contract Should Show

Your contract has these clauses:
1. Definitions
2. Term and Termination
3.01 Effective Date and Term
3.02 Notice
4.01 Confidentiality
5.01 Non-Solicitation
6.01 Governing Law
7.01 Dispute Resolution
8.01 Payment and Financial Terms
9.01 Intellectual Property
10.01 Code of Conduct
11.01 Entire Agreement
12.01 Amendment and Waiver
13.01 Severability
14.01 Notices
15.01 Acknowledgement and Acceptance (should be filtered as signature block)

**Expected: 14-15 clauses** (depending on whether 15.01 is filtered)

## Debugging

If you still see only 1 clause:

1. Check the parsed text:
```python
from ingestion.parser import parser
doc = parser.parse('data/uploads/contract_2026-03-04.txt')
print(doc.raw_text[:1000])  # Check if clause numbers are preserved
```

2. Check boundary detection:
```python
from ingestion.segmenter import segmenter
lines = doc.raw_text.split('\n')
boundaries = segmenter._find_boundaries(lines)
print(f"Found {len(boundaries)} boundaries")
for b in boundaries[:5]:
    print(b)
```

3. Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Additional Improvements Made

1. **Markdown handling**: Strips `**` from headings automatically
2. **Colon handling**: Removes trailing colons from headings
3. **Better logging**: Shows exactly what was detected at each step
4. **Robust fallback**: If no patterns match, falls back to paragraph splitting

## Files Modified

- `ingestion/segmenter.py` - Complete rewrite with enhanced patterns
- `ingestion/parser.py` - Improved clause boundary injection (attempted)

## Next Steps

If segmentation works but reviews are still poor:

1. **Improve prompts** in `prompts/review_prompts.py`
2. **Tune the model** - try `qwen2.5:14b` instead of `llama3.2:3b`
3. **Add more playbook rules** in `playbook.yaml`
4. **Enable RAG** by running `python main.py kb-init`

## Quick Verification

Run this one-liner to count clauses:
```bash
python -c "from ingestion.parser import parser; from ingestion.segmenter import segmenter; doc = parser.parse('data/uploads/contract_2026-03-04.txt'); clauses = segmenter.segment(doc); print(f'Clauses: {len(clauses)}')"
```

Should output: `Clauses: 14` or `Clauses: 15`
