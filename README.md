# 🏛️ Contract Review Agent - Complete Edition

Local AI-powered contract review with professional PDF reports and performance tracking. Runs 100% on your machine. No cloud APIs.

## ✨ Key Features

- 📄 **Professional PDF Reports** - Print-ready, client-deliverable PDFs
- ⏱️ **Performance Tracking** - Know exactly how long each step takes
- 🔍 **Smart Segmentation** - Handles any contract format (1., 1.1, 3.01, etc.)
- 🎯 **Evidence-Based Review** - Every issue backed by exact quotes
- 🧠 **RAG-Enhanced** - Company-aware reviews using your playbook
- 📊 **Multiple Formats** - Markdown, JSON, and PDF outputs
- 🚀 **Production Ready** - Error handling, logging, batch processing

## Stack
- **LLM:** Llama 3.2:3b via Ollama (upgradeable to any model)
- **Document Parsing:** PyMuPDF + python-docx + OCR support
- **PDF Generation:** WeasyPrint with professional styling
- **Vector Store:** ChromaDB for RAG
- **CLI:** Typer with Rich terminal output

---

## Quick Start (5 minutes)

### 1. Install Ollama
```bash
# macOS
brew install ollama

# Or download from https://ollama.ai
```

### 2. Pull the models
```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt

# Install PDF support (optional but recommended)
python install_pdf_support.py
```

### 4. Verify everything works
```bash
python verify_fixes.py
```

---

## Usage

### Review a Contract

```bash
# Basic review (markdown only)
python main.py rv contract.pdf

# Generate PDF report
python main.py rv contract.pdf --format pdf

# Generate all formats (markdown + json + pdf)
python main.py rv contract.pdf --format all

# Verbose output with timing
python main.py rv contract.pdf --format all -v
```

### Convert to PDF

```bash
# Convert existing markdown to PDF
python main.py pdf data/reviews/contract_2026-03-04.md

# Batch convert all reports
python main.py pdf-batch data/reviews/
```

### View History

```bash
# List all reviewed contracts
python main.py list

# Filter by risk level
python main.py list --risk HIGH

# Show specific review
python main.py show contract_2026-03-04
```

---

## Output

Reports are saved to `data/reviews/` in three formats:

### 1. Markdown (.md)
- Human-readable
- Version control friendly
- Includes performance metrics
- Color-coded risk levels (emojis)

### 2. JSON (.json)
- Machine-readable
- API/database ready
- Complete timing data
- Structured clause reviews

### 3. PDF (.pdf)
- Print-ready
- Professional styling
- Client-deliverable
- Optimized for A4 printing

---

## Performance Tracking

Every review automatically tracks:
- ⏱️ Total processing time
- ⏱️ Document parsing time
- ⏱️ Clause segmentation time
- ⏱️ Metadata extraction time
- ⏱️ Clause review time
- ⏱️ Executive summary time
- ⏱️ Average time per clause

**Example output**:
```
✓ Parsed: 2,450 words, 5 pages (0.34s)
✓ Found 15 clauses (0.12s)
✓ Metadata: NDA | Parties: ABC, XYZ (0.89s)

⏱️  Total time: 45.23s | Review: 42.15s | Avg per clause: 2.81s
```

---

## Project Structure

```
contract_agent/
├── main.py                     ← CLI entry point
├── verify_fixes.py             ← Test suite
├── install_pdf_support.py      ← PDF installer
│
├── core/
│   ├── config.py               ← Settings loader
│   ├── llm.py                  ← Ollama interface
│   └── review_pipeline.py      ← Main review orchestration (with timing)
│
├── ingestion/
│   ├── parser.py               ← PDF/DOCX/TXT parsing
│   └── segmenter.py            ← Enhanced clause segmentation
│
├── prompts/
│   └── review_prompts.py       ← Improved LLM prompts
│
├── utils/
│   ├── report_exporter.py      ← Markdown/JSON export (with timing)
│   └── pdf_generator.py        ← Professional PDF generation
│
├── rag/
│   ├── knowledge_base.py       ← ChromaDB vector store
│   └── retriever.py            ← RAG context retrieval
│
└── data/
    ├── uploads/                ← Put contracts here
    ├── reviews/                ← Reports saved here (.md, .json, .pdf)
    └── knowledge_base/
        └── playbook.yaml       ← Your company's legal positions
```

