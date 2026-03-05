"""
utils/pdf_generator.py - Professional PDF Report Generator
Converts markdown reports to PDFs.

Install: pip install markdown-pdf
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
    logger = _L()

try:
    from markdown_pdf import MarkdownPdf, Section
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Run: pip install markdown-pdf")


class PDFGenerator:
    """
    Generates professional PDF reports from markdown.
    Requires: pip install markdown-pdf  (no other dependencies)
    """

    def markdown_to_pdf(self, markdown_path: Path, output_path: Path = None) -> Path:
        if not AVAILABLE:
            raise ImportError("Run: pip install markdown-pdf")
        if not markdown_path.exists():
            raise FileNotFoundError(f"Not found: {markdown_path}")
        if output_path is None:
            output_path = markdown_path.with_suffix(".pdf")

        logger.info(f"Converting {markdown_path.name} to PDF...")

        md_text = markdown_path.read_text(encoding="utf-8")

        pdf = MarkdownPdf()
        pdf.meta["title"] = markdown_path.stem.replace("_", " ").title()
        pdf.add_section(Section(md_text))
        pdf.save(str(output_path))

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