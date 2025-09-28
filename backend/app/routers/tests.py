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
from app.database import get_supabase
from app.auth import get_current_user, get_current_user_optional, UserResponse, get_password_hash
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tests", tags=["Test Management"])

@router.post("/", response_model=TestResponse)
async def create_test(
    test_data: TestCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """
    Create a new test from a question bank
    """
    try:
        test_id = str(uuid.uuid4())
        
        # SUPABASE MIGRATION: Replace pool.acquire() with direct Supabase client calls
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

        # SUPABASE: Fetch availability per bank with filters
        diff_val = test_data.difficulty_filter.value if test_data.difficulty_filter else None
        cat_val = test_data.category_filter
        available_per_bank = []
        
        for b in banks:
            # Build Supabase query for question count
            query = supabase.table('questions').select('id', count='exact').eq('question_bank_id', b)
            if diff_val:
                query = query.eq('difficulty_level', diff_val)
            if cat_val:
                query = query.eq('category', cat_val)
            
            count_response = query.execute()
            available_per_bank.append(count_response.count or 0)

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

        # SUPABASE: Create test record with JSON array support
        import json
        primary_bank = banks[0]
        test_data_insert = {
            'id': test_id,
            'title': test_data.title,
            'description': test_data.description,
            'question_bank_id': primary_bank,
            'created_by': current_user.id,
            'num_questions': test_data.num_questions,
            'time_limit_minutes': test_data.time_limit_minutes,
            'difficulty_filter': diff_val,
            'category_filter': cat_val,
            'is_public': test_data.is_public,
            'scheduled_start': test_data.scheduled_start.isoformat() if test_data.scheduled_start else None,
            'scheduled_end': test_data.scheduled_end.isoformat() if test_data.scheduled_end else None,
            'max_attempts': test_data.max_attempts,
            'pass_threshold': test_data.pass_threshold,
            'question_bank_ids': banks  # Supabase handles JSON arrays natively
        }
        
        test_response = supabase.table('tests').insert(test_data_insert).execute()
        if not test_response.data:
            raise HTTPException(status_code=500, detail="Failed to create test")
        test_row = test_response.data[0]

        # SUPABASE: Select random questions from each bank according to final_counts
        question_order = 1
        test_questions_batch = []
        
        for idx, b in enumerate(banks):
            count = final_counts[idx]
            if count <= 0:
                continue
                
            # Build Supabase query for random questions
            query = supabase.table('questions').select('id').eq('question_bank_id', b)
            if diff_val:
                query = query.eq('difficulty_level', diff_val)
            if cat_val:
                query = query.eq('category', cat_val)
            
            # Note: Supabase doesn't have RANDOM(), so we'll fetch more and randomly select
            questions_response = query.limit(count * 3).execute()  # Get more to randomize
            
            if questions_response.data:
                import random
                available_questions = questions_response.data
                random.shuffle(available_questions)
                selected_questions = available_questions[:count]
                
                for q in selected_questions:
                    test_questions_batch.append({
                        'test_id': test_id,
                        'question_id': q['id'],
                        'question_order': question_order
                    })
                    question_order += 1
        
        # SUPABASE: Batch insert test questions
        if test_questions_batch:
            supabase.table('test_questions').insert(test_questions_batch).execute()
        
        # SUPABASE: Initialize analytics record
        supabase.table('test_analytics').insert({'test_id': test_id}).execute()
        
        # SUPABASE: Resolve bank names for response
        bank_names_response = supabase.table('question_banks').select('name').in_('id', banks).execute()
        bank_names_list = [r['name'] for r in bank_names_response.data] if bank_names_response.data else []

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
    supabase=Depends(get_supabase)
):
    """
    Get list of tests with analytics
    """
    try:
        # SUPABASE MIGRATION: Replace complex SQL with multiple Supabase queries
        # Build Supabase query for tests
        query = supabase.table('tests').select('*')
        
        # Apply filters
        if question_bank_id:
            # For Supabase, we'll filter after fetching since JSONB array filtering is complex
            pass  # Will filter in Python below
        
        if is_active is not None:
            query = query.eq('is_active', is_active)
        
        if created_by_me and current_user:
            query = query.eq('created_by', current_user.id)
        
        # If not authenticated, only show public tests
        if not current_user:
            query = query.eq('is_public', True)
        
        # Get tests with pagination
        tests_response = query.order('created_at', desc=True).range(skip, skip + limit - 1).execute()
        
        # Process each test to get related data
        test_results = []
        for test_row in tests_response.data:
            # SUPABASE: Filter by question_bank_id if needed (since we can't do complex JSONB queries easily)
            if question_bank_id:
                test_bank_ids = test_row.get('question_bank_ids', [])
                if isinstance(test_bank_ids, str):
                    import json
                    try:
                        test_bank_ids = json.loads(test_bank_ids)
                    except:
                        test_bank_ids = []
                
                single_bank_id = test_row.get('question_bank_id')
                all_bank_ids = test_bank_ids if test_bank_ids else ([single_bank_id] if single_bank_id else [])
                
                if question_bank_id not in all_bank_ids:
                    continue  # Skip this test
            
            # SUPABASE: Get creator name
            creator_response = supabase.table('users').select('name').eq('id', test_row['created_by']).execute()
            creator_name = creator_response.data[0]['name'] if creator_response.data else 'Unknown'
            
            # SUPABASE: Get analytics data
            analytics_response = supabase.table('test_analytics').select('*').eq('test_id', test_row['id']).execute()
            analytics = analytics_response.data[0] if analytics_response.data else {}
            
            # SUPABASE: Get question bank names
            bank_ids = test_row.get('question_bank_ids', [])
            if isinstance(bank_ids, str):
                import json
                try:
                    bank_ids = json.loads(bank_ids)
                except:
                    bank_ids = []
            
            if not bank_ids:
                single_bank = test_row.get('question_bank_id')
                bank_ids = [single_bank] if single_bank else []
            
            bank_names = []
            if bank_ids:
                bank_names_response = supabase.table('question_banks').select('name').in_('id', bank_ids).execute()
                bank_names = [b['name'] for b in bank_names_response.data] if bank_names_response.data else []
            
            # SUPABASE: Build TestResponse object
            test_results.append(TestResponse(
                id=str(test_row['id']),
                title=test_row['title'],
                description=test_row['description'],
                question_bank_id=str(test_row['question_bank_id']),
                question_bank_ids=(test_row['question_bank_ids'] if isinstance(test_row['question_bank_ids'], list) else None),
                question_bank_names=bank_names,
                created_by=str(test_row['created_by']),
                creator_name=creator_name,
                num_questions=test_row['num_questions'],
                time_limit_minutes=test_row['time_limit_minutes'],
                difficulty_filter=test_row['difficulty_filter'],
                category_filter=test_row['category_filter'],
                is_active=test_row['is_active'],
                is_public=test_row['is_public'],
                scheduled_start=datetime.fromisoformat(test_row['scheduled_start'].replace('Z', '+00:00')) if test_row.get('scheduled_start') and isinstance(test_row['scheduled_start'], str) else test_row.get('scheduled_start'),
                scheduled_end=datetime.fromisoformat(test_row['scheduled_end'].replace('Z', '+00:00')) if test_row.get('scheduled_end') and isinstance(test_row['scheduled_end'], str) else test_row.get('scheduled_end'),
                max_attempts=test_row['max_attempts'],
                pass_threshold=test_row['pass_threshold'],
                created_at=datetime.fromisoformat(test_row['created_at'].replace('Z', '+00:00')) if isinstance(test_row['created_at'], str) else test_row['created_at'],
                updated_at=datetime.fromisoformat(test_row['updated_at'].replace('Z', '+00:00')) if isinstance(test_row['updated_at'], str) else test_row['updated_at'],
                test_link=f"/test/{test_row['id']}",
                total_submissions=analytics.get('total_submissions', 0) or 0,
                total_participants=analytics.get('total_participants', 0) or 0,
                average_score=float(analytics.get('average_score', 0) or 0),
                pass_rate=float(analytics.get('pass_rate', 0) or 0)
            ))
        
        return test_results
    except Exception as e:
        logger.error(f"Error fetching tests: {e}")
        raise HTTPException(status_code=500, detail="Error fetching tests")

