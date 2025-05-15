from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from utils.auth import (
    UserCreate, UserLogin, Token, UserResponse,
    get_user_by_email, create_user, verify_password,
    create_access_token, get_current_active_user, 
    get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
)
from models import User, UserRole
import uuid
import logging

# Configure logging
logger = logging.getLogger("auth")
logger.setLevel(logging.DEBUG)

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate):
    """
    Register a new user with email and password
    """
    logger.debug(f"Registration attempt for email: {user_data.email}")
    
    try:
        user = await create_user(user_data)
        logger.info(f"User registered successfully: {user.email}")
        
        return {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at
        }
    except HTTPException as e:
        logger.error(f"Registration failed: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during registration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login with username (email) and password to get a JWT token
    """
    logger.debug(f"Login attempt for username: {form_data.username}")
    
    try:
        # Get user by email
        user = await get_user_by_email(form_data.username)
        if not user:
            logger.warning(f"Login failed: User not found: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(form_data.password, user.password_hash):
            logger.warning(f"Login failed: Invalid password for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Update last login time
        user.last_login = datetime.utcnow()
        await user.save()
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )
        
        logger.info(f"Login successful for user: {user.email}")
        # Return token using TokenModel to ensure validation
        token_response = Token(
            access_token=access_token,
            token_type="bearer",
            user_id=str(user.id),
            email=user.email,
            role=user.role
        )
        
        return token_response.dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Get current user information
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "role": current_user.role,
        "created_at": current_user.created_at
    }

@router.post("/create-admin", response_model=UserResponse)
async def create_admin_user(user_data: UserCreate):
    """
    Create an admin user - this endpoint should be secured in production
    """
    logger.debug(f"Admin creation attempt for email: {user_data.email}")
    
    try:
        # Check if any users exist - only allow admin creation if no users
        user_count = await User.all().count()
        if user_count > 0:
            # In production, you'd want a better security mechanism here
            # This is just a simple example to allow initial admin creation
            logger.warning(f"Admin creation denied: Users already exist")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin creation is only allowed during initial setup"
            )
        
        # Create a user with admin role
        user = await User.create(
            id=str(uuid.uuid4()),
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            role=UserRole.ADMIN
        )
        
        logger.info(f"Admin user created successfully: {user.email}")
        return {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during admin creation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Admin creation failed: {str(e)}"
        )

# Add a debug endpoint to help troubleshoot authentication issues
@router.get("/debug")
async def auth_debug(request: Request):
    """
    Debug endpoint to help troubleshoot authentication issues
    """
    logger.debug("Auth debug endpoint called")
    
    headers = dict(request.headers)
    # Remove sensitive information
    if "authorization" in headers:
        headers["authorization"] = headers["authorization"][:15] + "..."
    
    return {
        "headers": headers,
        "auth_config": {
            "token_url": "auth/login",
            "algorithm": "HS256",
            "expire_minutes": ACCESS_TOKEN_EXPIRE_MINUTES
        },
        "server_time": datetime.now().isoformat()
    } 