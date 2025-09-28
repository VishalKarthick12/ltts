"""
Test Sharing API endpoints - handles test invites and public links
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
import uuid
import secrets
from datetime import datetime, timedelta, timezone

from app.models import TestResponse
from app.database import get_supabase
from app.auth import get_current_user, get_current_user_optional, UserResponse
from pydantic import BaseModel, EmailStr, Field
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/test-sharing", tags=["Test Sharing"])

# Sharing models
class CreateInviteRequest(BaseModel):
    test_id: str
    invite_emails: List[EmailStr] = Field(..., min_items=1, max_items=50)
    message: Optional[str] = Field(None, max_length=500)
    expires_in_days: Optional[int] = Field(7, ge=1, le=30)

class CreatePublicLinkRequest(BaseModel):
    test_id: str
    max_uses: Optional[int] = Field(None, ge=1, le=1000)
    expires_in_days: Optional[int] = Field(30, ge=1, le=365)

class InviteResponse(BaseModel):
    id: str
    test_id: str
    test_title: str
    invited_email: str
    invite_token: str
    invite_url: str
    status: str
    expires_at: Optional[datetime]
    created_at: datetime

class PublicLinkResponse(BaseModel):
    id: str
    test_id: str
    test_title: str
    link_token: str
    public_url: str
    is_active: bool
    max_uses: Optional[int]
    current_uses: int
    expires_at: Optional[datetime]
    created_at: datetime

class SharedTestResponse(BaseModel):
    invite_id: str
    test_id: str
    test_title: str
    test_description: Optional[str]
    creator_name: str
    creator_email: str
    num_questions: int
    time_limit_minutes: Optional[int]
    pass_threshold: float
    invite_message: Optional[str]
    invited_at: datetime
    invite_expires_at: Optional[datetime]
    can_take: bool

@router.post("/invite", response_model=List[InviteResponse])
async def create_test_invites(
    invite_data: CreateInviteRequest,
    current_user: UserResponse = Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """
    Create invites for specific users to take a test
    """
    try:
        async with pool.acquire() as conn:
            # Verify test exists and user is creator
            test_row = await conn.fetchrow("""
                SELECT title, created_by FROM tests 
                WHERE id = $1 AND created_by = $2
            """, invite_data.test_id, current_user.id)
            
            if not test_row:
                raise HTTPException(status_code=404, detail="Test not found or not authorized")
            
            # Calculate expiration
            expires_at = None
            if invite_data.expires_in_days:
                expires_at = datetime.now(timezone.utc) + timedelta(days=invite_data.expires_in_days)
            
            invites = []
            for email in invite_data.invite_emails:
                # Check if user exists
                invited_user = await conn.fetchrow("""
                    SELECT id FROM users WHERE email = $1 AND is_active = true
                """, email)
                
                # Generate unique invite token
                invite_token = secrets.token_urlsafe(32)
                invite_id = str(uuid.uuid4())
                
                # Create invite
                invite_row = await conn.fetchrow("""
                    INSERT INTO test_invites (
                        id, test_id, created_by, invited_user_id, invited_email,
                        invite_token, invite_type, message, expires_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING *
                """, 
                    invite_id, invite_data.test_id, current_user.id,
                    invited_user['id'] if invited_user else None, email,
                    invite_token, 'email', invite_data.message, expires_at
                )
                
                invites.append(InviteResponse(
                    id=str(invite_row['id']),
                    test_id=str(invite_row['test_id']),
                    test_title=test_row['title'],
                    invited_email=invite_row['invited_email'],
                    invite_token=invite_row['invite_token'],
                    invite_url=f"/test/invite/{invite_row['invite_token']}",
                    status=invite_row['status'],
                    expires_at=invite_row['expires_at'],
                    created_at=invite_row['created_at']
                ))
            
            return invites
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating invites: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating invites: {str(e)}")

@router.post("/public-link", response_model=PublicLinkResponse)
async def create_public_link(
    link_data: CreatePublicLinkRequest,
    current_user: UserResponse = Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """
    Create a public shareable link for a test
    """
    try:
        async with pool.acquire() as conn:
            # Verify test exists and user is creator
            test_row = await conn.fetchrow("""
                SELECT title, created_by FROM tests 
                WHERE id = $1 AND created_by = $2
            """, link_data.test_id, current_user.id)
            
            if not test_row:
                raise HTTPException(status_code=404, detail="Test not found or not authorized")
            
            # Calculate expiration
            expires_at = None
            if link_data.expires_in_days:
                expires_at = datetime.now(timezone.utc) + timedelta(days=link_data.expires_in_days)
            
            # Generate unique link token
            link_token = secrets.token_urlsafe(16)
            link_id = str(uuid.uuid4())
            
            # Create public link
            link_row = await conn.fetchrow("""
                INSERT INTO test_public_links (
                    id, test_id, created_by, link_token, max_uses, expires_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
            """, 
                link_id, link_data.test_id, current_user.id,
                link_token, link_data.max_uses, expires_at
            )
            
            return PublicLinkResponse(
                id=str(link_row['id']),
                test_id=str(link_row['test_id']),
                test_title=test_row['title'],
                link_token=link_row['link_token'],
                public_url=f"/test/public/{link_row['link_token']}",
                is_active=link_row['is_active'],
                max_uses=link_row['max_uses'],
                current_uses=link_row['current_uses'],
                expires_at=link_row['expires_at'],
                created_at=link_row['created_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating public link: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating public link: {str(e)}")

@router.get("/invite/{invite_token}", response_model=SharedTestResponse)
async def get_invite_details(
    invite_token: str,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    supabase=Depends(get_supabase)
):
    """
    Get test details from invite token
    """
    try:
        async with pool.acquire() as conn:
            # Get invite details
            invite = await conn.fetchrow("""
                SELECT * FROM shared_tests_with_me
                WHERE invite_token = $1
            """, invite_token)
            
            if not invite:
                raise HTTPException(status_code=404, detail="Invite not found or expired")
            
            # Check if current user is the invited user (if authenticated)
            can_take = True
            if current_user:
                # Check if this user was specifically invited
                user_invite = await conn.fetchrow("""
                    SELECT * FROM test_invites 
                    WHERE invite_token = $1 
                    AND (invited_user_id = $2 OR invited_email = $3)
                """, invite_token, current_user.id, current_user.email)
                
                can_take = user_invite is not None
            
            return SharedTestResponse(
                invite_id=str(invite['invite_id']),
                test_id=str(invite['test_id']),
                test_title=invite['title'],
                test_description=invite['description'],
                creator_name=invite['creator_name'],
                creator_email=invite['creator_email'],
                num_questions=invite['num_questions'],
                time_limit_minutes=invite['time_limit_minutes'],
                pass_threshold=invite['pass_threshold'],
                invite_message=invite['message'],
                invited_at=invite['invited_at'],
                invite_expires_at=invite['invite_expires_at'],
                can_take=can_take
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting invite details: {e}")
        raise HTTPException(status_code=500, detail="Error getting invite details")

@router.get("/public/{link_token}")
async def get_public_test(
    link_token: str,
    request: Request,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    supabase=Depends(get_supabase)
):
    """
    Access test via public link
    """
    try:
        async with pool.acquire() as conn:
            # Get public link details
            link = await conn.fetchrow("""
                SELECT tpl.*, t.title, t.description, t.num_questions, 
                       t.time_limit_minutes, t.pass_threshold, t.is_active
                FROM test_public_links tpl
                JOIN tests t ON tpl.test_id = t.id
                WHERE tpl.link_token = $1 AND tpl.is_active = true
                AND (tpl.expires_at IS NULL OR tpl.expires_at > NOW())
            """, link_token)
            
            if not link:
                raise HTTPException(status_code=404, detail="Link not found or expired")
            
            # Check usage limits
            if link['max_uses'] and link['current_uses'] >= link['max_uses']:
                raise HTTPException(status_code=403, detail="Link usage limit exceeded")
            
            # Record link access
            client_ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "")
            
            await conn.execute("""
                INSERT INTO test_link_usage (link_id, user_id, ip_address, user_agent)
                VALUES ($1, $2, $3, $4)
            """, link['id'], current_user.id if current_user else None, client_ip, user_agent)
            
            # Return test details (redirect to test page)
            return {
                "test_id": str(link['test_id']),
                "title": link['title'],
                "description": link['description'],
                "num_questions": link['num_questions'],
                "time_limit_minutes": link['time_limit_minutes'],
                "pass_threshold": link['pass_threshold'],
                "is_active": link['is_active'],
                "redirect_url": f"/test/{link['test_id']}"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accessing public link: {e}")
        raise HTTPException(status_code=500, detail="Error accessing public link")

@router.get("/my-shared-tests", response_model=List[SharedTestResponse])
async def get_my_shared_tests(
    current_user: UserResponse = Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """
    Get tests shared with the current user
    """
    try:
        async with pool.acquire() as conn:
            shared_tests = await conn.fetch("""
                SELECT * FROM shared_tests_with_me
                WHERE invited_user_id = $1 OR invited_email = $2
                ORDER BY invited_at DESC
            """, current_user.id, current_user.email)
            
            return [
                SharedTestResponse(
                    invite_id=str(test['invite_id']),
                    test_id=str(test['test_id']),
                    test_title=test['title'],
                    test_description=test['description'],
                    creator_name=test['creator_name'],
                    creator_email=test['creator_email'],
                    num_questions=test['num_questions'],
                    time_limit_minutes=test['time_limit_minutes'],
                    pass_threshold=test['pass_threshold'],
                    invite_message=test['message'],
                    invited_at=test['invited_at'],
                    invite_expires_at=test['invite_expires_at'],
                    can_take=True
                )
                for test in shared_tests
            ]
            
    except Exception as e:
        logger.error(f"Error getting shared tests: {e}")
        raise HTTPException(status_code=500, detail="Error getting shared tests")

@router.post("/invite/{invite_token}/accept")
async def accept_invite(
    invite_token: str,
    current_user: UserResponse = Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """
    Accept a test invite
    """
    try:
        async with pool.acquire() as conn:
            # Update invite status
            result = await conn.execute("""
                UPDATE test_invites 
                SET status = 'accepted', accepted_at = NOW()
                WHERE invite_token = $1 
                AND (invited_user_id = $2 OR invited_email = $3)
                AND status = 'pending'
            """, invite_token, current_user.id, current_user.email)
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Invite not found or already processed")
            
            return {"message": "Invite accepted successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting invite: {e}")
        raise HTTPException(status_code=500, detail="Error accepting invite")

@router.get("/test/{test_id}/sharing-info")
async def get_test_sharing_info(
    test_id: str,
    current_user: UserResponse = Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """
    Get sharing information for a test (invites and public links)
    """
    try:
        async with pool.acquire() as conn:
            # Verify user is test creator
            is_creator = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1 AND created_by = $2)
            """, test_id, current_user.id)
            
            if not is_creator:
                raise HTTPException(status_code=403, detail="Not authorized")
            
            # Get invites
            invites = await conn.fetch("""
                SELECT ti.*, u.name as invited_user_name
                FROM test_invites ti
                LEFT JOIN users u ON ti.invited_user_id = u.id
                WHERE ti.test_id = $1
                ORDER BY ti.created_at DESC
            """, test_id)
            
            # Get public links
            public_links = await conn.fetch("""
                SELECT * FROM test_public_links
                WHERE test_id = $1 AND is_active = true
                ORDER BY created_at DESC
            """, test_id)
            
            return {
                "test_id": test_id,
                "invites": [
                    {
                        "id": str(invite['id']),
                        "invited_email": invite['invited_email'],
                        "invited_user_name": invite['invited_user_name'],
                        "status": invite['status'],
                        "invite_url": f"/test/invite/{invite['invite_token']}",
                        "expires_at": invite['expires_at'],
                        "created_at": invite['created_at']
                    }
                    for invite in invites
                ],
                "public_links": [
                    {
                        "id": str(link['id']),
                        "link_token": link['link_token'],
                        "public_url": f"/test/public/{link['link_token']}",
                        "max_uses": link['max_uses'],
                        "current_uses": link['current_uses'],
                        "expires_at": link['expires_at'],
                        "created_at": link['created_at']
                    }
                    for link in public_links
                ]
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sharing info: {e}")
        raise HTTPException(status_code=500, detail="Error getting sharing info")

