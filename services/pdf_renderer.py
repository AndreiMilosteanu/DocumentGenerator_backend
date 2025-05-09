from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from io import BytesIO
import pdfkit
import logging
from config import settings
from templates.structure import DOCUMENT_STRUCTURE

# Initialize Jinja2 environment
templates_dir = Path(__file__).parent.parent / "templates"
env = Environment(
    loader=FileSystemLoader(str(templates_dir)),
    autoescape=select_autoescape(["html", "xml"])
)

logger = logging.getLogger("pdf_renderer")

def render_pdf(document_id: str, doc_data: dict) -> BytesIO:
    """
    Render a PDF for the given document_id using the populated doc_data mapping.
    Uses wkhtmltopdf via pdfkit. Requires WKHTMLTOPDF_PATH in settings.
    Returns a BytesIO stream containing the PDF.
    """
    try:
        # 1. Validate and extract topic
        entry = doc_data.get(document_id)
        if not entry:
            raise ValueError(f"No data found for document_id '{document_id}'")
        
        logger.debug(f"Generating PDF for document {document_id}, entry: {entry.keys()}")
        
        topic = entry.get('_topic')
        if topic not in DOCUMENT_STRUCTURE:
            raise ValueError(f"Unknown topic: {topic}")
        sections = DOCUMENT_STRUCTURE[topic]

        # 2. Build structure for template
        structure = []  # List of dicts: {title, subsections, values}
        for sec in sections:
            title = list(sec.keys())[0]
            subsections = sec[title]
            
            # Get values for this section, handling both regular dicts and JSON objects
            values = entry.get(title, {}) or {}
            
            # Log warnings if expected sections are missing
            if not values and title != 'Anhänge':  # Anhänge (attachments) might be empty
                logger.warning(f"Section '{title}' has no data for document {document_id}")
                
            structure.append({
                'title': title,
                'subsections': subsections,
                'values': values
            })
            
        logger.debug(f"Built structure with {len(structure)} sections")

        # 3. Render HTML using Jinja2
        template = env.get_template('doc.html')
        html_content = template.render(
            title=topic,
            structure=structure
        )
        logger.debug(f"HTML content generated, length: {len(html_content)}")

        # 4. Configure wkhtmltopdf
        wkhtml_path = getattr(settings, 'WKHTMLTOPDF_PATH', None)
        wkhtml_path = str(wkhtml_path) if wkhtml_path is not None else None
        if not wkhtml_path:
            wkhtml_path = "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
        if not wkhtml_path or not Path(wkhtml_path).exists():
            raise RuntimeError(
                "wkhtmltopdf executable not found. "
                "Please install wkhtmltopdf and set WKHTMLTOPDF_PATH in your .env to its full path."
            )
        config = pdfkit.configuration(wkhtmltopdf=wkhtml_path)
        logger.debug(f"Using wkhtmltopdf path: {wkhtml_path}")

        # 5. Convert HTML to PDF (returns bytes)
        pdf_bytes = pdfkit.from_string(html_content, False, configuration=config)
        pdf_io = BytesIO(pdf_bytes)
        pdf_io.seek(0)
        logger.debug(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
        return pdf_io
        
    except Exception as e:
        logger.error(f"Error generating PDF for document {document_id}: {str(e)}")
        raise