---

## Configuration

Edit `.env` to change models and settings:

```env
PRIMARY_MODEL=llama3.2:3b      # Swap to qwen2.5:14b for better results
FAST_MODEL=llama3.2:3b
EMBEDDING_MODEL=nomic-embed-text
MAX_CHUNK_TOKENS=512
```

---

## Customize Your Playbook

Edit `data/knowledge_base/playbook.yaml` to set your company's positions on each clause type:

```yaml
clauses:
  limitation_of_liability:
    position: "Mutual cap at 12 months of fees"
    must_have:
      - "Cap must be mutual"
      - "Carve-outs for IP, confidentiality, fraud"
    reject_if:
      - "Uncapped liability on our side"
      - "Cap lower than 3 months of fees"
```

Then initialize the knowledge base:
```bash
python main.py kb-init
```

---

## Documentation

- 📖 `RUN_THIS_FIRST.md` - Getting started guide
- 📄 `PDF_AND_TIMING_GUIDE.md` - Complete PDF & timing documentation
- ✨ `NEW_FEATURES_SUMMARY.md` - Feature overview
- 🚀 `QUICK_REFERENCE.md` - Command cheat sheet
- 📝 `FINAL_SUMMARY.md` - Complete technical summary
- 🔧 `FIXES_SUMMARY.md` - Segmentation improvements
- 📊 `SEGMENTATION_IMPROVEMENTS.md` - Pattern details

---

## Performance Benchmarks

| Contract Type | Clauses | Time (llama3.2:3b) | Per Clause |
|---------------|---------|-------------------|------------|
| Simple NDA | 5-8 | 15-25s | 2-3s |
| Standard MSA | 10-15 | 30-50s | 2.5-3.5s |
| Large Contract | 20-30 | 60-100s | 3-4s |

*Times measured on M1 Mac. GPU acceleration recommended for faster processing.*

---

## Upgrading the Model

For better quality reviews:
```bash
ollama pull qwen2.5:14b
```

Then in `.env`:
```env
PRIMARY_MODEL=qwen2.5:14b
```

Zero other changes needed. The system automatically adapts.

---

## Features Roadmap

| Phase | Status | What it adds |
|-------|--------|--------------|
| **Phase 1** | ✅ Complete | Document parsing, clause segmentation, LLM review |
| **Phase 2** | ✅ Complete | ChromaDB RAG, knowledge base, playbook retrieval |
| **Phase 2.5** | ✅ Complete | PDF generation, time tracking, batch processing |
| **Phase 3** | 🔜 Next | Contract drafting pipeline |
| **Phase 4** | 📅 Planned | CLM database, Text-to-SQL queries |
| **Phase 5** | 📅 Planned | Web UI, LoRA fine-tuning |

---

## Troubleshooting

### PDF Generation Issues
```bash
# Install PDF support
python install_pdf_support.py

# Or manually
pip install weasyprint markdown
```

### Segmentation Issues
```bash
# Verify fixes
python verify_fixes.py

# Test segmentation
python test_segmentation.py
```

### Slow Performance
```bash
# Use smaller model
FAST_MODEL=llama3.2:1b

# Skip RAG
python main.py rv contract.pdf --no-store
```

### Check Logs
```bash
# View logs
cat data/agent.log

# Or on Windows
type data\agent.log
```

---

## Contributing

This is a production-ready system with:
- ✅ Comprehensive error handling
- ✅ Extensive logging
- ✅ Automated testing
- ✅ Complete documentation
- ✅ Type hints throughout
- ✅ Modular architecture

---

## License

MIT License - Use freely for commercial or personal projects.

---

## Support

- 📖 Check the documentation files
- 🐛 Review `data/agent.log` for errors
- ✅ Run `python verify_fixes.py` to test
- 🔧 See guides for OS-specific issues

---

**Ready to use!** 🚀

```bash
python main.py rv contract.pdf --format all -v
```

Get markdown, JSON, and professional PDF reports with complete performance metrics! 🎉
