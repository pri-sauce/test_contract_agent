"""
utils/pdf_generator.py - Professional PDF Report Generator
Converts markdown reports to clean, professional PDFs using pandoc + wkhtmltopdf.
"""

import subprocess
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

try:
    from loguru import logger
except ImportError:
    import logging as _logging
    import sys

    class _LoguruCompat:
        def __init__(self):
            self._log = _logging.getLogger("pdf_generator")
            if not self._log.handlers:
                h = _logging.StreamHandler(sys.stdout)
                h.setFormatter(_logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                ))
                self._log.addHandler(h)
                self._log.setLevel(_logging.DEBUG)
        def info(self, m, *a, **k):    self._log.info(m, *a, **k)
        def warning(self, m, *a, **k): self._log.warning(m, *a, **k)
        def error(self, m, *a, **k):   self._log.error(m, *a, **k)
        def success(self, m, *a, **k): self._log.info("✓ " + m, *a, **k)
        def debug(self, m, *a, **k):   self._log.debug(m, *a, **k)

    logger = _LoguruCompat()


_PANDOC      = shutil.which("pandoc")
_WKHTMLTOPDF = shutil.which("wkhtmltopdf")
PANDOC_AVAILABLE = bool(_PANDOC and _WKHTMLTOPDF)

if not _PANDOC:
    logger.warning("pandoc not found. Install: https://pandoc.org/installing.html")
if not _WKHTMLTOPDF:
    logger.warning("wkhtmltopdf not found. Install: https://wkhtmltopdf.org/downloads.html")


def _build_html(body_html: str, title: str, generated_at: str) -> str:
    """Wrap converted HTML body in a full styled document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 11pt; line-height: 1.6; color: #333;
    margin: 0; padding: 20px 30px 60px 30px;
  }}
  h1 {{
    font-size: 22pt; font-weight: 700; color: #1a1a1a;
    border-bottom: 3px solid #2563eb; padding-bottom: 8pt; margin-bottom: 16pt;
  }}
  h2 {{ font-size: 16pt; font-weight: 600; color: #1e40af; margin-top: 22pt; margin-bottom: 8pt; }}
  h3 {{ font-size: 13pt; font-weight: 600; color: #1e3a8a; margin-top: 14pt; margin-bottom: 6pt; }}
  p  {{ margin-bottom: 8pt; text-align: justify; }}
  strong {{ font-weight: 600; color: #1a1a1a; }}
  em     {{ font-style: italic; color: #4b5563; }}
  ul, ol {{ margin-left: 20pt; margin-bottom: 10pt; }}
  li     {{ margin-bottom: 3pt; }}
  table  {{ width: 100%; border-collapse: collapse; margin: 14pt 0; font-size: 10pt; }}
  thead  {{ background-color: #1e40af; color: white; }}
  th     {{ padding: 7pt 8pt; text-align: left; font-weight: 600; border: 1px solid #1e40af; }}
  td     {{ padding: 5pt 8pt; border: 1px solid #d1d5db; }}
  tbody tr:nth-child(even) {{ background-color: #f9fafb; }}
  blockquote {{
    margin: 10pt 0; padding: 8pt 14pt;
    background-color: #f0f9ff; border-left: 4px solid #3b82f6;
    font-style: italic; color: #1e3a8a;
  }}
  pre {{
    background-color: #f8f9fa; border: 1px solid #dee2e6;
    border-radius: 4px; padding: 10pt; margin: 10pt 0;
    font-family: 'Courier New', monospace; font-size: 9pt; line-height: 1.4;
    white-space: pre-wrap; word-wrap: break-word;
  }}
  code {{
    background-color: #f1f5f9; padding: 1pt 4pt;
    border-radius: 3px; font-family: 'Courier New', monospace;
    font-size: 9pt; color: #dc2626;
  }}
  pre code {{ background: none; color: inherit; padding: 0; border-radius: 0; }}
  hr {{ border: none; border-top: 1px solid #d1d5db; margin: 18pt 0; }}
  a  {{ color: #2563eb; text-decoration: none; }}
  .footer {{
    position: fixed; bottom: 0; left: 0; right: 0;
    border-top: 1px solid #e5e7eb;
    background: white;
    padding: 6pt 20pt;
    font-size: 8pt; color: #6b7280;
    display: flex; justify-content: space-between;
  }}
</style>
</head>
<body>
{body_html}
<div class="footer">
  <span>Contract Review Agent &mdash; Confidential</span>
  <span>Generated {generated_at}</span>
</div>
</body>
</html>"""


