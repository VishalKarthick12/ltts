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
from app.database import get_supabase
from app.auth import get_current_user, UserResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["Analytics & Reporting"])

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: UserResponse = Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """
    Get comprehensive dashboard statistics
    """
    try:
        # SUPABASE MIGRATION: Replace pool operations with direct Supabase client calls
        # Get basic counts using separate Supabase queries
        
        # Count question banks created by user
        qb_response = supabase.table('question_banks').select('id', count='exact').eq('created_by', current_user.id).execute()
        total_question_banks = qb_response.count or 0
        
        # Count questions in user's question banks
        user_qb_ids = [qb['id'] for qb in qb_response.data] if qb_response.data else []
        total_questions = 0
        if user_qb_ids:
            questions_response = supabase.table('questions').select('id', count='exact').in_('question_bank_id', user_qb_ids).execute()
            total_questions = questions_response.count or 0
        
        # Count tests created by user
        tests_response = supabase.table('tests').select('id', count='exact').eq('created_by', current_user.id).execute()
        total_tests = tests_response.count or 0
        
        # Count submissions for user's tests
        user_test_ids = [t['id'] for t in tests_response.data] if tests_response.data else []
        total_submissions = 0
        if user_test_ids:
            submissions_response = supabase.table('test_submissions').select('id', count='exact').in_('test_id', user_test_ids).execute()
            total_submissions = submissions_response.count or 0
        
        # Count total active users
        users_response = supabase.table('users').select('id', count='exact').eq('is_active', True).execute()
        total_users = users_response.count or 0
        
        # SUPABASE: Get recent uploads with question counts
        recent_uploads_response = supabase.table('question_banks').select('*').eq('created_by', current_user.id).order('created_at', desc=True).limit(5).execute()
        
        recent_uploads_with_counts = []
        for qb in recent_uploads_response.data or []:
            # Get question count for each question bank
            q_count_response = supabase.table('questions').select('id', count='exact').eq('question_bank_id', qb['id']).execute()
            qb['question_count'] = q_count_response.count or 0
            recent_uploads_with_counts.append(qb)
        
        # SUPABASE: Get recent tests with analytics
        recent_tests_response = supabase.table('tests').select('*').eq('created_by', current_user.id).order('created_at', desc=True).limit(5).execute()
        
        recent_tests_with_analytics = []
        for test in recent_tests_response.data or []:
            # Get creator name
            creator_response = supabase.table('users').select('name').eq('id', test['created_by']).execute()
            test['creator_name'] = creator_response.data[0]['name'] if creator_response.data else 'Unknown'
            
            # Get test analytics
            analytics_response = supabase.table('test_analytics').select('*').eq('test_id', test['id']).execute()
            if analytics_response.data:
                analytics = analytics_response.data[0]
                test['total_submissions'] = analytics.get('total_submissions', 0)
                test['total_participants'] = analytics.get('total_participants', 0)
                test['average_score'] = analytics.get('average_score', 0)
                test['pass_rate'] = analytics.get('pass_rate', 0)
            else:
                test['total_submissions'] = 0
                test['total_participants'] = 0
                test['average_score'] = 0
                test['pass_rate'] = 0
            
            recent_tests_with_analytics.append(test)
        
        # SUPABASE: Get recent activity (simplified - just recent submissions for user's tests)
        recent_activity_data = []
        if user_test_ids:
            # Get recent submissions with test and user details
            recent_submissions_response = supabase.table('test_submissions').select('*').in_('test_id', user_test_ids).order('submitted_at', desc=True).limit(10).execute()
            
            for submission in recent_submissions_response.data or []:
                # Get test title
                test_response = supabase.table('tests').select('title').eq('id', submission['test_id']).execute()
                test_title = test_response.data[0]['title'] if test_response.data else 'Unknown Test'
                
                # Get user name if user_id exists
                user_name = 'Anonymous'
                if submission.get('user_id'):
                    user_response = supabase.table('users').select('name').eq('id', submission['user_id']).execute()
                    user_name = user_response.data[0]['name'] if user_response.data else 'Unknown'
                
                recent_activity_data.append({
                    'id': submission['id'],
                    'test_id': submission['test_id'],
                    'test_title': test_title,
                    'participant_name': submission.get('participant_name', 'Anonymous'),
                    'participant_email': submission.get('participant_email', ''),
                    'user_name': user_name,
                    'score': submission.get('score', 0),
                    'is_passed': submission.get('is_passed', False),
                    'time_taken_minutes': submission.get('time_taken_minutes', 0),
                    'submitted_at': submission.get('submitted_at')
                })
        
        # SUPABASE: Get top performers (simplified - top users by submission count)
        # Note: This is a simplified version since we can't do complex aggregations easily
        top_performers_data = []
        # For now, return empty list - this would need a more complex query or view
        # In production, consider creating a materialized view in Supabase for this
        
        return DashboardStats(
            total_question_banks=total_question_banks,
            total_questions=total_questions,
            total_tests=total_tests,
            total_submissions=total_submissions,
            total_users=total_users,
            recent_uploads=[
                QuestionBankResponse(
                    id=str(row['id']),
                    name=row['name'],
                    description=row['description'],
                    file_path=row['file_path'],
                    created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at'],
                    updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')) if isinstance(row['updated_at'], str) else row['updated_at'],
                    created_by=str(row['created_by']),
                    question_count=row['question_count']
                )
                for row in recent_uploads_with_counts
            ],
            recent_tests=[
                TestResponse(
                    id=str(row['id']),
                    title=row['title'],
                    description=row['description'],
                    question_bank_id=str(row['question_bank_id']),
                    question_bank_ids=row.get('question_bank_ids'),
                    question_bank_names=[],  # Simplified for now
                    created_by=str(row['created_by']),
                    creator_name=row['creator_name'],
                    num_questions=row['num_questions'],
                    time_limit_minutes=row['time_limit_minutes'],
                    difficulty_filter=row['difficulty_filter'],
                    category_filter=row['category_filter'],
                    is_active=row['is_active'],
                    is_public=row['is_public'],
                    scheduled_start=datetime.fromisoformat(row['scheduled_start'].replace('Z', '+00:00')) if row.get('scheduled_start') and isinstance(row['scheduled_start'], str) else row.get('scheduled_start'),
                    scheduled_end=datetime.fromisoformat(row['scheduled_end'].replace('Z', '+00:00')) if row.get('scheduled_end') and isinstance(row['scheduled_end'], str) else row.get('scheduled_end'),
                    max_attempts=row['max_attempts'],
                    pass_threshold=row['pass_threshold'],
                    created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at'],
                    updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')) if isinstance(row['updated_at'], str) else row['updated_at'],
                    test_link=f"/test/{row['id']}",
                    total_submissions=row['total_submissions'] or 0,
                    total_participants=row['total_participants'] or 0,
                    average_score=float(row['average_score']) if row['average_score'] else 0,
                    pass_rate=float(row['pass_rate']) if row['pass_rate'] else 0
                )
                for row in recent_tests_with_analytics
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
                    submitted_at=datetime.fromisoformat(row['submitted_at'].replace('Z', '+00:00')) if row.get('submitted_at') and isinstance(row['submitted_at'], str) else row.get('submitted_at')
                )
                for row in recent_activity_data
            ],
            top_performers=[]  # Simplified for now
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
    supabase=Depends(get_supabase)
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
    supabase=Depends(get_supabase)
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
    supabase=Depends(get_supabase)
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

