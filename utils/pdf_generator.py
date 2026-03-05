# """
# utils/pdf_generator.py - Professional PDF Report Generator
# Converts markdown reports to clean, professional PDFs with proper formatting.
# """

# from pathlib import Path
# from datetime import datetime
# from loguru import logger

# try:
#     from weasyprint import HTML, CSS
#     from weasyprint.text.fonts import FontConfiguration
#     WEASYPRINT_AVAILABLE = True
# except ImportError:
#     WEASYPRINT_AVAILABLE = False
#     logger.warning("WeasyPrint not installed. PDF generation will be unavailable.")


# class PDFGenerator:
#     """
#     Generates professional PDF reports from markdown.
#     Uses WeasyPrint for high-quality PDF rendering with custom styling.
#     """

#     def __init__(self):
#         self.font_config = FontConfiguration() if WEASYPRINT_AVAILABLE else None

#     def markdown_to_pdf(self, markdown_path: Path, output_path: Path = None) -> Path:
#         """
#         Convert a markdown file to a professional PDF.
        
#         Args:
#             markdown_path: Path to the markdown file
#             output_path: Optional output path. If None, uses same name with .pdf extension
            
#         Returns:
#             Path to the generated PDF
#         """
#         if not WEASYPRINT_AVAILABLE:
#             raise ImportError(
#                 "WeasyPrint is required for PDF generation. "
#                 "Install it with: pip install weasyprint"
#             )

#         if not markdown_path.exists():
#             raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

#         # Determine output path
#         if output_path is None:
#             output_path = markdown_path.with_suffix('.pdf')

#         logger.info(f"Converting {markdown_path.name} to PDF...")

#         # Read markdown content
#         markdown_content = markdown_path.read_text(encoding='utf-8')

#         # Convert markdown to HTML
#         html_content = self._markdown_to_html(markdown_content)

#         # Generate PDF with custom styling
#         self._generate_pdf(html_content, output_path)

#         logger.success(f"PDF generated: {output_path}")
#         return output_path

#     def _markdown_to_html(self, markdown_text: str) -> str:
#         """
#         Convert markdown to HTML with proper structure.
#         Uses markdown library for conversion.
#         """
#         try:
#             import markdown
#             from markdown.extensions.tables import TableExtension
#             from markdown.extensions.fenced_code import FencedCodeExtension
#             from markdown.extensions.codehilite import CodeHiliteExtension
#         except ImportError:
#             raise ImportError(
#                 "markdown library is required. "
#                 "Install it with: pip install markdown"
#             )

#         # Convert markdown to HTML with extensions
#         md = markdown.Markdown(extensions=[
#             TableExtension(),
#             FencedCodeExtension(),
#             CodeHiliteExtension(),
#             'nl2br',  # Newline to <br>
#             'sane_lists',  # Better list handling
#         ])

#         body_html = md.convert(markdown_text)

#         # Wrap in full HTML document with professional styling
#         html = f"""
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>Contract Review Report</title>
#     <style>
#         {self._get_css_styles()}
#     </style>
# </head>
# <body>
#     <div class="container">
#         {body_html}
#     </div>
#     <div class="footer">
#         <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
#         <p>Contract Review Agent - Confidential</p>
#     </div>
# </body>
# </html>
# """
#         return html

#     def _get_css_styles(self) -> str:
#         """
#         Professional CSS styling for the PDF report.
#         Clean, readable, and print-optimized.
#         """
#         return """
#         @page {
#             size: A4;
#             margin: 2cm 1.5cm;
#             @top-right {
#                 content: "Page " counter(page) " of " counter(pages);
#                 font-size: 9pt;
#                 color: #666;
#             }
#         }

#         * {
#             margin: 0;
#             padding: 0;
#             box-sizing: border-box;
#         }

#         body {
#             font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
#             font-size: 11pt;
#             line-height: 1.6;
#             color: #333;
#             background: white;
#         }

#         .container {
#             max-width: 100%;
#             padding: 0;
#         }

#         /* Headings */
#         h1 {
#             font-size: 24pt;
#             font-weight: 700;
#             color: #1a1a1a;
#             margin-bottom: 20pt;
#             padding-bottom: 10pt;
#             border-bottom: 3px solid #2563eb;
#             page-break-after: avoid;
#         }

#         h2 {
#             font-size: 18pt;
#             font-weight: 600;
#             color: #1e40af;
#             margin-top: 24pt;
#             margin-bottom: 12pt;
#             page-break-after: avoid;
#         }

#         h3 {
#             font-size: 14pt;
#             font-weight: 600;
#             color: #1e3a8a;
#             margin-top: 16pt;
#             margin-bottom: 8pt;
#             page-break-after: avoid;
#         }

#         /* Paragraphs */
#         p {
#             margin-bottom: 8pt;
#             text-align: justify;
#         }

