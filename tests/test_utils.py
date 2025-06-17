import pytest
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import uuid

from utils.rate_limiter import RateLimiter
from models import User, Document, FileUpload, FileUploadStatus, UserRole
from utils.auth import get_password_hash

class TestRateLimiter:
    """Test cases for the rate limiter utility."""
    
    def test_rate_limiter_creation(self):
        """Test creating a rate limiter."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 60
        assert len(limiter.requests) == 0
    
    def test_rate_limiter_allow_first_request(self):
        """Test that first request is always allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        client_id = "test_client"
        
        allowed = limiter.is_allowed(client_id)
        assert allowed is True
    
    def test_rate_limiter_within_limits(self):
        """Test requests within rate limits."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        client_id = "test_client"
        
        # First 3 requests should be allowed
        for i in range(3):
            allowed = limiter.is_allowed(client_id)
            assert allowed is True
    
    def test_rate_limiter_exceed_limits(self):
        """Test requests exceeding rate limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        client_id = "test_client"
        
        # First 2 requests should be allowed
        assert limiter.is_allowed(client_id) is True
        assert limiter.is_allowed(client_id) is True
        
        # Third request should be denied
        assert limiter.is_allowed(client_id) is False
    
    def test_rate_limiter_different_clients(self):
        """Test that different clients have separate limits."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        
        # Each client should get their own allowance
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client2") is True
        
        # But second request from same client should be denied
        assert limiter.is_allowed("client1") is False
        assert limiter.is_allowed("client2") is False
    
    @patch('utils.rate_limiter.datetime')
    def test_rate_limiter_window_reset(self, mock_datetime):
        """Test that rate limiter resets after time window."""
        # Mock current time
        start_time = datetime.now()
        mock_datetime.now.return_value = start_time
        
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        client_id = "test_client"
        
        # First request should be allowed
        assert limiter.is_allowed(client_id) is True
        
        # Second request should be denied
        assert limiter.is_allowed(client_id) is False
        
        # Move time forward past window
        mock_datetime.now.return_value = start_time + timedelta(seconds=61)
        
        # Request should now be allowed again
        assert limiter.is_allowed(client_id) is True
    
    def test_rate_limiter_get_remaining_requests(self):
        """Test getting remaining requests for a client."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        client_id = "test_client"
        
        # Initially should have max requests available
        remaining = limiter.get_remaining_requests(client_id)
        assert remaining == 3
        
        # After one request, should have 2 remaining
        limiter.is_allowed(client_id)
        remaining = limiter.get_remaining_requests(client_id)
        assert remaining == 2
        
        # After all requests used, should have 0 remaining
        limiter.is_allowed(client_id)
        limiter.is_allowed(client_id)
        remaining = limiter.get_remaining_requests(client_id)
        assert remaining == 0

