"""
Complete authentication system with database integration
"""

from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
import bcrypt
from app.database import get_supabase

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production-make-it-long-and-random")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Password hashing (using direct bcrypt for better compatibility)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

# Models
class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    created_at: datetime
    is_active: bool

class UserInDB(UserResponse):
    password_hash: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    email: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class SignupRequest(UserCreate):
    pass

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using direct bcrypt"""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Hash a password using direct bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

async def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Get user from database by email using Supabase"""
    try:
        client = get_supabase()
        response = client.table('users').select('id, name, email, password_hash, created_at, is_active').eq('email', email).eq('is_active', True).execute()
        
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return UserInDB(
                id=str(row['id']),
                name=row['name'],
                email=row['email'],
                password_hash=row['password_hash'],
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at'],
                is_active=row['is_active']
            )
    except Exception as e:
        print(f"Error getting user by email: {e}")
    return None

async def get_user_by_id(user_id: str) -> Optional[UserInDB]:
    """Get user from database by ID using Supabase"""
    try:
        client = get_supabase()
        response = client.table('users').select('id, name, email, password_hash, created_at, is_active').eq('id', user_id).eq('is_active', True).execute()
        
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return UserInDB(
                id=str(row['id']),
                name=row['name'],
                email=row['email'],
                password_hash=row['password_hash'],
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at'],
                is_active=row['is_active']
            )
    except Exception as e:
        print(f"Error getting user by ID: {e}")
    return None

async def create_user(user_data: UserCreate) -> UserInDB:
    """Create a new user in the database using Supabase"""
    # Hash the password
    password_hash = get_password_hash(user_data.password)
    
    try:
        client = get_supabase()
        
        # Check if user already exists
        existing_response = client.table('users').select('id').eq('email', user_data.email).execute()
        if existing_response.data and len(existing_response.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        insert_response = client.table('users').insert({
            'name': user_data.name,
            'email': user_data.email,
            'password_hash': password_hash
        }).execute()
        
        if insert_response.data and len(insert_response.data) > 0:
            row = insert_response.data[0]
            return UserInDB(
                id=str(row['id']),
                name=row['name'],
                email=row['email'],
                password_hash=row['password_hash'],
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at'],
                is_active=row['is_active']
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

async def authenticate_user(email: str, password: str) -> Optional[UserInDB]:
    """Authenticate a user"""
    user = await get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> UserResponse:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Require authentication - no fallback for production security
    if not credentials:
        raise credentials_exception
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user = await get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at,
        is_active=user.is_active
    )

# Optional: Development-only user for testing endpoints without auth
async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[UserResponse]:
    """Get current user, but allow None for development endpoints"""
    if not credentials:
        return None
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        
        user = await get_user_by_email(email=email)
        if user is None:
            return None
        
        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at,
            is_active=user.is_active
        )
    except JWTError:
        return None
