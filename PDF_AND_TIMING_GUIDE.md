# 📄 PDF Generation & Time Tracking Guide

## New Features Added ✨

### 1. Professional PDF Reports
Convert markdown reviews to beautiful, print-ready PDFs with:
- Clean, professional styling
- Proper page breaks
- Table of contents
- Color-coded risk levels
- Optimized for printing

### 2. Performance Tracking
Every review now tracks:
- Total processing time
- Time per step (parsing, segmentation, review, etc.)
- Average time per clause
- Displayed in terminal and saved in reports

---

## Installation

Install the PDF generation dependencies:

```bash
pip install weasyprint markdown
```

**Note**: WeasyPrint requires system dependencies on some platforms:

### Windows
```bash
# Usually works out of the box with pip
pip install weasyprint
```

### macOS
```bash
brew install cairo pango gdk-pixbuf libffi
pip install weasyprint
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get install build-essential python3-dev python3-pip python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
pip install weasyprint
```

---

## Usage

### Generate PDF During Review

```bash
# Generate PDF only
python main.py rv contract.pdf --format pdf

# Generate markdown + PDF
python main.py rv contract.pdf --format all

# Generate markdown + JSON + PDF
python main.py rv contract.pdf --format all
```

### Convert Existing Markdown to PDF

```bash
# Convert single file
python main.py pdf data/reviews/contract_2026-03-04.md

# Convert with custom output path
python main.py pdf report.md -o custom_report.pdf

# Batch convert all markdown files in a directory
python main.py pdf-batch data/reviews/

# Batch convert to different directory
python main.py pdf-batch data/reviews/ -o data/pdfs/
```

---

## PDF Features

### Professional Styling

The PDF includes:
- **Clean typography** - Segoe UI font family
- **Color-coded sections** - Blue headers, risk-colored badges
- **Proper spacing** - Optimized line height and margins
- **Page breaks** - Smart breaks to avoid orphaned content
- **Tables** - Styled with alternating row colors
- **Blockquotes** - Highlighted evidence sections
- **Code blocks** - Monospace font for technical content

### Page Layout

- **Size**: A4 (210mm × 297mm)
- **Margins**: 2cm top/bottom, 1.5cm left/right
- **Page numbers**: Automatic in header
- **Footer**: Generation timestamp and confidentiality notice

### Risk Level Colors

