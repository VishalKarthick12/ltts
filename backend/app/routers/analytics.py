"""
Analytics and Reporting API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta

from app.models import (
    DashboardStats, LeaderboardEntry, RecentActivity, UserPerformance,
    TestAnalytics, QuestionBankResponse, TestResponse
)
from app.database import get_db_pool
from app.auth import get_current_user, UserResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["Analytics & Reporting"])

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    """
    Get comprehensive dashboard statistics
    """
    try:
        async with pool.acquire() as conn:
            # Get basic counts
            stats = await conn.fetchrow("""
                SELECT 
                    (SELECT COUNT(*) FROM question_banks WHERE created_by = $1) as total_question_banks,
                    (SELECT COUNT(*) FROM questions q 
                     JOIN question_banks qb ON q.question_bank_id = qb.id 
                     WHERE qb.created_by = $1) as total_questions,
                    (SELECT COUNT(*) FROM tests WHERE created_by = $1) as total_tests,
                    (SELECT COUNT(*) FROM test_submissions ts 
                     JOIN tests t ON ts.test_id = t.id 
                     WHERE t.created_by = $1) as total_submissions,
                    (SELECT COUNT(*) FROM users WHERE is_active = true) as total_users
            """, current_user.id)
            
            # Get recent uploads
            recent_uploads = await conn.fetch("""
                SELECT 
                    qb.id, qb.name, qb.description, qb.file_path,
                    qb.created_at, qb.updated_at, qb.created_by,
                    COUNT(q.id) as question_count
                FROM question_banks qb
                LEFT JOIN questions q ON qb.id = q.question_bank_id
                WHERE qb.created_by = $1
                GROUP BY qb.id, qb.name, qb.description, qb.file_path,
                         qb.created_at, qb.updated_at, qb.created_by
                ORDER BY qb.created_at DESC
                LIMIT 5
            """, current_user.id)
            
            # Get recent tests
            recent_tests = await conn.fetch("""
                SELECT 
                    t.*,
                    u.name as creator_name,
                    ta.total_submissions,
                    ta.total_participants,
                    ta.average_score,
                    ta.pass_rate
                FROM tests t
                LEFT JOIN users u ON t.created_by = u.id
                LEFT JOIN test_analytics ta ON t.id = ta.test_id
                WHERE t.created_by = $1
                ORDER BY t.created_at DESC
                LIMIT 5
            """, current_user.id)
            
            # Get recent activity
            recent_activity = await conn.fetch("""
                SELECT * FROM recent_test_activity
                WHERE test_id IN (SELECT id FROM tests WHERE created_by = $1)
                LIMIT 10
            """, current_user.id)
            
            # Get top performers
            top_performers = await conn.fetch("""
                SELECT * FROM user_leaderboard
                LIMIT 10
            """)
            
            return DashboardStats(
                total_question_banks=stats['total_question_banks'],
                total_questions=stats['total_questions'],
                total_tests=stats['total_tests'],
                total_submissions=stats['total_submissions'],
                total_users=stats['total_users'],
                recent_uploads=[
                    QuestionBankResponse(
                        id=str(row['id']),
                        name=row['name'],
                        description=row['description'],
                        file_path=row['file_path'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        created_by=str(row['created_by']),
                        question_count=row['question_count']
                    )
                    for row in recent_uploads
                ],
                recent_tests=[
                    TestResponse(
                        id=str(row['id']),
                        title=row['title'],
                        description=row['description'],
                        question_bank_id=str(row['question_bank_id']),
                        created_by=str(row['created_by']),
                        creator_name=row['creator_name'],
                        num_questions=row['num_questions'],
                        time_limit_minutes=row['time_limit_minutes'],
                        difficulty_filter=row['difficulty_filter'],
                        category_filter=row['category_filter'],
                        is_active=row['is_active'],
                        is_public=row['is_public'],
                        scheduled_start=row['scheduled_start'],
                        scheduled_end=row['scheduled_end'],
                        max_attempts=row['max_attempts'],
                        pass_threshold=row['pass_threshold'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        test_link=f"/test/{row['id']}",
                        total_submissions=row['total_submissions'] or 0,
                        total_participants=row['total_participants'] or 0,
                        average_score=float(row['average_score']) if row['average_score'] else 0,
                        pass_rate=float(row['pass_rate']) if row['pass_rate'] else 0
                    )
                    for row in recent_tests
                ],
                recent_activity=[
                    RecentActivity(
                        id=str(row['id']),
                        test_id=str(row['test_id']),
                        test_title=row['test_title'],
                        participant_name=row['participant_name'],
                        participant_email=row['participant_email'],
                        user_name=row['user_name'],
                        score=float(row['score']),
                        is_passed=row['is_passed'],
                        time_taken_minutes=row['time_taken_minutes'],
                        submitted_at=row['submitted_at']
                    )
                    for row in recent_activity
                ],
                top_performers=[
                    LeaderboardEntry(
                        user_id=str(row['user_id']),
                        name=row['name'],
                        email=row['email'],
                        tests_taken=row['tests_taken'],
                        average_best_score=float(row['average_best_score']),
                        total_attempts=row['total_attempts'],
                        total_time_minutes=row['total_time_minutes'],
                        tests_passed=row['tests_passed']
                    )
                    for row in top_performers
                ]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        raise HTTPException(status_code=500, detail="Error fetching dashboard stats")

@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    limit: int = Query(20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    """
    Get user leaderboard
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM user_leaderboard
                LIMIT $1
            """, limit)
            
            return [
                LeaderboardEntry(
                    user_id=str(row['user_id']),
                    name=row['name'],
                    email=row['email'],
                    tests_taken=row['tests_taken'],
                    average_best_score=float(row['average_best_score']),
                    total_attempts=row['total_attempts'],
                    total_time_minutes=row['total_time_minutes'],
                    tests_passed=row['tests_passed']
                )
                for row in rows
            ]
            
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Error fetching leaderboard")

@router.get("/recent-activity", response_model=List[RecentActivity])
async def get_recent_activity(
    limit: int = Query(20, ge=1, le=100),
    test_id: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    """
    Get recent test activity
    """
    try:
        async with pool.acquire() as conn:
            if test_id:
                # Check if user is test creator
                is_creator = await conn.fetchval("""
                    SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1 AND created_by = $2)
                """, test_id, current_user.id)
                
                if not is_creator:
                    raise HTTPException(status_code=403, detail="Not authorized")
                
                query = """
                    SELECT * FROM recent_test_activity
                    WHERE test_id = $1
                    LIMIT $2
                """
                params = [test_id, limit]
            else:
                # Show activity for all user's tests
                query = """
                    SELECT * FROM recent_test_activity
                    WHERE test_id IN (SELECT id FROM tests WHERE created_by = $1)
                    LIMIT $2
                """
                params = [current_user.id, limit]
            
            rows = await conn.fetch(query, *params)
            
            return [
                RecentActivity(
                    id=str(row['id']),
                    test_id=str(row['test_id']),
                    test_title=row['test_title'],
                    participant_name=row['participant_name'],
                    participant_email=row['participant_email'],
                    user_name=row['user_name'],
                    score=float(row['score']),
                    is_passed=row['is_passed'],
                    time_taken_minutes=row['time_taken_minutes'],
                    submitted_at=row['submitted_at']
                )
                for row in rows
            ]
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching recent activity: {e}")
        raise HTTPException(status_code=500, detail="Error fetching recent activity")

@router.get("/user-performance", response_model=List[UserPerformance])
async def get_user_performance(
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    """
    Get current user's performance across all tests
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    up.*,
                    t.title as test_title
                FROM user_performance up
                JOIN tests t ON up.test_id = t.id
                WHERE up.user_id = $1
                ORDER BY up.last_attempt_at DESC
            """, current_user.id)
            
            return [
                UserPerformance(
                    user_id=str(row['user_id']),
                    user_name=current_user.name,
                    test_id=str(row['test_id']),
                    test_title=row['test_title'],
                    best_score=float(row['best_score']),
                    attempts_count=row['attempts_count'],
                    total_time_minutes=row['total_time_minutes'],
                    first_attempt_at=row['first_attempt_at'],
                    last_attempt_at=row['last_attempt_at']
                )
                for row in rows
            ]
            
    except Exception as e:
        logger.error(f"Error fetching user performance: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user performance")

