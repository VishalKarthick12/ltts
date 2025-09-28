"""
Test Management API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
import uuid
import random
import secrets
from datetime import datetime, timedelta

from app.models import (
    TestCreateRequest, TestResponse, TestUpdateRequest, TestDetailsResponse,
    TestSubmissionRequest, TestSubmissionResponse, TestQuestionResponse,
    TestAnalytics, UserPerformance, LeaderboardEntry, RecentActivity
)
from app.database import get_db_pool
from app.auth import get_current_user, get_current_user_optional, UserResponse, get_password_hash
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tests", tags=["Test Management"])

@router.post("/", response_model=TestResponse)
async def create_test(
    test_data: TestCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    """
    Create a new test from a question bank
    """
    try:
        test_id = str(uuid.uuid4())
        
        async with pool.acquire() as conn:
            # Determine selected question banks (multiple or single)
            banks = test_data.question_bank_ids or ([] if not test_data.question_bank_id else [test_data.question_bank_id])
            if not banks:
                raise HTTPException(status_code=400, detail="Please select at least one question bank")

            # Build desired distribution across banks
            k = len(banks)
            total = test_data.num_questions
            base = total // k
            rem = total % k
            target_counts = [base + (1 if i < rem else 0) for i in range(k)]

            # Fetch availability per bank with filters
            diff_val = test_data.difficulty_filter.value if test_data.difficulty_filter else None
            cat_val = test_data.category_filter
            available_per_bank = []
            for b in banks:
                avail = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM questions 
                    WHERE question_bank_id = $1
                    AND ($2::text IS NULL OR difficulty_level = $2)
                    AND ($3::text IS NULL OR category = $3)
                    """,
                    b, diff_val, cat_val
                )
                available_per_bank.append(int(avail or 0))

            # Rebalance allocation if some banks do not have enough questions
            final_counts = target_counts[:]
            shortage = 0
            for i in range(k):
                if available_per_bank[i] < final_counts[i]:
                    shortage += (final_counts[i] - available_per_bank[i])
                    final_counts[i] = available_per_bank[i]
            if shortage > 0:
                for i in range(k):
                    if shortage == 0:
                        break
                    extra = max(available_per_bank[i] - final_counts[i], 0)
                    if extra > 0:
                        take = min(extra, shortage)
                        final_counts[i] += take
                        shortage -= take

            if sum(final_counts) < total:
                total_available = sum(available_per_bank)
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough questions across selected banks. Available {total_available}, requested {total}."
                )

            # Create test record, storing question_bank_ids JSONB and keeping first bank for backward compatibility
            import json
            primary_bank = banks[0]
            test_row = await conn.fetchrow(
                """
                INSERT INTO tests (
                    id, title, description, question_bank_id, created_by, num_questions,
                    time_limit_minutes, difficulty_filter, category_filter, is_public,
                    scheduled_start, scheduled_end, max_attempts, pass_threshold, question_bank_ids
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15::jsonb)
                RETURNING *
                """,
                test_id, test_data.title, test_data.description, primary_bank,
                current_user.id, test_data.num_questions, test_data.time_limit_minutes,
                diff_val, cat_val, test_data.is_public, test_data.scheduled_start,
                test_data.scheduled_end, test_data.max_attempts, test_data.pass_threshold,
                json.dumps(banks)
            )

            # Select random questions from each bank according to final_counts
            question_order = 1
            for idx, b in enumerate(banks):
                count = final_counts[idx]
                if count <= 0:
                    continue
                qs = await conn.fetch(
                    """
                    SELECT id FROM questions
                    WHERE question_bank_id = $1
                    AND ($2::text IS NULL OR difficulty_level = $2)
                    AND ($3::text IS NULL OR category = $3)
                    ORDER BY RANDOM()
                    LIMIT $4
                    """,
                    b, diff_val, cat_val, count
                )
                for q in qs:
                    await conn.execute(
                        """
                        INSERT INTO test_questions (test_id, question_id, question_order)
                        VALUES ($1, $2, $3)
                        """,
                        test_id, q['id'], question_order
                    )
                    question_order += 1
            
            # Initialize analytics record
            await conn.execute("""
                INSERT INTO test_analytics (test_id) VALUES ($1)
            """, test_id)
            
            # Resolve bank names for response
            bank_names = await conn.fetch(
                "SELECT name FROM question_banks WHERE id = ANY($1::uuid[]) ORDER BY name",
                banks
            )
            bank_names_list = [r['name'] for r in bank_names]

            return TestResponse(
                id=str(test_row['id']),
                title=test_row['title'],
                description=test_row['description'],
                question_bank_id=str(test_row['question_bank_id']),
                question_bank_ids=(test_row['question_bank_ids'] if isinstance(test_row['question_bank_ids'], list) else None),
                question_bank_names=bank_names_list,
                created_by=str(test_row['created_by']),
                creator_name=current_user.name,
                num_questions=test_row['num_questions'],
                time_limit_minutes=test_row['time_limit_minutes'],
                difficulty_filter=test_row['difficulty_filter'],
                category_filter=test_row['category_filter'],
                is_active=test_row['is_active'],
                is_public=test_row['is_public'],
                scheduled_start=test_row['scheduled_start'],
                scheduled_end=test_row['scheduled_end'],
                max_attempts=test_row['max_attempts'],
                pass_threshold=test_row['pass_threshold'],
                created_at=test_row['created_at'],
                updated_at=test_row['updated_at'],
                test_link=f"/test/{test_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating test: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating test: {str(e)}")

