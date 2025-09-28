"""
Question Banks API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Optional
import uuid
import os
from datetime import datetime

from app.models import (
    QuestionBankCreate, QuestionBankResponse, QuestionResponse,
    FileUploadResponse, ErrorResponse, QuestionBankUpdate
)
from app.database import get_supabase, get_supabase_manager
from app.services.file_processor import file_processor
from app.auth import get_current_user, get_current_user_optional, UserResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/question-banks", tags=["Question Banks"])

@router.post("/upload", response_model=FileUploadResponse)
async def upload_question_bank(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    current_user: UserResponse = Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """
    Upload and process a question bank file (Excel/CSV)
    """
    try:
        # Generate unique ID for question bank
        question_bank_id = str(uuid.uuid4())
        
        # Create question bank record first
        supabase.table('question_banks').insert({
            'id': question_bank_id,
            'name': name,
            'description': description,
            'file_path': f"uploads/{file.filename}",
            'created_by': current_user.id
        }).execute()
        
        # Process the uploaded file
        questions = await file_processor.process_file(file, question_bank_id)
        
        # Insert questions into database using Supabase
        questions_imported = 0
        questions_to_insert = []
        
        for question in questions:
            try:
                question_data = {
                    'id': str(uuid.uuid4()),
                    'question_bank_id': question.question_bank_id,
                    'question_text': question.question_text,
                    'question_type': question.question_type.value,
                    'options': question.options,
                    'correct_answer': question.correct_answer,
                    'difficulty_level': question.difficulty_level.value if question.difficulty_level else None,
                    'category': question.category
                }
                questions_to_insert.append(question_data)
                questions_imported += 1
            except Exception as e:
                logger.error(f"Error preparing question: {e}")
                continue
        
        # Batch insert questions
        if questions_to_insert:
            try:
                supabase.table('questions').insert(questions_to_insert).execute()
            except Exception as e:
                logger.error(f"Error batch inserting questions: {e}")
                # Try individual inserts as fallback
                questions_imported = 0
                for question_data in questions_to_insert:
                    try:
                        supabase.table('questions').insert(question_data).execute()
                        questions_imported += 1
                    except Exception as e2:
                        logger.error(f"Error inserting individual question: {e2}")
        
        # Update question bank with file path (you might want to actually upload to Supabase Storage)
        file_path = f"uploads/{question_bank_id}/{file.filename}"
        
        return FileUploadResponse(
            message=f"Successfully imported {questions_imported} questions by {current_user.email}",
            question_bank_id=question_bank_id,
            questions_imported=questions_imported,
            file_path=file_path
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error uploading question bank: {e}")
        # Clean up question bank if it was created
        try:
            supabase.table('question_banks').delete().eq('id', question_bank_id).execute()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.get("/", response_model=List[QuestionBankResponse])
async def get_question_banks(
    skip: int = 0,
    limit: int = 100,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    supabase=Depends(get_supabase)
):
    """
    Get list of question banks with question counts
    """
    try:
        # Get question banks with pagination
        response = supabase.table('question_banks').select(
            'id, name, description, file_path, created_at, updated_at, created_by'
        ).order('created_at', desc=True).range(skip, skip + limit - 1).execute()
        
        question_banks = []
        for row in response.data:
            # Get question count for each bank
            count_response = supabase.table('questions').select(
                'id', count='exact'
            ).eq('question_bank_id', row['id']).execute()
            
            question_count = count_response.count if count_response.count else 0
            
            question_banks.append(QuestionBankResponse(
                id=str(row['id']),
                name=row['name'],
                description=row['description'],
                file_path=row['file_path'],
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at'],
                updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')) if isinstance(row['updated_at'], str) else row['updated_at'],
                created_by=str(row['created_by']),
                question_count=question_count
            ))
        
        return question_banks
    except Exception as e:
        logger.error(f"Error fetching question banks: {e}")
        raise HTTPException(status_code=500, detail="Error fetching question banks")

@router.get("/{question_bank_id}", response_model=QuestionBankResponse)
async def get_question_bank(
    question_bank_id: str,
    supabase=Depends(get_supabase)
):
    """
    Get specific question bank details
    """
    try:
        # Get question bank details
        response = supabase.table('question_banks').select(
            'id, name, description, file_path, created_at, updated_at, created_by'
        ).eq('id', question_bank_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Question bank not found")
        
        row = response.data[0]
        
        # Get question count
        count_response = supabase.table('questions').select(
            'id', count='exact'
        ).eq('question_bank_id', question_bank_id).execute()
        
        question_count = count_response.count if count_response.count else 0
        
        return QuestionBankResponse(
            id=str(row['id']),
            name=row['name'],
            description=row['description'],
            file_path=row['file_path'],
            created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at'],
            updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')) if isinstance(row['updated_at'], str) else row['updated_at'],
            created_by=str(row['created_by']),
            question_count=question_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching question bank: {e}")
        raise HTTPException(status_code=500, detail="Error fetching question bank")

@router.put("/{question_bank_id}", response_model=QuestionBankResponse)
async def update_question_bank(
    question_bank_id: str,
    update: QuestionBankUpdate,
    current_user: UserResponse = Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """
    Update question bank metadata (name, description). Only the creator can edit.
    """
    try:
        # Verify question bank exists and user owns it
        existing_response = supabase.table('question_banks').select('*').eq(
            'id', question_bank_id
        ).eq('created_by', current_user.id).execute()
        
        if not existing_response.data:
            # Check if question bank exists at all
            check_response = supabase.table('question_banks').select('id').eq('id', question_bank_id).execute()
            if not check_response.data:
                raise HTTPException(status_code=404, detail="Question bank not found")
            else:
                raise HTTPException(status_code=403, detail="Not authorized to edit this question bank")
        
        # Prepare update data
        update_data = {}
        if update.name is not None:
            update_data['name'] = update.name
        if update.description is not None:
            update_data['description'] = update.description
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No changes provided")
        
        # Add updated timestamp
        update_data['updated_at'] = datetime.now().isoformat()
        
        # Update the question bank
        update_response = supabase.table('question_banks').update(update_data).eq(
            'id', question_bank_id
        ).eq('created_by', current_user.id).execute()
        
        if not update_response.data:
            raise HTTPException(status_code=500, detail="Failed to update question bank")
        
        row = update_response.data[0]
        
        # Get question count for response
        count_response = supabase.table('questions').select(
            'id', count='exact'
        ).eq('question_bank_id', question_bank_id).execute()
        
        question_count = count_response.count if count_response.count else 0

        return QuestionBankResponse(
            id=str(row['id']),
            name=row['name'],
            description=row['description'],
            file_path=row['file_path'],
            created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at'],
            updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00')) if isinstance(row['updated_at'], str) else row['updated_at'],
            created_by=str(row['created_by']),
            question_count=question_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating question bank: {e}")
        raise HTTPException(status_code=500, detail="Error updating question bank")

@router.get("/{question_bank_id}/questions", response_model=List[QuestionResponse])
async def get_questions(
    question_bank_id: str,
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    supabase=Depends(get_supabase)
):
    """
    Get questions from a specific question bank
    """
    try:
        # Build Supabase query
        query = supabase.table('questions').select(
            'id, question_bank_id, question_text, question_type, options, correct_answer, difficulty_level, category, created_at'
        ).eq('question_bank_id', question_bank_id)
        
        if category:
            query = query.eq('category', category)
        
        if difficulty:
            query = query.eq('difficulty_level', difficulty)
        
        response = query.order('created_at', desc=True).range(skip, skip + limit - 1).execute()
        
        return [
            QuestionResponse(
                id=str(row['id']),
                question_bank_id=str(row['question_bank_id']),
                question_text=row['question_text'],
                question_type=row['question_type'],
                options=row['options'],
                correct_answer=row['correct_answer'],
                difficulty_level=row['difficulty_level'],
                category=row['category'],
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at']
            )
            for row in response.data
        ]
    except Exception as e:
        logger.error(f"Error fetching questions: {e}")
        raise HTTPException(status_code=500, detail="Error fetching questions")

@router.delete("/{question_bank_id}")
async def delete_question_bank(
    question_bank_id: str,
    current_user: UserResponse = Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """
    Delete a question bank and all its questions
    """
    try:
        # Verify question bank exists and user owns it
        existing_response = supabase.table('question_banks').select('*').eq(
            'id', question_bank_id
        ).eq('created_by', current_user.id).execute()
        
        if not existing_response.data:
            # Check if question bank exists at all
            check_response = supabase.table('question_banks').select('id').eq('id', question_bank_id).execute()
            if not check_response.data:
                raise HTTPException(status_code=404, detail="Question bank not found")
            else:
                raise HTTPException(status_code=403, detail="Not authorized to delete this question bank")
        
        # Delete questions first (foreign key constraint)
        supabase.table('questions').delete().eq('question_bank_id', question_bank_id).execute()
        
        # Delete question bank
        delete_response = supabase.table('question_banks').delete().eq(
            'id', question_bank_id
        ).eq('created_by', current_user.id).execute()
        
        if not delete_response.data:
            raise HTTPException(status_code=500, detail="Failed to delete question bank")
        
        return {"message": "Question bank deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting question bank: {e}")
        raise HTTPException(status_code=500, detail="Error deleting question bank")
