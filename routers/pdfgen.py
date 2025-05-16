from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from io import BytesIO
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import logging
from tortoise.exceptions import DoesNotExist
from tortoise import Tortoise

from services.pdf_renderer import render_pdf
from models import Document, SectionData, ApprovedSubsection, User, Project
from templates.structure import DOCUMENT_STRUCTURE
from utils.auth import get_current_active_user, get_admin_user

# Configure logger
logger = logging.getLogger("pdfgen")
logger.setLevel(logging.DEBUG)

router = APIRouter()

class SubsectionApproval(BaseModel):
    section: str
    subsection: str
    value: str = ""  # Make value optional since it will be ignored and loaded from section_data

class SimpleSubsectionApproval(BaseModel):
    section: str
    subsection: str

class SubsectionApprovalResponse(BaseModel):
    document_id: str
    section: str
    subsection: str
    approved: bool

class SubsectionApprovalBatch(BaseModel):
    approvals: List[SubsectionApproval]

async def get_document_data(document_id: str, approved_only: bool = False) -> Dict[str, Any]:
    """
    Retrieves document data from the database and formats it for PDF generation.
    
    Parameters:
    - document_id: The ID of the document
    - approved_only: If True, only include subsections that have been explicitly approved
    """
    logger.debug(f"get_document_data called for document {document_id}, approved_only={approved_only}")
    try:
        # Get document record
        doc = await Document.get(id=document_id)
        logger.debug(f"Found document with topic '{doc.topic}'")
        
        # Format data in the structure expected by PDF generator
        pdf_data = {
            "_topic": doc.topic,
        }
        
        if approved_only:
            # Get only approved subsections
            approved = await ApprovedSubsection.filter(document=doc).all()
            logger.debug(f"Found {len(approved)} approved subsections")
            
            if not approved:
                logger.warning(f"No approved content found for document {document_id}")
                raise ValueError(f"No approved content found for document {document_id}")
            
            # Structure data from approved subsections
            sections_data = {}
            for item in approved:
                if item.section not in sections_data:
                    sections_data[item.section] = {}
                
                sections_data[item.section][item.subsection] = item.approved_value
                logger.debug(f"Added approved value for {item.section}.{item.subsection}")
            
            # Add all section data
            for section, data in sections_data.items():
                pdf_data[section] = data
            
            pdf_data["_section_idx"] = len(sections_data)  # Number of sections with approved content
            logger.debug(f"Prepared data with {len(sections_data)} sections from approved content")
        else:
            # Get all section data regardless of approval status
            sections = await SectionData.filter(document=doc).all()
            logger.debug(f"Found {len(sections)} section records")
            
            if not sections:
                logger.warning(f"No section data found for document {document_id}")
                raise ValueError(f"No section data found for document {document_id}")
            
            # Add all section data
            for section in sections:
                # Make sure data is a dictionary
                section_data = section.data
                if not isinstance(section_data, dict):
                    logger.warning(f"Section data for '{section.section}' is not a dict, got {type(section_data)}")
                    section_data = {}
                    
                pdf_data[section.section] = section_data
                logger.debug(f"Added section '{section.section}' with {len(section_data)} subsections")
                
            pdf_data["_section_idx"] = len(sections)  # Number of completed sections
            logger.debug(f"Prepared data with {len(sections)} sections from all section data")
            
        return pdf_data
    except DoesNotExist:
        logger.error(f"Document {document_id} not found")
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    except Exception as e:
        logger.error(f"Error retrieving document data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving document data: {str(e)}")

async def _check_document_access(document_id: str, user: User) -> Document:
    """
    Check if user has access to the document via a project.
    Admin users have access to all documents.
    Returns the document if access is allowed, otherwise raises HTTPException.
    """
    try:
        doc = await Document.get(id=document_id)
        
        # Admin users have access to all documents
        if user.role == "admin":
            return doc
            
        # For regular users, check if they have a project with this document
        project = await Project.filter(document_id=document_id, user=user).first()
        if not project:
            raise HTTPException(status_code=403, detail="Access denied to this document")
            
        return doc
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Document not found")

