import pytest
import uuid
from unittest.mock import patch
from datetime import datetime, timedelta
from fastapi import HTTPException
from jose import jwt

from utils.auth import (
    get_password_hash, verify_password, create_access_token,
    get_user_by_email, create_user, UserCreate, get_current_active_user
)
from models import User, UserRole

class TestPasswordUtils:
    """Test password hashing and verification utilities."""
    
    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        # Hash should be different from original password
        assert hashed != password
        
        # Verification should work
        assert verify_password(password, hashed) is True
        
        # Wrong password should fail
        assert verify_password("wrong_password", hashed) is False
    
    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        password1 = "password123"
        password2 = "password456"
        
        hash1 = get_password_hash(password1)
        hash2 = get_password_hash(password2)
        
        assert hash1 != hash2

class TestTokenUtils:
    """Test JWT token creation and validation."""
    
    @patch('utils.auth.SECRET_KEY', 'test-secret-key')
    def test_create_access_token(self):
        """Test JWT token creation."""
        data = {"sub": "user123"}
        token = create_access_token(data)
        
        # Token should be a string
        assert isinstance(token, str)
        
        # Token should contain the data
        with patch('utils.auth.SECRET_KEY', 'test-secret-key'):
            decoded = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
            assert decoded["sub"] == "user123"
    
    @patch('utils.auth.SECRET_KEY', 'test-secret-key')
    def test_create_access_token_with_expiration(self):
        """Test JWT token creation with custom expiration."""
        data = {"sub": "user123"}
        expires_delta = timedelta(minutes=30)
        token = create_access_token(data, expires_delta)
        
        with patch('utils.auth.SECRET_KEY', 'test-secret-key'):
            decoded = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
            
            # Check that expiration is set
            assert "exp" in decoded
            # Expiration should be in the future
            assert decoded["exp"] > datetime.utcnow().timestamp()

class TestUserOperations:
    """Test user-related database operations."""
    
    @pytest.mark.asyncio
    async def test_get_user_by_email(self, db):
        """Test retrieving user by email."""
        # Create a test user
        user = await User.create(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        # Test successful retrieval
        found_user = await get_user_by_email("test@example.com")
        assert found_user is not None
        assert found_user.email == "test@example.com"
        
        # Test non-existent user
        not_found = await get_user_by_email("nonexistent@example.com")
        assert not_found is None
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, db):
        """Test successful user creation."""
        user_data = UserCreate(
            email="newuser@example.com",
            password="password123"
        )
        
        user = await create_user(user_data)
        
        assert user.email == "newuser@example.com"
        assert user.role == UserRole.USER
        assert user.is_active is True
        assert verify_password("password123", user.password_hash)
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, db):
        """Test user creation with duplicate email."""
        email = "duplicate@example.com"
        
        # Create first user
        await User.create(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        
        # Try to create user with same email
        user_data = UserCreate(email=email, password="password456")
        
        with pytest.raises(HTTPException) as exc_info:
            await create_user(user_data)
        
        assert exc_info.value.status_code == 400
        assert "already registered" in exc_info.value.detail.lower()

class TestAuthRoutes:
    """Test authentication API endpoints."""
    
    @pytest.mark.asyncio
    async def test_register_success(self, test_client, db):
        """Test successful user registration."""
        user_data = {
            "email": "register@example.com",
            "password": "password123"
        }
        
        response = await test_client.post("/auth/register", json=user_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "register@example.com"
        assert data["role"] == "user"
        assert "id" in data
        assert "created_at" in data
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, test_client, db, test_user):
        """Test registration with duplicate email."""
        user_data = {
            "email": test_user.email,
            "password": "password123"
        }
        
        response = await test_client.post("/auth/register", json=user_data)
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, test_client, db):
        """Test registration with invalid email."""
        user_data = {
            "email": "invalid-email",
            "password": "password123"
        }
        
        response = await test_client.post("/auth/register", json=user_data)
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_login_success(self, test_client, db, test_user):
        """Test successful login."""
        form_data = {
            "username": test_user.email,
            "password": "testpassword123"
        }
        
        response = await test_client.post(
            "/auth/login",
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["email"] == test_user.email
        assert data["user_id"] == str(test_user.id)
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, test_client, db, test_user):
        """Test login with wrong password."""
        form_data = {
            "username": test_user.email,
            "password": "wrongpassword"
        }
        
        response = await test_client.post(
            "/auth/login",
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, test_client, db):
        """Test login with non-existent user."""
        form_data = {
            "username": "nonexistent@example.com",
            "password": "password123"
        }
        
        response = await test_client.post(
            "/auth/login",
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_get_current_user(self, test_client, db, test_user, auth_headers):
        """Test getting current user information."""
        response = await test_client.get("/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == str(test_user.id)
        assert data["role"] == test_user.role
    
    @pytest.mark.asyncio
    async def test_get_current_user_unauthorized(self, test_client, db):
        """Test getting current user without authentication."""
        response = await test_client.get("/auth/me")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, test_client, db):
        """Test getting current user with invalid token."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = await test_client.get("/auth/me", headers=headers)
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_create_admin_first_user(self, test_client, db):
        """Test creating admin user when no users exist."""
        user_data = {
            "email": "admin@example.com",
            "password": "adminpassword123"
        }
        
        response = await test_client.post("/auth/create-admin", json=user_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@example.com"
        assert data["role"] == "admin"
    
    @pytest.mark.asyncio
    async def test_create_admin_users_exist(self, test_client, db, test_user):
        """Test creating admin user when users already exist."""
        user_data = {
            "email": "admin2@example.com",
            "password": "adminpassword123"
        }
        
        response = await test_client.post("/auth/create-admin", json=user_data)
        
        assert response.status_code == 403
        assert "only allowed during initial setup" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_auth_debug_endpoint(self, test_client, db):
        """Test the auth debug endpoint."""
        response = await test_client.get("/auth/debug")
        
        assert response.status_code == 200
        data = response.json()
        assert "headers" in data
        assert "auth_config" in data
        assert "server_time" in data
        assert data["auth_config"]["algorithm"] == "HS256"

class TestAuthDependencies:
    """Test authentication dependency functions."""
    
    @pytest.mark.asyncio
    async def test_get_current_active_user_valid(self, db, test_user):
        """Test getting current active user with valid token."""
        token = create_access_token(data={"sub": str(test_user.id)})
        
        # Mock the token extraction process
        with patch('utils.auth.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user
            current_user = await get_current_active_user(test_user)
            assert current_user.id == test_user.id
            assert current_user.is_active is True
    
    @pytest.mark.asyncio
    async def test_get_current_active_user_inactive(self, db):
        """Test getting current user when user is inactive."""
        inactive_user = await User.create(
            id=str(uuid.uuid4()),
            email="inactive@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER,
            is_active=False
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(inactive_user)
        
        assert exc_info.value.status_code == 400
        assert "Inactive user" in exc_info.value.detail 