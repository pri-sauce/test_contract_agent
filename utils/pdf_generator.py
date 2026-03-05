"""
utils/pdf_generator.py - Professional PDF Report Generator
Converts markdown reports to clean, professional PDFs with proper formatting.
"""

import re
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Logger — uses loguru if available, falls back to stdlib logging
# ---------------------------------------------------------------------------
try:
    from loguru import logger
except ImportError:
    import logging as _logging
    import sys

    class _LoguruCompat:
        """Minimal loguru-compatible logger backed by stdlib logging."""
        def __init__(self):
            self._log = _logging.getLogger("pdf_generator")
            if not self._log.handlers:
                handler = _logging.StreamHandler(sys.stdout)
                handler.setFormatter(_logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                ))
                self._log.addHandler(handler)
                self._log.setLevel(_logging.DEBUG)

        def info(self, msg, *a, **kw):    self._log.info(msg, *a, **kw)
        def warning(self, msg, *a, **kw): self._log.warning(msg, *a, **kw)
        def error(self, msg, *a, **kw):   self._log.error(msg, *a, **kw)
        def success(self, msg, *a, **kw): self._log.info("✓ " + msg, *a, **kw)
        def debug(self, msg, *a, **kw):   self._log.debug(msg, *a, **kw)

    logger = _LoguruCompat()

# ---------------------------------------------------------------------------
# ReportLab imports + colour palette (all inside one try block so the colour
# constants are only defined when reportlab is actually present)
# ---------------------------------------------------------------------------
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable, PageBreak, Preformatted,
    )

    REPORTLAB_AVAILABLE = True

    # Colour palette — mirrors the original WeasyPrint CSS
    BLUE_DARK   = colors.HexColor("#1e40af")
    BLUE_DARKER = colors.HexColor("#1e3a8a")
    BLUE_MID    = colors.HexColor("#2563eb")
    BLUE_LIGHT  = colors.HexColor("#f0f9ff")
    GREY_TEXT   = colors.HexColor("#333333")
    GREY_LIGHT  = colors.HexColor("#6b7280")
    GREY_BORDER = colors.HexColor("#d1d5db")
    RED_CODE    = colors.HexColor("#dc2626")
    BG_CODE     = colors.HexColor("#f8f9fa")
    BG_ROW_ALT  = colors.HexColor("#f9fafb")
    WHITE       = colors.white

