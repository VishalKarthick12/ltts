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
        # SUPABASE MIGRATION: Replace pool operations with Supabase client calls
        # Check if test exists and user is creator
        test_response = supabase.table('tests').select('*').eq('id', test_id).eq('created_by', current_user.id).execute()
        
        if not test_response.data:
            raise HTTPException(status_code=404, detail="Test not found or not authorized")
        
        # Build update data
        update_fields = update_data.dict(exclude_unset=True)
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Add updated_at timestamp
        update_fields['updated_at'] = datetime.utcnow().isoformat()
        
        # SUPABASE: Update the test
        update_response = supabase.table('tests').update(update_fields).eq('id', test_id).eq('created_by', current_user.id).execute()
        
        if not update_response.data:
            raise HTTPException(status_code=500, detail="Failed to update test")
        
        updated_row = update_response.data[0]
        
        return TestResponse(
            id=str(updated_row['id']),
            title=updated_row['title'],
            description=updated_row['description'],
            question_bank_id=str(updated_row['question_bank_id']),
            question_bank_ids=(updated_row['question_bank_ids'] if isinstance(updated_row['question_bank_ids'], list) else None),
            question_bank_names=[],  # Simplified for now
            created_by=str(updated_row['created_by']),
            creator_name=current_user.name,  # Use current user's name since they're the creator
            num_questions=updated_row['num_questions'],
            time_limit_minutes=updated_row['time_limit_minutes'],
            difficulty_filter=updated_row['difficulty_filter'],
            category_filter=updated_row['category_filter'],
            is_active=updated_row['is_active'],
            is_public=updated_row['is_public'],
            scheduled_start=datetime.fromisoformat(updated_row['scheduled_start'].replace('Z', '+00:00')) if updated_row.get('scheduled_start') and isinstance(updated_row['scheduled_start'], str) else updated_row.get('scheduled_start'),
            scheduled_end=datetime.fromisoformat(updated_row['scheduled_end'].replace('Z', '+00:00')) if updated_row.get('scheduled_end') and isinstance(updated_row['scheduled_end'], str) else updated_row.get('scheduled_end'),
            max_attempts=updated_row['max_attempts'],
            pass_threshold=updated_row['pass_threshold'],
            created_at=datetime.fromisoformat(updated_row['created_at'].replace('Z', '+00:00')) if isinstance(updated_row['created_at'], str) else updated_row['created_at'],
            updated_at=datetime.fromisoformat(updated_row['updated_at'].replace('Z', '+00:00')) if isinstance(updated_row['updated_at'], str) else updated_row['updated_at'],
            test_link=f"/test/{updated_row['id']}",
            total_submissions=0,  # Will be populated by analytics if needed
            total_participants=0,
            average_score=0,
            pass_rate=0
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
        # SUPABASE: Check if test exists and user is creator
        test_response = supabase.table('tests').select('id').eq('id', test_id).eq('created_by', current_user.id).execute()
        
        if not test_response.data:
            raise HTTPException(status_code=404, detail="Test not found or not authorized")
        
        # SUPABASE: Delete test (cascades to submissions, questions, analytics)
        delete_response = supabase.table('tests').delete().eq('id', test_id).execute()
        
        if not delete_response.data:
            raise HTTPException(status_code=500, detail="Failed to delete test")
        
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
        # SUPABASE MIGRATION: Fix submit_test to use Supabase instead of pool
        # Get test details
        test_response = supabase.table('tests').select('*').eq('id', test_id).eq('is_active', True).execute()
        
        if not test_response.data:
            raise HTTPException(status_code=404, detail="Test not found or inactive")
        
        test_row = test_response.data[0]
        
        # Check if test is accessible
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
        
        # SUPABASE: Check user attempts if authenticated
        if current_user:
            attempts_response = supabase.table('user_performance').select('attempts_count').eq('user_id', current_user.id).eq('test_id', test_id).execute()
            
            attempts = attempts_response.data[0]['attempts_count'] if attempts_response.data else 0
            
            if attempts and attempts >= test_row['max_attempts']:
                raise HTTPException(status_code=403, detail="Maximum attempts exceeded")
            
        # SUPABASE: Get correct answers with JOIN-like behavior
        test_questions_response = supabase.table('test_questions').select('question_id').eq('test_id', test_id).execute()
        
        if not test_questions_response.data:
            raise HTTPException(status_code=400, detail="No questions found for this test")
        
        question_ids = [tq['question_id'] for tq in test_questions_response.data]
        questions_response = supabase.table('questions').select('id, correct_answer').in_('id', question_ids).execute()
        
        correct_map = {str(row['id']): row['correct_answer'] for row in questions_response.data} if questions_response.data else {}
        
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
        
        total_questions = len(questions_response.data) if questions_response.data else 0
        score = (correct_count / total_questions * 100) if total_questions > 0 else 0
        is_passed = score >= test_row['pass_threshold']
        
        # SUPABASE: Store submission
        submission_id = str(uuid.uuid4())
        import json
        submission_data = {
            'id': submission_id,
            'test_id': test_id,
            'user_id': current_user.id if current_user else None,
            'participant_name': submission.participant_name,
            'participant_email': submission.participant_email,
            'score': score,
            'total_questions': total_questions,
            'correct_answers': correct_count,
            'time_taken_minutes': submission.time_taken_minutes,
            'answers': json.dumps(question_results),
            'submitted_at': now.isoformat(),
            'is_passed': is_passed
        }
        
        submission_response = supabase.table('test_submissions').insert(submission_data).execute()
        
        if not submission_response.data:
            raise HTTPException(status_code=500, detail="Failed to store submission")
        
        submission_row = submission_response.data[0]
        
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
            submitted_at=datetime.fromisoformat(submission_row['submitted_at'].replace('Z', '+00:00')) if isinstance(submission_row['submitted_at'], str) else submission_row['submitted_at'],
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
        # SUPABASE: Check if user is test creator
        test_response = supabase.table('tests').select('created_by').eq('id', test_id).execute()
        
        if not test_response.data or test_response.data[0]['created_by'] != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view analytics")
        
        # SUPABASE: Get analytics
        analytics_response = supabase.table('test_analytics').select('*').eq('test_id', test_id).execute()
        
        if not analytics_response.data:
            # Calculate analytics on the fly if not in analytics table
            submissions_response = supabase.table('test_submissions').select('*').eq('test_id', test_id).execute()
            
            if not submissions_response.data:
                # Return empty analytics
                return TestAnalytics(
                    test_id=test_id,
                    total_submissions=0,
                    total_participants=0,
                    average_score=0.0,
                    pass_rate=0.0,
                    average_time_minutes=0.0,
                    last_updated=datetime.utcnow()
                )
            
            # Calculate analytics from submissions
            submissions = submissions_response.data
            total_submissions = len(submissions)
            
            # Calculate unique participants
            participants = set()
            for sub in submissions:
                if sub.get('user_id'):
                    participants.add(sub['user_id'])
                elif sub.get('participant_email'):
                    participants.add(sub['participant_email'])
            total_participants = len(participants)
            
            # Calculate averages
            scores = [sub.get('score', 0) for sub in submissions]
            average_score = sum(scores) / len(scores) if scores else 0
            
            passed_count = sum(1 for sub in submissions if sub.get('is_passed', False))
            pass_rate = (passed_count / total_submissions * 100) if total_submissions > 0 else 0
            
            times = [sub.get('time_taken_minutes', 0) for sub in submissions if sub.get('time_taken_minutes')]
            average_time_minutes = sum(times) / len(times) if times else 0
            
            return TestAnalytics(
                test_id=test_id,
                total_submissions=total_submissions,
                total_participants=total_participants,
                average_score=float(average_score),
                pass_rate=float(pass_rate),
                average_time_minutes=float(average_time_minutes),
                last_updated=datetime.utcnow()
            )
        
        analytics = analytics_response.data[0]
        
        # Parse last_updated if string
        last_updated = analytics.get('last_updated')
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
        
        return TestAnalytics(
            test_id=str(analytics['test_id']),
            total_submissions=analytics.get('total_submissions', 0),
            total_participants=analytics.get('total_participants', 0),
            average_score=float(analytics.get('average_score', 0)),
            pass_rate=float(analytics.get('pass_rate', 0)),
            average_time_minutes=float(analytics.get('average_time_minutes', 0)),
            last_updated=last_updated or datetime.utcnow()
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
        # SUPABASE MIGRATION: Fix get_test_submissions to use Supabase and match frontend expectations
        # Check if user is test creator
        is_creator_response = supabase.table('tests').select('id, title').eq('id', test_id).eq('created_by', current_user.id).execute()
        
        if not is_creator_response.data:
            # Check if test exists
            test_exists_response = supabase.table('tests').select('id').eq('id', test_id).execute()
            if not test_exists_response.data:
                raise HTTPException(status_code=404, detail="Test not found")
            raise HTTPException(status_code=403, detail="Not authorized to view submissions")

        test_title = is_creator_response.data[0]['title']
        
        # SUPABASE: Get submissions with filters - start with base query
        query = supabase.table('test_submissions').select('*').eq('test_id', test_id)
        
        # Apply date filters if provided
        if start_date:
            query = query.gte('submitted_at', start_date)
        if end_date:
            query = query.lte('submitted_at', end_date)
        
        # Apply ordering and pagination
        submissions_response = query.order('submitted_at', desc=True).range(skip, skip + limit - 1).execute()
        
        if not submissions_response.data:
            return []
        
        # Enrich submissions with user names and apply user filter if needed
        enriched_submissions = []
        for submission in submissions_response.data:
            # Get user name if user_id exists
            user_name = submission.get('participant_name', 'Anonymous')
            if submission.get('user_id'):
                user_response = supabase.table('users').select('name, email').eq('id', submission['user_id']).execute()
                if user_response.data:
                    user_data = user_response.data[0]
                    user_name = user_data['name']
                    # Update participant_email with actual user email if not set
                    if not submission.get('participant_email'):
                        submission['participant_email'] = user_data['email']
            
            submission['user_name'] = user_name
            
            # Apply user filter in Python (since Supabase doesn't support complex text search easily)
            if user:
                user_lower = user.lower()
                participant_name = (submission.get('participant_name') or '').lower()
                participant_email = (submission.get('participant_email') or '').lower()
                user_name_lower = user_name.lower()
                
                if not (user_lower in participant_name or user_lower in participant_email or user_lower in user_name_lower):
                    continue
            
            enriched_submissions.append(submission)
        
        # Return submissions in the expected format for frontend analytics
        return [
            TestSubmissionResponse(
                id=str(sub['id']),
                test_id=str(sub['test_id']),
                test_title=test_title,
                participant_name=sub['participant_name'],
                participant_email=sub.get('participant_email'),
                score=float(sub['score']),
                total_questions=sub['total_questions'],
                correct_answers=sub['correct_answers'],
                time_taken_minutes=sub.get('time_taken_minutes'),
                is_passed=sub['is_passed'],
                submitted_at=datetime.fromisoformat(sub['submitted_at'].replace('Z', '+00:00')) if isinstance(sub['submitted_at'], str) else sub['submitted_at']
            )
            for sub in enriched_submissions
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
        # SUPABASE: Verify test ownership
        test_response = supabase.table('tests').select('id').eq('id', test_id).eq('created_by', current_user.id).execute()
        
        if not test_response.data:
            # Check if test exists at all
            test_exists = supabase.table('tests').select('id').eq('id', test_id).execute()
            if not test_exists.data:
                raise HTTPException(status_code=404, detail="Test not found")
            raise HTTPException(status_code=403, detail="Not authorized")

        # SUPABASE: Create or reuse an active link
        now = datetime.utcnow()
        existing_response = supabase.table('test_public_links').select('*').eq('test_id', test_id).eq('is_active', True).order('created_at', desc=True).limit(1).execute()
        
        if existing_response.data:
            # Check if not expired
            existing = existing_response.data[0]
            if existing.get('expires_at'):
                expires_at = datetime.fromisoformat(existing['expires_at'].replace('Z', '+00:00')) if isinstance(existing['expires_at'], str) else existing['expires_at']
                if expires_at and expires_at < now:
                    existing = None
            
            if existing:
                return {
                    "test_id": test_id,
                    "share_url": f"/test/{test_id}?token={existing['link_token']}",
                    "link_token": existing['link_token'],
                    "expires_at": existing.get('expires_at')
                }
        
        # Create new link
        link_token = secrets.token_urlsafe(16)
        link_id = str(uuid.uuid4())
        
        new_link_response = supabase.table('test_public_links').insert({
            'id': link_id,
            'test_id': test_id,
            'created_by': current_user.id,
            'link_token': link_token,
            'is_active': True,
            'created_at': now.isoformat()
        }).execute()
        
        if not new_link_response.data:
            raise HTTPException(status_code=500, detail="Failed to create share link")
        
        return {
            "test_id": test_id,
            "share_url": f"/test/{test_id}?token={link_token}",
            "link_token": link_token,
            "expires_at": None
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
        # SUPABASE: Check public link first
        now = datetime.utcnow()
        link_response = supabase.table('test_public_links').select('*').eq('link_token', token).eq('is_active', True).execute()
        
        test_data = None
        if link_response.data:
            link = link_response.data[0]
            # Check expiry
            if link.get('expires_at'):
                expires_at = datetime.fromisoformat(link['expires_at'].replace('Z', '+00:00')) if isinstance(link['expires_at'], str) else link['expires_at']
                if expires_at and expires_at < now:
                    link = None
            
            if link:
                # Get test details
                test_response = supabase.table('tests').select('*').eq('id', link['test_id']).execute()
                if test_response.data:
                    test_data = test_response.data[0]
        
        # If not found, check invite tokens
        if not test_data:
            invite_response = supabase.table('test_invites').select('*').eq('invite_token', token).eq('status', 'pending').execute()
            
            if invite_response.data:
                invite = invite_response.data[0]
                # Check expiry
                if invite.get('expires_at'):
                    expires_at = datetime.fromisoformat(invite['expires_at'].replace('Z', '+00:00')) if isinstance(invite['expires_at'], str) else invite['expires_at']
                    if expires_at and expires_at < now:
                        invite = None
                
                if invite:
                    # Get test details
                    test_response = supabase.table('tests').select('*').eq('id', invite['test_id']).execute()
                    if test_response.data:
                        test_data = test_response.data[0]
        
        if not test_data:
            raise HTTPException(status_code=404, detail="Invalid or expired share token")

        return {
            "test_id": str(test_data['id']),
            "title": test_data['title'],
            "description": test_data.get('description'),
            "num_questions": test_data['num_questions'],
            "time_limit_minutes": test_data.get('time_limit_minutes'),
            "pass_threshold": test_data.get('pass_threshold', 60),
            "is_active": test_data.get('is_active', True),
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
        # SUPABASE: Resolve test via token
        now = datetime.utcnow()
        test_data = None
        
        # Check public link
        link_response = supabase.table('test_public_links').select('*').eq('link_token', token).eq('is_active', True).execute()
        if link_response.data:
            link = link_response.data[0]
            # Check expiry
            if link.get('expires_at'):
                expires_at = datetime.fromisoformat(link['expires_at'].replace('Z', '+00:00')) if isinstance(link['expires_at'], str) else link['expires_at']
                if not expires_at or expires_at > now:
                    # Get test
                    test_response = supabase.table('tests').select('*').eq('id', link['test_id']).execute()
                    if test_response.data:
                        test_data = test_response.data[0]
        
        # If not found, check invite token
        if not test_data:
            invite_response = supabase.table('test_invites').select('*').eq('invite_token', token).eq('status', 'pending').execute()
            if invite_response.data:
                invite = invite_response.data[0]
                # Check expiry
                if invite.get('expires_at'):
                    expires_at = datetime.fromisoformat(invite['expires_at'].replace('Z', '+00:00')) if isinstance(invite['expires_at'], str) else invite['expires_at']
                    if not expires_at or expires_at > now:
                        # Get test
                        test_response = supabase.table('tests').select('*').eq('id', invite['test_id']).execute()
                        if test_response.data:
                            test_data = test_response.data[0]
        
        if not test_data:
            raise HTTPException(status_code=404, detail="Invalid or expired share token")

        test_id = str(test_data['id'])

        # SUPABASE: Resolve or create user
        user_id = None
        if current_user:
            user_id = current_user.id
        elif submission.participant_email:
            existing_user_response = supabase.table('users').select('id').eq('email', submission.participant_email).eq('is_active', True).execute()
            if existing_user_response.data:
                user_id = existing_user_response.data[0]['id']
            else:
                # Try to create new user
                try:
                    password_hash = get_password_hash(secrets.token_urlsafe(16))
                    new_user_response = supabase.table('users').insert({
                        'name': submission.participant_name,
                        'email': submission.participant_email,
                        'password_hash': password_hash,
                        'is_active': True
                    }).execute()
                    if new_user_response.data:
                        user_id = new_user_response.data[0]['id']
                except Exception:
                    user_id = None

        # SUPABASE: Get correct answers
        test_questions_response = supabase.table('test_questions').select('question_id').eq('test_id', test_id).execute()
        
        if not test_questions_response.data:
            raise HTTPException(status_code=400, detail="No questions found for this test")
        
        question_ids = [tq['question_id'] for tq in test_questions_response.data]
        questions_response = supabase.table('questions').select('id, correct_answer').in_('id', question_ids).execute()
        
        correct_map = {str(row['id']): row['correct_answer'] for row in questions_response.data} if questions_response.data else {}

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

        total_questions = len(questions_response.data) if questions_response.data else 0
        score = (correct_count / total_questions * 100) if total_questions > 0 else 0
        is_passed = score >= test_data.get('pass_threshold', 60)

        # SUPABASE: Store submission
        submission_id = str(uuid.uuid4())
        import json
        submission_data = {
            'id': submission_id,
            'test_id': test_id,
            'user_id': user_id,
            'participant_name': submission.participant_name,
            'participant_email': submission.participant_email,
            'score': score,
            'total_questions': total_questions,
            'correct_answers': correct_count,
            'is_passed': is_passed,
            'time_taken_minutes': submission.time_taken_minutes,
            'answers': json.dumps(question_results),
            'submitted_at': now.isoformat(),
            'invite_token': token
        }
        
        submission_response = supabase.table('test_submissions').insert(submission_data).execute()
        
        if not submission_response.data:
            raise HTTPException(status_code=500, detail="Failed to store submission")
        
        submission_row = submission_response.data[0]

        # SUPABASE: Update analytics (simplified - analytics can be computed on demand)
        # This is handled by the analytics endpoints when needed

        return TestSubmissionResponse(
            id=str(submission_row['id']),
            test_id=str(submission_row['test_id']),
            test_title=test_data['title'],
            participant_name=submission_row['participant_name'],
            participant_email=submission_row.get('participant_email'),
            score=float(submission_row['score']),
            total_questions=submission_row['total_questions'],
            correct_answers=submission_row['correct_answers'],
            time_taken_minutes=submission_row.get('time_taken_minutes'),
            is_passed=is_passed,
            submitted_at=datetime.fromisoformat(submission_row['submitted_at'].replace('Z', '+00:00')) if isinstance(submission_row['submitted_at'], str) else submission_row['submitted_at'],
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
        # SUPABASE MIGRATION: Fix test leaderboard to use Supabase and match frontend expectations
        # Check if user is test creator
        is_creator_response = supabase.table('tests').select('id').eq('id', test_id).eq('created_by', current_user.id).execute()
        
        if not is_creator_response.data:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Get all submissions for this test
        submissions_response = supabase.table('test_submissions').select('*').eq('test_id', test_id).execute()
        
        if not submissions_response.data:
            return []

        # Group by user (user_id or participant_email) and calculate best scores
        user_stats = {}
        for submission in submissions_response.data:
            # Use user_id if available, otherwise use participant_email as key
            user_key = submission.get('user_id') or submission.get('participant_email')
            if not user_key:
                continue
                
            if user_key not in user_stats:
                user_stats[user_key] = {
                    'scores': [],
                    'attempts': 0,
                    'last_attempt': None,
                    'name': submission.get('participant_name', 'Anonymous'),
                    'email': submission.get('participant_email', ''),
                    'user_id': submission.get('user_id')
                }
            
            stats = user_stats[user_key]
            stats['scores'].append(submission.get('score', 0))
            stats['attempts'] += 1
            
            submitted_at = submission.get('submitted_at')
            if isinstance(submitted_at, str):
                submitted_at = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
            
            if not stats['last_attempt'] or submitted_at > stats['last_attempt']:
                stats['last_attempt'] = submitted_at

        # Enrich with actual user data if user_id exists
        leaderboard = []
        for user_key, stats in user_stats.items():
            name = stats['name']
            email = stats['email']
            
            # If we have a user_id, get the actual user data
            if stats['user_id']:
                user_response = supabase.table('users').select('name, email').eq('id', stats['user_id']).execute()
                if user_response.data:
                    user_data = user_response.data[0]
                    name = user_data['name']
                    email = user_data['email']
            
            best_score = max(stats['scores']) if stats['scores'] else 0
            
            leaderboard.append({
                "name": name,
                "email": email,
                "best_score": float(best_score),
                "attempts": stats['attempts'],
                "last_attempt": stats['last_attempt']
            })

        # Sort by best score descending, then by last attempt
        leaderboard.sort(key=lambda x: (-x['best_score'], x['last_attempt'] or datetime.min), reverse=False)
        
        return leaderboard[:limit]
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
        # SUPABASE: Ensure creator
        test_response = supabase.table('tests').select('id').eq('id', test_id).eq('created_by', current_user.id).execute()
        
        if not test_response.data:
            raise HTTPException(status_code=403, detail="Not authorized")

        # SUPABASE: Get all submissions
        submissions_response = supabase.table('test_submissions').select('*').eq('test_id', test_id).order('submitted_at', desc=True).execute()
        
        rows = submissions_response.data or []

        # Build CSV
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Submitted At", "Name", "Email", "Score", "Total Questions", "Correct", "Time Minutes", "Passed"]) 
        for r in rows:
            writer.writerow([
                r.get('submitted_at', ''), 
                r.get('participant_name', ''), 
                r.get('participant_email', ''),
                float(r.get('score', 0)), 
                r.get('total_questions', 0), 
                r.get('correct_answers', 0),
                r.get('time_taken_minutes', 0), 
                r.get('is_passed', False)
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
