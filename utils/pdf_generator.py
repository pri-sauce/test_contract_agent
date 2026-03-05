"""
utils/pdf_generator.py - Professional PDF Report Generator
Converts markdown reports to clean, professional PDFs.
Uses: pdfkit + markdown (pip install pdfkit markdown)
"""

from pathlib import Path
from datetime import datetime

try:
    from loguru import logger
except ImportError:
    import logging as _logging, sys
    class _L:
        def __init__(self):
            self._l = _logging.getLogger("pdf_generator")
            if not self._l.handlers:
                h = _logging.StreamHandler(sys.stdout)
                h.setFormatter(_logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))
                self._l.addHandler(h)
                self._l.setLevel(_logging.DEBUG)
        def info(self, m, *a, **k):    self._l.info(m, *a, **k)
        def warning(self, m, *a, **k): self._l.warning(m, *a, **k)
        def error(self, m, *a, **k):   self._l.error(m, *a, **k)
        def success(self, m, *a, **k): self._l.info("✓ " + m, *a, **k)
        def debug(self, m, *a, **k):   self._l.debug(m, *a, **k)
    logger = _L()

try:
    import pdfkit
    import markdown as _markdown
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Run: pip install pdfkit markdown")

CSS = """
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; line-height: 1.6; color: #333; padding: 20px 40px 60px; }
h1 { font-size: 22pt; color: #1a1a1a; border-bottom: 3px solid #2563eb; padding-bottom: 8px; margin-bottom: 16px; }
h2 { font-size: 16pt; color: #1e40af; margin-top: 24px; }
h3 { font-size: 13pt; color: #1e3a8a; margin-top: 16px; }
p  { text-align: justify; margin-bottom: 8px; }
table { width: 100%; border-collapse: collapse; margin: 14px 0; font-size: 10pt; }
thead { background: #1e40af; color: white; }
th { padding: 7px 8px; text-align: left; border: 1px solid #1e40af; }
td { padding: 5px 8px; border: 1px solid #d1d5db; }
tbody tr:nth-child(even) { background: #f9fafb; }
blockquote { margin: 10px 0; padding: 8px 14px; background: #f0f9ff; border-left: 4px solid #3b82f6; font-style: italic; color: #1e3a8a; }
pre { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 10px; font-family: 'Courier New', monospace; font-size: 9pt; }
code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-family: 'Courier New', monospace; font-size: 9pt; color: #dc2626; }
pre code { background: none; color: inherit; padding: 0; }
hr { border: none; border-top: 1px solid #d1d5db; margin: 18px 0; }
ul, ol { margin-left: 20px; margin-bottom: 10px; }
li { margin-bottom: 3px; }
.footer { position: fixed; bottom: 0; left: 0; right: 0; border-top: 1px solid #e5e7eb; padding: 5px 40px; font-size: 8pt; color: #6b7280; display: flex; justify-content: space-between; background: white; }
"""


class PDFGenerator:
    """
    Generates professional PDF reports from markdown.
    Requires: pip install pdfkit markdown
    On Windows also install wkhtmltopdf: https://wkhtmltopdf.org/downloads.html
    """

    def markdown_to_pdf(self, markdown_path: Path, output_path: Path = None) -> Path:
        if not AVAILABLE:
            raise ImportError("Run: pip install pdfkit markdown")
        if not markdown_path.exists():
            raise FileNotFoundError(f"Not found: {markdown_path}")
        if output_path is None:
            output_path = markdown_path.with_suffix(".pdf")

        logger.info(f"Converting {markdown_path.name} to PDF...")

        md_text = markdown_path.read_text(encoding="utf-8")
        html = _markdown.markdown(md_text, extensions=["tables", "fenced_code", "nl2br", "sane_lists"])
        generated = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        full_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>{CSS}</style></head><body>
{html}
<div class="footer">
  <span>Contract Review Agent — Confidential</span>
  <span>Generated {generated}</span>
</div>
</body></html>"""

        options = {"page-size": "A4", "margin-top": "20", "margin-bottom": "20",
                   "margin-left": "15", "margin-right": "15", "encoding": "UTF-8", "quiet": ""}
        pdfkit.from_string(full_html, str(output_path), options=options)

        logger.success(f"PDF generated: {output_path}")
        return output_path

    def batch_convert(self, markdown_dir: Path, output_dir: Path = None) -> list[Path]:
        if output_dir is None:
            output_dir = markdown_dir
        else:
            output_dir.mkdir(parents=True, exist_ok=True)

        files = list(markdown_dir.glob("*.md"))
        results = []
        logger.info(f"Converting {len(files)} markdown files to PDF...")
        for f in files:
            try:
                results.append(self.markdown_to_pdf(f, output_dir / f.with_suffix(".pdf").name))
            except Exception as e:
                logger.error(f"Failed {f.name}: {e}")
        logger.success(f"Converted {len(results)}/{len(files)} files")
        return results


# Singleton
pdf_generator = PDFGenerator()