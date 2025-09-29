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
        # SUPABASE MIGRATION: Calculate leaderboard from test_submissions and user_performance
        # Since we don't have a materialized view, compute in Python
        
        # Get all users with their submission stats
        all_submissions_response = supabase.table('test_submissions').select('user_id, score, is_passed, time_taken_minutes, test_id').execute()
        
        if not all_submissions_response.data:
            return []
        
        # Group by user_id and calculate stats
        user_stats = {}
        for submission in all_submissions_response.data:
            user_id = submission.get('user_id')
            if not user_id:  # Skip anonymous submissions
                continue
            
            if user_id not in user_stats:
                user_stats[user_id] = {
                    'scores': [],
                    'tests': set(),
                    'total_attempts': 0,
                    'total_time': 0,
                    'tests_passed': 0
                }
            
            stats = user_stats[user_id]
            stats['scores'].append(submission.get('score', 0))
            stats['tests'].add(submission.get('test_id'))
            stats['total_attempts'] += 1
            stats['total_time'] += submission.get('time_taken_minutes', 0) or 0
            if submission.get('is_passed'):
                stats['tests_passed'] += 1
        
        # Convert to leaderboard entries
        leaderboard = []
        for user_id, stats in user_stats.items():
            # Get user details
            user_response = supabase.table('users').select('name, email').eq('id', user_id).execute()
            if not user_response.data:
                continue
            
            user = user_response.data[0]
            average_score = sum(stats['scores']) / len(stats['scores']) if stats['scores'] else 0
            
            leaderboard.append(LeaderboardEntry(
                user_id=str(user_id),
                name=user['name'],
                email=user['email'],
                tests_taken=len(stats['tests']),
                average_best_score=float(average_score),
                total_attempts=stats['total_attempts'],
                total_time_minutes=stats['total_time'],
                tests_passed=stats['tests_passed']
            ))
        
        # Sort by average score descending
        leaderboard.sort(key=lambda x: x.average_best_score, reverse=True)
        
        return leaderboard[:limit]
            
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
        # SUPABASE MIGRATION: Get recent activity using Supabase queries
        if test_id:
            # Check if user is test creator
            is_creator_response = supabase.table('tests').select('id').eq('id', test_id).eq('created_by', current_user.id).execute()
            
            if not is_creator_response.data:
                raise HTTPException(status_code=403, detail="Not authorized")
            
            # Get submissions for specific test
            submissions_response = supabase.table('test_submissions').select('*').eq('test_id', test_id).order('submitted_at', desc=True).limit(limit).execute()
        else:
            # Get all user's tests first
            user_tests_response = supabase.table('tests').select('id').eq('created_by', current_user.id).execute()
            
            if not user_tests_response.data:
                return []
            
            user_test_ids = [test['id'] for test in user_tests_response.data]
            
            # Get submissions for all user's tests
            submissions_response = supabase.table('test_submissions').select('*').in_('test_id', user_test_ids).order('submitted_at', desc=True).limit(limit).execute()
        
        if not submissions_response.data:
            return []
        
        # Enrich submission data with test titles and user names
        activities = []
        for submission in submissions_response.data:
            # Get test title
            test_response = supabase.table('tests').select('title').eq('id', submission['test_id']).execute()
            test_title = test_response.data[0]['title'] if test_response.data else 'Unknown Test'
            
            # Get user name if user_id exists
            user_name = 'Anonymous'
            if submission.get('user_id'):
                user_response = supabase.table('users').select('name').eq('id', submission['user_id']).execute()
                user_name = user_response.data[0]['name'] if user_response.data else 'Unknown'
            
            activities.append(RecentActivity(
                id=str(submission['id']),
                test_id=str(submission['test_id']),
                test_title=test_title,
                participant_name=submission.get('participant_name', 'Anonymous'),
                participant_email=submission.get('participant_email'),
                user_name=user_name,
                score=float(submission.get('score', 0)),
                is_passed=submission.get('is_passed', False),
                time_taken_minutes=submission.get('time_taken_minutes'),
                submitted_at=datetime.fromisoformat(submission['submitted_at'].replace('Z', '+00:00')) if isinstance(submission['submitted_at'], str) else submission['submitted_at']
            ))
        
        return activities
            
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
        # SUPABASE MIGRATION: Calculate user performance from test_submissions
        # Get all user's submissions
        user_submissions_response = supabase.table('test_submissions').select('*').eq('user_id', current_user.id).order('submitted_at', desc=True).execute()
        
        if not user_submissions_response.data:
            return []
        
        # Group submissions by test_id to calculate performance metrics
        test_performance = {}
        for submission in user_submissions_response.data:
            test_id = submission['test_id']
            
            if test_id not in test_performance:
                test_performance[test_id] = {
                    'scores': [],
                    'attempts': 0,
                    'total_time': 0,
                    'first_attempt': None,
                    'last_attempt': None
                }
            
            perf = test_performance[test_id]
            perf['scores'].append(submission.get('score', 0))
            perf['attempts'] += 1
            perf['total_time'] += submission.get('time_taken_minutes', 0) or 0
            
            submitted_at = submission.get('submitted_at')
            if isinstance(submitted_at, str):
                submitted_at = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
            
            if not perf['first_attempt'] or submitted_at < perf['first_attempt']:
                perf['first_attempt'] = submitted_at
            if not perf['last_attempt'] or submitted_at > perf['last_attempt']:
                perf['last_attempt'] = submitted_at
        
        # Convert to UserPerformance objects
        performance_list = []
        for test_id, perf in test_performance.items():
            # Get test title
            test_response = supabase.table('tests').select('title').eq('id', test_id).execute()
            test_title = test_response.data[0]['title'] if test_response.data else 'Unknown Test'
            
            best_score = max(perf['scores']) if perf['scores'] else 0
            
            performance_list.append(UserPerformance(
                user_id=str(current_user.id),
                user_name=current_user.name,
                test_id=str(test_id),
                test_title=test_title,
                best_score=float(best_score),
                attempts_count=perf['attempts'],
                total_time_minutes=perf['total_time'],
                first_attempt_at=perf['first_attempt'],
                last_attempt_at=perf['last_attempt']
            ))
        
        # Sort by last attempt date descending
        performance_list.sort(key=lambda x: x.last_attempt_at or datetime.min, reverse=True)
        
        return performance_list
            
    except Exception as e:
        logger.error(f"Error fetching user performance: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user performance")

