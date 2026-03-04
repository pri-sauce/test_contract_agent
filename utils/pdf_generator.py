"""
utils/pdf_generator.py - Professional PDF Report Generator
Converts markdown reports to clean, professional PDFs with proper formatting.
"""

from pathlib import Path
from datetime import datetime
from loguru import logger

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("WeasyPrint not installed. PDF generation will be unavailable.")


class PDFGenerator:
    """
    Generates professional PDF reports from markdown.
    Uses WeasyPrint for high-quality PDF rendering with custom styling.
    """

    def __init__(self):
        self.font_config = FontConfiguration() if WEASYPRINT_AVAILABLE else None

    def markdown_to_pdf(self, markdown_path: Path, output_path: Path = None) -> Path:
        """
        Convert a markdown file to a professional PDF.
        
        Args:
            markdown_path: Path to the markdown file
            output_path: Optional output path. If None, uses same name with .pdf extension
            
        Returns:
            Path to the generated PDF
        """
        if not WEASYPRINT_AVAILABLE:
            raise ImportError(
                "WeasyPrint is required for PDF generation. "
                "Install it with: pip install weasyprint"
            )

        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        # Determine output path
        if output_path is None:
            output_path = markdown_path.with_suffix('.pdf')

        logger.info(f"Converting {markdown_path.name} to PDF...")

        # Read markdown content
        markdown_content = markdown_path.read_text(encoding='utf-8')

        # Convert markdown to HTML
        html_content = self._markdown_to_html(markdown_content)

        # Generate PDF with custom styling
        self._generate_pdf(html_content, output_path)

        logger.success(f"PDF generated: {output_path}")
        return output_path

    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        Convert markdown to HTML with proper structure.
        Uses markdown library for conversion.
        """
        try:
            import markdown
            from markdown.extensions.tables import TableExtension
            from markdown.extensions.fenced_code import FencedCodeExtension
            from markdown.extensions.codehilite import CodeHiliteExtension
        except ImportError:
            raise ImportError(
                "markdown library is required. "
                "Install it with: pip install markdown"
            )

        # Convert markdown to HTML with extensions
        md = markdown.Markdown(extensions=[
            TableExtension(),
            FencedCodeExtension(),
            CodeHiliteExtension(),
            'nl2br',  # Newline to <br>
            'sane_lists',  # Better list handling
        ])

        body_html = md.convert(markdown_text)

        # Wrap in full HTML document with professional styling
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contract Review Report</title>
    <style>
        {self._get_css_styles()}
    </style>
</head>
<body>
    <div class="container">
        {body_html}
    </div>
    <div class="footer">
        <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
        <p>Contract Review Agent - Confidential</p>
    </div>
</body>
</html>
"""
        return html

    def _get_css_styles(self) -> str:
        """
        Professional CSS styling for the PDF report.
        Clean, readable, and print-optimized.
        """
        return """
        @page {
            size: A4;
            margin: 2cm 1.5cm;
            @top-right {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            background: white;
        }

        .container {
            max-width: 100%;
            padding: 0;
        }

        /* Headings */
        h1 {
            font-size: 24pt;
            font-weight: 700;
            color: #1a1a1a;
            margin-bottom: 20pt;
            padding-bottom: 10pt;
            border-bottom: 3px solid #2563eb;
            page-break-after: avoid;
        }

        h2 {
            font-size: 18pt;
            font-weight: 600;
            color: #1e40af;
            margin-top: 24pt;
            margin-bottom: 12pt;
            page-break-after: avoid;
        }

        h3 {
            font-size: 14pt;
            font-weight: 600;
            color: #1e3a8a;
            margin-top: 16pt;
            margin-bottom: 8pt;
            page-break-after: avoid;
        }

        /* Paragraphs */
        p {
            margin-bottom: 8pt;
            text-align: justify;
        }

        /* Strong/Bold */
        strong {
            font-weight: 600;
            color: #1a1a1a;
        }

        /* Emphasis/Italic */
        em {
            font-style: italic;
            color: #4b5563;
        }

        /* Lists */
        ul, ol {
            margin-left: 20pt;
            margin-bottom: 12pt;
        }

        li {
            margin-bottom: 4pt;
        }

        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 16pt 0;
            font-size: 10pt;
            page-break-inside: avoid;
        }

        thead {
            background-color: #1e40af;
            color: white;
        }

        th {
            padding: 8pt;
            text-align: left;
            font-weight: 600;
            border: 1px solid #1e40af;
        }

        td {
            padding: 6pt 8pt;
            border: 1px solid #d1d5db;
        }

        tbody tr:nth-child(even) {
            background-color: #f9fafb;
        }

        tbody tr:hover {
            background-color: #f3f4f6;
        }

        /* Blockquotes */
        blockquote {
            margin: 12pt 0;
            padding: 10pt 15pt;
            background-color: #f0f9ff;
            border-left: 4px solid #3b82f6;
            font-style: italic;
            color: #1e3a8a;
            page-break-inside: avoid;
        }

        /* Code blocks */
        pre {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 12pt;
            margin: 12pt 0;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
            font-size: 9pt;
            line-height: 1.4;
            page-break-inside: avoid;
        }

        code {
            background-color: #f1f5f9;
            padding: 2pt 4pt;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 9pt;
            color: #dc2626;
        }

        /* Horizontal rules */
        hr {
            border: none;
            border-top: 1px solid #d1d5db;
            margin: 20pt 0;
        }

        /* Links */
        a {
            color: #2563eb;
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        /* Risk level badges (emojis) */
        .risk-high {
            color: #dc2626;
            font-weight: 600;
        }

        .risk-medium {
            color: #f59e0b;
            font-weight: 600;
        }

        .risk-low {
            color: #3b82f6;
            font-weight: 600;
        }

        .risk-acceptable {
            color: #10b981;
            font-weight: 600;
        }

        /* Footer */
        .footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 8pt;
            color: #6b7280;
            padding: 10pt;
            border-top: 1px solid #e5e7eb;
        }

        .footer p {
            margin: 2pt 0;
        }

        /* Page breaks */
        .page-break {
            page-break-after: always;
        }

        /* Avoid breaking inside these elements */
        h1, h2, h3, h4, h5, h6 {
            page-break-after: avoid;
        }

        table, figure, img {
            page-break-inside: avoid;
        }

        /* Print optimizations */
        @media print {
            body {
                background: white;
            }
            
            a {
                color: #1e40af;
            }
        }
        """

    def _generate_pdf(self, html_content: str, output_path: Path):
        """
        Generate PDF from HTML using WeasyPrint.
        """
        try:
            # Create HTML object
            html = HTML(string=html_content, base_url=str(output_path.parent))

            # Generate PDF with custom CSS
            html.write_pdf(
                output_path,
                font_config=self.font_config,
                optimize_size=('fonts', 'images'),  # Optimize file size
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
                pdf_path = output_dir / md_file.with_suffix('.pdf').name
                self.markdown_to_pdf(md_file, pdf_path)
                pdf_paths.append(pdf_path)
            except Exception as e:
                logger.error(f"Failed to convert {md_file.name}: {e}")

        logger.success(f"Converted {len(pdf_paths)}/{len(markdown_files)} files")
        return pdf_paths


# Singleton
pdf_generator = PDFGenerator()