@router.get("/{test_id}", response_model=TestDetailsResponse)
async def get_test_details(
    test_id: str,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    supabase=Depends(get_supabase)
):
    """
    Get test details - accessible for both authenticated and anonymous users for public tests
    """
    """
    Get test details with questions (for taking the test)
    """
    try:
        # SUPABASE MIGRATION: Replace pool operations with Supabase client calls
        # Get test info with creator details
        test_response = supabase.table('tests').select('*').eq('id', test_id).execute()
        
        if not test_response.data:
            raise HTTPException(status_code=404, detail="Test not found")
        
        test_row = test_response.data[0]
        
        # Get creator name
        creator_response = supabase.table('users').select('name').eq('id', test_row['created_by']).execute()
        creator_name = creator_response.data[0]['name'] if creator_response.data else 'Unknown'
        test_row['creator_name'] = creator_name
        
        # Check if test is accessible
        if not test_row['is_public'] and (not current_user or current_user.id != test_row['created_by']):
            raise HTTPException(status_code=403, detail="Test is not public")
        
        # Check if test is scheduled and available
        now = datetime.utcnow()
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
        
        # SUPABASE: Get test questions with join-like behavior
        test_questions_response = supabase.table('test_questions').select('*').eq('test_id', test_id).order('question_order').execute()
        
        questions = []
        if test_questions_response.data:
            question_ids = [tq['question_id'] for tq in test_questions_response.data]
            questions_response = supabase.table('questions').select('id, question_text, question_type, options').in_('id', question_ids).execute()
            
            # Create a lookup dict for question details
            question_details = {q['id']: q for q in questions_response.data} if questions_response.data else {}
            
            # Combine test_questions with question details
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
        
        # SUPABASE: Check user attempts if authenticated
        user_attempts = 0
        user_best_score = None
        can_attempt = True
        
        if current_user:
            performance_response = supabase.table('user_performance').select('attempts_count, best_score').eq('user_id', current_user.id).eq('test_id', test_id).execute()
            
            if performance_response.data:
                performance = performance_response.data[0]
                user_attempts = performance['attempts_count']
                user_best_score = float(performance['best_score']) if performance['best_score'] else None
                can_attempt = user_attempts < test_row['max_attempts']
        
        return TestDetailsResponse(
            id=str(test_row['id']),
            title=test_row['title'],
            description=test_row['description'],
            time_limit_minutes=test_row['time_limit_minutes'],
            total_questions=test_row['num_questions'],
            max_attempts=test_row['max_attempts'],
            pass_threshold=test_row['pass_threshold'],
            scheduled_start=test_row.get('scheduled_start'),
            scheduled_end=test_row.get('scheduled_end'),
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
    supabase=Depends(get_supabase)
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
    supabase=Depends(get_supabase)
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
    supabase=Depends(get_supabase)
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
    supabase=Depends(get_supabase)
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
    supabase=Depends(get_supabase)
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
    supabase=Depends(get_supabase)
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
async def get_shared_test(token: str, supabase=Depends(get_supabase)):
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
    supabase=Depends(get_supabase)
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
    supabase=Depends(get_supabase)
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
    supabase=Depends(get_supabase)
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