except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not installed. PDF generation will be unavailable.")


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _build_styles() -> dict:
    """Return a dict of named ParagraphStyle objects."""
    styles = {}

    styles["Normal"] = ParagraphStyle(
        "Normal",
        fontName="Helvetica",
        fontSize=11,
        leading=18,
        textColor=GREY_TEXT,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
    styles["H1"] = ParagraphStyle(
        "H1",
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=colors.HexColor("#1a1a1a"),
        spaceBefore=0,
        spaceAfter=14,
    )
    styles["H2"] = ParagraphStyle(
        "H2",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=24,
        textColor=BLUE_DARK,
        spaceBefore=18,
        spaceAfter=10,
    )
    styles["H3"] = ParagraphStyle(
        "H3",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=20,
        textColor=BLUE_DARKER,
        spaceBefore=12,
        spaceAfter=6,
    )
    styles["Blockquote"] = ParagraphStyle(
        "Blockquote",
        fontName="Helvetica-Oblique",
        fontSize=11,
        leading=16,
        textColor=BLUE_DARKER,
        leftIndent=15,
        rightIndent=10,
        spaceBefore=8,
        spaceAfter=8,
        backColor=BLUE_LIGHT,
        borderPadding=8,
    )
    styles["Code"] = ParagraphStyle(
        "Code",
        fontName="Courier",
        fontSize=9,
        leading=13,
        textColor=GREY_TEXT,
        backColor=BG_CODE,
        leftIndent=10,
        rightIndent=10,
        spaceBefore=8,
        spaceAfter=8,
        borderPadding=8,
    )
    styles["ListItem"] = ParagraphStyle(
        "ListItem",
        fontName="Helvetica",
        fontSize=11,
        leading=16,
        textColor=GREY_TEXT,
        leftIndent=20,
        spaceAfter=3,
    )
    styles["Footer"] = ParagraphStyle(
        "Footer",
        fontName="Helvetica",
        fontSize=8,
        leading=12,
        textColor=GREY_LIGHT,
        alignment=TA_CENTER,
    )

    return styles


# ---------------------------------------------------------------------------
# Markdown → ReportLab flowables parser
# ---------------------------------------------------------------------------

class _MarkdownParser:
    """
    Lightweight parser that converts a markdown string into a list of
    ReportLab Flowable objects.  Handles: headings, paragraphs, bold/italic
    inline, unordered/ordered lists, blockquotes, fenced code blocks, inline
    code, horizontal rules, and GFM-style pipe tables.
    """

    def __init__(self, styles: dict):
        self.styles = styles

    def parse(self, markdown_text: str) -> list:
        flowables = []
        lines = markdown_text.splitlines()
        i = 0

        while i < len(lines):
            line = lines[i]

            # Fenced code block
            if line.strip().startswith("```"):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                flowables.append(
                    Preformatted("\n".join(code_lines), self.styles["Code"])
                )
                i += 1
                continue

            # Horizontal rule
            if re.match(r"^[-*_]{3,}\s*$", line.strip()):
                flowables.append(Spacer(1, 6))
                flowables.append(HRFlowable(width="100%", thickness=1, color=GREY_BORDER))
                flowables.append(Spacer(1, 6))
                i += 1
                continue

            # H1
            if line.startswith("# "):
                flowables.append(Paragraph(self._inline(line[2:].strip()), self.styles["H1"]))
                flowables.append(HRFlowable(width="100%", thickness=3, color=BLUE_MID, spaceAfter=10))
                i += 1
                continue

            # H2
            if line.startswith("## "):
                flowables.append(Paragraph(self._inline(line[3:].strip()), self.styles["H2"]))
                i += 1
                continue

            # H3
            if line.startswith("### "):
                flowables.append(Paragraph(self._inline(line[4:].strip()), self.styles["H3"]))
                i += 1
                continue

            # Blockquote
            if line.startswith("> "):
                bq_lines = []
                while i < len(lines) and lines[i].startswith("> "):
                    bq_lines.append(lines[i][2:])
                    i += 1
                flowables.append(
                    Paragraph(self._inline(" ".join(bq_lines)), self.styles["Blockquote"])
                )
                continue

            # Unordered list
            if re.match(r"^[-*+] ", line):
                while i < len(lines) and re.match(r"^[-*+] ", lines[i]):
                    item = lines[i][2:].strip()
                    flowables.append(Paragraph(f"• {self._inline(item)}", self.styles["ListItem"]))
                    i += 1
                flowables.append(Spacer(1, 4))
                continue

            # Ordered list
            if re.match(r"^\d+\. ", line):
                while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                    m = re.match(r"^(\d+)\. (.*)", lines[i])
                    flowables.append(
                        Paragraph(f"{m.group(1)}. {self._inline(m.group(2))}", self.styles["ListItem"])
                    )
                    i += 1
                flowables.append(Spacer(1, 4))
                continue

            # GFM pipe table
            if "|" in line:
                table_lines = []
                while i < len(lines) and "|" in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                tbl = self._parse_table(table_lines)
                if tbl:
                    flowables.append(tbl)
                    flowables.append(Spacer(1, 8))
                continue

            # Blank line
            if line.strip() == "":
                flowables.append(Spacer(1, 6))
                i += 1
                continue

            # Normal paragraph — collect until a structural break
            para_lines = []
            while i < len(lines):
                l = lines[i]
                if (
                    l.strip() == ""
                    or l.startswith(("#", ">", "```", "|"))
                    or re.match(r"^[-*+] ", l)
                    or re.match(r"^\d+\. ", l)
                    or re.match(r"^[-*_]{3,}\s*$", l.strip())
                ):
                    break
                para_lines.append(l)
                i += 1
            text = " ".join(para_lines).strip()
            if text:
                flowables.append(Paragraph(self._inline(text), self.styles["Normal"]))

        return flowables

    def _inline(self, text: str) -> str:
        """Convert inline markdown to ReportLab XML tags."""
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = re.sub(r"\*\*\*(.*?)\*\*\*", r"<b><i>\1</i></b>", text)
        text = re.sub(r"\*\*(.*?)\*\*",     r"<b>\1</b>",         text)
        text = re.sub(r"\*(.*?)\*",          r"<i>\1</i>",         text)
        text = re.sub(r"_(.*?)_",            r"<i>\1</i>",         text)
        text = re.sub(
            r"`(.*?)`",
            r'<font name="Courier" color="#dc2626" backColor="#f1f5f9">\1</font>',
            text,
        )
        text = re.sub(r"~~(.*?)~~", r"<strike>\1</strike>", text)
        return text

    def _parse_table(self, lines: list):
        """Parse GFM pipe-table lines into a ReportLab Table flowable."""
        def split_row(line):
            return [c.strip() for c in line.strip().strip("|").split("|")]

        rows = []
        for line in lines:
            if re.match(r"^[\|\s\-:]+$", line):
                continue
            rows.append(split_row(line))

        if not rows:
            return None

        data = []
        for r_idx, row in enumerate(rows):
            style = self.styles["H3"] if r_idx == 0 else self.styles["Normal"]
            data.append([Paragraph(self._inline(c), style) for c in row])

        col_count = max(len(r) for r in data)
        for row in data:
            while len(row) < col_count:
                row.append(Paragraph("", self.styles["Normal"]))

        col_width = (A4[0] - 3 * cm) / col_count
        tbl = Table(data, colWidths=[col_width] * col_count, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  BLUE_DARK),
            ("TEXTCOLOR",      (0, 0), (-1, 0),  WHITE),
            ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, 0),  10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_ROW_ALT]),
            ("GRID",           (0, 0), (-1, -1), 0.5, GREY_BORDER),
            ("TOPPADDING",     (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 6),
            ("LEFTPADDING",    (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
            ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ]))
        return tbl


