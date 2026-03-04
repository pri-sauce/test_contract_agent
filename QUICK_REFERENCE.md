# 🚀 Quick Reference Card

## Installation

```bash
# Install PDF support
python install_pdf_support.py

# Or manually
pip install weasyprint markdown
```

## Review Commands

```bash
# Basic review (markdown only)
python main.py rv contract.pdf

# Generate PDF
python main.py rv contract.pdf --format pdf

# Generate all formats (markdown + json + pdf)
python main.py rv contract.pdf --format all

# Verbose output
python main.py rv contract.pdf -v

# Custom output directory
python main.py rv contract.pdf -o ./reports/

# Skip RAG storage (faster)
python main.py rv contract.pdf --no-store
```

## PDF Commands

```bash
# Convert markdown to PDF
python main.py pdf report.md

# Custom output path
python main.py pdf report.md -o custom.pdf

# Batch convert directory
python main.py pdf-batch data/reviews/

# Batch to different directory
python main.py pdf-batch data/reviews/ -o data/pdfs/
```

## History Commands

```bash
# List all reviews
python main.py list

# Filter by risk
python main.py list --risk HIGH

# Show specific review
python main.py show contract_2026-03-04
```

## Knowledge Base Commands

```bash
# Initialize KB
python main.py kb-init

# Show stats
python main.py kb-stats

# Reset KB
python main.py kb-reset
```

## System Commands

```bash
# Check system
python main.py check

# Verify fixes
python verify_fixes.py

# Test segmentation
python test_segmentation.py
```

## Format Options

| Format | Output Files | Use Case |
|--------|-------------|----------|
| `markdown` | .md | Default, human-readable |
| `json` | .json | Machine-readable, API |
| `pdf` | .pdf | Print-ready, client delivery |
| `both` | .md + .json | Development |
| `all` | .md + .json + .pdf | Production |

## Time Tracking

Automatically tracked for every review:
- ⏱️ Total time
- ⏱️ Parse time
- ⏱️ Segment time
- ⏱️ Review time
- ⏱️ Average per clause

Shown in:
- Terminal output
- Markdown report (Performance Metrics section)
- JSON report (metadata.timing)

## Expected Performance

| Contract | Clauses | Time (llama3.2:3b) |
|----------|---------|-------------------|
| Small NDA | 5-8 | 15-25s |
| Medium MSA | 10-15 | 30-50s |
| Large Contract | 20-30 | 60-100s |

## File Locations

```
data/
├── uploads/          # Put contracts here
├── reviews/          # Reports saved here
│   ├── *.md         # Markdown reports
│   ├── *.json       # JSON reports
│   └── *.pdf        # PDF reports
└── knowledge_base/   # RAG database
```

## Troubleshooting

### PDF Issues
```bash
# Install dependencies
pip install weasyprint markdown

# macOS
brew install cairo pango gdk-pixbuf libffi

# Linux
sudo apt-get install libcairo2 libpango-1.0-0
```

### Slow Performance
```bash
# Use smaller model
FAST_MODEL=llama3.2:1b

# Skip RAG
python main.py rv contract.pdf --no-store
```

### Segmentation Issues
```bash
# Verify fixes
python verify_fixes.py

# Test segmentation
python test_segmentation.py
```

## Quick Examples

### Example 1: Quick Review
```bash
python main.py rv contract.pdf
```

### Example 2: Production Review
```bash
python main.py rv contract.pdf --format all -v
```

### Example 3: Batch PDF Generation
```bash
python main.py pdf-batch data/reviews/
```

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point |
| `verify_fixes.py` | Test suite |
| `install_pdf_support.py` | PDF installer |
| `RUN_THIS_FIRST.md` | Getting started |
| `PDF_AND_TIMING_GUIDE.md` | Detailed guide |
| `NEW_FEATURES_SUMMARY.md` | Feature overview |

## Support

- 📖 Full docs: `PDF_AND_TIMING_GUIDE.md`
- 🐛 Logs: `data/agent.log`
- ✅ Tests: `python verify_fixes.py`
- 🔧 Config: `.env` file

---

**Most Common Command**:
```bash
python main.py rv contract.pdf --format all -v
```

This gives you everything: markdown, JSON, PDF, and verbose output with timing! 🎉