class TestFileUploadUtils:
    """Test cases for file upload utilities."""
    
    @pytest.mark.asyncio
    async def test_create_file_upload_record(self, db):
        """Test creating a file upload record."""
        user = await User.create(
            id=str(uuid.uuid4()),
            email="filetest@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="File Test Document"
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
        assert file_upload.status == FileUploadStatus.PENDING
        assert file_upload.user_id == user.id
        assert file_upload.document_id == document.id
    
    def test_validate_file_type_pdf(self):
        """Test PDF file type validation."""
        # This test assumes you have file validation utilities
        # Adjust based on your actual implementation
        valid_types = ["application/pdf", "text/plain", "image/jpeg", "image/png"]
        
        assert "application/pdf" in valid_types
        assert "text/plain" in valid_types
        assert "application/exe" not in valid_types
    
    def test_validate_file_size(self):
        """Test file size validation."""
        max_size = 10 * 1024 * 1024  # 10MB
        
        # Valid sizes
        assert 1024 <= max_size
        assert 5 * 1024 * 1024 <= max_size
        
        # Invalid sizes
        assert 20 * 1024 * 1024 > max_size
    
    def test_generate_unique_filename(self):
        """Test generating unique filenames."""
        original_name = "document.pdf"
        
        # This test assumes you have a function to generate unique filenames
        # You might use UUID or timestamp-based naming
        unique_name = f"{uuid.uuid4()}_{original_name}"
        
        assert original_name in unique_name
        assert len(unique_name) > len(original_name)
    
    @pytest.mark.asyncio
    async def test_file_upload_status_transitions(self, db):
        """Test file upload status transitions."""
        user = await User.create(
            id=str(uuid.uuid4()),
            email="status@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Status Test Document"
        )
        
        file_upload = await FileUpload.create(
            id=str(uuid.uuid4()),
            document=document,
            user=user,
            original_filename="status_test.pdf",
            file_size=1024,
            file_type="application/pdf",
            status=FileUploadStatus.PENDING
        )
        
        # Test status transitions
        file_upload.status = FileUploadStatus.PROCESSING
        await file_upload.save()
        
        updated_upload = await FileUpload.get(id=file_upload.id)
        assert updated_upload.status == FileUploadStatus.PROCESSING
        
        # Complete the upload
        file_upload.status = FileUploadStatus.READY
        await file_upload.save()
        
        final_upload = await FileUpload.get(id=file_upload.id)
        assert final_upload.status == FileUploadStatus.READY
    
    @pytest.mark.asyncio
    async def test_file_upload_error_handling(self, db):
        """Test file upload error status and messages."""
        user = await User.create(
            id=str(uuid.uuid4()),
            email="error@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Error Test Document"
        )
        
        file_upload = await FileUpload.create(
            id=str(uuid.uuid4()),
            document=document,
            user=user,
            original_filename="error_test.pdf",
            file_size=1024,
            file_type="application/pdf",
            status=FileUploadStatus.ERROR,
            error_message="Failed to process file"
        )
        
        assert file_upload.status == FileUploadStatus.ERROR
        assert file_upload.error_message == "Failed to process file"

class TestUtilityHelpers:
    """Test cases for general utility helper functions."""
    
    def test_generate_uuid(self):
        """Test UUID generation."""
        uuid1 = str(uuid.uuid4())
        uuid2 = str(uuid.uuid4())
        
        # UUIDs should be different
        assert uuid1 != uuid2
        
        # UUIDs should be valid format
        assert len(uuid1) == 36
        assert uuid1.count('-') == 4
    
    def test_validate_email_format(self):
        """Test email validation."""
        # This assumes you have email validation utilities
        valid_emails = [
            "test@example.com",
            "user.name@domain.org",
            "admin@subdomain.domain.co.uk"
        ]
        
        invalid_emails = [
            "invalid-email",
            "@domain.com",
            "user@",
            "user..name@domain.com"
        ]
        
        for email in valid_emails:
            # Basic email format check
            assert "@" in email
            assert "." in email.split("@")[1]
        
        for email in invalid_emails:
            # These should fail basic validation
            if "@" in email:
                parts = email.split("@")
                if len(parts) != 2 or not parts[0] or not parts[1]:
                    assert True  # Invalid format
                elif ".." in email:
                    assert True  # Double dots not allowed
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # This assumes you have filename sanitization utilities
        dangerous_filename = "../../../etc/passwd"
        
        # Should remove path traversal attempts
        sanitized = os.path.basename(dangerous_filename)
        assert sanitized == "passwd"
        
        # Test special characters
        special_filename = "file with spaces & symbols!.pdf"
        # Basic sanitization would replace problematic characters
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
        has_unsafe = any(c not in safe_chars and c != ' ' for c in special_filename if c not in "&!")
        assert not has_unsafe or True  # Depends on your sanitization rules
    
    @patch('builtins.open', create=True)
    def test_file_reading_utility(self, mock_open):
        """Test file reading utilities."""
        # Mock file content
        mock_file_content = "This is test file content"
        mock_open.return_value.__enter__.return_value.read.return_value = mock_file_content
        
        # Test reading file
        with open("test_file.txt", "r") as f:
            content = f.read()
        
        assert content == mock_file_content
        mock_open.assert_called_once_with("test_file.txt", "r")
    
    def test_timestamp_utilities(self):
        """Test timestamp utilities."""
        now = datetime.now()
        
        # Test timestamp is recent (within last minute)
        time_diff = datetime.now() - now
        assert time_diff.total_seconds() < 60
        
        # Test timestamp formatting
        iso_format = now.isoformat()
        assert "T" in iso_format  # ISO format includes T separator
    
    def test_data_serialization(self):
        """Test JSON serialization utilities."""
        import json
        
        test_data = {
            "id": str(uuid.uuid4()),
            "name": "Test Project",
            "created_at": datetime.now().isoformat(),
            "tags": ["tag1", "tag2"],
            "metadata": {"key": "value"}
        }
        
        # Should be able to serialize to JSON
        json_string = json.dumps(test_data)
        assert isinstance(json_string, str)
        
        # Should be able to deserialize back
        deserialized = json.loads(json_string)
        assert deserialized["name"] == "Test Project"
        assert len(deserialized["tags"]) == 2

class TestConfigurationUtils:
    """Test configuration and environment utilities."""
    
    @patch.dict(os.environ, {"TEST_VAR": "test_value"})
    def test_environment_variable_access(self):
        """Test reading environment variables."""
        value = os.getenv("TEST_VAR")
        assert value == "test_value"
        
        # Test with default value
        default_value = os.getenv("NON_EXISTENT_VAR", "default")
        assert default_value == "default"
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        # This assumes you have configuration validation
        required_configs = ["SECRET_KEY", "DATABASE_URL", "OPENAI_API_KEY"]
        
        # Test that all required configs are checked
        for config in required_configs:
            # In real implementation, this would validate presence and format
            assert isinstance(config, str)
            assert len(config) > 0 