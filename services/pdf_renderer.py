from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from io import BytesIO
import pdfkit
import logging
from config import settings
from templates.structure import DOCUMENT_STRUCTURE
import json
from datetime import datetime
import PyPDF2
import tempfile
import os
from typing import List, Dict, Any, Optional
import subprocess
import sys
import uuid

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

async def get_document_files(document_id: str) -> List[dict]:
    """
    Get all uploaded files for a document that are in READY status
    """
    try:
        # Need to import here to avoid circular import
        from models import Document, FileUpload, FileUploadStatus
        
        doc = await Document.get(id=document_id)
        files = await FileUpload.filter(
            document=doc,
            status=FileUploadStatus.READY
        ).all()
        
        return files
    except Exception as e:
        logger.error(f"Error getting document files: {e}")
        return []

def convert_to_pdf(input_file: bytes, file_type: str, output_path: str) -> bool:
    """
    Convert non-PDF files to PDF format when possible
    Currently handles: DOCX, TXT, CSV, JSON
    Returns True if conversion was successful
    """
    try:
        # Save input to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as temp:
            temp.write(input_file)
            temp_path = temp.name
            
        # Select conversion method based on file type
        if file_type == "docx":
            # For Word documents, use LibreOffice if available
            libreoffice_paths = [
                "C:\\Program Files\\LibreOffice\\program\\soffice.exe",  # Windows
                "/usr/bin/libreoffice",  # Linux
                "/Applications/LibreOffice.app/Contents/MacOS/soffice"  # macOS
            ]
            
            executable = None
            for path in libreoffice_paths:
                if os.path.exists(path):
                    executable = path
                    break
                    
            if executable:
                subprocess.run([
                    executable,
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", os.path.dirname(output_path),
                    temp_path
                ], check=True)
                
                # Rename the output file to match our expected path
                temp_pdf = f"{os.path.splitext(temp_path)[0]}.pdf"
                if os.path.exists(temp_pdf):
                    os.rename(temp_pdf, output_path)
                    return True
            return False
            
        elif file_type in ["txt", "csv", "json"]:
            # For text files, use wkhtmltopdf
            wkhtml_path = getattr(settings, 'WKHTMLTOPDF_PATH', None)
            wkhtml_path = str(wkhtml_path) if wkhtml_path is not None else None
            if not wkhtml_path:
                wkhtml_path = "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
            if not wkhtml_path or not Path(wkhtml_path).exists():
                return False
                
            # Create a simple HTML file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as html_temp:
                try:
                    content = input_file.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        content = input_file.decode('latin-1')
                    except:
                        content = "[Binary content]"
                
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Converted Document</title>
                    <style>
                        body {{ font-family: monospace; white-space: pre-wrap; }}
                    </style>
                </head>
                <body>
                    {content}
                </body>
                </html>
                """
                html_temp.write(html_content.encode('utf-8'))
                html_path = html_temp.name
            
            # Convert HTML to PDF
            subprocess.run([
                wkhtml_path,
                html_path,
                output_path
            ], check=True)
            
            os.unlink(html_path)
            return os.path.exists(output_path)
        
        return False
    except Exception as e:
        logger.error(f"Error converting file to PDF: {e}")
        return False
    finally:
        # Clean up temp file
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass

def merge_pdfs(main_pdf_path: str, additional_pdfs: List[str], output_path: str) -> bool:
    """
    Merge multiple PDF files into one
    Returns True if successful
    """
    try:
        merger = PyPDF2.PdfMerger()
        
        # Add the main PDF
        merger.append(main_pdf_path)
        
        # Add all additional PDFs
        for pdf in additional_pdfs:
            if os.path.exists(pdf):
                merger.append(pdf)
        
        # Write the merged PDF
        merger.write(output_path)
        merger.close()
        return True
    except Exception as e:
        logger.error(f"Error merging PDFs: {e}")
        return False

async def render_pdf_with_attachments(document_id: str, doc_data: dict) -> BytesIO:
    """
    Render a PDF for the document and append any uploaded files
    Returns a BytesIO stream containing the merged PDF
    """
    try:
        # First, render the main document PDF
        main_pdf = render_pdf(document_id, doc_data)
        
        # Get all uploaded files for this document
        files = await get_document_files(document_id)
        
        # Check if we have files with binary data
        files_with_data = [f for f in files if hasattr(f, 'file_data') and f.file_data]
        
        if not files_with_data:
            # No attachments with data to append, return the main PDF
            return main_pdf
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as main_temp:
            main_temp.write(main_pdf.getvalue())
            main_pdf_path = main_temp.name
        
        output_pdf_path = f"{main_pdf_path}_merged.pdf"
        additional_pdfs = []
        temp_files = []
        
        try:
            # Process each file
            for file in files_with_data:
                if not file.file_data:
                    continue
                
                file_ext = os.path.splitext(file.original_filename)[1].lower().lstrip('.')
                
                if file_ext == 'pdf':
                    # For PDF files, add directly
                    temp_path = f"{tempfile.gettempdir()}/{uuid.uuid4()}.pdf"
                    with open(temp_path, 'wb') as f:
                        f.write(file.file_data)
                    additional_pdfs.append(temp_path)
                    temp_files.append(temp_path)
                else:
                    # For non-PDF files, try to convert
                    temp_path = f"{tempfile.gettempdir()}/{uuid.uuid4()}.pdf"
                    if convert_to_pdf(file.file_data, file_ext, temp_path):
                        additional_pdfs.append(temp_path)
                        temp_files.append(temp_path)
            
            # Merge all PDFs
            if additional_pdfs:
                if merge_pdfs(main_pdf_path, additional_pdfs, output_pdf_path):
                    # Read the merged PDF
                    with open(output_pdf_path, 'rb') as f:
                        merged_pdf = BytesIO(f.read())
                    return merged_pdf
            
            # If anything fails, return the original PDF
            return main_pdf
            
        finally:
            # Clean up temporary files
            for path in temp_files + [main_pdf_path, output_pdf_path]:
                if os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
    
    except Exception as e:
        logger.error(f"Error rendering PDF with attachments: {e}")
        # Return the original PDF if anything fails
        return main_pdf

def format_dict_string(dict_str: str) -> str:
    """
    Format a dictionary-like string into a readable format.
    Works with strings that may not be valid Python syntax but look like dictionaries.
    Returns a string with each key-value pair on a new line.
    """
    try:
        # Remove outer quotes and braces
        cleaned = dict_str.strip()
        if cleaned.startswith("'") and cleaned.endswith("'"):
            cleaned = cleaned[1:-1]
        cleaned = cleaned.strip("{}").strip()
        
        # Simple case: no nested dicts
        if "': '" in cleaned:
            result = ""
            # Split pairs, handling possible commas in the values
            current_pair = ""
            in_quotes = False
            pairs = []
            
            for char in cleaned + ", ":  # Add a comma at the end for easier processing
                if char == "'" and (not current_pair.endswith("\\")):
                    in_quotes = not in_quotes
                
                current_pair += char
                
                if char == "," and not in_quotes and current_pair.count("'") % 2 == 0:
                    pairs.append(current_pair[:-1].strip())  # Remove the trailing comma
                    current_pair = ""
            
            # Process each key-value pair
            for pair in pairs:
                if "': '" in pair:
                    key, val = pair.split("': '", 1)
                    key = key.strip("'\" ")
                    val = val.strip("'\" ")
                    result += f"{key}: {val}\n"
            
            return result.rstrip("\n")
    except Exception as e:
        logger.warning(f"Failed to format dictionary string using custom parser: {str(e)}")
    
    # If all else fails, return the original string
    return dict_str

def fix_address_format(value):
    """
    Special case handler for the common pattern we're seeing in the logs:
    {'Adresse': 'Strada Preot Bacca 13, 550145 Hermannstadt'}
    
    This will extract just the 'Adresse: value' part.
    """
    if isinstance(value, str) and value.startswith("{'Adresse': '") and "'}":
        try:
            # Extract just the address value
            address = value.split("'Adresse': '")[1].split("'")[0]
            return f"Adresse: {address}"
        except Exception as e:
            logger.warning(f"Failed to parse address format: {str(e)}")
    return value

def process_raw_structure(structure):
    """
    Process the raw structure and directly fix any string values that look like dictionaries.
    This is a brute-force approach to handle the specific case seen in the logs.
    """
    for section in structure:
        content = section.get('content', {})
        for subsec, value in content.items():
            # Special case for address format
            fixed_value = fix_address_format(value)
            if fixed_value != value:
                content[subsec] = fixed_value
                logger.info(f"Fixed address format in {section['title']}.{subsec}")
                continue
                
            # General case for dictionary-like strings
            if isinstance(value, str) and value.startswith("{'") and value.endswith("'}"):
                logger.info(f"Direct fixing dictionary string in {section['title']}.{subsec}")
                # Remove outer quotes and braces
                inner_content = value[2:-2]  # Remove "{' and '}"
                parts = inner_content.split("', '")
                formatted = ""
                for part in parts:
                    if ": " in part:
                        key, val = part.split(": ", 1)
                        formatted += f"{key}: {val}\n"
                
                if formatted:
                    content[subsec] = formatted.strip()
                    logger.info(f"Successfully reformatted dictionary with direct approach")
    
    return structure

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
                
                # Format any string value that looks like a dictionary or list
                if isinstance(value, str):
                    stripped_value = value.strip()
                    
                    # Check if this looks like a dictionary string (has braces or quotes+colon pattern)
                    if (('{' in stripped_value and '}' in stripped_value) or 
                            ("': '" in stripped_value) or 
                            ("':" in stripped_value)):
                        
                        logger.debug(f"Processing potential dictionary string in {title}.{subsec}: {stripped_value[:100]}")
                        
                        # First try ast.literal_eval for clean parsing
                        try:
                            import ast
                            dict_value = ast.literal_eval(stripped_value)
                            if isinstance(dict_value, dict):
                                # Format dictionary into a readable string
                                formatted_value = ""
                                for key, val in dict_value.items():
                                    formatted_value += f"{key}: {val}\n"
                                value = formatted_value.rstrip("\n")  # Remove trailing newline
                                logger.info(f"Formatted dictionary using ast.literal_eval for {title}.{subsec}")
                            continue  # Skip other parsing attempts
                        except Exception as e:
                            logger.debug(f"ast.literal_eval failed: {str(e)}, trying custom parser")
                        
                        # If ast.literal_eval fails, try our custom parser
                        formatted = format_dict_string(stripped_value)
                        if formatted != stripped_value:
                            value = formatted
                            logger.info(f"Formatted dictionary using custom parser for {title}.{subsec}")
                    
                    # Check if it looks like a list string
                    elif stripped_value.startswith('[') and stripped_value.endswith(']'):
                        try:
                            # Try to evaluate it as a Python list
                            import ast
                            list_value = ast.literal_eval(stripped_value)
                            if isinstance(list_value, list):
                                # Format list into a bulleted list
                                formatted_value = ""
                                for item in list_value:
                                    formatted_value += f"• {item}\n"
                                value = formatted_value.rstrip("\n")  # Remove trailing newline
                                logger.info(f"Formatted string list value for {title}.{subsec}")
                        except Exception as e:
                            logger.warning(f"Failed to parse list string: {e}")
                
                # Debug: Log subsection values
                logger.debug(f"Subsection '{subsec}' final value of type {type(value)}")
                if value and isinstance(value, str) and len(value) > 0:
                    logger.debug(f"Value preview: {value[:50]}...")
                
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
        
        # Brute force fix for dictionary strings
        structure = process_raw_structure(structure)
        
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