#         /* Strong/Bold */
#         strong {
#             font-weight: 600;
#             color: #1a1a1a;
#         }

#         /* Emphasis/Italic */
#         em {
#             font-style: italic;
#             color: #4b5563;
#         }

#         /* Lists */
#         ul, ol {
#             margin-left: 20pt;
#             margin-bottom: 12pt;
#         }

#         li {
#             margin-bottom: 4pt;
#         }

#         /* Tables */
#         table {
#             width: 100%;
#             border-collapse: collapse;
#             margin: 16pt 0;
#             font-size: 10pt;
#             page-break-inside: avoid;
#         }

#         thead {
#             background-color: #1e40af;
#             color: white;
#         }

#         th {
#             padding: 8pt;
#             text-align: left;
#             font-weight: 600;
#             border: 1px solid #1e40af;
#         }

#         td {
#             padding: 6pt 8pt;
#             border: 1px solid #d1d5db;
#         }

#         tbody tr:nth-child(even) {
#             background-color: #f9fafb;
#         }

#         tbody tr:hover {
#             background-color: #f3f4f6;
#         }

#         /* Blockquotes */
#         blockquote {
#             margin: 12pt 0;
#             padding: 10pt 15pt;
#             background-color: #f0f9ff;
#             border-left: 4px solid #3b82f6;
#             font-style: italic;
#             color: #1e3a8a;
#             page-break-inside: avoid;
#         }

#         /* Code blocks */
#         pre {
#             background-color: #f8f9fa;
#             border: 1px solid #dee2e6;
#             border-radius: 4px;
#             padding: 12pt;
#             margin: 12pt 0;
#             overflow-x: auto;
#             font-family: 'Courier New', monospace;
#             font-size: 9pt;
#             line-height: 1.4;
#             page-break-inside: avoid;
#         }

#         code {
#             background-color: #f1f5f9;
#             padding: 2pt 4pt;
#             border-radius: 3px;
#             font-family: 'Courier New', monospace;
#             font-size: 9pt;
#             color: #dc2626;
#         }

#         /* Horizontal rules */
#         hr {
#             border: none;
#             border-top: 1px solid #d1d5db;
#             margin: 20pt 0;
#         }

#         /* Links */
#         a {
#             color: #2563eb;
#             text-decoration: none;
#         }

#         a:hover {
#             text-decoration: underline;
#         }

#         /* Risk level badges (emojis) */
#         .risk-high {
#             color: #dc2626;
#             font-weight: 600;
#         }

#         .risk-medium {
#             color: #f59e0b;
#             font-weight: 600;
#         }

#         .risk-low {
#             color: #3b82f6;
#             font-weight: 600;
#         }

#         .risk-acceptable {
#             color: #10b981;
#             font-weight: 600;
#         }

#         /* Footer */
#         .footer {
#             position: fixed;
#             bottom: 0;
#             left: 0;
#             right: 0;
#             text-align: center;
#             font-size: 8pt;
#             color: #6b7280;
#             padding: 10pt;
#             border-top: 1px solid #e5e7eb;
#         }

#         .footer p {
#             margin: 2pt 0;
#         }

#         /* Page breaks */
#         .page-break {
#             page-break-after: always;
#         }

#         /* Avoid breaking inside these elements */
#         h1, h2, h3, h4, h5, h6 {
#             page-break-after: avoid;
#         }

#         table, figure, img {
#             page-break-inside: avoid;
#         }

#         /* Print optimizations */
#         @media print {
#             body {
#                 background: white;
#             }
            
#             a {
#                 color: #1e40af;
#             }
#         }
#         """

#     def _generate_pdf(self, html_content: str, output_path: Path):
#         """
#         Generate PDF from HTML using WeasyPrint.
#         """
#         try:
#             # Create HTML object
#             html = HTML(string=html_content, base_url=str(output_path.parent))

#             # Generate PDF with custom CSS
#             html.write_pdf(
#                 output_path,
#                 font_config=self.font_config,
#                 optimize_size=('fonts', 'images'),  # Optimize file size
#             )

#         except Exception as e:
#             logger.error(f"PDF generation failed: {e}")
#             raise

#     def batch_convert(self, markdown_dir: Path, output_dir: Path = None) -> list[Path]:
#         """
#         Convert all markdown files in a directory to PDFs.
        
#         Args:
#             markdown_dir: Directory containing markdown files
#             output_dir: Optional output directory. If None, uses same directory
            
#         Returns:
#             List of generated PDF paths
#         """
#         if output_dir is None:
#             output_dir = markdown_dir
#         else:
#             output_dir.mkdir(parents=True, exist_ok=True)

#         markdown_files = list(markdown_dir.glob("*.md"))
#         pdf_paths = []

#         logger.info(f"Converting {len(markdown_files)} markdown files to PDF...")

