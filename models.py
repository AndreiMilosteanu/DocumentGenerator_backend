from tortoise import fields
from tortoise.models import Model
from enum import Enum
from typing import List, Optional

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"

class User(Model):
    """
    Represents a user in the system.
    """
    id = fields.UUIDField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    password_hash = fields.CharField(max_length=255)
    role = fields.CharEnumField(UserRole, default=UserRole.USER)
    created_at = fields.DatetimeField(auto_now_add=True)
    last_login = fields.DatetimeField(null=True)
    is_active = fields.BooleanField(default=True)

    class Meta:
        table = "users"

    def __str__(self):
        return f"{self.email} ({self.role})"

class Document(Model):
    """
    Represents a document (topic) and stores metadata and generated PDF bytes.
    """
    id = fields.UUIDField(pk=True)
    topic = fields.CharField(max_length=100)
    thread_id = fields.CharField(max_length=255, null=True)
    pdf_data = fields.BinaryField(null=True)  # store generated PDF bytes
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "documents"

class Project(Model):
    """
    Represents a user project that references a document.
    """
    id = fields.UUIDField(pk=True)
    name = fields.CharField(max_length=255)
    document = fields.OneToOneField("models.Document", related_name="project")
    created_at = fields.DatetimeField(auto_now_add=True)
    user = fields.ForeignKeyField("models.User", related_name="projects", null=True)

    class Meta:
        table = "projects"

class SectionData(Model):
    """
    Stores structured JSON data for each section of a document.
    """
    id = fields.IntField(pk=True)
    document = fields.ForeignKeyField("models.Document", related_name="sections")
    section = fields.CharField(max_length=100)
    data = fields.JSONField()

    class Meta:
        table = "section_data"
        unique_together = (("document_id", "section"),)

class ChatMessage(Model):
    """
    Persists chat history messages and file references for a document.
    """
    id = fields.IntField(pk=True)
    document = fields.ForeignKeyField("models.Document", related_name="messages")
    role = fields.CharField(max_length=10)
    content = fields.TextField(null=True)
    file_path = fields.CharField(max_length=255, null=True)  # optional file upload reference
    timestamp = fields.DatetimeField(auto_now_add=True)
    # New fields to track which section and subsection this message belongs to
    section = fields.CharField(max_length=100, null=True)
    subsection = fields.CharField(max_length=100, null=True)

    class Meta:
        table = "chat_messages"

class ActiveSubsection(Model):
    """
    Tracks which subsection is currently active for a document.
    """
    id = fields.IntField(pk=True)
    document = fields.ForeignKeyField("models.Document", related_name="active_subsections")
    section = fields.CharField(max_length=100)
    subsection = fields.CharField(max_length=100)
    last_accessed = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "active_subsections"
        unique_together = (("document_id", "section", "subsection"),)

class ApprovedSubsection(Model):
    """
    Tracks which subsections have been approved by the user for inclusion in the PDF.
    """
    id = fields.IntField(pk=True)
    document = fields.ForeignKeyField("models.Document", related_name="approved_subsections")
    section = fields.CharField(max_length=100)
    subsection = fields.CharField(max_length=100)
    approved_value = fields.TextField()  # Stores the approved text/value for this subsection
    approved_at = fields.DatetimeField(auto_now=True, use_tz=False)  # Use naive datetime without timezone

    class Meta:
        table = "approved_subsections"
        unique_together = (("document_id", "section", "subsection"),)

class FileUploadStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"

class FileUpload(Model):
    """
    Tracks files uploaded to OpenAI and associated with documents/conversations.
    """
    id = fields.UUIDField(pk=True)
    document = fields.ForeignKeyField("models.Document", related_name="files")
    user = fields.ForeignKeyField("models.User", related_name="uploads")
    original_filename = fields.CharField(max_length=255)
    openai_file_id = fields.CharField(max_length=255, null=True)
    file_size = fields.IntField()
    file_type = fields.CharField(max_length=100)
    status = fields.CharEnumField(FileUploadStatus, default=FileUploadStatus.PENDING)
    error_message = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    # Optional message association (for files added during conversation)
    associated_message = fields.ForeignKeyField("models.ChatMessage", related_name="files", null=True)
    
    # Track current section/subsection when file was uploaded
    section = fields.CharField(max_length=100, null=True)
    subsection = fields.CharField(max_length=100, null=True)
    file_data = fields.BinaryField(null=True)  # Store binary file data for PDF merging

    class Meta:
        table = "file_uploads"

class CoverPageData(Model):
    """
    Stores cover page data for documents. Each document can have customizable cover page fields.
    """
    id = fields.IntField(pk=True)
    document = fields.OneToOneField("models.Document", related_name="cover_page")
    data = fields.JSONField(default=dict)  # Stores all cover page fields as JSON
    updated_at = fields.DatetimeField(null=True)  # Manually managed datetime field

    class Meta:
        table = "cover_page_data"