# ---------------------------------------------------------------------------
# Footer canvas callback
# ---------------------------------------------------------------------------

def _footer_canvas(canvas, doc):
    """Draw footer and page number on every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY_LIGHT)
    footer_y = 1 * cm
    canvas.drawCentredString(
        A4[0] / 2, footer_y + 12,
        f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
    )
    canvas.drawCentredString(
        A4[0] / 2, footer_y,
        "Contract Review Agent - Confidential",
    )
    canvas.drawRightString(
        A4[0] - 1.5 * cm, A4[1] - 1 * cm,
        f"Page {doc.page}",
    )
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Main class  (same public API as the original WeasyPrint version)
# ---------------------------------------------------------------------------

class PDFGenerator:
    """
    Generates professional PDF reports from markdown.
    Uses ReportLab for high-quality PDF rendering with custom styling.
    """

    def __init__(self):
        self._styles = _build_styles() if REPORTLAB_AVAILABLE else None

    def markdown_to_pdf(self, markdown_path: Path, output_path: Path = None) -> Path:
        """
        Convert a markdown file to a professional PDF.

        Args:
            markdown_path: Path to the markdown file
            output_path:   Optional output path. If None, uses same name with .pdf extension

        Returns:
            Path to the generated PDF
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "ReportLab is required for PDF generation. "
                "Install it with: pip install reportlab"
            )

        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        if output_path is None:
            output_path = markdown_path.with_suffix(".pdf")

        logger.info(f"Converting {markdown_path.name} to PDF...")
        markdown_content = markdown_path.read_text(encoding="utf-8")
        self._generate_pdf(markdown_content, output_path)
        logger.success(f"PDF generated: {output_path}")
        return output_path

    def _generate_pdf(self, markdown_text: str, output_path: Path):
        """Generate PDF from markdown text using ReportLab."""
        try:
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                leftMargin=1.5 * cm,
                rightMargin=1.5 * cm,
                topMargin=2 * cm,
                bottomMargin=2.5 * cm,
                title="Contract Review Report",
                author="Contract Review Agent",
            )
            parser = _MarkdownParser(self._styles)
            flowables = parser.parse(markdown_text)
            doc.build(flowables, onFirstPage=_footer_canvas, onLaterPages=_footer_canvas)

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise

    def batch_convert(self, markdown_dir: Path, output_dir: Path = None) -> list[Path]:
        """
        Convert all markdown files in a directory to PDFs.

        Args:
            markdown_dir: Directory containing markdown files
            output_dir:   Optional output directory. If None, uses same directory

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