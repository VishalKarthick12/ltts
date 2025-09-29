"""
Test Taking API endpoints - handles the complete test-taking flow
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
import uuid
import secrets
from datetime import datetime, timedelta, timezone
import json

from app.models import (
    TestSessionStart, TestSessionResponse, TestSessionStatus,
    SaveAnswerRequest, SaveAnswerResponse, TestDetailsResponse,
    TestSubmissionRequest, TestSubmissionResponse, TestQuestionResponse
)
from app.database import get_supabase
from app.auth import get_current_user_optional, UserResponse, get_password_hash
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/test-taking", tags=["Test Taking"])

@router.post("/{test_id}/start", response_model=TestSessionResponse)
async def start_test_session(
    test_id: str,
    session_data: TestSessionStart,
    request: Request,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    supabase=Depends(get_supabase)
):
    """
    Start a new test session with timer and session tracking
    """
    try:
        # SUPABASE MIGRATION: Replace pool.acquire() with direct Supabase client calls
        # Get test details using Supabase
        test_response = supabase.table('tests').select('*').eq('id', test_id).eq('is_active', True).execute()
        
        if not test_response.data:
            raise HTTPException(status_code=404, detail="Test not found or inactive")
        
        test_row = test_response.data[0]
        
        # Check if test is accessible
        now = datetime.now(timezone.utc)
        scheduled_start = test_row.get('scheduled_start')
        scheduled_end = test_row.get('scheduled_end')
        
        if scheduled_start:
            if isinstance(scheduled_start, str):
                scheduled_start = datetime.fromisoformat(scheduled_start.replace('Z', '+00:00'))
            if now < scheduled_start:
                raise HTTPException(status_code=403, detail="Test has not started yet")
                
        if scheduled_end:
            if isinstance(scheduled_end, str):
                scheduled_end = datetime.fromisoformat(scheduled_end.replace('Z', '+00:00'))
            if now > scheduled_end:
                raise HTTPException(status_code=403, detail="Test has ended")
        
        # SUPABASE: Resolve or create user if possible
        resolved_user_id = None
        if current_user:
            resolved_user_id = current_user.id
        elif session_data.participant_email:
            # Try to find existing user by email using Supabase
            existing_user_response = supabase.table('users').select('id').eq('email', session_data.participant_email).eq('is_active', True).execute()
            
            if existing_user_response.data:
                resolved_user_id = existing_user_response.data[0]['id']
            else:
                # Create lightweight user record using Supabase
                try:
                    password_hash = get_password_hash(secrets.token_urlsafe(16))
                    new_user_response = supabase.table('users').insert({
                        'name': session_data.participant_name,
                        'email': session_data.participant_email,
                        'password_hash': password_hash,
                        'is_active': True
                    }).execute()
                    
                    resolved_user_id = new_user_response.data[0]['id'] if new_user_response.data else None
                except Exception:
                    # Fallback to anonymous if user table constraints prevent creation
                    resolved_user_id = None

        # SUPABASE: Validate invite token if provided
        if getattr(session_data, 'invite_token', None):
            # Check public links
            public_link_response = supabase.table('test_public_links').select('id').eq('link_token', session_data.invite_token).eq('test_id', test_id).eq('is_active', True).execute()
            
            # Check test invites  
            invite_response = supabase.table('test_invites').select('id').eq('invite_token', session_data.invite_token).eq('test_id', test_id).eq('status', 'pending').execute()
            
            # TODO: Add expiry checking for invites (requires date comparison)
            token_valid = bool(public_link_response.data or invite_response.data)
            
            if not token_valid:
                raise HTTPException(status_code=403, detail="Invalid or expired invite token")

        # SUPABASE: Check user attempts if authenticated
        if resolved_user_id:
            attempts_response = supabase.table('user_performance').select('attempts_count').eq('user_id', resolved_user_id).eq('test_id', test_id).execute()
            
            attempts = attempts_response.data[0]['attempts_count'] if attempts_response.data else 0
            
            if attempts and attempts >= test_row['max_attempts']:
                raise HTTPException(status_code=403, detail="Maximum attempts exceeded")
            
            # SUPABASE: Check for active session
            # Note: Supabase doesn't have NOW() function, so we'll filter in Python
            active_session_response = supabase.table('test_sessions').select('id, session_token, expires_at, started_at').eq('test_id', test_id).eq('user_id', resolved_user_id).eq('is_active', True).execute()
            
            active_session = None
            if active_session_response.data:
                for session in active_session_response.data:
                    expires_at_str = session['expires_at']
                    if isinstance(expires_at_str, str):
                        expires_at_dt = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                        if expires_at_dt > now:
                            active_session = session
                            break
            
            if active_session:
                # Return existing session
                expires_at_dt = datetime.fromisoformat(active_session['expires_at'].replace('Z', '+00:00')) if isinstance(active_session['expires_at'], str) else active_session['expires_at']
                minutes_remaining = (expires_at_dt - now).total_seconds() / 60
                started_at_dt = datetime.fromisoformat(active_session['started_at'].replace('Z', '+00:00')) if isinstance(active_session['started_at'], str) else active_session['started_at']
                
                return TestSessionResponse(
                    session_id=str(active_session['id']),
                    session_token=active_session['session_token'],
                    test_id=test_id,
                    test_title=test_row['title'],
                    participant_name=session_data.participant_name,
                    started_at=started_at_dt,
                    expires_at=expires_at_dt,
                    time_limit_minutes=test_row['time_limit_minutes'],
                    total_questions=test_row['num_questions'],
                    current_question=1,
                    minutes_remaining=max(0, minutes_remaining)
                )
        
        # Calculate expiration time
        if test_row['time_limit_minutes']:
            expires_at = now + timedelta(minutes=test_row['time_limit_minutes'])
        else:
            expires_at = now + timedelta(hours=24)  # Default 24 hour limit
        
        # Create new session
        session_token = secrets.token_urlsafe(32)
        session_id = str(uuid.uuid4())
        
        # Get client info
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        
        # SUPABASE: Insert new test session
        session_data_insert = {
            'id': session_id,
            'test_id': test_id,
            'user_id': resolved_user_id,
            'participant_name': session_data.participant_name,
            'participant_email': session_data.participant_email,
            'session_token': session_token,
            'started_at': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'ip_address': client_ip,
            'user_agent': user_agent,
            'invite_token': getattr(session_data, 'invite_token', None),
            'is_active': True
        }
        
        session_response = supabase.table('test_sessions').insert(session_data_insert).execute()
        
        if not session_response.data:
            raise HTTPException(status_code=500, detail="Failed to create test session")
        
        session_row = session_response.data[0]
        minutes_remaining = (expires_at - now).total_seconds() / 60
        
        return TestSessionResponse(
            session_id=str(session_row['id']),
            session_token=session_row['session_token'],
            test_id=test_id,
            test_title=test_row['title'],
            participant_name=session_row['participant_name'],
            started_at=now,
            expires_at=expires_at,
            time_limit_minutes=test_row['time_limit_minutes'],
            total_questions=test_row['num_questions'],
            current_question=1,
            minutes_remaining=minutes_remaining
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting test session: {e}")
        raise HTTPException(status_code=500, detail=f"Error starting test session: {str(e)}")

@router.get("/{test_id}/questions", response_model=List[TestQuestionResponse])
async def get_test_questions(
    test_id: str,
    session_token: str,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    supabase=Depends(get_supabase)
):
    """
    Get test questions for an active session
    """
    try:
        # SUPABASE MIGRATION: Replace pool operations with Supabase client calls
        # Verify session with JOIN-like behavior using separate queries
        session_response = supabase.table('test_sessions').select('*').eq('test_id', test_id).eq('session_token', session_token).eq('is_active', True).execute()
        
        if not session_response.data:
            raise HTTPException(status_code=403, detail="Invalid or expired session")
        
        session = session_response.data[0]
        
        # Check if session is expired (manual expiry check since no NOW() in Supabase)
        now = datetime.now(timezone.utc)
        expires_at_str = session['expires_at']
        if isinstance(expires_at_str, str):
            expires_at_dt = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if expires_at_dt <= now:
                raise HTTPException(status_code=403, detail="Session expired")
        
        # Get test details for security checks
        test_response = supabase.table('tests').select('title, is_public, created_by').eq('id', test_id).execute()
        
        if not test_response.data:
            raise HTTPException(status_code=404, detail="Test not found")
        
        test_data = test_response.data[0]
        session['title'] = test_data['title']
        session['is_public'] = test_data['is_public']
        session['created_by'] = test_data['created_by']
        
        # Additional security check for private tests
        if not session['is_public']:
            # Allow if session was created via a valid invite/public link
            has_invite = False
            try:
                has_invite = bool(session['invite_token'])
            except Exception:
                has_invite = False
            if not has_invite:
                # For private tests without invite token, require creator or session owner
                if not current_user:
                    raise HTTPException(status_code=403, detail="Authentication required for private test")
                is_creator = current_user.id == session['created_by']
                is_session_owner = session['user_id'] and current_user.id == session['user_id']
                if not (is_creator or is_session_owner):
                    raise HTTPException(status_code=403, detail="Not authorized for this test")
        
        # SUPABASE: Get test questions with JOIN-like behavior
        # First get test_questions, then get question details
        test_questions_response = supabase.table('test_questions').select('question_id, question_order').eq('test_id', test_id).order('question_order').execute()
        
        if not test_questions_response.data:
            return []  # No questions in test
        
        # Get question IDs and fetch question details
        question_ids = [tq['question_id'] for tq in test_questions_response.data]
        questions_response = supabase.table('questions').select('id, question_text, question_type, options').in_('id', question_ids).execute()
        
        # Create a lookup dict for question details
        question_details = {q['id']: q for q in questions_response.data} if questions_response.data else {}
        
        # Combine test_questions with question details in order
        questions = []
        for tq in test_questions_response.data:
            qid = tq['question_id']
            if qid in question_details:
                q_details = question_details[qid]
                questions.append({
                    'id': q_details['id'],
                    'question_text': q_details['question_text'],
                    'question_type': q_details['question_type'],
                    'options': q_details['options'],
                    'question_order': tq['question_order']
                })
        
        return [
            TestQuestionResponse(
                id=str(q['id']),
                question_text=q['question_text'],
                question_type=q['question_type'],
                options=q['options'],
                question_order=q['question_order']
            )
            for q in questions
        ]
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching test questions: {e}")
        raise HTTPException(status_code=500, detail="Error fetching test questions")

@router.get("/session/{session_token}/status", response_model=TestSessionStatus)
async def get_session_status(
    session_token: str,
    supabase=Depends(get_supabase)
):
    """
    Get current session status including time remaining
    """
    try:
        # SUPABASE: Get session status without pool
        now = datetime.now(timezone.utc)
        
        # First cleanup expired sessions by updating them
        supabase.table('test_sessions').update({
            'is_active': False
        }).lt('expires_at', now.isoformat()).execute()
        
        # Get session details
        session_response = supabase.table('test_sessions').select('*').eq('session_token', session_token).eq('is_active', True).execute()
        
        if not session_response.data:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        session = session_response.data[0]
        
        # Check if expired
        expires_at = datetime.fromisoformat(session['expires_at'].replace('Z', '+00:00')) if isinstance(session['expires_at'], str) else session['expires_at']
        if now > expires_at:
            # Mark as inactive
            supabase.table('test_sessions').update({'is_active': False}).eq('id', session['id']).execute()
            raise HTTPException(status_code=404, detail="Session expired")
        
        # Get test details for num_questions
        test_response = supabase.table('tests').select('num_questions').eq('id', session['test_id']).execute()
        num_questions = test_response.data[0]['num_questions'] if test_response.data else 10
        
        # Count saved answers
        answers_draft = session.get('answers_draft') or {}
        if isinstance(answers_draft, str):
            answers_draft = json.loads(answers_draft)
        
        answers_saved = len(answers_draft)
        can_submit = answers_saved >= num_questions  # All questions answered
        
        # Calculate time remaining
        started_at = datetime.fromisoformat(session['started_at'].replace('Z', '+00:00')) if isinstance(session['started_at'], str) else session['started_at']
        time_elapsed = (now - started_at).total_seconds() / 60  # in minutes
        time_limit = session.get('time_limit_minutes') or 60
        minutes_remaining = max(0, time_limit - time_elapsed)
        
        return TestSessionStatus(
            session_id=str(session['id']),
            is_active=session['is_active'],
            current_question=session.get('current_question', 1),
            minutes_remaining=minutes_remaining,
            answers_saved=answers_saved,
            can_submit=can_submit
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(status_code=500, detail="Error getting session status")

@router.post("/session/{session_token}/save-answer", response_model=SaveAnswerResponse)
async def save_answer(
    session_token: str,
    answer_data: SaveAnswerRequest,
    supabase=Depends(get_supabase)
):
    """
    Save/autosave an answer during test taking
    """
    try:
        # SUPABASE MIGRATION: Fix save_answer to use Supabase instead of pool
        # Verify session exists and is active
        session_response = supabase.table('test_sessions').select('id, answers_draft, expires_at, is_active').eq('session_token', session_token).eq('is_active', True).execute()
        
        if not session_response.data:
            raise HTTPException(status_code=403, detail="Invalid or expired session")
        
        session = session_response.data[0]
        
        # Check if session has expired (manual check since Supabase doesn't have NOW())
        now = datetime.now(timezone.utc)
        expires_at_str = session['expires_at']
        if isinstance(expires_at_str, str):
            expires_at_dt = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if now > expires_at_dt:
                raise HTTPException(status_code=403, detail="Session has expired")
        
        # SUPABASE: Update answers draft - parse existing answers correctly
        answers_draft = session['answers_draft'] or {}
        if isinstance(answers_draft, str):
            import json
            answers_draft = json.loads(answers_draft)
        
        # Add new answer to draft with proper structure
        answers_draft[answer_data.question_id] = {
            "selected_answer": answer_data.selected_answer,
            "question_number": answer_data.question_number,
            "saved_at": now.isoformat()
        }
        
        # SUPABASE: Update session with new answers_draft
        update_response = supabase.table('test_sessions').update({
            'answers_draft': json.dumps(answers_draft),
            'current_question': answer_data.question_number
        }).eq('id', session['id']).execute()
        
        if not update_response.data:
            raise HTTPException(status_code=500, detail="Failed to save answer")
        
        return SaveAnswerResponse(
            success=True,
            question_number=answer_data.question_number,
            answers_saved=len(answers_draft),
            auto_saved_at=now
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving answer: {e}")
        raise HTTPException(status_code=500, detail="Error saving answer")

@router.post("/session/{session_token}/submit", response_model=TestSubmissionResponse)
async def submit_test_session(
    session_token: str,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    supabase=Depends(get_supabase)
):
    """
    Submit a test session and calculate final score
    """
    try:
        # SUPABASE MIGRATION: Replace pool operations with Supabase client calls
        # Get session details with JOIN-like behavior
        session_response = supabase.table('test_sessions').select('*').eq('session_token', session_token).eq('is_active', True).execute()
        
        if not session_response.data:
            raise HTTPException(status_code=403, detail="Invalid or expired session")
        
        session = session_response.data[0]
        
        # Get test details for title and pass_threshold
        test_response = supabase.table('tests').select('title, pass_threshold').eq('id', session['test_id']).execute()
        
        if not test_response.data:
            raise HTTPException(status_code=404, detail="Test not found")
        
        test_data = test_response.data[0]
        session['title'] = test_data['title']
        session['pass_threshold'] = test_data['pass_threshold']
        
        # Check if session has expired
        now = datetime.now(timezone.utc)
        expires_at_str = session['expires_at']
        if isinstance(expires_at_str, str):
            expires_at_dt = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if now > expires_at_dt:
                raise HTTPException(status_code=403, detail="Session has expired")
        
        # Get answers from session
        answers_draft = session['answers_draft'] or {}
        if isinstance(answers_draft, str):
            import json
            answers_draft = json.loads(answers_draft)
        
        if not answers_draft:
            raise HTTPException(status_code=400, detail="No answers found to submit")
        
        # SUPABASE: Get correct answers with JOIN-like behavior
        test_questions_response = supabase.table('test_questions').select('question_id').eq('test_id', session['test_id']).execute()
        
        if not test_questions_response.data:
            raise HTTPException(status_code=400, detail="No questions found for this test")
        
        question_ids = [tq['question_id'] for tq in test_questions_response.data]
        questions_response = supabase.table('questions').select('id, correct_answer').in_('id', question_ids).execute()
        
        correct_map = {str(row['id']): row['correct_answer'] for row in questions_response.data} if questions_response.data else {}
        
        # Calculate score
        correct_count = 0
        question_results = []
        
        for question_id, answer_data in answers_draft.items():
            selected_answer = answer_data.get('selected_answer', '')
            correct_answer = correct_map.get(question_id, '')
            is_correct = correct_answer.strip().lower() == selected_answer.strip().lower()
            
            if is_correct:
                correct_count += 1
            
            question_results.append({
                "question_id": question_id,
                "selected_answer": selected_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct
            })
        
        total_questions = len(questions_response.data) if questions_response.data else 0
        score = (correct_count / total_questions * 100) if total_questions > 0 else 0
        is_passed = score >= session['pass_threshold']
        
        # Calculate time taken
        started_at_str = session['started_at']
        if isinstance(started_at_str, str):
            started_at_dt = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
        else:
            started_at_dt = started_at_str
        
        time_taken = now - started_at_dt
        time_taken_minutes = int(time_taken.total_seconds() / 60)
        
        # SUPABASE: Create submission record
        submission_id = str(uuid.uuid4())
        submission_data = {
            'id': submission_id,
            'test_id': session['test_id'],
            'user_id': session['user_id'],
            'participant_name': session['participant_name'],
            'participant_email': session['participant_email'],
            'score': score,
            'total_questions': total_questions,
            'correct_answers': correct_count,
            'is_passed': is_passed,
            'time_taken_minutes': time_taken_minutes,
            'answers': json.dumps(question_results),
            'session_id': session['id'],
            'submitted_at': now.isoformat(),
            'invite_token': session.get('invite_token')
        }
        
        submission_response = supabase.table('test_submissions').insert(submission_data).execute()
        
        if not submission_response.data:
            raise HTTPException(status_code=500, detail="Failed to create submission record")
        
        submission_row = submission_response.data[0]

        # SUPABASE: Update analytics for this test (simplified version)
        # Get all submissions for this test to recalculate analytics
        all_submissions_response = supabase.table('test_submissions').select('score, is_passed, time_taken_minutes, user_id, participant_email').eq('test_id', session['test_id']).execute()
        
        if all_submissions_response.data:
            submissions = all_submissions_response.data
            total_submissions = len(submissions)
            
            # Calculate unique participants (by user_id or email)
            participants = set()
            for sub in submissions:
                if sub['user_id']:
                    participants.add(str(sub['user_id']))
                elif sub['participant_email']:
                    participants.add(sub['participant_email'])
            total_participants = len(participants)
            
            # Calculate averages
            scores = [sub['score'] for sub in submissions if sub['score'] is not None]
            average_score = sum(scores) / len(scores) if scores else 0
            
            passed_count = sum(1 for sub in submissions if sub['is_passed'])
            pass_rate = (passed_count / total_submissions * 100) if total_submissions > 0 else 0
            
            times = [sub['time_taken_minutes'] for sub in submissions if sub['time_taken_minutes'] is not None]
            average_time_minutes = sum(times) / len(times) if times else 0
            
            # Update or create analytics record
            analytics_data = {
                'total_submissions': total_submissions,
                'total_participants': total_participants,
                'average_score': average_score,
                'pass_rate': pass_rate,
                'average_time_minutes': average_time_minutes,
                'last_updated': now.isoformat()
            }
            
            # Try to update existing analytics record
            existing_analytics = supabase.table('test_analytics').select('test_id').eq('test_id', session['test_id']).execute()
            
            if existing_analytics.data:
                supabase.table('test_analytics').update(analytics_data).eq('test_id', session['test_id']).execute()
            else:
                analytics_data['test_id'] = session['test_id']
                supabase.table('test_analytics').insert(analytics_data).execute()
        
        # SUPABASE: Update session to mark as completed
        supabase.table('test_sessions').update({
            'is_active': False,
            'submission_id': submission_id
        }).eq('id', session['id']).execute()
        
        return TestSubmissionResponse(
                id=str(submission_row['id']),
                test_id=str(submission_row['test_id']),
                test_title=session['title'],
                participant_name=submission_row['participant_name'],
                participant_email=submission_row['participant_email'],
                score=float(submission_row['score']),
                total_questions=submission_row['total_questions'],
                correct_answers=submission_row['correct_answers'],
                time_taken_minutes=submission_row['time_taken_minutes'],
                is_passed=is_passed,
                submitted_at=submission_row['submitted_at'],
                question_results=question_results
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting test session: {e}")
        raise HTTPException(status_code=500, detail=f"Error submitting test: {str(e)}")

@router.get("/submission/{submission_id}", response_model=TestSubmissionResponse)
async def get_submission_result(
    submission_id: str,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    supabase=Depends(get_supabase)
):
    """
    Get detailed submission results
    """
    try:
        # SUPABASE: Get submission with test details
        submission_response = supabase.table('test_submissions').select('*').eq('id', submission_id).execute()
        
        if not submission_response.data:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        submission = submission_response.data[0]
        
        # Get test details
        test_response = supabase.table('tests').select('title, pass_threshold').eq('id', submission['test_id']).execute()
        if test_response.data:
            test = test_response.data[0]
            submission['test_title'] = test['title']
            submission['pass_threshold'] = test['pass_threshold']
        else:
            submission['test_title'] = 'Unknown Test'
            submission['pass_threshold'] = 60
        
        # Security check - allow access to:
        # 1. Own submissions (by user_id)
        # 2. Test creator
        # 3. Participant by email (for shared tests where user_id might be null)
        if current_user:
            is_own_submission = submission.get('user_id') == current_user.id
            is_own_by_email = submission.get('participant_email') == current_user.email
            
            if not (is_own_submission or is_own_by_email):
                # Check if user is test creator
                creator_response = supabase.table('tests').select('created_by').eq('id', submission['test_id']).execute()
                if not creator_response.data or creator_response.data[0]['created_by'] != current_user.id:
                    raise HTTPException(status_code=403, detail="Not authorized to view this submission")
        
        # Parse answers
        answers_data = submission.get('answers', [])
        if isinstance(answers_data, str):
            answers_data = json.loads(answers_data)
        
        is_passed = submission.get('score', 0) >= submission['pass_threshold']
        
        # Parse submitted_at if string
        submitted_at = submission.get('submitted_at')
        if isinstance(submitted_at, str):
            submitted_at = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
        
        return TestSubmissionResponse(
            id=str(submission['id']),
            test_id=str(submission['test_id']),
            test_title=submission['test_title'],
            participant_name=submission.get('participant_name', 'Anonymous'),
            participant_email=submission.get('participant_email'),
            score=float(submission.get('score', 0)),
            total_questions=submission.get('total_questions', 0),
            correct_answers=submission.get('correct_answers', 0),
            time_taken_minutes=submission.get('time_taken_minutes'),
            is_passed=is_passed,
            submitted_at=submitted_at,
            question_results=answers_data
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching submission: {e}")
        raise HTTPException(status_code=500, detail="Error fetching submission")

@router.get("/results/{test_id}/{participant_email}", response_model=TestSubmissionResponse)
async def get_result_by_email(
    test_id: str,
    participant_email: str,
    supabase=Depends(get_supabase)
):
    """
    Get the latest submission result for a participant by email (for shared tests)
    """
    try:
        # SUPABASE: Get the most recent submission for this test and email
        submissions_response = supabase.table('test_submissions').select('*').eq('test_id', test_id).ilike('participant_email', participant_email).order('submitted_at', desc=True).limit(1).execute()
        
        if not submissions_response.data:
            raise HTTPException(status_code=404, detail="No results found for this email and test")
        
        submission = submissions_response.data[0]
        
        # Get test details
        test_response = supabase.table('tests').select('title, pass_threshold').eq('id', test_id).execute()
        if test_response.data:
            test = test_response.data[0]
            submission['test_title'] = test['title']
            submission['pass_threshold'] = test['pass_threshold']
        else:
            submission['test_title'] = 'Unknown Test'
            submission['pass_threshold'] = 60
        
        # Parse answers
        answers_data = submission.get('answers', [])
        if isinstance(answers_data, str):
            answers_data = json.loads(answers_data)
        
        is_passed = submission.get('score', 0) >= submission['pass_threshold']
        
        # Parse submitted_at if string
        submitted_at = submission.get('submitted_at')
        if isinstance(submitted_at, str):
            submitted_at = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
        
        return TestSubmissionResponse(
            id=str(submission['id']),
            test_id=str(submission['test_id']),
            test_title=submission['test_title'],
            participant_name=submission.get('participant_name', 'Anonymous'),
            participant_email=submission.get('participant_email'),
            score=float(submission.get('score', 0)),
            total_questions=submission.get('total_questions', 0),
            correct_answers=submission.get('correct_answers', 0),
            time_taken_minutes=submission.get('time_taken_minutes'),
            is_passed=is_passed,
            submitted_at=submitted_at,
            question_results=answers_data
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching result by email: {e}")
        raise HTTPException(status_code=500, detail="Error fetching result")

@router.get("/user/attempts", response_model=List[TestSubmissionResponse])
async def get_user_attempts(
    current_user: UserResponse = Depends(get_current_user_optional),
    supabase=Depends(get_supabase)
):
    """
    Get all test attempts for the current user
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # SUPABASE: Get all test attempts for the current user
        submissions_response = supabase.table('test_submissions').select('*').eq('user_id', current_user.id).order('submitted_at', desc=True).execute()
        
        if not submissions_response.data:
            return []
        
        # Enrich with test details
        result = []
        for sub in submissions_response.data:
            # Get test details
            test_response = supabase.table('tests').select('title, pass_threshold').eq('id', sub['test_id']).execute()
            if test_response.data:
                test = test_response.data[0]
                sub['test_title'] = test['title']
                sub['pass_threshold'] = test['pass_threshold']
            else:
                sub['test_title'] = 'Unknown Test'
                sub['pass_threshold'] = 60
            
            # Parse submitted_at if string
            submitted_at = sub.get('submitted_at')
            if isinstance(submitted_at, str):
                submitted_at = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
            
            result.append(
                TestSubmissionResponse(
                    id=str(sub['id']),
                    test_id=str(sub['test_id']),
                    test_title=sub['test_title'],
                    participant_name=sub.get('participant_name', 'Anonymous'),
                    participant_email=sub.get('participant_email'),
                    score=float(sub.get('score', 0)),
                    total_questions=sub.get('total_questions', 0),
                    correct_answers=sub.get('correct_answers', 0),
                    time_taken_minutes=sub.get('time_taken_minutes'),
                    is_passed=sub.get('score', 0) >= sub['pass_threshold'],
                    submitted_at=submitted_at
                )
            )
        
        return result
            
    except Exception as e:
        logger.error(f"Error fetching user attempts: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user attempts")

@router.delete("/session/{session_token}")
async def cancel_test_session(
    session_token: str,
    supabase=Depends(get_supabase)
):
    """
    Cancel an active test session
    """
    try:
        # SUPABASE: Cancel test session
        update_response = supabase.table('test_sessions').update({
            'is_active': False
        }).eq('session_token', session_token).eq('is_active', True).execute()
        
        if not update_response.data:
            raise HTTPException(status_code=404, detail="Session not found or already inactive")
        
        return {"message": "Session cancelled successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling session: {e}")
        raise HTTPException(status_code=500, detail="Error cancelling session")
