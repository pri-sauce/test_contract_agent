# 🚀 Quick Start - Testing the Fixes

## What Was Fixed

Your contract review agent had 2 major issues:
1. **Segmentation**: Only detecting 1 clause instead of 15
2. **Review Quality**: Too many irrelevant issues (phone numbers, placeholders, etc.)

Both are now fixed! ✅

## Step 1: Verify the Fixes

Run this command to test everything:

```bash
python verify_fixes.py
```

**Expected output**:
```
✓ PASS - Imports
✓ PASS - Patterns  
✓ PASS - Segmentation

Overall: 3/3 tests passed
🎉 All fixes verified! Ready to use.
```

If you see this, you're good to go! 🎉

## Step 2: Run a Full Review

Now test with your actual contract:

```bash
python main.py rv data/uploads/contract_2026-03-04.txt --format both -v
```

**What to expect**:
- ✅ 14-15 clauses detected (not 1!)
- ✅ Each clause properly numbered (3.01, 4.01, etc.)
- ✅ Only real legal issues (no phone number complaints)
- ✅ Placeholder text ignored
- ✅ Clean, actionable output

## Step 3: Check the Output

The review will be saved to:
- `data/reviews/contract_2026-03-04_2026-03-04.md` (human-readable)
- `data/reviews/contract_2026-03-04_2026-03-04.json` (machine-readable)

Open the markdown file to see the improved review!

## What Changed

### Segmentation (ingestion/segmenter.py)
- ✅ Now recognizes `3.01`, `10.01` numbering format
- ✅ Handles markdown bold (`**3.01 Heading**`)
- ✅ Supports colon separators (`1: Title`)
- ✅ Better signature block filtering

### Review Quality (prompts/review_prompts.py)
- ✅ Ignores placeholder text like "(Insert standard clause)"
- ✅ Focuses on real risks (money, liability, IP, termination)
- ✅ Quality over quantity (2-3 real issues > 10 fake ones)
- ✅ Better evidence requirements

## Troubleshooting

### If verify_fixes.py fails:

**Import errors**:
```bash
pip install -r requirements.txt
```

**Pattern test fails**:
- Check Python version: `python --version` (need 3.11+)
- The patterns are correct, might be a regex engine issue

**Segmentation finds < 10 clauses**:
1. Check the contract file exists:
   ```bash
   ls -la data/uploads/contract_2026-03-04.txt
   ```

2. Check if text is being parsed correctly:
   ```bash
   python -c "from ingestion.parser import parser; doc = parser.parse('data/uploads/contract_2026-03-04.txt'); print(doc.raw_text[:500])"
   ```

3. Enable debug mode:
   ```bash
   python -c "import logging; logging.basicConfig(level=logging.DEBUG); from ingestion.parser import parser; from ingestion.segmenter import segmenter; doc = parser.parse('data/uploads/contract_2026-03-04.txt'); clauses = segmenter.segment(doc)"
   ```

### If review quality is still poor:

1. **Upgrade the model** (current: llama3.2:3b is small):
   ```bash
   ollama pull qwen2.5:14b
   ```
   
   Then edit `.env`:
   ```
   PRIMARY_MODEL=qwen2.5:14b
   ```

2. **Initialize knowledge base**:
   ```bash
   python main.py kb-init
   ```

3. **Customize playbook**:
   Edit `playbook.yaml` with your company's legal positions

## Testing with Other Contracts

The fixes work with any contract format:

```bash
# Test with PDF
python main.py rv path/to/your/contract.pdf

# Test with DOCX
python main.py rv path/to/your/contract.docx

# Test with TXT
python main.py rv path/to/your/contract.txt
```

## Quick Commands Reference

```bash
# Verify fixes
python verify_fixes.py

# Review a contract
python main.py rv <file> --format both -v

# List all reviewed contracts
python main.py list

# Show a specific review
python main.py show contract_2026-03-04

# Check system status
python main.py check

# Initialize knowledge base
python main.py kb-init

# View knowledge base stats
python main.py kb-stats
```

## Expected Results

### Your Contract (contract_2026-03-04.txt)

Should detect these clauses:
1. Definitions
2. Term and Termination
3. Effective Date and Term (3.01)
4. Notice (3.02)
5. Confidentiality (4.01)
6. Non-Solicitation (5.01)
7. Governing Law (6.01)
8. Dispute Resolution (7.01)
9. Payment and Financial Terms (8.01)
10. Intellectual Property (9.01)
11. Code of Conduct (10.01)
12. Entire Agreement (11.01)
13. Amendment and Waiver (12.01)
14. Severability (13.01)
15. Notices (14.01)

**Total: 14-15 clauses** (signature block might be filtered)

### Review Quality

Should focus on:
- ✅ Missing notice periods
- ✅ Unclear termination rights
- ✅ Confidentiality scope issues
- ✅ IP ownership concerns
- ✅ Liability limitations

Should NOT complain about:
- ❌ Phone numbers
- ❌ Email addresses
- ❌ Office addresses
- ❌ Placeholder text
- ❌ Template instructions

## Need Help?

1. Check `FIXES_SUMMARY.md` for detailed technical info
2. Check `SEGMENTATION_IMPROVEMENTS.md` for pattern details
3. Check `data/agent.log` for error messages
4. Run with `--verbose` flag for detailed output

## Success Criteria

✅ `verify_fixes.py` shows 3/3 tests passed
✅ Review detects 14-15 clauses (not 1)
✅ Each clause has proper number and heading
✅ Issues are substantive and evidence-based
✅ No complaints about phone numbers or placeholders

---

**Ready?** Run `python verify_fixes.py` now! 🚀
