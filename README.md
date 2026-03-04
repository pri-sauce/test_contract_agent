Python 3.11+ - Modern Python with type hints

dataclasses - Clean data models
pathlib - Modern file handling
typing - Type safety
Regex (re module) - Pattern matching engine

Compiled patterns for performance
Non-greedy matching (+?) to prevent over-matching
Lookahead/lookbehind for context-aware matching
Ollama - Local LLM inference

llama3.2:3b - Fast, lightweight model
nomic-embed-text - Local embeddings
No cloud APIs = privacy + speed
Document Parsing

PyMuPDF (fitz) - PDF extraction
python-docx - DOCX parsing
pytesseract - OCR for scanned PDFs
Vector Database

ChromaDB - Local vector store
Cosine similarity search
Persistent storage
CLI & Display

typer - Modern CLI framework
rich - Beautiful terminal output
loguru - Better logging
Key Design Patterns
Singleton Pattern

segmenter = ClauseSegmenter()  # Single instance
Strategy Pattern

# Multiple patterns, try each until one matches
for pattern in COMPILED_PATTERNS:
    if match := pattern.match(line):
        return match.groups()
Pipeline Pattern

doc → parse → segment → classify → review → export
Factory Pattern

if suffix == ".pdf":
    return self._parse_pdf(path)
elif suffix == ".docx":
    return self._parse_docx(path)
Performance Optimizations
Compiled Regex - Pre-compile patterns once

COMPILED_PATTERNS = [re.compile(p, re.MULTILINE) for p in PATTERNS]
Lazy Initialization - Load patterns only when needed

_CLAUSE_BREAK_RES = None  # Lazy load
Early Returns - Exit fast on matches

if heading.lower() in HEADING_OVERRIDES:
    return HEADING_OVERRIDES[heading.lower()]  # Fast path
Caching - Store parsed documents

@dataclass
class ParsedDocument:
    raw_text: str
    pages: list[str]  # Cached page splits
The Secret Sauce 🔥
1. Defensive Programming
# Handle None, empty, and edge cases
heading = (clause.heading or "").upper().strip()
text = (clause.text or "").strip()
2. Graceful Degradation
if not boundaries:
    # No structure detected? Fall back to paragraph splitting
    return self._paragraph_fallback(lines)
3. Comprehensive Logging
logger.debug(f"Line {i}: Found clause header - Number: '{number}', Heading: '{heading}'")
logger.success(f"Segmented into {len(clauses)} clauses")
4. Test-Driven Fixes
Created verify_fixes.py to test each component
Pattern tests verify regex works
Integration tests verify end-to-end flow
