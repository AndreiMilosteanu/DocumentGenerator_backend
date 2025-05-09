from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, UUID4
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import uuid
from models import Document, ChatMessage, SectionData, Project
from templates.structure import DOCUMENT_STRUCTURE

router = APIRouter()
logger = logging.getLogger("projects")

class ProjectSummary(BaseModel):
    id: str
    name: str
    topic: str
    document_id: str
    thread_id: Optional[str] = None
    created_at: datetime
    last_activity: Optional[datetime] = None
    has_pdf: bool

class ChatHistoryItem(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime

class ProjectDetail(BaseModel):
    id: str
    name: str
    topic: str
    document_id: str
    thread_id: Optional[str] = None
    created_at: datetime
    section_data: Dict[str, Any]
    messages: List[ChatHistoryItem]
    has_pdf: bool

class ProjectUpdateRequest(BaseModel):
    name: str

class ProjectCreationRequest(BaseModel):
    name: str
    topic: str

class ProjectCreationResponse(BaseModel):
    id: str
    name: str
    topic: str
    document_id: str
    thread_id: Optional[str] = None

class ProjectStatusResponse(BaseModel):
    id: str
    name: str
    topic: str
    document_id: str
    thread_id: Optional[str] = None
    created_at: datetime
    sections_completed: int
    total_sections: int
    completion_percentage: float
    has_pdf: bool
    messages_count: int
    last_activity: Optional[datetime] = None

class DocumentLinkRequest(BaseModel):
    document_id: str
    name: str

class ConversationThreadInfo(BaseModel):
    document_id: str
    thread_id: Optional[str] = None
    is_new_thread: bool
    topic: str

@router.get("/list", response_model=List[ProjectSummary])
async def list_projects():
    """
    List all available projects with basic information.
    """
    # Use prefetch_related to efficiently load related Document objects
    projects = await Project.all().prefetch_related('document').order_by("-created_at")
    
    result = []
    for project in projects:
        doc = project.document
        
        # Get last activity time based on chat messages
        last_msg = await ChatMessage.filter(document=doc).order_by("-timestamp").first()
        last_activity = last_msg.timestamp if last_msg else None
        
        result.append(ProjectSummary(
            id=str(project.id),
            name=project.name,
            topic=doc.topic,
            document_id=str(doc.id),
            thread_id=doc.thread_id,
            created_at=project.created_at,
            last_activity=last_activity,
            has_pdf=bool(doc.pdf_data)
        ))
    
    return result

@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project_detail(project_id: str):
    """
    Get detailed information about a specific project, including chat history.
    """
    try:
        project = await Project.get(id=project_id).prefetch_related('document')
        doc = project.document
    except Project.DoesNotExist:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get section data
    sections = await SectionData.filter(document=doc).all()
    section_data = {s.section: s.data for s in sections}
    
    # Get chat history
    messages = await ChatMessage.filter(document=doc).order_by("timestamp").all()
    chat_history = [
        ChatHistoryItem(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp
        ) 
        for msg in messages
    ]
    
    return ProjectDetail(
        id=str(project.id),
        name=project.name,
        topic=doc.topic,
        document_id=str(doc.id),
        thread_id=doc.thread_id,
        created_at=project.created_at,
        section_data=section_data,
        messages=chat_history,
        has_pdf=bool(doc.pdf_data)
    )

@router.put("/{project_id}", response_model=ProjectSummary)
async def update_project(project_id: str, request: ProjectUpdateRequest):
    """
    Update project details (currently only name).
    """
    try:
        project = await Project.get(id=project_id).prefetch_related('document')
        doc = project.document
    except Project.DoesNotExist:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.name = request.name
    await project.save()
    
    return ProjectSummary(
        id=str(project.id),
        name=project.name,
        topic=doc.topic,
        document_id=str(doc.id),
        thread_id=doc.thread_id,
        created_at=project.created_at,
        has_pdf=bool(doc.pdf_data)
    )

@router.delete("/{project_id}")
async def delete_project(project_id: str):
    """
    Delete a project but keep the underlying document.
    """
    try:
        project = await Project.get(id=project_id)
    except Project.DoesNotExist:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete only the project (document stays intact)
    await project.delete()
    
    return {"success": True, "message": "Project deleted successfully"}

@router.post("/create", response_model=ProjectCreationResponse)
async def create_project(request: ProjectCreationRequest):
    """
    Create a new project with a name and topic, generating unique IDs.
    """
    # Validate topic
    topic = request.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
    
    # Generate unique IDs
    project_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    
    # Create the document record first
    doc = await Document.create(
        id=document_id,
        topic=topic
    )
    
    # Create the project record that references the document
    project = await Project.create(
        id=project_id,
        name=request.name,
        document=doc
    )
    
    logger.info(f"Created new project: {request.name} (ID: {project_id}, Document ID: {document_id}, Topic: {topic})")
    
    return ProjectCreationResponse(
        id=project_id,
        name=request.name,
        topic=topic,
        document_id=document_id,
        thread_id=doc.thread_id  # Will be None until conversation starts
    )

@router.get("/{project_id}/status", response_model=ProjectStatusResponse)
async def get_project_status(project_id: str):
    """
    Get project status including completion metrics.
    """
    try:
        project = await Project.get(id=project_id).prefetch_related('document')
        doc = project.document
    except Project.DoesNotExist:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get section data to calculate completion
    sections = await SectionData.filter(document=doc).all()
    completed_sections = len(sections)
    
    # Get total expected sections based on document structure
    total_sections = 0
    if doc.topic in DOCUMENT_STRUCTURE:
        total_sections = len(DOCUMENT_STRUCTURE[doc.topic])
    
    # Calculate completion percentage
    completion_percentage = 0
    if total_sections > 0:
        completion_percentage = (completed_sections / total_sections) * 100
    
    # Get messages count
    messages_count = await ChatMessage.filter(document=doc).count()
    
    # Get last activity
    last_msg = await ChatMessage.filter(document=doc).order_by("-timestamp").first()
    last_activity = last_msg.timestamp if last_msg else None
    
    return ProjectStatusResponse(
        id=str(project.id),
        name=project.name,
        topic=doc.topic,
        document_id=str(doc.id),
        thread_id=doc.thread_id,
        created_at=project.created_at,
        sections_completed=completed_sections,
        total_sections=total_sections,
        completion_percentage=completion_percentage,
        has_pdf=bool(doc.pdf_data),
        messages_count=messages_count,
        last_activity=last_activity
    )

@router.get("/{project_id}/chat-history", response_model=List[ChatHistoryItem])
async def get_chat_history(project_id: str, skip: int = 0, limit: int = 100):
    """
    Get chat history for a project with pagination.
    """
    try:
        project = await Project.get(id=project_id).prefetch_related('document')
        doc = project.document
    except Project.DoesNotExist:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get chat messages with pagination
    messages = await ChatMessage.filter(document=doc).order_by("timestamp").offset(skip).limit(limit).all()
    
    # Format response
    chat_history = [
        ChatHistoryItem(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp
        ) 
        for msg in messages
    ]
    
    return chat_history

@router.post("/link-document", response_model=ProjectCreationResponse)
async def link_document_to_project(request: DocumentLinkRequest):
    """
    Create a new project that links to an existing document.
    """
    # Check if document exists
    try:
        doc = await Document.get(id=request.document_id)
    except Document.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {request.document_id} not found")
    
    # Check if document already has a project
    existing_project = await Project.filter(document_id=request.document_id).first()
    if existing_project:
        raise HTTPException(status_code=400, detail=f"Document {request.document_id} is already linked to project {existing_project.id}")
    
    # Generate a project ID
    project_id = str(uuid.uuid4())
    
    # Create the project
    project = await Project.create(
        id=project_id,
        name=request.name,
        document=doc
    )
    
    logger.info(f"Linked document {request.document_id} to new project {project_id} ({request.name})")
    
    return ProjectCreationResponse(
        id=project_id,
        name=request.name,
        topic=doc.topic,
        document_id=request.document_id,
        thread_id=doc.thread_id
    )

@router.get("/document/{document_id}", response_model=Optional[ProjectSummary])
async def get_project_by_document(document_id: str):
    """
    Find a project by its document ID.
    """
    # Check if the document exists
    try:
        doc = await Document.get(id=document_id)
    except Document.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    # Find associated project
    project = await Project.filter(document_id=document_id).first()
    if not project:
        return None
    
    # Get last activity
    last_msg = await ChatMessage.filter(document=doc).order_by("-timestamp").first()
    last_activity = last_msg.timestamp if last_msg else None
    
    return ProjectSummary(
        id=str(project.id),
        name=project.name,
        topic=doc.topic,
        document_id=document_id,
        thread_id=doc.thread_id,
        created_at=project.created_at,
        last_activity=last_activity,
        has_pdf=bool(doc.pdf_data)
    )

@router.get("/{project_id}/conversation", response_model=ConversationThreadInfo)
async def get_conversation_thread(project_id: str):
    """
    Get conversation thread information for a project.
    If no thread exists yet, this provides the information needed to start one.
    """
    try:
        project = await Project.get(id=project_id).prefetch_related('document')
        doc = project.document
    except Project.DoesNotExist:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if thread already exists
    is_new_thread = doc.thread_id is None
    
    return ConversationThreadInfo(
        document_id=str(doc.id),
        thread_id=doc.thread_id,
        is_new_thread=is_new_thread,
        topic=doc.topic
    ) 