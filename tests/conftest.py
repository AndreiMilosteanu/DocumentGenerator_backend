import pytest
import pytest_asyncio
import asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from tortoise import Tortoise
from fastapi.testclient import TestClient
from unittest.mock import patch
import os
import tempfile

from main import app
from models import User, Document, Project, UserRole
from utils.auth import get_password_hash, create_access_token

# Test database configuration
TEST_DB_URL = "sqlite://test_db.sqlite3"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def initialize_db():
    """Initialize test database."""
    await Tortoise.init(
        db_url=TEST_DB_URL,
        modules={"models": ["models"]},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()

@pytest_asyncio.fixture
async def db():
    """Create a fresh database for each test."""
    # Database is already initialized by the session fixture
    # Just ensure we have a clean slate for each test
    yield
    # Clean up any test data here if needed

@pytest_asyncio.fixture
async def test_client():
    """Create a test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture
def sync_client():
    """Create a synchronous test client for the FastAPI app."""
    return TestClient(app)

@pytest_asyncio.fixture
async def test_user():
    """Create a test user."""
    user = await User.create(
        id=str(uuid.uuid4()),
        email="testuser@example.com",
        password_hash=get_password_hash("testpassword123"),
        role=UserRole.USER,
        is_active=True
    )
    return user

@pytest_asyncio.fixture
async def admin_user():
    """Create an admin test user."""
    user = await User.create(
        id=str(uuid.uuid4()),
        email="admin@example.com",
        password_hash=get_password_hash("adminpassword123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    return user

@pytest_asyncio.fixture
async def auth_headers(test_user):
    """Create authorization headers for a test user."""
    access_token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {access_token}"}

@pytest_asyncio.fixture
async def admin_headers(admin_user):
    """Create authorization headers for an admin user."""
    access_token = create_access_token(data={"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {access_token}"}

@pytest_asyncio.fixture
async def test_document(test_user):
    """Create a test document."""
    document = await Document.create(
        id=str(uuid.uuid4()),
        topic="Test Document Topic",
        thread_id="test_thread_123"
    )
    return document

@pytest_asyncio.fixture
async def test_project(test_user, test_document):
    """Create a test project."""
    project = await Project.create(
        id=str(uuid.uuid4()),
        name="Test Project",
        document=test_document,
        user=test_user
    )
    return project

@pytest.fixture
def mock_openai():
    """Mock OpenAI API calls."""
    with patch('openai.Client') as mock_client:
        # Mock common OpenAI responses
        mock_client.return_value.chat.completions.create.return_value.choices[0].message.content = "Mocked AI response"
        mock_client.return_value.files.create.return_value.id = "file_mock_123"
        yield mock_client

@pytest.fixture
def temp_file():
    """Create a temporary file for testing uploads."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(b"Test file content")
        tmp.flush()
        yield tmp.name
    os.unlink(tmp.name)

@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        "SECRET_KEY": "test-secret-key-for-testing-only",
        "DATABASE_URL": TEST_DB_URL,
        "OPENAI_API_KEY": "test-openai-key",
        "DEBUG": "True"
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars 