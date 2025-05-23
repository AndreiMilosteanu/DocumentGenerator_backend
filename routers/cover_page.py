from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ValidationError
from typing import Dict, Any, List, Optional
import logging
from tortoise.exceptions import DoesNotExist

from models import Document, CoverPageData, User, Project
from utils.auth import get_current_active_user
from templates.structure import COVER_PAGE_STRUCTURE

router = APIRouter()
logger = logging.getLogger("cover_page")

class CoverPageFieldInfo(BaseModel):
    label: str
    type: str
    required: bool

class CoverPageCategoryInfo(BaseModel):
    fields: Dict[str, CoverPageFieldInfo]

class CoverPageStructureResponse(BaseModel):
    topic: str
    categories: Dict[str, CoverPageCategoryInfo]

class CoverPageDataUpdate(BaseModel):
    data: Dict[str, Any]

class CoverPageDataResponse(BaseModel):
    document_id: str
    topic: str
    data: Dict[str, Any]
    updated_at: Optional[str] = None

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

def _validate_cover_page_data(topic: str, data: Dict[str, Any]) -> Dict[str, str]:
    """
    Validate cover page data against the topic's structure.
    Returns a dictionary of validation errors, if any.
    """
    errors = {}
    
    if topic not in COVER_PAGE_STRUCTURE:
        errors["topic"] = f"No cover page structure defined for topic '{topic}'"
        return errors
    
    structure = COVER_PAGE_STRUCTURE[topic]
    
    logger.info(f"Validating cover page data for topic '{topic}'")
    logger.info(f"Expected structure categories: {list(structure.keys())}")
    logger.info(f"Received data categories: {list(data.keys())}")
    
    # Check for unknown categories in data
    for category in data.keys():
        if category not in structure:
            logger.warning(f"Unknown category '{category}' in data")
            # Don't treat this as an error - just log it
    
    # Check each category in the structure
    for category, fields in structure.items():
        category_data = data.get(category, {})
        
        logger.info(f"Validating category '{category}':")
        logger.info(f"  Expected fields: {list(fields.keys())}")
        logger.info(f"  Received fields: {list(category_data.keys())}")
        
        # Check for unknown fields in category data
        for field_name in category_data.keys():
            if field_name not in fields:
                logger.warning(f"Unknown field '{field_name}' in category '{category}'")
                # Don't treat this as an error - just log it
        
        # Check required fields
        for field_name, field_info in fields.items():
            if field_info.get('required', False):
                field_value = category_data.get(field_name)
                # For now, be more lenient with required fields to avoid blocking frontend development
                # Only require fields if they are completely missing, allow empty strings
                if field_value is None:
                    errors[f"{category}.{field_name}"] = f"Field '{field_info['label']}' is required"
                    logger.error(f"Required field missing: {category}.{field_name}")
                # TODO: Re-enable strict validation after frontend is stable
                # if not field_value or (isinstance(field_value, str) and not field_value.strip()):
                #     errors[f"{category}.{field_name}"] = f"Field '{field_info['label']}' is required"
                #     logger.error(f"Required field missing: {category}.{field_name}")
            
            # Validate field types if data is provided
            field_value = category_data.get(field_name)
            if field_value:
                field_type = field_info.get('type', 'text')
                if field_type == 'date':
                    # Basic date validation - you might want to use a more robust validator
                    try:
                        from datetime import datetime
                        if isinstance(field_value, str):
                            # Try multiple date formats
                            date_formats = ['%Y-%m-%d', '%d.%m.%Y', '%m/%d/%Y']
                            parsed = False
                            for fmt in date_formats:
                                try:
                                    datetime.strptime(field_value, fmt)
                                    parsed = True
                                    break
                                except ValueError:
                                    continue
                            if not parsed:
                                errors[f"{category}.{field_name}"] = f"Field '{field_info['label']}' must be a valid date (YYYY-MM-DD, DD.MM.YYYY, or MM/DD/YYYY format)"
                    except Exception as e:
                        errors[f"{category}.{field_name}"] = f"Field '{field_info['label']}' has invalid date format: {str(e)}"
    
    logger.info(f"Validation completed. Found {len(errors)} errors: {list(errors.keys())}")
    return errors

