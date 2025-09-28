"""
Complete authentication endpoints with signup and login
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer

from app.auth import (
    authenticate_user, create_access_token, get_current_user, create_user,
    ACCESS_TOKEN_EXPIRE_MINUTES, Token, LoginRequest, SignupRequest, UserResponse
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer()

@router.post("/signup", response_model=Token)
async def signup(signup_data: SignupRequest):
    """
    User registration endpoint
    """
    try:
        # Create new user
        user = await create_user(signup_data)
        
        # Generate access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        
        user_response = UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at,
            is_active=user.is_active
        )
        
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "user": user_response
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}"
        )

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest):
    """
    User login endpoint
    """
    user = await authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    user_response = UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        created_at=user.created_at,
        is_active=user.is_active
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": user_response
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: UserResponse = Depends(get_current_user)):
    """
    Get current user information
    """
    return current_user

@router.post("/test-token")
async def test_token(current_user: UserResponse = Depends(get_current_user)):
    """
    Test endpoint to verify token is working
    """
    return {"message": f"Hello {current_user.name}, your token is valid!", "user": current_user}

@router.post("/logout")
async def logout(current_user: UserResponse = Depends(get_current_user)):
    """
    Logout endpoint (client should discard the token)
    """
    return {"message": "Successfully logged out. Please discard your token."}