- 🔴 **HIGH** - Red (#dc2626)
- 🟡 **MEDIUM** - Orange (#f59e0b)
- 🔵 **LOW** - Blue (#3b82f6)
- ✅ **ACCEPTABLE** - Green (#10b981)

---

## Time Tracking

### What's Tracked

Every review now measures:

1. **Parse Time** - Document extraction (PDF/DOCX/TXT)
2. **Segment Time** - Clause boundary detection
3. **Metadata Time** - Contract info extraction
4. **Review Time** - LLM analysis of all clauses
5. **Summary Time** - Executive summary generation
6. **Total Time** - End-to-end processing

### Where to See It

#### Terminal Output
```
✓ Parsed: 2,450 words, 5 pages (0.34s)
✓ Found 15 clauses (0.12s)
✓ Metadata: NDA | Parties: ABC, XYZ (0.89s)

Review Complete
⏱️  Total time: 45.23s | Review: 42.15s | Avg per clause: 2.81s
```

#### Markdown Report
```markdown
## Performance Metrics

| Metric | Time |
|--------|------|
| Total Processing Time | 45.23s |
| Document Parsing | 0.34s |
| Clause Segmentation | 0.12s |
| Metadata Extraction | 0.89s |
| Clause Review | 42.15s |
| Executive Summary | 1.73s |
| Average per Clause | 2.81s |
```

#### JSON Report
```json
{
  "metadata": {
    "timing": {
      "total_seconds": 45.23,
      "parse_seconds": 0.34,
      "segment_seconds": 0.12,
      "metadata_seconds": 0.89,
      "review_seconds": 42.15,
      "summary_seconds": 1.73,
      "avg_seconds_per_clause": 2.81
    }
  }
}
```

---

## Performance Benchmarks

### Expected Times (llama3.2:3b)

| Contract Size | Clauses | Total Time | Per Clause |
|---------------|---------|------------|------------|
| Small NDA | 5-8 | 15-25s | 2-3s |
| Medium MSA | 10-15 | 30-50s | 2.5-3.5s |
| Large Contract | 20-30 | 60-100s | 3-4s |

### Optimization Tips

1. **Use faster model for quick reviews**:
   ```bash
   # In .env
   FAST_MODEL=llama3.2:1b
   ```

2. **Use better model for quality**:
   ```bash
   ollama pull qwen2.5:14b
   # In .env
   PRIMARY_MODEL=qwen2.5:14b
   ```

3. **Reduce context window**:
   ```bash
   # In .env
   MAX_CHUNK_TOKENS=256  # Default: 512
   ```

4. **Skip RAG for speed**:
   ```bash
   python main.py rv contract.pdf --no-store
   ```

---

## PDF Customization

### Modify Styling

Edit `utils/pdf_generator.py` → `_get_css_styles()` method:

```python
# Change colors
h1 {
    color: #your-color;
    border-bottom: 3px solid #your-color;
}

# Change fonts
body {
    font-family: 'Your Font', sans-serif;
}

# Change page size
@page {
    size: Letter;  # or A4, Legal, etc.
}
```

### Add Company Logo

In `_markdown_to_html()` method:

```python
html = f"""
<body>
    <div class="header">
        <img src="logo.png" alt="Company Logo">
    </div>
    <div class="container">
        {body_html}
    </div>
</body>
"""
```

### Custom Footer

In `_get_css_styles()`:

```python
.footer {
    content: "Your Company Name - Confidential";
}
```

---

## Troubleshooting

### PDF Generation Fails

**Error**: `OSError: cannot load library 'gobject-2.0-0'`

**Solution**: Install system dependencies (see Installation section above)

---

**Error**: `ModuleNotFoundError: No module named 'weasyprint'`

**Solution**:
```bash
pip install weasyprint markdown
```

---

**Error**: `PDF generation failed: Font not found`

**Solution**: WeasyPrint will use system fonts. On Windows, it uses fonts from `C:\Windows\Fonts\`. The default fonts (Segoe UI, Arial) should work out of the box.

---

### Slow Performance

**Issue**: Review takes too long

**Solutions**:
1. Use smaller model: `llama3.2:1b`
2. Reduce max tokens in `.env`
3. Skip RAG: `--no-store` flag
4. Use GPU acceleration (if available)

---

**Issue**: PDF generation is slow

**Solution**: This is normal for first PDF. WeasyPrint caches fonts after first run. Subsequent PDFs will be faster.

---

### Time Tracking Issues

**Issue**: Times not showing in report

**Solution**: Make sure you're using the updated `review_pipeline.py`. The timing data is automatically added to `report.metadata['timing']`.

---

**Issue**: Times seem inaccurate

**Solution**: Times include LLM inference, which can vary based on:
- Model size
- System load
- GPU availability
- Clause complexity

---

## Examples

### Complete Workflow

```bash
# 1. Review contract with all outputs
python main.py rv contract.pdf --format all -v

# Output:
# ✓ Parsed: 2,450 words (0.34s)
# ✓ Found 15 clauses (0.12s)
# ✓ Metadata extracted (0.89s)
# ✓ Review complete (42.15s)
# ✓ PDF generated
#
# Saved:
#   data/reviews/contract_2026-03-04.md
#   data/reviews/contract_2026-03-04.json
#   data/reviews/contract_2026-03-04.pdf

# 2. Convert old reports to PDF
python main.py pdf-batch data/reviews/

# Output:
# ✓ Converted 10 files!
#   contract_2026-03-02.pdf
#   contract_2026-03-03.pdf
#   ...
```

### Quick PDF Preview

```bash
# Generate PDF only (no markdown/json)
python main.py rv contract.pdf --format pdf

# Open the PDF
# Windows
start data/reviews/contract_2026-03-04.pdf

# macOS
open data/reviews/contract_2026-03-04.pdf

# Linux
xdg-open data/reviews/contract_2026-03-04.pdf
```

---

## API Usage (Programmatic)

### Generate PDF from Python

```python
from pathlib import Path
from utils.pdf_generator import pdf_generator

# Convert markdown to PDF
md_file = Path("data/reviews/contract_2026-03-04.md")
pdf_file = Path("data/reviews/contract_2026-03-04.pdf")

pdf_generator.markdown_to_pdf(md_file, pdf_file)
print(f"PDF generated: {pdf_file}")
```

### Batch Convert

```python
from pathlib import Path
from utils.pdf_generator import pdf_generator

# Convert all markdown files
reviews_dir = Path("data/reviews")
pdf_paths = pdf_generator.batch_convert(reviews_dir)

print(f"Converted {len(pdf_paths)} files")
```

### Access Timing Data

```python
from core.review_pipeline import review_pipeline

# Run review
report = review_pipeline.review_file("contract.pdf")

# Access timing
timing = report.metadata.get('timing', {})
print(f"Total time: {timing['total_seconds']}s")
print(f"Review time: {timing['review_seconds']}s")
print(f"Avg per clause: {timing['avg_seconds_per_clause']}s")
```

---

## Best Practices

### For Speed
1. Use `--format pdf` (skip markdown/json if not needed)
2. Use smaller model for drafts
3. Skip RAG with `--no-store`
4. Review in batches during off-hours

### For Quality
1. Use `--format all` (keep all formats)
2. Use larger model (qwen2.5:14b)
3. Enable RAG with `kb-init`
4. Review with `--verbose` flag

### For Production
1. Always generate PDF for client delivery
2. Keep JSON for database/tracking
3. Keep markdown for version control
4. Track timing for SLA monitoring

---

## Summary

✅ **PDF Generation** - Professional, print-ready reports
✅ **Time Tracking** - Performance metrics for every review
✅ **Batch Conversion** - Convert multiple files at once
✅ **Customizable** - Modify styling, fonts, colors
✅ **Production Ready** - Error handling, logging, optimization

**Commands Added**:
- `python main.py rv <file> --format pdf` - Generate PDF during review
- `python main.py pdf <file>` - Convert markdown to PDF
- `python main.py pdf-batch <dir>` - Batch convert directory

**Files Added**:
- `utils/pdf_generator.py` - PDF generation engine
- `PDF_AND_TIMING_GUIDE.md` - This guide

**Files Modified**:
- `core/review_pipeline.py` - Added time tracking
- `utils/report_exporter.py` - Added timing section to markdown
- `main.py` - Added PDF commands and format options
- `requirements.txt` - Added weasyprint and markdown

---

**Ready to use!** 🚀

Generate your first PDF:
```bash
python main.py rv data/uploads/contract_2026-03-04.txt --format all -v
```
