import pytest
import uuid
from datetime import datetime
from models import (
    User, UserRole, Document, Project, SectionData, 
    ChatMessage, ActiveSubsection, ApprovedSubsection,
    FileUpload, FileUploadStatus, CoverPageData
)
from utils.auth import get_password_hash

class TestUserModel:
    """Test cases for the User model."""
    
    @pytest.mark.asyncio
    async def test_create_user(self, db):
        """Test creating a user with valid data."""
        user = await User.create(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        assert user.email == "test@example.com"
        assert user.role == UserRole.USER
        assert user.is_active is True
        assert user.created_at is not None
        assert user.last_login is None
    
    @pytest.mark.asyncio
    async def test_create_admin_user(self, db):
        """Test creating an admin user."""
        user = await User.create(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            password_hash=get_password_hash("adminpass"),
            role=UserRole.ADMIN
        )
        
        assert user.role == UserRole.ADMIN
    
    @pytest.mark.asyncio
    async def test_user_str_representation(self, db):
        """Test the string representation of a user."""
        user = await User.create(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        assert str(user) == "test@example.com (user)"
    
    @pytest.mark.asyncio
    async def test_unique_email_constraint(self, db):
        """Test that email must be unique."""
        email = "duplicate@example.com"
        
        await User.create(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        # This should raise an exception due to unique constraint
        with pytest.raises(Exception):
            await User.create(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=get_password_hash("password456"),
                role=UserRole.USER
            )

class TestDocumentModel:
    """Test cases for the Document model."""
    
    @pytest.mark.asyncio
    async def test_create_document(self, db):
        """Test creating a document."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Test Document",
            thread_id="thread_123"
        )
        
        assert document.topic == "Test Document"
        assert document.thread_id == "thread_123"
        assert document.pdf_data is None
        assert document.created_at is not None
    
    @pytest.mark.asyncio
    async def test_document_with_pdf_data(self, db):
        """Test creating a document with PDF data."""
        pdf_data = b"fake pdf content"
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="PDF Document",
            pdf_data=pdf_data
        )
        
        assert document.pdf_data == pdf_data

class TestProjectModel:
    """Test cases for the Project model."""
    
    @pytest.mark.asyncio
    async def test_create_project_with_user(self, db):
        """Test creating a project with a user and document."""
        # Create user first
        user = await User.create(
            id=str(uuid.uuid4()),
            email="project@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        # Create document
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Project Document"
        )
        
        # Create project
        project = await Project.create(
            id=str(uuid.uuid4()),
            name="Test Project",
            document=document,
            user=user
        )
        
        assert project.name == "Test Project"
        assert project.document_id == document.id
        assert project.user_id == user.id
        assert project.created_at is not None
    
    @pytest.mark.asyncio
    async def test_project_relationships(self, db):
        """Test project relationships with user and document."""
        user = await User.create(
            id=str(uuid.uuid4()),
            email="user@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Related Document"
        )
        
        project = await Project.create(
            id=str(uuid.uuid4()),
            name="Related Project",
            document=document,
            user=user
        )
        
        # Test forward relationships
        await project.fetch_related("document", "user")
        assert project.document.topic == "Related Document"
        assert project.user.email == "user@example.com"
        
        # Test reverse relationships
        await user.fetch_related("projects")
        assert len(user.projects) == 1
        assert user.projects[0].name == "Related Project"

class TestSectionDataModel:
    """Test cases for the SectionData model."""
    
    @pytest.mark.asyncio
    async def test_create_section_data(self, db):
        """Test creating section data with JSON content."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Section Test Document"
        )
        
        section_data = await SectionData.create(
            document=document,
            section="introduction",
            data={"content": "This is the introduction", "status": "draft"}
        )
        
        assert section_data.section == "introduction"
        assert section_data.data["content"] == "This is the introduction"
        assert section_data.data["status"] == "draft"
    
    @pytest.mark.asyncio
    async def test_unique_document_section_constraint(self, db):
        """Test that document-section combination must be unique."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Unique Test Document"
        )
        
        await SectionData.create(
            document=document,
            section="methodology",
            data={"content": "First methodology"}
        )
        
        # This should raise an exception due to unique constraint
        with pytest.raises(Exception):
            await SectionData.create(
                document=document,
                section="methodology",
                data={"content": "Second methodology"}
            )

class TestChatMessageModel:
    """Test cases for the ChatMessage model."""
    
    @pytest.mark.asyncio
    async def test_create_chat_message(self, db):
        """Test creating a chat message."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Chat Test Document"
        )
        
        message = await ChatMessage.create(
            document=document,
            role="user",
            content="Hello, this is a test message",
            section="introduction",
            subsection="overview"
        )
        
        assert message.role == "user"
        assert message.content == "Hello, this is a test message"
        assert message.section == "introduction"
        assert message.subsection == "overview"
        assert message.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_chat_message_with_file(self, db):
        """Test creating a chat message with file reference."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="File Chat Document"
        )
        
        message = await ChatMessage.create(
            document=document,
            role="assistant",
            content="Here's the analysis of your file",
            file_path="/uploads/test_file.pdf"
        )
        
        assert message.file_path == "/uploads/test_file.pdf"

class TestFileUploadModel:
    """Test cases for the FileUpload model."""
    
    @pytest.mark.asyncio
    async def test_create_file_upload(self, db):
        """Test creating a file upload record."""
        user = await User.create(
            id=str(uuid.uuid4()),
            email="fileuser@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="File Upload Document"
        )
        
        file_upload = await FileUpload.create(
            id=str(uuid.uuid4()),
            document=document,
            user=user,
            original_filename="test.pdf",
            file_size=1024,
            file_type="application/pdf",
            status=FileUploadStatus.PENDING
        )
        
        assert file_upload.original_filename == "test.pdf"
        assert file_upload.file_size == 1024
        assert file_upload.status == FileUploadStatus.PENDING
        assert file_upload.created_at is not None
    
    @pytest.mark.asyncio
    async def test_file_upload_status_enum(self, db):
        """Test file upload status enumeration."""
        user = await User.create(
            id=str(uuid.uuid4()),
            email="enumuser@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Enum Test Document"
        )
        
        # Test all status values
        for status in FileUploadStatus:
            file_upload = await FileUpload.create(
                id=str(uuid.uuid4()),
                document=document,
                user=user,
                original_filename=f"test_{status.value}.pdf",
                file_size=1024,
                file_type="application/pdf",
                status=status
            )
            assert file_upload.status == status

class TestCoverPageDataModel:
    """Test cases for the CoverPageData model."""
    
    @pytest.mark.asyncio
    async def test_create_cover_page_data(self, db):
        """Test creating cover page data."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Cover Page Document"
        )
        
        cover_data = await CoverPageData.create(
            document=document,
            data={
                "title": "Research Report",
                "author": "John Doe",
                "organization": "Test University",
                "date": "2024-01-15"
            }
        )
        
        assert cover_data.data["title"] == "Research Report"
        assert cover_data.data["author"] == "John Doe"
        assert cover_data.data["organization"] == "Test University"
    
    @pytest.mark.asyncio
    async def test_cover_page_one_to_one_relationship(self, db):
        """Test one-to-one relationship between document and cover page."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="One-to-One Document"
        )
        
        await CoverPageData.create(
            document=document,
            data={"title": "First Cover"}
        )
        
        # This should raise an exception due to unique constraint
        with pytest.raises(Exception):
            await CoverPageData.create(
                document=document,
                data={"title": "Second Cover"}
            ) 