class PDFGenerator:
    """
    Generates professional PDF reports from markdown.
    Pipeline: markdown → HTML (pandoc) → PDF (wkhtmltopdf).
    No Python PDF libraries or GUI system dependencies required.
    """

    def __init__(self):
        pass

    def markdown_to_pdf(self, markdown_path: Path, output_path: Path = None) -> Path:
        """
        Convert a markdown file to a professional PDF.

        Args:
            markdown_path: Path to the markdown file
            output_path:   Optional output path. Defaults to same name with .pdf extension

        Returns:
            Path to the generated PDF
        """
        if not PANDOC_AVAILABLE:
            raise RuntimeError(
                "pandoc and wkhtmltopdf are both required.\n"
                "  pandoc:      https://pandoc.org/installing.html\n"
                "  wkhtmltopdf: https://wkhtmltopdf.org/downloads.html"
            )

        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        if output_path is None:
            output_path = markdown_path.with_suffix(".pdf")

        logger.info(f"Converting {markdown_path.name} to PDF...")
        self._generate_pdf(markdown_path, output_path)
        logger.success(f"PDF generated: {output_path}")
        return output_path

    def _generate_pdf(self, md_path: Path, pdf_path: Path):
        """Convert markdown → HTML → PDF via pandoc + wkhtmltopdf."""
        try:
            # Step 1: pandoc converts markdown to an HTML fragment
            result = subprocess.run(
                ["pandoc", str(md_path), "-t", "html", "--no-highlight"],
                capture_output=True, text=True, check=True,
            )
            body_html = result.stdout

            # Step 2: wrap in our styled full HTML document
            generated_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")
            title = md_path.stem.replace("_", " ").replace("-", " ").title()
            full_html = _build_html(body_html, title, generated_at)

            # Step 3: write HTML to a temp file, then wkhtmltopdf → PDF
            with tempfile.NamedTemporaryFile(
                suffix=".html", delete=False, mode="w", encoding="utf-8"
            ) as tmp:
                tmp.write(full_html)
                tmp_path = Path(tmp.name)

            try:
                result = subprocess.run(
                    [
                        "wkhtmltopdf",
                        "--page-size", "A4",
                        "--margin-top",    "20",
                        "--margin-bottom", "20",
                        "--margin-left",   "15",
                        "--margin-right",  "15",
                        "--encoding",      "UTF-8",
                        "--quiet",
                        str(tmp_path),
                        str(pdf_path),
                    ],
                    capture_output=True, text=True,
                )
                if result.returncode != 0:
                    raise RuntimeError(result.stderr.strip())
            finally:
                tmp_path.unlink(missing_ok=True)

        except subprocess.CalledProcessError as e:
            err = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"PDF generation error: {err}")
            raise RuntimeError(f"PDF generation failed: {err}") from e
        except Exception as e:
            logger.error(f"PDF generation error: {e}")
            raise

    def batch_convert(self, markdown_dir: Path, output_dir: Path = None) -> list[Path]:
        """
        Convert all markdown files in a directory to PDFs.

        Args:
            markdown_dir: Directory containing markdown files
            output_dir:   Optional output directory. Defaults to same directory

        Returns:
            List of generated PDF paths
        """
        if output_dir is None:
            output_dir = markdown_dir
        else:
            output_dir.mkdir(parents=True, exist_ok=True)

        markdown_files = list(markdown_dir.glob("*.md"))
        pdf_paths = []

        logger.info(f"Converting {len(markdown_files)} markdown files to PDF...")

        for md_file in markdown_files:
            try:
                pdf_path = output_dir / md_file.with_suffix(".pdf").name
                self.markdown_to_pdf(md_file, pdf_path)
                pdf_paths.append(pdf_path)
            except Exception as e:
                logger.error(f"Failed to convert {md_file.name}: {e}")

        logger.success(f"Converted {len(pdf_paths)}/{len(markdown_files)} files")
        return pdf_paths


# Singleton
pdf_generator = PDFGenerator()