#         for md_file in markdown_files:
#             try:
#                 pdf_path = output_dir / md_file.with_suffix('.pdf').name
#                 self.markdown_to_pdf(md_file, pdf_path)
#                 pdf_paths.append(pdf_path)
#             except Exception as e:
#                 logger.error(f"Failed to convert {md_file.name}: {e}")

#         logger.success(f"Converted {len(pdf_paths)}/{len(markdown_files)} files")
#         return pdf_paths


# # Singleton
# pdf_generator = PDFGenerator()


"""
utils/pdf_generator.py - Professional PDF Report Generator
Converts markdown reports to clean, professional PDFs with proper formatting.
"""

from pathlib import Path
from datetime import datetime
from loguru import logger

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, pt
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak, Preformatted
    )
    from reportlab.platypus.flowables import HRFlowable
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not installed. PDF generation will be unavailable.")


# ---------------------------------------------------------------------------
# Colour palette (mirrors the original WeasyPrint CSS)
# ---------------------------------------------------------------------------
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


def _build_styles():
    """Return a dict of named ParagraphStyle objects."""
    base = getSampleStyleSheet()

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
        borderPadding=(0, 0, 8, 0),
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
    styles["InlineCode"] = ParagraphStyle(
        "InlineCode",
        fontName="Courier",
        fontSize=9,
        leading=13,
        textColor=RED_CODE,
        backColor=colors.HexColor("#f1f5f9"),
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
# Minimal Markdown → ReportLab flowables parser
# ---------------------------------------------------------------------------

class _MarkdownParser:
    """
    Lightweight parser that converts a markdown string into a list of
    ReportLab Flowable objects.  Handles the subset of Markdown used by
    contract-review reports: headings, paragraphs, bold/italic inline,
    unordered/ordered lists, blockquotes, fenced code blocks, inline code,
    horizontal rules, and GFM-style pipe tables.
    """

    def __init__(self, styles: dict):
        self.styles = styles

    def parse(self, markdown_text: str) -> list:
        flowables = []
        lines = markdown_text.splitlines()
        i = 0

        while i < len(lines):
            line = lines[i]

            # ── Fenced code block ──────────────────────────────────────────
            if line.strip().startswith("```"):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                code_text = "\n".join(code_lines)
                flowables.append(Preformatted(code_text, self.styles["Code"]))
                i += 1
                continue

            # ── Horizontal rule ────────────────────────────────────────────
            if line.strip() in ("---", "***", "___") and len(line.strip()) >= 3:
                flowables.append(Spacer(1, 6))
                flowables.append(HRFlowable(width="100%", thickness=1,
                                            color=GREY_BORDER))
                flowables.append(Spacer(1, 6))
                i += 1
                continue

            # ── Headings ───────────────────────────────────────────────────
            if line.startswith("# "):
                flowables.append(Paragraph(self._inline(line[2:].strip()),
                                           self.styles["H1"]))
                flowables.append(HRFlowable(width="100%", thickness=3,
                                            color=BLUE_MID, spaceAfter=10))
                i += 1
                continue
            if line.startswith("## "):
                flowables.append(Paragraph(self._inline(line[3:].strip()),
                                           self.styles["H2"]))
                i += 1
                continue
            if line.startswith("### "):
                flowables.append(Paragraph(self._inline(line[4:].strip()),
                                           self.styles["H3"]))
                i += 1
                continue

            # ── Blockquote ─────────────────────────────────────────────────
            if line.startswith("> "):
                bq_lines = []
                while i < len(lines) and lines[i].startswith("> "):
                    bq_lines.append(lines[i][2:])
                    i += 1
                text = " ".join(bq_lines)
                flowables.append(Paragraph(self._inline(text),
                                           self.styles["Blockquote"]))
                continue

            # ── Unordered list ─────────────────────────────────────────────
            if line.startswith(("- ", "* ", "+ ")):
                while i < len(lines) and lines[i].startswith(("- ", "* ", "+ ")):
                    item_text = lines[i][2:].strip()
                    flowables.append(Paragraph(
                        f"• {self._inline(item_text)}", self.styles["ListItem"]))
                    i += 1
                flowables.append(Spacer(1, 4))
                continue

            # ── Ordered list ───────────────────────────────────────────────
            import re
            ol_match = re.match(r"^(\d+)\.\s+(.*)", line)
            if ol_match:
                counter = 0
                while i < len(lines):
                    m = re.match(r"^(\d+)\.\s+(.*)", lines[i])
                    if not m:
                        break
                    counter += 1
                    flowables.append(Paragraph(
                        f"{m.group(1)}. {self._inline(m.group(2))}",
                        self.styles["ListItem"]))
                    i += 1
                flowables.append(Spacer(1, 4))
                continue

            # ── GFM pipe table ─────────────────────────────────────────────
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

            # ── Blank line ─────────────────────────────────────────────────
            if line.strip() == "":
                flowables.append(Spacer(1, 6))
                i += 1
                continue

            # ── Normal paragraph ───────────────────────────────────────────
            para_lines = []
            while i < len(lines) and lines[i].strip() != "" \
                    and not lines[i].startswith(("#", ">", "- ", "* ", "+ ", "```", "|")) \
                    and not re.match(r"^\d+\.\s", lines[i]):
                para_lines.append(lines[i])
                i += 1
            text = " ".join(para_lines).strip()
            if text:
                flowables.append(Paragraph(self._inline(text),
                                           self.styles["Normal"]))

        return flowables

    # ── Inline formatting ──────────────────────────────────────────────────

    def _inline(self, text: str) -> str:
        """
        Convert inline markdown (bold, italic, inline-code) to ReportLab
        XML tags understood by Paragraph.
        """
        import re

        # Escape existing XML special chars first (except we'll add our own tags)
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Bold+italic  ***text***
        text = re.sub(r"\*\*\*(.*?)\*\*\*",
                      r"<b><i>\1</i></b>", text)
        # Bold  **text**
        text = re.sub(r"\*\*(.*?)\*\*",
                      r"<b>\1</b>", text)
        # Italic  *text*  or _text_
        text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
        text = re.sub(r"_(.*?)_",   r"<i>\1</i>", text)
        # Inline code  `code`
        text = re.sub(r"`(.*?)`",
                      r'<font name="Courier" color="#dc2626" backColor="#f1f5f9">\1</font>',
                      text)
        # Strikethrough  ~~text~~
        text = re.sub(r"~~(.*?)~~", r"<strike>\1</strike>", text)

        return text

    # ── Table helper ───────────────────────────────────────────────────────

    def _parse_table(self, lines: list):
        """Parse GFM pipe-table lines into a ReportLab Table flowable."""
        import re

        def split_row(line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            return cells

        rows = []
        for line in lines:
            # Skip separator rows like |---|---|
            if re.match(r"^[\|\s\-:]+$", line):
                continue
            rows.append(split_row(line))

        if not rows:
            return None

        # Apply inline formatting to every cell
        data = []
        for r_idx, row in enumerate(rows):
            formatted = []
            for cell in row:
                style = self.styles["H3"] if r_idx == 0 else self.styles["Normal"]
                formatted.append(Paragraph(self._inline(cell), style))
            data.append(formatted)

        col_count = max(len(r) for r in data)
        # Pad short rows
        for row in data:
            while len(row) < col_count:
                row.append(Paragraph("", self.styles["Normal"]))

        page_width = A4[0] - 3 * cm   # approximate usable width
        col_width = page_width / col_count

        tbl = Table(data, colWidths=[col_width] * col_count, repeatRows=1)

        style_cmds = [
            ("BACKGROUND",  (0, 0), (-1, 0),  BLUE_DARK),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  WHITE),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0),  10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_ROW_ALT]),
            ("GRID",        (0, 0), (-1, -1), 0.5, GREY_BORDER),
            ("TOPPADDING",  (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
        ]
        tbl.setStyle(TableStyle(style_cmds))
        return tbl


# ---------------------------------------------------------------------------
# Footer canvas callback
# ---------------------------------------------------------------------------

def _footer_canvas(canvas, doc):
    """Draw page-number footer on every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY_LIGHT)

    footer_y = 1 * cm
    canvas.drawCentredString(
        A4[0] / 2,
        footer_y + 12,
        f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
    )
    canvas.drawCentredString(
        A4[0] / 2,
        footer_y,
        "Contract Review Agent - Confidential",
    )
    # Page number (top-right, matching original CSS @page rule)
    canvas.drawRightString(
        A4[0] - 1.5 * cm,
        A4[1] - 1 * cm,
        f"Page {doc.page}",
    )
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Main class  (same public API as the WeasyPrint version)
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
            output_path: Optional output path. If None, uses same name with .pdf extension

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
        """
        Generate PDF from markdown text using ReportLab.
        """
        try:
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                leftMargin=1.5 * cm,
                rightMargin=1.5 * cm,
                topMargin=2 * cm,
                bottomMargin=2.5 * cm,  # room for footer
                title="Contract Review Report",
                author="Contract Review Agent",
            )

            parser = _MarkdownParser(self._styles)
            flowables = parser.parse(markdown_text)

            doc.build(
                flowables,
                onFirstPage=_footer_canvas,
                onLaterPages=_footer_canvas,
            )

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise

    def batch_convert(self, markdown_dir: Path, output_dir: Path = None) -> list[Path]:
        """
        Convert all markdown files in a directory to PDFs.

        Args:
            markdown_dir: Directory containing markdown files
            output_dir: Optional output directory. If None, uses same directory

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