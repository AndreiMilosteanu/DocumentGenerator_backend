from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from io import BytesIO
import pdfkit
import logging
from config import settings
from templates.structure import DOCUMENT_STRUCTURE
import json
from datetime import datetime

# Initialize Jinja2 environment
templates_dir = Path(__file__).parent.parent / "templates"
env = Environment(
    loader=FileSystemLoader(str(templates_dir)),
    autoescape=select_autoescape(["html", "xml"])
)

# Add custom filters
def safe_str(value):
    """Safely convert any value to string, including datetime objects"""
    if isinstance(value, datetime):
        return value.isoformat()
    elif value is None:
        return ""
    else:
        return str(value)

env.filters['safe_str'] = safe_str

logger = logging.getLogger("pdf_renderer")

def render_pdf(document_id: str, doc_data: dict) -> BytesIO:
    """
    Render a PDF for the given document_id using the populated doc_data mapping.
    Uses wkhtmltopdf via pdfkit. Requires WKHTMLTOPDF_PATH in settings.
    Returns a BytesIO stream containing the PDF.
    
    The doc_data format is:
    {
        document_id: {
            "_topic": "TopicName",
            "_section_idx": 3,  # Number of sections with data
            "Section Name": {
                "Subsection1": "Value1",
                "Subsection2": "Value2"
            }
        }
    }
    """
    try:
        # 1. Validate and extract topic
        entry = doc_data.get(document_id)
        if not entry:
            raise ValueError(f"No data found for document_id '{document_id}'")
        
        logger.debug(f"Generating PDF for document {document_id}, entry keys: {list(entry.keys())}")
        
        topic = entry.get('_topic')
        if topic not in DOCUMENT_STRUCTURE:
            raise ValueError(f"Unknown topic: {topic}")
        sections = DOCUMENT_STRUCTURE[topic]

        # 2. Build structure for template
        structure = []  # List of dicts: {title, subsections, values}
        for sec in sections:
            title = list(sec.keys())[0]
            subsections = sec[title]
            
            # Debug: Log section and subsections
            logger.debug(f"Processing section '{title}' with subsections: {subsections}")
            
            # Get values for this section, handling both regular dicts and JSON objects
            values = entry.get(title, {}) or {}
            
            # Debug: Check values type
            logger.debug(f"Values for section '{title}' is type {type(values)}: {values}")
            
            # Ensure values is a dict
            if not isinstance(values, dict):
                logger.warning(f"Values for section '{title}' is not a dict, got {type(values)}. Converting to empty dict.")
                values = {}
            
            # Check if we have any data for this section
            if not values and title != 'Anhänge' and title != 'Deckblatt':  # Anhänge (attachments) and Deckblatt might be empty
                logger.warning(f"Section '{title}' has no data for document {document_id}")
                # Add section with empty values
                structure.append({
                    'title': title,
                    'subsections': subsections,
                    'content': {subsec: "" for subsec in subsections},
                    'has_data': False,
                    'is_empty': True
                })
                continue
            
            # For sections with data, only include subsections that have values
            subsection_data = {}
            has_data = False
            
            for subsec in subsections:
                # Get the value for this subsection
                value = values.get(subsec, '')
                if value is None:
                    value = ''
                
                # Debug: Log subsection values
                logger.debug(f"Subsection '{subsec}' has value of type {type(value)}")
                
                # Ensure value is a string
                if not isinstance(value, str):
                    logger.warning(f"Value for subsection '{subsec}' is not a string, got {type(value)}. Converting to string.")
                    value = str(value)
                
                # Include all subsections, even empty ones
                subsection_data[subsec] = value
                if value and value.strip():  # Check if any have actual content
                    has_data = True
            
            structure.append({
                'title': title,
                'subsections': subsections,
                'content': subsection_data,
                'has_data': has_data,
                'is_empty': not has_data
            })
            
        logger.debug(f"Built structure with {len(structure)} sections")
        
        # Debug: Dump the complete structure data for inspection
        logger.debug(f"Template structure: {json.dumps(structure, indent=2, default=str)}")

        # 3. Render HTML using Jinja2
        template = env.get_template('doc.html')
        html_content = template.render(
            title=topic,
            structure=structure,
            document_id=document_id,
            is_initial=not any(sec.get('has_data', False) for sec in structure)
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
        pdf_options = {
            'page-size': 'A4',
            'margin-top': '20mm',
            'margin-right': '20mm',
            'margin-bottom': '20mm',
            'margin-left': '20mm',
            'encoding': 'UTF-8',
            'no-outline': None,
            'quiet': ''
        }
        pdf_bytes = pdfkit.from_string(html_content, False, configuration=config, options=pdf_options)
        pdf_io = BytesIO(pdf_bytes)
        pdf_io.seek(0)
        logger.debug(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
        return pdf_io
        
    except Exception as e:
        logger.error(f"Error generating PDF for document {document_id}: {str(e)}")
        logger.exception("PDF generation exception")
        raise