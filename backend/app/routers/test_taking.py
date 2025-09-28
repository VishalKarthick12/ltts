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
from app.database import get_db_pool
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
    pool=Depends(get_db_pool)
):
    """
    Start a new test session with timer and session tracking
    """
    try:
        async with pool.acquire() as conn:
            # Get test details
            test_row = await conn.fetchrow("""
                SELECT * FROM tests WHERE id = $1 AND is_active = true
            """, test_id)
            
            if not test_row:
                raise HTTPException(status_code=404, detail="Test not found or inactive")
            
            # Check if test is accessible
            now = datetime.now(timezone.utc)
            if test_row['scheduled_start'] and now < test_row['scheduled_start']:
                raise HTTPException(status_code=403, detail="Test has not started yet")
            if test_row['scheduled_end'] and now > test_row['scheduled_end']:
                raise HTTPException(status_code=403, detail="Test has ended")
            
            # Resolve or create user if possible
            resolved_user_id = None
            if current_user:
                resolved_user_id = current_user.id
            elif session_data.participant_email:
                # Try to find existing user by email
                existing_user = await conn.fetchrow("""
                    SELECT id FROM users WHERE email = $1 AND is_active = TRUE
                """, session_data.participant_email)
                if existing_user:
                    resolved_user_id = existing_user['id']
                else:
                    # Create lightweight user record
                    try:
                        password_hash = get_password_hash(secrets.token_urlsafe(16))
                        new_user = await conn.fetchrow("""
                            INSERT INTO users (name, email, password_hash, is_active)
                            VALUES ($1, $2, $3, TRUE)
                            RETURNING id
                        """, session_data.participant_name, session_data.participant_email, password_hash)
                        resolved_user_id = new_user['id'] if new_user else None
                    except Exception:
                        # Fallback to anonymous if user table constraints prevent creation
                        resolved_user_id = None

            # Validate invite token if provided
            if getattr(session_data, 'invite_token', None):
                token_valid = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM test_public_links 
                        WHERE link_token = $1 AND test_id = $2 AND is_active = TRUE 
                        AND (expires_at IS NULL OR expires_at > NOW())
                    ) OR EXISTS(
                        SELECT 1 FROM test_invites 
                        WHERE invite_token = $1 AND test_id = $2 AND status = 'pending'
                        AND (expires_at IS NULL OR expires_at > NOW())
                    )
                """, session_data.invite_token, test_id)
                if not token_valid:
                    raise HTTPException(status_code=403, detail="Invalid or expired invite token")

            # Check user attempts if authenticated
            if resolved_user_id:
                attempts = await conn.fetchval("""
                    SELECT attempts_count FROM user_performance
                    WHERE user_id = $1 AND test_id = $2
                """, resolved_user_id, test_id)
                
                if attempts and attempts >= test_row['max_attempts']:
                    raise HTTPException(status_code=403, detail="Maximum attempts exceeded")
                
                # Check for active session
                active_session = await conn.fetchrow("""
                    SELECT id, session_token, expires_at FROM test_sessions
                    WHERE test_id = $1 AND user_id = $2 AND is_active = true AND expires_at > NOW()
                """, test_id, resolved_user_id)
                
                if active_session:
                    # Return existing session
                    minutes_remaining = (active_session['expires_at'] - now).total_seconds() / 60
                    return TestSessionResponse(
                        session_id=str(active_session['id']),
                        session_token=active_session['session_token'],
                        test_id=test_id,
                        test_title=test_row['title'],
                        participant_name=session_data.participant_name,
                        started_at=active_session['started_at'] if 'started_at' in active_session else now,
                        expires_at=active_session['expires_at'],
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
            
            session_row = await conn.fetchrow("""
                INSERT INTO test_sessions (
                    id, test_id, user_id, participant_name, participant_email,
                    session_token, started_at, expires_at, ip_address, user_agent, invite_token
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING *
            """, 
                session_id, test_id, resolved_user_id,
                session_data.participant_name, session_data.participant_email,
                session_token, now, expires_at, client_ip, user_agent, getattr(session_data, 'invite_token', None)
            )
            
            minutes_remaining = (expires_at - now).total_seconds() / 60
            
            return TestSessionResponse(
                session_id=str(session_row['id']),
                session_token=session_row['session_token'],
                test_id=test_id,
                test_title=test_row['title'],
                participant_name=session_row['participant_name'],
                started_at=session_row['started_at'],
                expires_at=session_row['expires_at'],
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
    pool=Depends(get_db_pool)
):
    """
    Get test questions for an active session
    """
    try:
        async with pool.acquire() as conn:
            # Verify session
            session = await conn.fetchrow("""
                SELECT ts.*, t.title, t.is_public, t.created_by
                FROM test_sessions ts
                JOIN tests t ON ts.test_id = t.id
                WHERE ts.test_id = $1 AND ts.session_token = $2 
                AND ts.is_active = true AND ts.expires_at > NOW()
            """, test_id, session_token)
            
            if not session:
                raise HTTPException(status_code=403, detail="Invalid or expired session")
            
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
            
            # Get test questions in order
            questions = await conn.fetch("""
                SELECT 
                    q.id, q.question_text, q.question_type, q.options,
                    tq.question_order
                FROM test_questions tq
                JOIN questions q ON tq.question_id = q.id
                WHERE tq.test_id = $1
                ORDER BY tq.question_order
            """, test_id)
            
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
    pool=Depends(get_db_pool)
):
    """
    Get current session status including time remaining
    """
    try:
        async with pool.acquire() as conn:
            # Cleanup expired sessions first
            await conn.execute("SELECT cleanup_expired_sessions()")
            
            session = await conn.fetchrow("""
                SELECT * FROM active_test_sessions
                WHERE session_token = $1
            """, session_token)
            
            if not session:
                raise HTTPException(status_code=404, detail="Session not found or expired")
            
            # Count saved answers
            answers_draft = session['answers_draft'] or {}
            if isinstance(answers_draft, str):
                answers_draft = json.loads(answers_draft)
            
            answers_saved = len(answers_draft)
            can_submit = answers_saved >= session['num_questions']  # All questions answered
            
            return TestSessionStatus(
                session_id=str(session['id']),
                is_active=session['is_active'],
                current_question=session['current_question'],
                minutes_remaining=max(0, session['minutes_remaining']),
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
    pool=Depends(get_db_pool)
):
    """
    Save/autosave an answer during test taking
    """
    try:
        async with pool.acquire() as conn:
            # Verify session
            session = await conn.fetchrow("""
                SELECT id, answers_draft, expires_at, is_active
                FROM test_sessions
                WHERE session_token = $1 AND is_active = true AND expires_at > NOW()
            """, session_token)
            
            if not session:
                raise HTTPException(status_code=403, detail="Invalid or expired session")
            
            # Update answers draft
            answers_draft = session['answers_draft'] or {}
            if isinstance(answers_draft, str):
                answers_draft = json.loads(answers_draft)
            
            answers_draft[answer_data.question_id] = {
                "selected_answer": answer_data.selected_answer,
                "question_number": answer_data.question_number,
                "saved_at": datetime.utcnow().isoformat()
            }
            
            # Update session
            await conn.execute("""
                UPDATE test_sessions 
                SET answers_draft = $1, current_question = $2
                WHERE id = $3
            """, json.dumps(answers_draft), answer_data.question_number, session['id'])
            
            return SaveAnswerResponse(
                success=True,
                question_number=answer_data.question_number,
                answers_saved=len(answers_draft),
                auto_saved_at=datetime.utcnow()
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
    pool=Depends(get_db_pool)
):
    """
    Submit a test session and calculate final score
    """
    try:
        async with pool.acquire() as conn:
            # Get session details
            session = await conn.fetchrow("""
                SELECT ts.*, t.title, t.pass_threshold
                FROM test_sessions ts
                JOIN tests t ON ts.test_id = t.id
                WHERE ts.session_token = $1 AND ts.is_active = true
            """, session_token)
            
            if not session:
                raise HTTPException(status_code=403, detail="Invalid or expired session")
            
            # Check if session has expired
            if datetime.now(timezone.utc) > session['expires_at']:
                raise HTTPException(status_code=403, detail="Session has expired")
            
            # Get answers from session
            answers_draft = session['answers_draft'] or {}
            if isinstance(answers_draft, str):
                answers_draft = json.loads(answers_draft)
            
            if not answers_draft:
                raise HTTPException(status_code=400, detail="No answers found to submit")
            
            # Get correct answers
            correct_answers = await conn.fetch("""
                SELECT q.id, q.correct_answer
                FROM test_questions tq
                JOIN questions q ON tq.question_id = q.id
                WHERE tq.test_id = $1
            """, session['test_id'])
            
            correct_map = {str(row['id']): row['correct_answer'] for row in correct_answers}
            
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
            
            total_questions = len(correct_answers)
            score = (correct_count / total_questions * 100) if total_questions > 0 else 0
            is_passed = score >= session['pass_threshold']
            
            # Calculate time taken
            time_taken = datetime.now(timezone.utc) - session['started_at']
            time_taken_minutes = int(time_taken.total_seconds() / 60)
            
            # Create submission record
            submission_id = str(uuid.uuid4())
            submission_row = await conn.fetchrow("""
                INSERT INTO test_submissions (
                    id, test_id, user_id, participant_name, participant_email,
                    score, total_questions, correct_answers, is_passed, time_taken_minutes,
                    answers, session_id, submitted_at, invite_token
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW(), $13)
                RETURNING *
            """,
                submission_id, session['test_id'], session['user_id'],
                session['participant_name'], session['participant_email'],
                score, total_questions, correct_count, is_passed, time_taken_minutes,
                json.dumps(question_results), session['id'],
                (session['invite_token'] if ('invite_token' in session.keys() if hasattr(session, 'keys') else False) else None)
            )

            # Update analytics for this test
            await conn.execute("""
                UPDATE test_analytics ta
                SET total_submissions = s.total_submissions,
                    total_participants = s.total_participants,
                    average_score = s.average_score,
                    pass_rate = s.pass_rate,
                    average_time_minutes = s.average_time_minutes,
                    last_updated = NOW()
                FROM (
                    SELECT COUNT(*) AS total_submissions,
                           COUNT(DISTINCT COALESCE(CAST(user_id AS TEXT), participant_email)) AS total_participants,
                           COALESCE(AVG(score), 0) AS average_score,
                           COALESCE(AVG(CASE WHEN is_passed THEN 1 ELSE 0 END) * 100, 0) AS pass_rate,
                           COALESCE(AVG(time_taken_minutes), 0) AS average_time_minutes
                    FROM test_submissions
                    WHERE test_id = $1
                ) s
                WHERE ta.test_id = $1
            """, session['test_id'])
            
            # Update session to mark as completed
            await conn.execute("""
                UPDATE test_sessions 
                SET is_active = false, submission_id = $1
                WHERE id = $2
            """, submission_id, session['id'])
            
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
    pool=Depends(get_db_pool)
):
    """
    Get detailed submission results
    """
    try:
        async with pool.acquire() as conn:
            # Get submission with test details
            submission = await conn.fetchrow("""
                SELECT ts.*, t.title as test_title, t.pass_threshold
                FROM test_submissions ts
                JOIN tests t ON ts.test_id = t.id
                WHERE ts.id = $1
            """, submission_id)
            
            if not submission:
                raise HTTPException(status_code=404, detail="Submission not found")
            
            # Security check - allow access to:
            # 1. Own submissions (by user_id)
            # 2. Test creator
            # 3. Participant by email (for shared tests where user_id might be null)
            if current_user:
                is_own_submission = submission['user_id'] == current_user.id
                is_own_by_email = submission['participant_email'] == current_user.email
                
                if not (is_own_submission or is_own_by_email):
                    # Check if user is test creator
                    is_creator = await conn.fetchval("""
                        SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1 AND created_by = $2)
                    """, submission['test_id'], current_user.id)
                    
                    if not is_creator:
                        raise HTTPException(status_code=403, detail="Not authorized to view this submission")
            
            # Parse answers
            answers_data = submission['answers']
            if isinstance(answers_data, str):
                answers_data = json.loads(answers_data)
            
            is_passed = submission['score'] >= submission['pass_threshold']
            
            return TestSubmissionResponse(
                id=str(submission['id']),
                test_id=str(submission['test_id']),
                test_title=submission['test_title'],
                participant_name=submission['participant_name'],
                participant_email=submission['participant_email'],
                score=float(submission['score']),
                total_questions=submission['total_questions'],
                correct_answers=submission['correct_answers'],
                time_taken_minutes=submission['time_taken_minutes'],
                is_passed=is_passed,
                submitted_at=submission['submitted_at'],
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
    pool=Depends(get_db_pool)
):
    """
    Get the latest submission result for a participant by email (for shared tests)
    """
    try:
        async with pool.acquire() as conn:
            # Get the most recent submission for this test and email
            submission = await conn.fetchrow("""
                SELECT ts.*, t.title as test_title, t.pass_threshold
                FROM test_submissions ts
                JOIN tests t ON ts.test_id = t.id
                WHERE ts.test_id = $1 AND LOWER(ts.participant_email) = LOWER($2)
                ORDER BY ts.submitted_at DESC
                LIMIT 1
            """, test_id, participant_email)
            
            if not submission:
                raise HTTPException(status_code=404, detail="No results found for this email and test")
            
            # Parse answers
            answers_data = submission['answers']
            if isinstance(answers_data, str):
                answers_data = json.loads(answers_data)
            
            is_passed = submission['score'] >= submission['pass_threshold']
            
            return TestSubmissionResponse(
                id=str(submission['id']),
                test_id=str(submission['test_id']),
                test_title=submission['test_title'],
                participant_name=submission['participant_name'],
                participant_email=submission['participant_email'],
                score=float(submission['score']),
                total_questions=submission['total_questions'],
                correct_answers=submission['correct_answers'],
                time_taken_minutes=submission['time_taken_minutes'],
                is_passed=is_passed,
                submitted_at=submission['submitted_at'],
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
    pool=Depends(get_db_pool)
):
    """
    Get all test attempts for the current user
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        async with pool.acquire() as conn:
            submissions = await conn.fetch("""
                SELECT ts.*, t.title as test_title, t.pass_threshold
                FROM test_submissions ts
                JOIN tests t ON ts.test_id = t.id
                WHERE ts.user_id = $1
                ORDER BY ts.submitted_at DESC
            """, current_user.id)
            
            return [
                TestSubmissionResponse(
                    id=str(sub['id']),
                    test_id=str(sub['test_id']),
                    test_title=sub['test_title'],
                    participant_name=sub['participant_name'],
                    participant_email=sub['participant_email'],
                    score=float(sub['score']),
                    total_questions=sub['total_questions'],
                    correct_answers=sub['correct_answers'],
                    time_taken_minutes=sub['time_taken_minutes'],
                    is_passed=sub['score'] >= sub['pass_threshold'],
                    submitted_at=sub['submitted_at']
                )
                for sub in submissions
            ]
            
    except Exception as e:
        logger.error(f"Error fetching user attempts: {e}")
        raise HTTPException(status_code=500, detail="Error fetching user attempts")

@router.delete("/session/{session_token}")
async def cancel_test_session(
    session_token: str,
    pool=Depends(get_db_pool)
):
    """
    Cancel an active test session
    """
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE test_sessions 
                SET is_active = false 
                WHERE session_token = $1 AND is_active = true
            """, session_token)
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Session not found or already inactive")
            
            return {"message": "Session cancelled successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling session: {e}")
        raise HTTPException(status_code=500, detail="Error cancelling session")