@router.get("/", response_model=List[TestResponse])
async def get_tests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    question_bank_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    created_by_me: bool = Query(False, description="Show only tests created by current user"),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    pool=Depends(get_db_pool)
):
    """
    Get list of tests with analytics
    """
    try:
        # Build dynamic query
        conditions = ["1=1"]
        params = []
        param_count = 0
        
        if question_bank_id:
            param_count += 1
            # Match if the filtered bank is either the legacy single bank or present in the JSONB array
            conditions.append(
                f"(${param_count}::uuid = ANY(COALESCE((SELECT array_agg((elem)::uuid) FROM jsonb_array_elements_text(t.question_bank_ids) elem), ARRAY[t.question_bank_id]::uuid[])))"
            )
            params.append(question_bank_id)
        
        if is_active is not None:
            param_count += 1
            conditions.append(f"t.is_active = ${param_count}")
            params.append(is_active)
        
        if created_by_me and current_user:
            param_count += 1
            conditions.append(f"t.created_by = ${param_count}::uuid")
            params.append(current_user.id)
        
        # If not authenticated, only show public tests
        if not current_user:
            conditions.append("t.is_public = true")
        
        query = f"""
            SELECT 
                t.*,
                u.name as creator_name,
                ta.total_submissions,
                ta.total_participants,
                ta.average_score,
                ta.pass_rate,
                bn.bank_names
            FROM tests t
            LEFT JOIN users u ON t.created_by = u.id
            LEFT JOIN test_analytics ta ON t.id = ta.test_id
            LEFT JOIN LATERAL (
                SELECT array_agg(qb.name ORDER BY qb.name) AS bank_names
                FROM question_banks qb
                WHERE qb.id = ANY(
                    COALESCE(
                        (SELECT array_agg((elem)::uuid) FROM jsonb_array_elements_text(t.question_bank_ids) elem),
                        ARRAY[t.question_bank_id]::uuid[]
                    )
                )
            ) bn ON TRUE
            WHERE {' AND '.join(conditions)}
            ORDER BY t.created_at DESC
            OFFSET ${param_count + 1} LIMIT ${param_count + 2}
        """
        params.extend([skip, limit])
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
            return [
                TestResponse(
                    id=str(row['id']),
                    title=row['title'],
                    description=row['description'],
                    question_bank_id=str(row['question_bank_id']),
                    question_bank_ids=(row['question_bank_ids'] if isinstance(row['question_bank_ids'], list) else None),
                    question_bank_names=row['bank_names'],
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
                for row in rows
            ]
    except Exception as e:
        logger.error(f"Error fetching tests: {e}")
        raise HTTPException(status_code=500, detail="Error fetching tests")

@router.get("/{test_id}", response_model=TestDetailsResponse)
async def get_test_details(
    test_id: str,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    pool=Depends(get_db_pool)
):
    """
    Get test details - accessible for both authenticated and anonymous users for public tests
    """
    """
    Get test details with questions (for taking the test)
    """
    try:
        async with pool.acquire() as conn:
            # Get test info
            test_row = await conn.fetchrow("""
                SELECT t.*, u.name as creator_name
                FROM tests t
                LEFT JOIN users u ON t.created_by = u.id
                WHERE t.id = $1
            """, test_id)
            
            if not test_row:
                raise HTTPException(status_code=404, detail="Test not found")
            
            # Check if test is accessible
            if not test_row['is_public'] and (not current_user or current_user.id != test_row['created_by']):
                raise HTTPException(status_code=403, detail="Test is not public")
            
            # Check if test is scheduled and available
            now = datetime.utcnow()
            if test_row['scheduled_start'] and now < test_row['scheduled_start']:
                raise HTTPException(status_code=403, detail="Test has not started yet")
            if test_row['scheduled_end'] and now > test_row['scheduled_end']:
                raise HTTPException(status_code=403, detail="Test has ended")
            
            # Get test questions
            questions = await conn.fetch("""
                SELECT 
                    q.id, q.question_text, q.question_type, q.options,
                    tq.question_order
                FROM test_questions tq
                JOIN questions q ON tq.question_id = q.id
                WHERE tq.test_id = $1
                ORDER BY tq.question_order
            """, test_id)
            
            # Check user attempts if authenticated
            user_attempts = 0
            user_best_score = None
            can_attempt = True
            
            if current_user:
                performance = await conn.fetchrow("""
                    SELECT attempts_count, best_score FROM user_performance
                    WHERE user_id = $1 AND test_id = $2
                """, current_user.id, test_id)
                
                if performance:
                    user_attempts = performance['attempts_count']
                    user_best_score = float(performance['best_score'])
                    can_attempt = user_attempts < test_row['max_attempts']
            
            return TestDetailsResponse(
                id=str(test_row['id']),
                title=test_row['title'],
                description=test_row['description'],
                time_limit_minutes=test_row['time_limit_minutes'],
                total_questions=test_row['num_questions'],
                max_attempts=test_row['max_attempts'],
                pass_threshold=test_row['pass_threshold'],
                scheduled_start=test_row['scheduled_start'],
                scheduled_end=test_row['scheduled_end'],
                questions=[
                    TestQuestionResponse(
                        id=str(q['id']),
                        question_text=q['question_text'],
                        question_type=q['question_type'],
                        options=q['options'],
                        question_order=q['question_order']
                    )
                    for q in questions
                ],
                user_attempts=user_attempts,
                user_best_score=user_best_score,
                can_attempt=can_attempt
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching test details: {e}")
        raise HTTPException(status_code=500, detail="Error fetching test details")

@router.put("/{test_id}", response_model=TestResponse)
async def update_test(
    test_id: str,
    update_data: TestUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    """
    Update test settings (only by creator)
    """
    try:
        async with pool.acquire() as conn:
            # Check if test exists and user is creator
            test_row = await conn.fetchrow("""
                SELECT * FROM tests WHERE id = $1 AND created_by = $2
            """, test_id, current_user.id)
            
            if not test_row:
                raise HTTPException(status_code=404, detail="Test not found or not authorized")
            
            # Build update query dynamically
            updates = []
            params = []
            param_count = 0
            
            update_fields = update_data.dict(exclude_unset=True)
            for field, value in update_fields.items():
                if value is not None:
                    param_count += 1
                    updates.append(f"{field} = ${param_count}")
                    params.append(value)
            
            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            # Add updated_at
            param_count += 1
            updates.append(f"updated_at = ${param_count}")
            params.append(datetime.utcnow())
            
            # Add test_id for WHERE clause
            param_count += 1
            params.append(test_id)
            
            query = f"""
                UPDATE tests 
                SET {', '.join(updates)}
                WHERE id = ${param_count}
                RETURNING *
            """
            
            updated_row = await conn.fetchrow(query, *params)
            
            # Get creator name
            creator = await conn.fetchrow("SELECT name FROM users WHERE id = $1", current_user.id)
            
            return TestResponse(
                id=str(updated_row['id']),
                title=updated_row['title'],
                description=updated_row['description'],
                question_bank_id=str(updated_row['question_bank_id']),
                question_bank_ids=(updated_row['question_bank_ids'] if isinstance(updated_row['question_bank_ids'], list) else None),
                created_by=str(updated_row['created_by']),
                creator_name=creator['name'] if creator else current_user.name,
                num_questions=updated_row['num_questions'],
                time_limit_minutes=updated_row['time_limit_minutes'],
                difficulty_filter=updated_row['difficulty_filter'],
                category_filter=updated_row['category_filter'],
                is_active=updated_row['is_active'],
                is_public=updated_row['is_public'],
                scheduled_start=updated_row['scheduled_start'],
                scheduled_end=updated_row['scheduled_end'],
                max_attempts=updated_row['max_attempts'],
                pass_threshold=updated_row['pass_threshold'],
                created_at=updated_row['created_at'],
                updated_at=updated_row['updated_at'],
                test_link=f"/test/{updated_row['id']}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating test: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating test: {str(e)}")

@router.delete("/{test_id}")
async def delete_test(
    test_id: str,
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    """
    Delete a test (only by creator)
    """
    try:
        async with pool.acquire() as conn:
            # Check if test exists and user is creator
            test_exists = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1 AND created_by = $2)
            """, test_id, current_user.id)
            
            if not test_exists:
                raise HTTPException(status_code=404, detail="Test not found or not authorized")
            
            # Delete test (cascades to submissions, questions, analytics)
            await conn.execute("DELETE FROM tests WHERE id = $1", test_id)
            
            return {"message": "Test deleted successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting test: {e}")
        raise HTTPException(status_code=500, detail="Error deleting test")

@router.post("/{test_id}/submit", response_model=TestSubmissionResponse)
async def submit_test(
    test_id: str,
    submission: TestSubmissionRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    pool=Depends(get_db_pool)
):
    """
    Submit test answers and calculate score
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
            now = datetime.utcnow()
            if test_row['scheduled_start'] and now < test_row['scheduled_start']:
                raise HTTPException(status_code=403, detail="Test has not started yet")
            if test_row['scheduled_end'] and now > test_row['scheduled_end']:
                raise HTTPException(status_code=403, detail="Test has ended")
            
            # Check user attempts if authenticated
            if current_user:
                attempts = await conn.fetchval("""
                    SELECT attempts_count FROM user_performance
                    WHERE user_id = $1 AND test_id = $2
                """, current_user.id, test_id)
                
                if attempts and attempts >= test_row['max_attempts']:
                    raise HTTPException(status_code=403, detail="Maximum attempts exceeded")
            
            # Get correct answers
            correct_answers = await conn.fetch("""
                SELECT q.id, q.correct_answer
                FROM test_questions tq
                JOIN questions q ON tq.question_id = q.id
                WHERE tq.test_id = $1
            """, test_id)
            
            correct_map = {str(row['id']): row['correct_answer'] for row in correct_answers}
            
            # Calculate score
            correct_count = 0
            question_results = []
            
            for answer in submission.answers:
                is_correct = correct_map.get(answer.question_id, "").strip().lower() == answer.selected_answer.strip().lower()
                if is_correct:
                    correct_count += 1
                
                question_results.append({
                    "question_id": answer.question_id,
                    "selected_answer": answer.selected_answer,
                    "correct_answer": correct_map.get(answer.question_id, ""),
                    "is_correct": is_correct
                })
            
            total_questions = len(correct_answers)
            score = (correct_count / total_questions * 100) if total_questions > 0 else 0
            is_passed = score >= test_row['pass_threshold']
            
            # Store submission
            submission_id = str(uuid.uuid4())
            import json
            submission_row = await conn.fetchrow("""
                INSERT INTO test_submissions (
                    id, test_id, user_id, participant_name, participant_email,
                    score, total_questions, correct_answers, time_taken_minutes,
                    answers, submitted_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING *
            """, 
                submission_id, test_id, current_user.id if current_user else None,
                submission.participant_name, submission.participant_email,
                score, total_questions, correct_count, submission.time_taken_minutes,
                json.dumps(question_results), now
            )
            
            return TestSubmissionResponse(
                id=str(submission_row['id']),
                test_id=str(submission_row['test_id']),
                test_title=test_row['title'],
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
        logger.error(f"Error submitting test: {e}")
        raise HTTPException(status_code=500, detail=f"Error submitting test: {str(e)}")

@router.get("/{test_id}/analytics", response_model=TestAnalytics)
async def get_test_analytics(
    test_id: str,
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    """
    Get detailed analytics for a test (creator only)
    """
    try:
        async with pool.acquire() as conn:
            # Check if user is test creator
            is_creator = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1 AND created_by = $2)
            """, test_id, current_user.id)
            
            if not is_creator:
                raise HTTPException(status_code=403, detail="Not authorized to view analytics")
            
            # Get analytics
            analytics = await conn.fetchrow("""
                SELECT * FROM test_analytics WHERE test_id = $1
            """, test_id)
            
            if not analytics:
                raise HTTPException(status_code=404, detail="Analytics not found")
            
            return TestAnalytics(
                test_id=str(analytics['test_id']),
                total_submissions=analytics['total_submissions'],
                total_participants=analytics['total_participants'],
                average_score=float(analytics['average_score']),
                pass_rate=float(analytics['pass_rate']),
                average_time_minutes=float(analytics['average_time_minutes']),
                last_updated=analytics['last_updated']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail="Error fetching analytics")

@router.get("/{test_id}/submissions", response_model=List[TestSubmissionResponse])
async def get_test_submissions(
    test_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user: Optional[str] = Query(None, description="Filter by user name or email"),
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    """
    Get all submissions for a test (creator only)
    """
    try:
        async with pool.acquire() as conn:
            # Check if user is test creator (avoid UUID vs string mismatch)
            is_creator = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1 AND created_by = $2)
            """, test_id, current_user.id)
            if not is_creator:
                # Determine if it's a not found vs forbidden
                exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1)", test_id)
                if not exists:
                    raise HTTPException(status_code=404, detail="Test not found")
                raise HTTPException(status_code=403, detail="Not authorized to view submissions")

            # Retrieve test title for response mapping
            test_row = await conn.fetchrow("SELECT title FROM tests WHERE id = $1", test_id)
            
            # Build dynamic filters
            conditions = ["ts.test_id = $1"]
            params = [test_id]
            param_idx = 1
            if start_date:
                param_idx += 1
                conditions.append(f"ts.submitted_at >= ${param_idx}")
                params.append(start_date)
            if end_date:
                param_idx += 1
                conditions.append(f"ts.submitted_at <= ${param_idx}")
                params.append(end_date)
            if user:
                param_idx += 1
                conditions.append(f"(LOWER(COALESCE(u.name, ts.participant_name)) LIKE ${param_idx} OR LOWER(COALESCE(u.email, ts.participant_email)) LIKE ${param_idx})")
                params.append(f"%{user.lower()}%")

            params.extend([skip, limit])

            # Get submissions
            query = f"""
                SELECT ts.*, u.name as user_name
                FROM test_submissions ts
                LEFT JOIN users u ON ts.user_id = u.id
                WHERE {' AND '.join(conditions)}
                ORDER BY ts.submitted_at DESC
                OFFSET ${param_idx + 1} LIMIT ${param_idx + 2}
            """
            submissions = await conn.fetch(query, *params)
            
            return [
                TestSubmissionResponse(
                    id=str(sub['id']),
                    test_id=str(sub['test_id']),
                    test_title=test_row['title'],
                    participant_name=sub['participant_name'],
                    participant_email=sub['participant_email'],
                    score=float(sub['score']),
                    total_questions=sub['total_questions'],
                    correct_answers=sub['correct_answers'],
                    time_taken_minutes=sub['time_taken_minutes'],
                    is_passed=sub['is_passed'],
                    submitted_at=sub['submitted_at']
                )
                for sub in submissions
            ]
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching submissions: {e}")
        raise HTTPException(status_code=500, detail="Error fetching submissions")

# New: Generate share link for a test (public link)
@router.post("/{test_id}/share")
async def generate_share_link(
    test_id: str,
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    try:
        async with pool.acquire() as conn:
            # Verify test ownership (avoid UUID vs string mismatch)
            is_creator = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1 AND created_by = $2)
            """, test_id, current_user.id)
            if not is_creator:
                # Also 404 if test doesn't exist
                exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1)", test_id)
                if not exists:
                    raise HTTPException(status_code=404, detail="Test not found")
                raise HTTPException(status_code=403, detail="Not authorized")

            # Create or reuse an active link
            existing = await conn.fetchrow("""
                SELECT * FROM test_public_links 
                WHERE test_id = $1 AND is_active = TRUE 
                AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY created_at DESC
                LIMIT 1
            """, test_id)
            if existing:
                link_token = existing['link_token']
                expires_at = existing['expires_at']
            else:
                link_token = secrets.token_urlsafe(16)
                link_id = str(uuid.uuid4())
                row = await conn.fetchrow("""
                    INSERT INTO test_public_links (id, test_id, created_by, link_token)
                    VALUES ($1, $2, $3, $4)
                    RETURNING *
                """, link_id, test_id, current_user.id, link_token)
                expires_at = row['expires_at']

            return {
                "test_id": test_id,
                "share_url": f"/test/{test_id}?token={link_token}",
                "link_token": link_token,
                "expires_at": expires_at
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating share link: {e}")
        raise HTTPException(status_code=500, detail="Error generating share link")

# New: Validate shared token and return test details
@router.get("/share/{token}")
async def get_shared_test(token: str, pool=Depends(get_db_pool)):
    try:
        async with pool.acquire() as conn:
            link = await conn.fetchrow("""
                SELECT tpl.*, t.*
                FROM test_public_links tpl
                JOIN tests t ON tpl.test_id = t.id
                WHERE tpl.link_token = $1 AND tpl.is_active = TRUE
                AND (tpl.expires_at IS NULL OR tpl.expires_at > NOW())
            """, token)
            if not link:
                # Allow invite tokens as well
                invite = await conn.fetchrow("""
                    SELECT ti.*, t.*
                    FROM test_invites ti
                    JOIN tests t ON ti.test_id = t.id
                    WHERE ti.invite_token = $1 AND ti.status = 'pending'
                    AND (ti.expires_at IS NULL OR ti.expires_at > NOW())
                """, token)
                if not invite:
                    raise HTTPException(status_code=404, detail="Invalid or expired share token")
                link = invite

            return {
                "test_id": str(link['test_id']),
                "title": link['title'],
                "description": link['description'],
                "num_questions": link['num_questions'],
                "time_limit_minutes": link['time_limit_minutes'],
                "pass_threshold": link['pass_threshold'],
                "is_active": link['is_active'],
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating share token: {e}")
        raise HTTPException(status_code=500, detail="Error validating share token")

# New: Submit answers via shared token (guest friendly)
@router.post("/share/{token}/submit", response_model=TestSubmissionResponse)
async def submit_via_share_token(
    token: str,
    submission: TestSubmissionRequest,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    pool=Depends(get_db_pool)
):
    try:
        async with pool.acquire() as conn:
            # Resolve test via token
            row = await conn.fetchrow("""
                SELECT t.* FROM test_public_links tpl
                JOIN tests t ON tpl.test_id = t.id
                WHERE tpl.link_token = $1 AND tpl.is_active = TRUE
                AND (tpl.expires_at IS NULL OR tpl.expires_at > NOW())
            """, token)
            if not row:
                row = await conn.fetchrow("""
                    SELECT t.* FROM test_invites ti
                    JOIN tests t ON ti.test_id = t.id
                    WHERE ti.invite_token = $1 AND ti.status = 'pending'
                    AND (ti.expires_at IS NULL OR ti.expires_at > NOW())
                """, token)
            if not row:
                raise HTTPException(status_code=404, detail="Invalid or expired share token")

            test_id = str(row['id'])

            # Resolve or create user
            user_id = None
            if current_user:
                user_id = current_user.id
            elif submission.participant_email:
                existing_user = await conn.fetchrow("""
                    SELECT id FROM users WHERE email = $1 AND is_active = TRUE
                """, submission.participant_email)
                if existing_user:
                    user_id = existing_user['id']
                else:
                    try:
                        password_hash = get_password_hash(secrets.token_urlsafe(16))
                        new_user = await conn.fetchrow("""
                            INSERT INTO users (name, email, password_hash, is_active)
                            VALUES ($1, $2, $3, TRUE)
                            RETURNING id
                        """, submission.participant_name, submission.participant_email, password_hash)
                        user_id = new_user['id'] if new_user else None
                    except Exception:
                        user_id = None

            # Get correct answers
            correct_answers = await conn.fetch("""
                SELECT q.id, q.correct_answer
                FROM test_questions tq
                JOIN questions q ON tq.question_id = q.id
                WHERE tq.test_id = $1
            """, test_id)
            correct_map = {str(r['id']): r['correct_answer'] for r in correct_answers}

            # Score
            correct_count = 0
            question_results = []
            for answer in submission.answers:
                is_correct = correct_map.get(answer.question_id, "").strip().lower() == answer.selected_answer.strip().lower()
                if is_correct:
                    correct_count += 1
                question_results.append({
                    "question_id": answer.question_id,
                    "selected_answer": answer.selected_answer,
                    "correct_answer": correct_map.get(answer.question_id, ""),
                    "is_correct": is_correct
                })

            total_questions = len(correct_answers)
            score = (correct_count / total_questions * 100) if total_questions > 0 else 0
            is_passed = score >= row['pass_threshold']

            # Store submission
            submission_id = str(uuid.uuid4())
            import json
            submission_row = await conn.fetchrow("""
                INSERT INTO test_submissions (
                    id, test_id, user_id, participant_name, participant_email,
                    score, total_questions, correct_answers, is_passed, time_taken_minutes,
                    answers, submitted_at, invite_token
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), $12)
                RETURNING *
            """,
                submission_id, test_id, user_id,
                submission.participant_name, submission.participant_email,
                score, total_questions, correct_count, is_passed, submission.time_taken_minutes,
                json.dumps(question_results), token
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
            """, test_id)

            return TestSubmissionResponse(
                id=str(submission_row['id']),
                test_id=str(submission_row['test_id']),
                test_title=row['title'],
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
        logger.error(f"Error submitting via share token: {e}")
        raise HTTPException(status_code=500, detail="Error submitting via share token")

# New: Per-test leaderboard (best score per user/email)
@router.get("/{test_id}/leaderboard")
async def get_test_leaderboard(
    test_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    try:
        async with pool.acquire() as conn:
            # Ensure creator
            is_creator = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1 AND created_by = $2)
            """, test_id, current_user.id)
            if not is_creator:
                raise HTTPException(status_code=403, detail="Not authorized")

            rows = await conn.fetch("""
                WITH ranked AS (
                    SELECT 
                        COALESCE(CAST(ts.user_id AS TEXT), ts.participant_email) as user_key,
                        COALESCE(u.name, ts.participant_name) as name,
                        COALESCE(u.email, ts.participant_email) as email,
                        MAX(ts.score) as best_score,
                        COUNT(*) as attempts,
                        MAX(ts.submitted_at) as last_attempt
                    FROM test_submissions ts
                    LEFT JOIN users u ON ts.user_id = u.id
                    WHERE ts.test_id = $1
                    GROUP BY 
                        COALESCE(CAST(ts.user_id AS TEXT), ts.participant_email),
                        COALESCE(u.name, ts.participant_name),
                        COALESCE(u.email, ts.participant_email)
                )
                SELECT * FROM ranked
                ORDER BY best_score DESC, last_attempt DESC
                LIMIT $2
            """, test_id, limit)

            return [
                {
                    "name": r['name'],
                    "email": r['email'],
                    "best_score": float(r['best_score']) if r['best_score'] is not None else 0.0,
                    "attempts": r['attempts'],
                    "last_attempt": r['last_attempt']
                }
                for r in rows
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Error fetching leaderboard")

# New: Export submissions as CSV
@router.get("/{test_id}/export")
async def export_test_results(
    test_id: str,
    current_user: UserResponse = Depends(get_current_user),
    pool=Depends(get_db_pool)
):
    try:
        async with pool.acquire() as conn:
            # Ensure creator
            is_creator = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM tests WHERE id = $1 AND created_by = $2)
            """, test_id, current_user.id)
            if not is_creator:
                raise HTTPException(status_code=403, detail="Not authorized")

            rows = await conn.fetch("""
                SELECT ts.submitted_at, ts.participant_name, ts.participant_email, ts.score, ts.total_questions,
                       ts.correct_answers, ts.time_taken_minutes, ts.is_passed
                FROM test_submissions ts
                WHERE ts.test_id = $1
                ORDER BY ts.submitted_at DESC
            """, test_id)

            # Build CSV
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Submitted At", "Name", "Email", "Score", "Total Questions", "Correct", "Time Minutes", "Passed"]) 
            for r in rows:
                writer.writerow([
                    r['submitted_at'], r['participant_name'], r['participant_email'],
                    float(r['score']), r['total_questions'], r['correct_answers'],
                    r['time_taken_minutes'], r['is_passed']
                ])
            output.seek(0)
            filename = f"test_{test_id}_results.csv"
            headers = {
                "Content-Disposition": f"attachment; filename={filename}"
            }
            return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting results: {e}")
        raise HTTPException(status_code=500, detail="Error exporting results")
