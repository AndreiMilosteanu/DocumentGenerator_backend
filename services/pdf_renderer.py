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
from services.template_manager import TemplateManager

# Initialize template manager
template_manager = TemplateManager()

logger = logging.getLogger("pdf_renderer")

async def get_document_files(document_id: str) -> List[dict]:
    """
    Get only directly uploaded files for a document that are in READY status.
    Excludes files uploaded via conversation (message-file endpoint) which have associated_message set.
    """
    try:
        # Need to import here to avoid circular import
        from models import Document, FileUpload, FileUploadStatus
        
        doc = await Document.get(id=document_id)
        files = await FileUpload.filter(
            document=doc,
            status=FileUploadStatus.READY,
            associated_message=None  # Only include files without associated messages (direct uploads)
        ).all()
        
        logger.info(f"Found {len(files)} directly uploaded files (excluding conversation files) for document {document_id}")
        return files
    except Exception as e:
        logger.error(f"Error getting document files: {e}")
        return []

async def get_cover_page_data(document_id: str) -> dict:
    """
    Get cover page data for a document
    """
    try:
        from models import Document, CoverPageData
        
        doc = await Document.get(id=document_id)
        cover_page = await CoverPageData.filter(document=doc).first()
        
        if cover_page and cover_page.data:
            return cover_page.data
        else:
            return {}
    except Exception as e:
        logger.error(f"Error getting cover page data: {e}")
        return {}

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
    Render a PDF for the document and append any directly uploaded files.
    Only includes files uploaded via /upload/{document_id}/file endpoint.
    Files uploaded via conversation (/upload/{document_id}/message-file) are excluded.
    Returns a BytesIO stream containing the merged PDF
    """
    try:
        # First, render the main document PDF
        try:
            main_pdf = await render_pdf(document_id, doc_data)
        except Exception as e:
            logger.error(f"Error rendering main PDF: {e}")
            # Return empty PDF on failure
            return BytesIO()
        
        # Get all uploaded files for this document
        files = await get_document_files(document_id)
        logger.info(f"get_document_files returned {len(files)} files for document {document_id}")
        
        # Check if we have files with binary data
        files_with_data = [f for f in files if hasattr(f, 'file_data') and f.file_data]
        logger.info(f"Found {len(files_with_data)} files with binary data out of {len(files)} total files")
        
        if not files_with_data:
            # Log details about why files were excluded
            for i, file in enumerate(files):
                has_attr = hasattr(file, 'file_data')
                has_data = file.file_data is not None if has_attr else False
                data_size = len(file.file_data) if has_data else 0
                logger.warning(f"File {i+1} ({file.original_filename}): has_file_data_attr={has_attr}, has_data={has_data}, size={data_size}")
            
            logger.warning("No attachments with data to append, returning the main PDF")
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
        # Return empty PDF on failure
        return BytesIO()

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

async def render_pdf(document_id: str, doc_data: dict) -> BytesIO:
    """
    Render a PDF document based on the topic and document data
    Returns a BytesIO stream containing the rendered PDF
    """
    try:
        # Log incoming data structure
        logger.debug(f"render_pdf called with doc_data keys: {list(doc_data.keys())}")
        
        # Extract the document-specific data if it's in the nested format
        if document_id in doc_data:
            document_data = doc_data[document_id]
            logger.debug(f"Found document data using document_id as key, keys: {list(document_data.keys())}")
        else:
            document_data = doc_data
            logger.debug(f"Using doc_data directly, keys: {list(document_data.keys())}")
            
        # Get topic and prepare data
        topic = document_data.get('_topic', '')
        if not topic:
            logger.error(f"No topic specified for document {document_id}")
            return BytesIO()
        
        logger.debug(f"Topic from document data: '{topic}'")
        
        # Log all section keys in document_data
        sections_in_data = [k for k in document_data.keys() if not k.startswith('_')]
        logger.debug(f"Section keys in document_data: {sections_in_data}")
        
        # Extract all section data directly
        # We'll use the existing structure from document_data which should already
        # have sections as keys with subsection data
        section_data = {}
        for section_item in DOCUMENT_STRUCTURE.get(topic, []):
            for section, subsections in section_item.items():
                logger.debug(f"Processing section '{section}' from structure")
                # Check if this section exists in document data
                if section in document_data and isinstance(document_data[section], dict):
                    # Copy the section data directly
                    section_data[section] = document_data[section]
                    logger.debug(f"Copied section data for '{section}' with {len(document_data[section])} subsections: {list(document_data[section].keys())}")
                else:
                    # Initialize empty dictionary for the section
                    section_data[section] = {}
                    logger.debug(f"Created empty section data for '{section}'")
        
        # Log what we found
        total_sections = 0
        total_subsections = 0
        for section, subsections in section_data.items():
            if subsections:
                total_sections += 1
                total_subsections += len(subsections)
                logger.debug(f"Section '{section}' has {len(subsections)} subsections: {list(subsections.keys())}")
        
        if total_subsections > 0:
            logger.info(f"Found data for {total_sections} sections and {total_subsections} subsections")
        else:
            logger.warning(f"No section data found for document {document_id}")
        
        # Get cover page data
        cover_page_data = await get_cover_page_data(document_id)
        if cover_page_data:
            logger.info(f"Found cover page data with {len(cover_page_data)} categories")
        else:
            logger.info("No cover page data found")
        
        # Use the template manager to render the appropriate template with cover page data
        html_content = await template_manager.render_template(topic, document_data, section_data, cover_page_data)
        
        # Determine wkhtmltopdf path with environment variable support
        wkhtml_path = None
        
        # First, check if WKHTMLTOPDF_PATH environment variable is set
        env_path = os.environ.get('WKHTMLTOPDF_PATH')
        if env_path and Path(env_path).exists():
            wkhtml_path = env_path
            logger.debug(f"Using wkhtmltopdf from environment variable: {wkhtml_path}")
        else:
            # Fall back to settings
            settings_path = getattr(settings, 'WKHTMLTOPDF_PATH', None)
            if settings_path and Path(str(settings_path)).exists():
                wkhtml_path = str(settings_path)
                logger.debug(f"Using wkhtmltopdf from settings: {wkhtml_path}")
            else:
                # Try common system paths
                common_paths = [
                    "/usr/bin/wkhtmltopdf",  # Most common on Linux
                    "/usr/local/bin/wkhtmltopdf",  # Alternative Linux path
                    "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",  # Windows
                ]
                
                for path in common_paths:
                    if Path(path).exists():
                        wkhtml_path = path
                        logger.debug(f"Found wkhtmltopdf at system path: {wkhtml_path}")
                        break
                
                if not wkhtml_path:
                    # Last resort: assume it's in PATH
                    logger.warning("wkhtmltopdf path not found, assuming it's in system PATH")
        
        # Configure PDF options with robust settings for consistent rendering
        options = {
            'page-size': 'A4',
            'margin-top': '20mm',
            'margin-right': '20mm',
            'margin-bottom': '20mm',
            'margin-left': '20mm',
            'encoding': 'UTF-8',
            'footer-center': '[page] / [topage]',
            'footer-font-size': '9',
            'footer-spacing': '5',
            'quiet': '',
            'disable-smart-shrinking': '',  # Force exact rendering of contents
            'enable-local-file-access': '',  # Needed in some environments
            'print-media-type': '',  # Use print media CSS
            'page-offset': '0',  # Start page numbering at 1
            'no-pdf-compression': '',  # Disable compression for consistency
            'minimum-font-size': '8',  # Ensure minimum font size
            'dpi': '300',  # High DPI for consistent rendering
            'image-dpi': '300',  # High DPI for images
            'image-quality': '100',  # Maximum image quality
            'load-error-handling': 'ignore',  # Handle missing resources gracefully
            'load-media-error-handling': 'ignore',  # Handle missing media gracefully
            'disable-javascript': '',  # Disable JS for consistent rendering
            'no-stop-slow-scripts': '',  # Don't stop on slow scripts
            'debug-javascript': '',  # Enable JS debugging if needed
            'viewport-size': '1024x768',  # Set consistent viewport
            'zoom': '1.0',  # Ensure 1:1 zoom ratio
        }
        
        # Log the configuration being used
        logger.info(f"Rendering PDF with wkhtmltopdf path: {wkhtml_path or 'system PATH'}")
        
        # Render PDF using wkhtmltopdf
        pdf_data = pdfkit.from_string(
            html_content, 
            False, 
            options=options,
            configuration=pdfkit.configuration(wkhtmltopdf=wkhtml_path) if wkhtml_path else None
        )
        
        return BytesIO(pdf_data)
        
    except Exception as e:
        logger.error(f"Error rendering PDF for document {document_id}: {e}")
        raise