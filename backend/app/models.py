"""
Pydantic models for request/response schemas
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum

# Enums
class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"

class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class TestStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"

# Base models
class QuestionBankBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

class QuestionBankCreate(QuestionBankBase):
    pass

class QuestionBankUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

class QuestionBankResponse(QuestionBankBase):
    id: str
    file_path: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    question_count: Optional[int] = 0

class QuestionBase(BaseModel):
    question_text: str = Field(..., min_length=1)
    question_type: QuestionType
    options: Optional[List[str]] = Field(None, description="Options for multiple choice questions")
    correct_answer: str = Field(..., min_length=1)
    difficulty_level: Optional[DifficultyLevel] = None
    category: Optional[str] = Field(None, max_length=100)

    @validator('options')
    def validate_options(cls, v, values):
        question_type = values.get('question_type')
        if question_type == QuestionType.MULTIPLE_CHOICE and (not v or len(v) < 2):
            raise ValueError('Multiple choice questions must have at least 2 options')
        if question_type == QuestionType.TRUE_FALSE and v and len(v) != 2:
            raise ValueError('True/false questions should have exactly 2 options or none')
        return v

class QuestionCreate(QuestionBase):
    question_bank_id: str

class QuestionResponse(QuestionBase):
    id: str
    question_bank_id: str
    created_at: datetime

# File upload models
class FileUploadResponse(BaseModel):
    message: str
    question_bank_id: str
    questions_imported: int
    file_path: str

# Enhanced test generation models
class TestCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    # Backward compatibility: allow single question_bank_id OR multiple question_bank_ids
    question_bank_id: Optional[str] = None
    question_bank_ids: Optional[List[str]] = None
    num_questions: int = Field(..., ge=1, le=100)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=480)  # Max 8 hours
    difficulty_filter: Optional[DifficultyLevel] = None
    category_filter: Optional[str] = Field(None, max_length=100)
    is_public: bool = Field(False, description="Whether test is publicly accessible")
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    max_attempts: int = Field(1, ge=1, le=10)
    pass_threshold: float = Field(60.0, ge=0, le=100)

    @validator("question_bank_ids", always=True)
    def validate_banks(cls, v, values):
        # Ensure at least one of question_bank_id or question_bank_ids is provided
        single = values.get("question_bank_id")
        if (not v or len(v) == 0) and not single:
            raise ValueError("Provide question_bank_id or question_bank_ids with at least one id")
        return v

class TestResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    question_bank_id: str
    question_bank_ids: Optional[List[str]] = None
    question_bank_names: Optional[List[str]] = None
    created_by: str
    creator_name: Optional[str]
    num_questions: int
    time_limit_minutes: Optional[int]
    difficulty_filter: Optional[DifficultyLevel]
    category_filter: Optional[str]
    is_active: bool
    is_public: bool
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    max_attempts: int
    pass_threshold: float
    created_at: datetime
    updated_at: datetime
    test_link: str
    
    # Analytics data (when available)
    total_submissions: Optional[int] = 0
    total_participants: Optional[int] = 0
    average_score: Optional[float] = 0
    pass_rate: Optional[float] = 0

class TestUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=480)
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    max_attempts: Optional[int] = Field(None, ge=1, le=10)
    pass_threshold: Optional[float] = Field(None, ge=0, le=100)

# Test taking models
class TestQuestionResponse(BaseModel):
    id: str
    question_text: str
    question_type: QuestionType
    options: Optional[List[str]]
    question_order: int
    # Note: correct_answer is NOT included in test questions

class TestDetailsResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    time_limit_minutes: Optional[int]
    total_questions: int
    max_attempts: int
    pass_threshold: float
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    questions: List[TestQuestionResponse]
    question_bank_names: Optional[List[str]] = None
    
    # User-specific data (if authenticated)
    user_attempts: Optional[int] = 0
    user_best_score: Optional[float] = None
    can_attempt: bool = True

class AnswerSubmission(BaseModel):
    question_id: str
    selected_answer: str

class TestSubmissionRequest(BaseModel):
    participant_name: str = Field(..., min_length=1, max_length=100)
    participant_email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    answers: List[AnswerSubmission]
    time_taken_minutes: Optional[int] = Field(None, ge=0)

class TestSubmissionResponse(BaseModel):
    id: str
    test_id: str
    test_title: str
    participant_name: str
    participant_email: Optional[str]
    score: float
    total_questions: int
    correct_answers: int
    time_taken_minutes: Optional[int]
    is_passed: bool
    submitted_at: datetime
    
    # Detailed results
    question_results: Optional[List[Dict[str, Any]]] = None

# Analytics models
class TestAnalytics(BaseModel):
    test_id: str
    total_submissions: int
    total_participants: int
    average_score: float
    pass_rate: float
    average_time_minutes: float
    last_updated: datetime

class UserPerformance(BaseModel):
    user_id: str
    user_name: str
    test_id: str
    test_title: str
    best_score: float
    attempts_count: int
    total_time_minutes: int
    first_attempt_at: datetime
    last_attempt_at: datetime

class LeaderboardEntry(BaseModel):
    user_id: str
    name: str
    email: str
    tests_taken: int
    average_best_score: float
    total_attempts: int
    total_time_minutes: int
    tests_passed: int

class RecentActivity(BaseModel):
    id: str
    test_id: str
    test_title: str
    participant_name: str
    participant_email: Optional[str]
    user_name: Optional[str]
    score: float
    is_passed: bool
    time_taken_minutes: Optional[int]
    submitted_at: datetime

# Enhanced admin dashboard models
class DashboardStats(BaseModel):
    total_question_banks: int
    total_questions: int
    total_tests: int
    total_submissions: int
    total_users: int
    recent_uploads: List[QuestionBankResponse]
    recent_tests: List[TestResponse]
    recent_activity: List[RecentActivity]
    top_performers: List[LeaderboardEntry]

# Test session models
class TestSessionStart(BaseModel):
    participant_name: str = Field(..., min_length=1, max_length=100)
    participant_email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    # Optional: token from a shared/invite link to associate attempts
    invite_token: Optional[str] = None

class TestSessionResponse(BaseModel):
    session_id: str
    session_token: str
    test_id: str
    test_title: str
    participant_name: str
    started_at: datetime
    expires_at: datetime
    time_limit_minutes: Optional[int]
    total_questions: int
    current_question: int
    minutes_remaining: float

class TestSessionStatus(BaseModel):
    session_id: str
    is_active: bool
    current_question: int
    minutes_remaining: float
    answers_saved: int
    can_submit: bool

class SaveAnswerRequest(BaseModel):
    question_id: str
    selected_answer: str
    question_number: int

class SaveAnswerResponse(BaseModel):
    success: bool
    question_number: int
    answers_saved: int
    auto_saved_at: datetime

# Export and reporting models
class ExportRequest(BaseModel):
    test_id: str
    format: Literal["csv", "pdf"] = "csv"
    include_details: bool = True

class ExportResponse(BaseModel):
    download_url: str
    filename: str
    expires_at: datetime

# Error models
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

# Health check models
class HealthCheck(BaseModel):
    status: str
    message: str
    database_status: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
