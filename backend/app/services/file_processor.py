"""
File processing service for Excel/CSV question bank uploads
"""

import pandas as pd
import io
from typing import List, Dict, Any, Tuple
from fastapi import UploadFile, HTTPException
import logging
from app.models import QuestionCreate, QuestionType, DifficultyLevel

logger = logging.getLogger(__name__)

class FileProcessorService:
    """Service for processing uploaded question bank files"""
    
    SUPPORTED_EXTENSIONS = {'.xlsx', '.xls', '.csv'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Expected column mappings (flexible naming)
    COLUMN_MAPPINGS = {
        'question': ['question', 'question_text', 'q', 'question_content'],
        'type': ['type', 'question_type', 'qtype', 'kind'],
        'options': ['options', 'choices', 'answers', 'multiple_choice_options'],
        'correct_answer': ['correct_answer', 'answer', 'correct', 'solution'],
        'difficulty': ['difficulty', 'difficulty_level', 'level', 'diff'],
        'category': ['category', 'subject', 'topic', 'cat']
    }
    
    def __init__(self):
        pass
    
    async def process_file(self, file: UploadFile, question_bank_id: str) -> List[QuestionCreate]:
        """
        Process uploaded file and return list of questions
        """
        # Validate file
        await self._validate_file(file)
        
        # Read file content
        content = await file.read()
        
        # Parse based on file type
        if file.filename.lower().endswith('.csv'):
            df = self._parse_csv(content)
        else:  # Excel files
            df = self._parse_excel(content)
        
        # Validate and transform data
        questions = await self._transform_to_questions(df, question_bank_id)
        
        return questions
    
    async def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file"""
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Check file extension
        file_ext = '.' + file.filename.split('.')[-1].lower()
        if file_ext not in self.SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type. Supported: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )
        
        # Check file size (estimate)
        file.file.seek(0, 2)  # Seek to end
        size = file.file.tell()
        file.file.seek(0)  # Reset
        
        if size > self.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"File too large. Maximum size: {self.MAX_FILE_SIZE / (1024*1024):.1f}MB"
            )
    
    def _parse_csv(self, content: bytes) -> pd.DataFrame:
        """Parse CSV content"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    csv_string = content.decode(encoding)
                    df = pd.read_csv(io.StringIO(csv_string))
                    logger.info(f"Successfully parsed CSV with {encoding} encoding")
                    return df
                except UnicodeDecodeError:
                    continue
            
            raise HTTPException(status_code=400, detail="Could not decode CSV file")
            
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")
            raise HTTPException(status_code=400, detail=f"Error parsing CSV file: {str(e)}")
    
    def _parse_excel(self, content: bytes) -> pd.DataFrame:
        """Parse Excel content"""
        try:
            # Try to read Excel file
            df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            logger.info(f"Successfully parsed Excel file")
            return df
        except Exception as e:
            try:
                # Fallback to xlrd for older Excel files
                df = pd.read_excel(io.BytesIO(content), engine='xlrd')
                logger.info(f"Successfully parsed Excel file with xlrd")
                return df
            except Exception as e2:
                logger.error(f"Error parsing Excel: {e}, {e2}")
                raise HTTPException(status_code=400, detail=f"Error parsing Excel file: {str(e)}")
    
    async def _transform_to_questions(self, df: pd.DataFrame, question_bank_id: str) -> List[QuestionCreate]:
        """Transform DataFrame to Question objects"""
        if df.empty:
            raise HTTPException(status_code=400, detail="File contains no data")
        
        # Map columns to standard names
        column_mapping = self._detect_columns(df.columns.tolist())
        
        questions = []
        errors = []
        
        for index, row in df.iterrows():
            try:
                question = await self._create_question_from_row(row, column_mapping, question_bank_id)
                questions.append(question)
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
        
        if errors and not questions:
            raise HTTPException(
                status_code=400, 
                detail=f"No valid questions found. Errors: {'; '.join(errors[:5])}"
            )
        
        if errors:
            logger.warning(f"Processed {len(questions)} questions with {len(errors)} errors")
        
        return questions
    
    def _detect_columns(self, columns: List[str]) -> Dict[str, str]:
        """Detect which columns correspond to which fields"""
        mapping = {}
        columns_lower = [col.lower().strip() for col in columns]
        
        for field, possible_names in self.COLUMN_MAPPINGS.items():
            for possible_name in possible_names:
                if possible_name.lower() in columns_lower:
                    original_index = columns_lower.index(possible_name.lower())
                    mapping[field] = columns[original_index]
                    break
        
        # Validate required columns
        required = ['question', 'correct_answer']
        missing = [field for field in required if field not in mapping]
        if missing:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required columns: {missing}. Available columns: {columns}"
            )
        
        return mapping
    
    async def _create_question_from_row(self, row: pd.Series, column_mapping: Dict[str, str], question_bank_id: str) -> QuestionCreate:
        """Create QuestionCreate object from DataFrame row"""
        # Extract basic fields
        question_text = str(row[column_mapping['question']]).strip()
        if not question_text or question_text == 'nan':
            raise ValueError("Question text is required")
        
        correct_answer = str(row[column_mapping['correct_answer']]).strip()
        if not correct_answer or correct_answer == 'nan':
            raise ValueError("Correct answer is required")
        
        # Determine question type
        question_type = QuestionType.SHORT_ANSWER  # Default
        options = None
        
        if 'type' in column_mapping:
            type_value = str(row[column_mapping['type']]).lower().strip()
            if type_value in ['multiple_choice', 'mc', 'multiple', 'choice']:
                question_type = QuestionType.MULTIPLE_CHOICE
            elif type_value in ['true_false', 'tf', 'bool', 'boolean']:
                question_type = QuestionType.TRUE_FALSE
            elif type_value in ['essay', 'long_answer', 'text']:
                question_type = QuestionType.ESSAY
        
        # Handle options
        if 'options' in column_mapping:
            options_value = str(row[column_mapping['options']]).strip()
            if options_value and options_value != 'nan':
                # Split options by common delimiters
                options = [opt.strip() for opt in options_value.split('|') if opt.strip()]
                if not options:
                    options = [opt.strip() for opt in options_value.split(';') if opt.strip()]
                if not options:
                    options = [opt.strip() for opt in options_value.split(',') if opt.strip()]
                
                if options and len(options) >= 2:
                    question_type = QuestionType.MULTIPLE_CHOICE
        
        # Handle True/False questions
        if question_type == QuestionType.TRUE_FALSE:
            options = ["True", "False"]
        
        # Handle difficulty
        difficulty_level = None
        if 'difficulty' in column_mapping:
            diff_value = str(row[column_mapping['difficulty']]).lower().strip()
            if diff_value in ['easy', 'e', '1']:
                difficulty_level = DifficultyLevel.EASY
            elif diff_value in ['medium', 'med', 'm', '2']:
                difficulty_level = DifficultyLevel.MEDIUM
            elif diff_value in ['hard', 'h', 'difficult', '3']:
                difficulty_level = DifficultyLevel.HARD
        
        # Handle category
        category = None
        if 'category' in column_mapping:
            category_value = str(row[column_mapping['category']]).strip()
            if category_value and category_value != 'nan':
                category = category_value
        
        return QuestionCreate(
            question_bank_id=question_bank_id,
            question_text=question_text,
            question_type=question_type,
            options=options,
            correct_answer=correct_answer,
            difficulty_level=difficulty_level,
            category=category
        )

# Global instance
file_processor = FileProcessorService()