@router.get("/{document_id}/structure", response_model=CoverPageStructureResponse)
async def get_cover_page_structure(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the cover page structure for a document's topic.
    This returns the available fields and their metadata for the frontend to render forms.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    topic = doc.topic
    if topic not in COVER_PAGE_STRUCTURE:
        raise HTTPException(status_code=404, detail=f"No cover page structure defined for topic '{topic}'")
    
    structure = COVER_PAGE_STRUCTURE[topic]
    
    # Convert to response format
    categories = {}
    for category_name, fields in structure.items():
        category_fields = {}
        for field_name, field_info in fields.items():
            category_fields[field_name] = CoverPageFieldInfo(**field_info)
        categories[category_name] = CoverPageCategoryInfo(fields=category_fields)
    
    return CoverPageStructureResponse(
        topic=topic,
        categories=categories
    )

@router.get("/{document_id}/data", response_model=CoverPageDataResponse)
async def get_cover_page_data(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current cover page data for a document.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Get cover page data
    cover_page = await CoverPageData.filter(document=doc).first()
    
    data = {}
    updated_at = None
    
    if cover_page:
        data = cover_page.data or {}
        updated_at = cover_page.updated_at.isoformat() if cover_page.updated_at else None
    else:
        # Initialize with empty structure based on topic
        topic = doc.topic
        if topic in COVER_PAGE_STRUCTURE:
            structure = COVER_PAGE_STRUCTURE[topic]
            for category_name, fields in structure.items():
                data[category_name] = {}
                for field_name in fields.keys():
                    data[category_name][field_name] = ""
    
    return CoverPageDataResponse(
        document_id=document_id,
        topic=doc.topic,
        data=data,
        updated_at=updated_at
    )

@router.put("/{document_id}/data", response_model=CoverPageDataResponse)
async def update_cover_page_data(
    document_id: str,
    update: CoverPageDataUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update the cover page data for a document.
    """
    try:
        # Check if user has access to this document
        doc = await _check_document_access(document_id, current_user)
        
        # Log the incoming data for debugging
        logger.info(f"Updating cover page data for document {document_id}")
        logger.info(f"Topic: {doc.topic}")
        logger.info(f"Data keys: {list(update.data.keys())}")
        
        # Validate the data
        topic = doc.topic
        validation_errors = _validate_cover_page_data(topic, update.data)
        
        if validation_errors:
            logger.error(f"Validation failed with errors: {validation_errors}")
            raise HTTPException(
                status_code=400, 
                detail={
                    "message": "Validation errors in cover page data",
                    "errors": validation_errors,
                    "received_data_structure": {
                        "categories": list(update.data.keys()),
                        "category_details": {cat: list(fields.keys()) if isinstance(fields, dict) else "invalid" 
                                           for cat, fields in update.data.items()}
                    },
                    "expected_structure": {
                        "topic": topic,
                        "categories": list(COVER_PAGE_STRUCTURE.get(topic, {}).keys())
                    }
                }
            )
        
        # Get or create cover page data
        cover_page = await CoverPageData.filter(document=doc).first()
        created = False
        
        if cover_page:
            # Update existing data
            cover_page.data = update.data
            await cover_page.save()
        else:
            # Create new record without manual datetime
            cover_page = await CoverPageData.create(
                document=doc,
                data=update.data
            )
            created = True
        
        logger.info(f"{'Created' if created else 'Updated'} cover page data for document {document_id}")
        
        return CoverPageDataResponse(
            document_id=document_id,
            topic=doc.topic,
            data=cover_page.data,
            updated_at=cover_page.updated_at.isoformat() if cover_page.updated_at else None
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating cover page data: {str(e)}")
        logger.exception("Full error details:")
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error while updating cover page data",
                "error": str(e)
            }
        )

@router.patch("/{document_id}/data/{category}")
async def update_cover_page_category(
    document_id: str,
    category: str,
    update_data: Dict[str, Any],
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a specific category of cover page data.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    topic = doc.topic
    if topic not in COVER_PAGE_STRUCTURE:
        raise HTTPException(status_code=404, detail=f"No cover page structure defined for topic '{topic}'")
    
    if category not in COVER_PAGE_STRUCTURE[topic]:
        raise HTTPException(status_code=404, detail=f"Category '{category}' not found for topic '{topic}'")
    
    # Get or create cover page data
    cover_page = await CoverPageData.filter(document=doc).first()
    if not cover_page:
        cover_page = await CoverPageData.create(
            document=doc,
            data={}
        )
    
    # Initialize data structure if needed
    data = cover_page.data or {}
    if category not in data:
        data[category] = {}
    
    # Update the specific category
    data[category].update(update_data)
    
    # Validate the updated data
    validation_errors = _validate_cover_page_data(topic, data)
    
    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Validation errors in cover page data",
                "errors": validation_errors
            }
        )
    
    # Save the updated data
    cover_page.data = data
    await cover_page.save()
    
    logger.info(f"Updated cover page category '{category}' for document {document_id}")
    
    return {
        "document_id": document_id,
        "category": category,
        "data": data[category],
        "updated_at": cover_page.updated_at.isoformat()
    }

@router.delete("/{document_id}/data")
async def reset_cover_page_data(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Reset cover page data to empty values.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Delete existing cover page data
    await CoverPageData.filter(document=doc).delete()
    
    logger.info(f"Reset cover page data for document {document_id}")
    
    return {"message": "Cover page data reset successfully"}

@router.get("/{document_id}/preview")
async def preview_cover_page(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a preview of how the cover page will look with current data.
    This endpoint returns the data formatted for template rendering.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Get cover page data
    cover_page = await CoverPageData.filter(document=doc).first()
    
    if not cover_page or not cover_page.data:
        return {
            "document_id": document_id,
            "topic": doc.topic,
            "preview_data": {},
            "message": "No cover page data available"
        }
    
    # Flatten the data structure for template use
    flattened_data = {}
    for category, fields in cover_page.data.items():
        if isinstance(fields, dict):
            flattened_data.update(fields)
    
    return {
        "document_id": document_id,
        "topic": doc.topic,
        "preview_data": flattened_data,
        "structured_data": cover_page.data
    } 