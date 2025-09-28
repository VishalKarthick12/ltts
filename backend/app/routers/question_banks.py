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
from app.database import get_db_pool, get_supabase
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
    pool=Depends(get_db_pool),
    supabase=Depends(get_supabase)
):
    """
    Upload and process a question bank file (Excel/CSV)
    """
    try:
        # Generate unique ID for question bank
        question_bank_id = str(uuid.uuid4())
        
        # Create question bank record first
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO question_banks (id, name, description, file_path, created_by)
                VALUES ($1, $2, $3, $4, $5)
            """, question_bank_id, name, description, f"uploads/{file.filename}", current_user.id)
        
        # Process the uploaded file
        questions = await file_processor.process_file(file, question_bank_id)
        
        # Insert questions into database
        questions_imported = 0
        async with pool.acquire() as conn:
            for question in questions:
                try:
                    await conn.execute("""
                        INSERT INTO questions (
                            id, question_bank_id, question_text, question_type,
                            options, correct_answer, difficulty_level, category
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, 
                        str(uuid.uuid4()),
                        question.question_bank_id,
                        question.question_text,
                        question.question_type.value,
                        question.options,
                        question.correct_answer,
                        question.difficulty_level.value if question.difficulty_level else None,
                        question.category
                    )
                    questions_imported += 1
                except Exception as e:
                    logger.error(f"Error inserting question: {e}")
                    continue
        
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
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM question_banks WHERE id = $1", question_bank_id)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.get("/", response_model=List[QuestionBankResponse])
async def get_question_banks(
    skip: int = 0,
    limit: int = 100,
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
    pool=Depends(get_db_pool)
):
    """
    Get list of question banks with question counts
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    qb.id, qb.name, qb.description, qb.file_path,
                    qb.created_at, qb.updated_at, qb.created_by,
                    COUNT(q.id) as question_count
                FROM question_banks qb
                LEFT JOIN questions q ON qb.id = q.question_bank_id
                GROUP BY qb.id, qb.name, qb.description, qb.file_path,
                         qb.created_at, qb.updated_at, qb.created_by
                ORDER BY qb.created_at DESC
                OFFSET $1 LIMIT $2
            """, skip, limit)
            
            return [
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
                for row in rows
            ]
    except Exception as e:
        logger.error(f"Error fetching question banks: {e}")
        raise HTTPException(status_code=500, detail="Error fetching question banks")

@router.get("/{question_bank_id}", response_model=QuestionBankResponse)
async def get_question_bank(
    question_bank_id: str,
    pool=Depends(get_db_pool)
):
    """
    Get specific question bank details
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    qb.id, qb.name, qb.description, qb.file_path,
                    qb.created_at, qb.updated_at, qb.created_by,
                    COUNT(q.id) as question_count
                FROM question_banks qb
                LEFT JOIN questions q ON qb.id = q.question_bank_id
                WHERE qb.id = $1
                GROUP BY qb.id, qb.name, qb.description, qb.file_path,
                         qb.created_at, qb.updated_at, qb.created_by
            """, question_bank_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Question bank not found")
            
            return QuestionBankResponse(
                id=str(row['id']),
                name=row['name'],
                description=row['description'],
                file_path=row['file_path'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                created_by=str(row['created_by']),
                question_count=row['question_count']
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
    pool=Depends(get_db_pool)
):
    """
    Update question bank metadata (name, description). Only the creator can edit.
    """
    try:
        async with pool.acquire() as conn:
            # Verify ownership
            is_owner = await conn.fetchval(
                """
                SELECT EXISTS(SELECT 1 FROM question_banks WHERE id = $1 AND created_by = $2)
                """,
                question_bank_id, current_user.id
            )
            if not is_owner:
                # Determine if it's not found or forbidden
                exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM question_banks WHERE id = $1)", question_bank_id)
                if not exists:
                    raise HTTPException(status_code=404, detail="Question bank not found")
                raise HTTPException(status_code=403, detail="Not authorized to edit this question bank")

            updates = []
            params = []
            idx = 0
            if update.name is not None:
                idx += 1
                updates.append(f"name = ${idx}")
                params.append(update.name)
            if update.description is not None:
                idx += 1
                updates.append(f"description = ${idx}")
                params.append(update.description)
            if not updates:
                raise HTTPException(status_code=400, detail="No changes provided")

            # updated_at
            from datetime import datetime
            idx += 1
            updates.append(f"updated_at = ${idx}")
            params.append(datetime.utcnow())
            idx += 1
            params.append(question_bank_id)

            row = await conn.fetchrow(
                f"""
                UPDATE question_banks
                SET {', '.join(updates)}
                WHERE id = ${idx}
                RETURNING id, name, description, file_path, created_at, updated_at, created_by
                """,
                *params
            )

            # Fetch question count for response
            count = await conn.fetchval("SELECT COUNT(*) FROM questions WHERE question_bank_id = $1", question_bank_id)

            return QuestionBankResponse(
                id=str(row['id']),
                name=row['name'],
                description=row['description'],
                file_path=row['file_path'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                created_by=str(row['created_by']),
                question_count=count
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
    pool=Depends(get_db_pool)
):
    """
    Get questions from a specific question bank
    """
    try:
        # Build dynamic query
        conditions = ["question_bank_id = $1"]
        params = [question_bank_id]
        param_count = 1
        
        if category:
            param_count += 1
            conditions.append(f"category = ${param_count}")
            params.append(category)
        
        if difficulty:
            param_count += 1
            conditions.append(f"difficulty_level = ${param_count}")
            params.append(difficulty)
        
        query = f"""
            SELECT id, question_bank_id, question_text, question_type,
                   options, correct_answer, difficulty_level, category, created_at
            FROM questions
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
            OFFSET ${param_count + 1} LIMIT ${param_count + 2}
        """
        params.extend([skip, limit])
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
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
                    created_at=row['created_at']
                )
                for row in rows
            ]
    except Exception as e:
        logger.error(f"Error fetching questions: {e}")
        raise HTTPException(status_code=500, detail="Error fetching questions")

@router.delete("/{question_bank_id}")
async def delete_question_bank(
    question_bank_id: str,
    pool=Depends(get_db_pool)
):
    """
    Delete a question bank and all its questions
    """
    try:
        async with pool.acquire() as conn:
            # Check if question bank exists
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM question_banks WHERE id = $1)",
                question_bank_id
            )
            
            if not exists:
                raise HTTPException(status_code=404, detail="Question bank not found")
            
            # Delete questions first (due to foreign key constraint)
            await conn.execute("DELETE FROM questions WHERE question_bank_id = $1", question_bank_id)
            
            # Delete question bank
            await conn.execute("DELETE FROM question_banks WHERE id = $1", question_bank_id)
            
            return {"message": "Question bank deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting question bank: {e}")
        raise HTTPException(status_code=500, detail="Error deleting question bank")