@router.post("/{document_id}/approve", response_model=SubsectionApprovalResponse)
async def approve_subsection(
    document_id: str, 
    approval: SubsectionApproval,
    current_user: User = Depends(get_current_active_user)
):
    """
    Approve a subsection's content for inclusion in the PDF.
    This endpoint will use the existing section_data value for the subsection,
    not the value passed in the request (which might be the human readable message).
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    try:
        # Validate section and subsection against document structure
        topic = doc.topic
        if topic not in DOCUMENT_STRUCTURE:
            raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
            
        section_valid = False
        subsection_valid = False
        
        for sec_obj in DOCUMENT_STRUCTURE[topic]:
            sec_name = list(sec_obj.keys())[0]
            if sec_name == approval.section:
                section_valid = True
                if approval.subsection in sec_obj[sec_name]:
                    subsection_valid = True
                    break
        
        if not section_valid:
            raise HTTPException(status_code=400, detail=f"Invalid section '{approval.section}' for topic '{topic}'")
        
        if not subsection_valid:
            raise HTTPException(status_code=400, detail=f"Invalid subsection '{approval.subsection}' for section '{approval.section}'")
        
        # Get the correct value from section_data
        section_data = await SectionData.filter(document=doc, section=approval.section).first()
        if not section_data:
            raise HTTPException(status_code=404, detail=f"No data found for section '{approval.section}'")
            
        data = section_data.data
        if approval.subsection not in data:
            raise HTTPException(status_code=404, detail=f"No data found for subsection '{approval.subsection}'")
            
        # Get the correct value from section_data, not from the request
        correct_value = data[approval.subsection]
        logger.debug(f"Using value from section_data for {approval.section}.{approval.subsection}: {correct_value[:50]}...")
        
        try:
            # Use a direct SQL query to avoid datetime issues
            conn = Tortoise.get_connection("default")
            
            # Check if record exists
            query = """
                SELECT id FROM approved_subsections 
                WHERE document_id = $1 AND section = $2 AND subsection = $3;
            """
            result = await conn.execute_query(query, [str(doc.id), approval.section, approval.subsection])
            
            if result[1]:  # Record exists
                # Update existing record
                update_query = """
                    UPDATE approved_subsections 
                    SET approved_value = $4 
                    WHERE document_id = $1 AND section = $2 AND subsection = $3;
                """
                await conn.execute_query(update_query, 
                                        [str(doc.id), approval.section, approval.subsection, correct_value])
                logger.debug(f"Updated approval for {approval.section}.{approval.subsection}")
            else:
                # Insert new record
                insert_query = """
                    INSERT INTO approved_subsections(document_id, section, subsection, approved_value)
                    VALUES($1, $2, $3, $4);
                """
                await conn.execute_query(insert_query, 
                                        [str(doc.id), approval.section, approval.subsection, correct_value])
                logger.debug(f"Created approval for {approval.section}.{approval.subsection}")
                
        except Exception as e:
            logger.exception(f"Database error during approval: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        # Return the result without approved_at field
        return {
            "document_id": document_id,
            "section": approval.section,
            "subsection": approval.subsection,
            "approved": True
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    except Exception as e:
        logger.exception(f"Error in approve_subsection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error approving subsection: {str(e)}")

@router.post("/{document_id}/approve-batch")
async def approve_subsection_batch(document_id: str, approvals: SubsectionApprovalBatch):
    """
    Approve multiple subsections at once for inclusion in the PDF.
    """
    results = []
    for approval in approvals.approvals:
        try:
            result = await approve_subsection(document_id, approval)
            results.append(result)
        except HTTPException as e:
            results.append({
                "document_id": document_id,
                "section": approval.section,
                "subsection": approval.subsection,
                "approved": False,
                "error": e.detail
            })
    
    return results

@router.get("/{document_id}/approved")
async def get_approved_subsections(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a list of all approved subsections for this document.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    try:
        # Use raw SQL query to avoid datetime issues
        conn = Tortoise.get_connection("default")
        query = """
            SELECT id, section, subsection, approved_value 
            FROM approved_subsections 
            WHERE document_id = $1;
        """
        result = await conn.execute_query(query, [str(doc.id)])
        
        # Format the results
        results = []
        for row in result[1]:
            results.append({
                "section": row[1],
                "subsection": row[2],
                "value": row[3]
            })
        
        return results
    except DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    except Exception as e:
        logger.exception(f"Error retrieving approved subsections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving approved subsections: {str(e)}")

@router.get("/{document_id}/pdf")
async def generate_pdf(
    document_id: str, 
    approved_only: bool = False, 
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a PDF from the document structure and content.
    If approved_only=true, then only show content that has been explicitly approved.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    logger.debug(f"PDF requested for document {document_id}, approved_only={approved_only}")
    
    # 1. Grab the collected data from database
    doc_data = {}
    try:
        logger.debug(f"Fetching document data for {document_id}")
        pdf_data = await get_document_data(document_id, approved_only=approved_only)
        logger.debug(f"Retrieved data with keys: {list(pdf_data.keys())}")
        doc_data[document_id] = pdf_data
    except HTTPException as e:
        logger.warning(f"Caught HTTPException while getting document data: {e.status_code} - {e.detail}")
        if e.status_code == 404:
            # Document not found, create a new one
            logger.error(f"Document {document_id} not found")
            raise e
        elif approved_only:
            # If we're looking for approved data but none exists, try with all data
            logger.info(f"No approved content found, falling back to all section data for {document_id}")
            try:
                pdf_data = await get_document_data(document_id, approved_only=False)
                doc_data[document_id] = pdf_data
                logger.debug(f"Retrieved fallback data with keys: {list(pdf_data.keys())}")
            except HTTPException as e2:
                logger.warning(f"Fallback also failed: {e2.status_code} - {e2.detail}")
                # If that also fails, create a minimal PDF with just the structure
                doc = await Document.get(id=document_id)
                doc_data[document_id] = {
                    "_topic": doc.topic,
                    "_section_idx": 0
                }
                logger.debug(f"Using minimal data structure for {document_id}")
        else:
            # For any other error, re-raise
            logger.error(f"Error fetching document data: {e.detail}")
            raise e

    # 2. Render the PDF
    try:
        logger.debug(f"Starting PDF rendering for document {document_id}")
        pdf_io: BytesIO = render_pdf(document_id, doc_data)
        
        # Store the PDF in the database
        logger.debug(f"PDF rendered successfully, saving to database")
        doc = await Document.get(id=document_id)
        doc.pdf_data = pdf_io.getvalue()
        await doc.save()
        
        # Reset BytesIO position for streaming
        pdf_io.seek(0)
        logger.debug(f"PDF generated and stored successfully for {document_id}")
    except Exception as e:
        logger.error(f"Error rendering PDF: {str(e)}")
        logger.exception("PDF rendering exception details")
        raise HTTPException(status_code=500, detail=str(e))

    # 3. Stream it back
    logger.debug(f"Streaming PDF response for {document_id}")
    return StreamingResponse(pdf_io, media_type="application/pdf")

@router.get("/{document_id}/download")
async def download_pdf(document_id: str, approved_only: bool = True):
    """
    Download a PDF with document content.
    
    Parameters:
    - approved_only: If True (default), only include subsections that have been explicitly approved
    """
    # Try to get PDF from database first
    try:
        doc = await Document.get(id=document_id)
        if doc.pdf_data:
            pdf_io = BytesIO(doc.pdf_data)
            response = StreamingResponse(pdf_io, media_type="application/pdf")
            response.headers["Content-Disposition"] = f"attachment; filename=doc_{document_id}.pdf"
            return response
    except DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
    # If not in DB, generate it
    response = await generate_pdf(document_id, approved_only=approved_only)
    response.headers["Content-Disposition"] = f"attachment; filename=doc_{document_id}.pdf"
    return response

@router.get("/{document_id}/current-data")
async def get_current_data(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current SectionData for a document.
    This is useful for showing what data could be approved.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    try:
        # Get all section data
        sections = await SectionData.filter(document=doc).all()
        
        # Structure the data
        result = {
            "topic": doc.topic,
            "sections": {}
        }
        
        for section in sections:
            result["sections"][section.section] = section.data
            
        return result
    except DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving section data: {str(e)}")

@router.get("/{document_id}/debug-approval")
async def debug_subsection_approval(document_id: str):
    """
    Debug endpoint to diagnose issues with the subsection approval process.
    """
    try:
        # Get document
        doc = await Document.get(id=document_id)
        
        # Get approved subsections with all their fields
        approved = await ApprovedSubsection.filter(document=doc).all()
        
        results = []
        for item in approved:
            # Convert to dict and handle datetime objects
            item_dict = {
                "id": item.id,
                "document_id": str(item.document_id),
                "section": item.section,
                "subsection": item.subsection,
                "approved_value": item.approved_value,
                "approved_at": str(item.approved_at) if item.approved_at else None,
                "approved_at_type": str(type(item.approved_at))
            }
            results.append(item_dict)
        
        return {
            "document_id": document_id,
            "topic": doc.topic,
            "approved_count": len(approved),
            "approved_items": results
        }
    except DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    except Exception as e:
        logger.exception("Error in debug-approval endpoint")
        raise HTTPException(status_code=500, detail=f"Debug error: {str(e)}")

@router.post("/{document_id}/initialize-structure")
async def initialize_document_structure(document_id: str):
    """
    Initialize the document structure with empty section data.
    This is useful when creating a new document.
    """
    try:
        # Get document
        doc = await Document.get(id=document_id)
        topic = doc.topic
        
        if topic not in DOCUMENT_STRUCTURE:
            raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
        
        # Create empty section data for each section in the structure
        sections_created = []
        for sec_obj in DOCUMENT_STRUCTURE[topic]:
            section = list(sec_obj.keys())[0]
            subsections = sec_obj[section]
            
            # Initialize empty data for each subsection
            data = {subsec: "" for subsec in subsections}
            
            # Create or update section data
            section_data, created = await SectionData.update_or_create(
                document=doc,
                section=section,
                defaults={"data": data}
            )
            
            sections_created.append(section)
        
        # Generate an initial PDF with the structure - use approved_only=true to ensure it only shows approved content
        # For a new document, this will result in an empty PDF, which is expected
        await generate_pdf(document_id, approved_only=True)
        
        return {
            "document_id": document_id,
            "topic": topic,
            "sections_initialized": sections_created,
            "status": "success"
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing document structure: {str(e)}")

@router.post("/{document_id}/approve-simple", response_model=SubsectionApprovalResponse)
async def approve_subsection_simple(
    document_id: str, 
    approval: SimpleSubsectionApproval,
    current_user: User = Depends(get_current_active_user)
):
    """
    Simplified endpoint to approve a subsection's content.
    Only requires section and subsection - the value is automatically loaded from section_data.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    try:
        # Validate section and subsection against document structure
        topic = doc.topic
        if topic not in DOCUMENT_STRUCTURE:
            raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
            
        section_valid = False
        subsection_valid = False
        
        for sec_obj in DOCUMENT_STRUCTURE[topic]:
            sec_name = list(sec_obj.keys())[0]
            if sec_name == approval.section:
                section_valid = True
                if approval.subsection in sec_obj[sec_name]:
                    subsection_valid = True
                    break
        
        if not section_valid:
            raise HTTPException(status_code=400, detail=f"Invalid section '{approval.section}' for topic '{topic}'")
        
        if not subsection_valid:
            raise HTTPException(status_code=400, detail=f"Invalid subsection '{approval.subsection}' for section '{approval.section}'")
        
        # Get the correct value from section_data
        section_data = await SectionData.filter(document=doc, section=approval.section).first()
        if not section_data:
            raise HTTPException(status_code=404, detail=f"No data found for section '{approval.section}'")
            
        data = section_data.data
        if approval.subsection not in data:
            raise HTTPException(status_code=404, detail=f"No data found for subsection '{approval.subsection}'")
            
        # Get the correct value from section_data
        correct_value = data[approval.subsection]
        
        # Safely handle logging to prevent slicing errors
        if correct_value is not None:
            # Only try to slice if it's a string and has content
            if isinstance(correct_value, str) and len(correct_value) > 0:
                preview = correct_value[:50] + "..." if len(correct_value) > 50 else correct_value
                logger.debug(f"Using value from section_data for {approval.section}.{approval.subsection}: {preview}")
            else:
                logger.debug(f"Using value from section_data for {approval.section}.{approval.subsection}: {type(correct_value)}")
        else:
            logger.debug(f"Using NULL value from section_data for {approval.section}.{approval.subsection}")
            correct_value = ""  # Ensure it's not None for database operations
        
        try:
            # Use a direct SQL query to avoid datetime issues
            conn = Tortoise.get_connection("default")
            
            # Check if record exists
            query = """
                SELECT id FROM approved_subsections 
                WHERE document_id = $1 AND section = $2 AND subsection = $3;
            """
            result = await conn.execute_query(query, [str(doc.id), approval.section, approval.subsection])
            
            if result[1]:  # Record exists
                # Update existing record
                update_query = """
                    UPDATE approved_subsections 
                    SET approved_value = $4 
                    WHERE document_id = $1 AND section = $2 AND subsection = $3;
                """
                await conn.execute_query(update_query, 
                                        [str(doc.id), approval.section, approval.subsection, correct_value])
                logger.debug(f"Updated approval for {approval.section}.{approval.subsection}")
            else:
                # Insert new record
                insert_query = """
                    INSERT INTO approved_subsections(document_id, section, subsection, approved_value)
                    VALUES($1, $2, $3, $4);
                """
                await conn.execute_query(insert_query, 
                                        [str(doc.id), approval.section, approval.subsection, correct_value])
                logger.debug(f"Created approval for {approval.section}.{approval.subsection}")
                
        except Exception as e:
            logger.exception(f"Database error during approval: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        # Return the result without approved_at field
        return {
            "document_id": document_id,
            "section": approval.section,
            "subsection": approval.subsection,
            "approved": True
        }
        
    except DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    except Exception as e:
        logger.exception(f"Error in approve_subsection_simple: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error approving subsection: {str(e)}")