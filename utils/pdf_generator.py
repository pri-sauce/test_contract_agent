"""
utils/pdf_generator.py - Professional PDF Report Generator
Converts markdown reports to PDFs using reportlab.

Install: pip install reportlab markdown
"""

from pathlib import Path
from datetime import datetime
import re

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
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak,
        Table, TableStyle, ListFlowable, ListItem
    )
    from reportlab.lib import colors
    import markdown
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    logger.warning("Run: pip install reportlab markdown")


class PDFGenerator:
    """
    Generates professional PDF reports from markdown.
    Requires: pip install reportlab markdown
    """

    def __init__(self):
        if AVAILABLE:
            self.styles = getSampleStyleSheet()
            # Add custom styles
            self.styles.add(ParagraphStyle(
                name='CodeBlock',
                parent=self.styles['Code'],
                fontName='Courier',
                fontSize=9,
                leftIndent=20,
                rightIndent=20,
                spaceBefore=6,
                spaceAfter=6,
                backColor=colors.HexColor('#f4f4f4'),
            ))

    def _parse_markdown(self, md_text: str) -> list:
        """Convert markdown to reportlab flowables"""
        story = []
        
        # Simple parsing - split by lines and handle basic formatting
        lines = md_text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].rstrip()
            
            # Skip empty lines
            if not line:
                story.append(Spacer(1, 6))
                i += 1
                continue
            
            # Headers
            if line.startswith('# '):
                story.append(Paragraph(line[2:], self.styles['Title']))
                story.append(Spacer(1, 12))
            elif line.startswith('## '):
                story.append(Paragraph(line[3:], self.styles['Heading1']))
                story.append(Spacer(1, 6))
            elif line.startswith('### '):
                story.append(Paragraph(line[4:], self.styles['Heading2']))
                story.append(Spacer(1, 6))
            elif line.startswith('#### '):
                story.append(Paragraph(line[5:], self.styles['Heading3']))
                story.append(Spacer(1, 6))
            
            # Code blocks
            elif line.startswith('```'):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                code_text = '\n'.join(code_lines)
                # Escape XML special chars
                code_text = code_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(f'<pre>{code_text}</pre>', self.styles['CodeBlock']))
                story.append(Spacer(1, 6))
            
            # Lists
            elif line.startswith('- ') or line.startswith('* '):
                list_items = []
                while i < len(lines) and (lines[i].startswith('- ') or lines[i].startswith('* ')):
                    item_text = lines[i][2:].strip()
                    list_items.append(ListItem(Paragraph(item_text, self.styles['Normal'])))
                    i += 1
                story.append(ListFlowable(list_items, bulletType='bullet'))
                story.append(Spacer(1, 6))
                i -= 1  # Back up one since we'll increment at end
            
            # Numbered lists
            elif re.match(r'^\d+\. ', line):
                list_items = []
                while i < len(lines) and re.match(r'^\d+\. ', lines[i]):
                    item_text = re.sub(r'^\d+\. ', '', lines[i]).strip()
                    list_items.append(ListItem(Paragraph(item_text, self.styles['Normal'])))
                    i += 1
                story.append(ListFlowable(list_items, bulletType='1'))
                story.append(Spacer(1, 6))
                i -= 1
            
            # Horizontal rule
            elif line.strip() in ['---', '***', '___']:
                story.append(Spacer(1, 6))
                story.append(Table([['']], colWidths=[6*inch], style=[
                    ('LINEABOVE', (0,0), (-1,0), 1, colors.grey)
                ]))
                story.append(Spacer(1, 6))
            
            # Bold and italic formatting
            else:
                # Convert markdown formatting to reportlab tags
                text = line
                # Bold: **text** or __text__ -> <b>text</b>
                text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
                text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
                # Italic: *text* or _text_ -> <i>text</i>
                text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
                text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
                # Inline code: `text` -> <font name="Courier">text</font>
                text = re.sub(r'`(.+?)`', r'<font name="Courier" size="9">\1</font>', text)
                
                story.append(Paragraph(text, self.styles['Normal']))
                story.append(Spacer(1, 6))
            
            i += 1
        
        return story

    def markdown_to_pdf(self, markdown_path: Path, output_path: Path = None, 
                       pagesize=letter, title: str = None) -> Path:
        """
        Convert markdown file to PDF.
        
        Args:
            markdown_path: Path to markdown file
            output_path: Output PDF path (default: same name with .pdf extension)
            pagesize: Page size (letter or A4)
            title: PDF title metadata (default: derived from filename)
        
        Returns:
            Path to generated PDF
        """
        if not AVAILABLE:
            raise ImportError("Run: pip install reportlab markdown")
        if not markdown_path.exists():
            raise FileNotFoundError(f"Not found: {markdown_path}")
        if output_path is None:
            output_path = markdown_path.with_suffix(".pdf")

        logger.info(f"Converting {markdown_path.name} to PDF...")

        # Read markdown
        md_text = markdown_path.read_text(encoding="utf-8")

        # Create PDF
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=pagesize,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        # Set metadata
        if title is None:
            title = markdown_path.stem.replace("_", " ").replace("-", " ").title()
        doc.title = title
        doc.author = "PDF Generator"
        doc.subject = "Generated from Markdown"

        # Parse markdown and build PDF
        story = self._parse_markdown(md_text)
        doc.build(story)

        logger.success(f"PDF generated: {output_path}")
        return output_path

    def batch_convert(self, markdown_dir: Path, output_dir: Path = None) -> list[Path]:
        """
        Convert all markdown files in a directory to PDFs.
        
        Args:
            markdown_dir: Directory containing .md files
            output_dir: Output directory (default: same as input)
        
        Returns:
            List of generated PDF paths
        """
        if output_dir is None:
            output_dir = markdown_dir
        else:
            output_dir.mkdir(parents=True, exist_ok=True)

        files = list(markdown_dir.glob("*.md"))
        results = []
        logger.info(f"Converting {len(files)} markdown files to PDF...")
        for f in files:
            try:
                out_path = output_dir / f.with_suffix(".pdf").name
                results.append(self.markdown_to_pdf(f, out_path))
            except Exception as e:
                logger.error(f"Failed {f.name}: {e}")
        logger.success(f"Converted {len(results)}/{len(files)} files")
        return results


# Singleton
pdf_generator = PDFGenerator()