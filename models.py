from pydantic import BaseModel, conlist, ConfigDict, RootModel, EmailStr, Field
from fastapi import UploadFile
from typing import Optional, Literal, List, Union, Dict, Any
from datetime import datetime

class User(BaseModel):
    email: str
    password: str
class FormData(BaseModel):
    file: UploadFile

class RequestData(BaseModel):
    file_data: FormData | None = None
    source: str | None = None

class SourceValidatorOutput(BaseModel):
    is_valid: bool

class QuizQuestion(BaseModel):
    question: str
    options: conlist(str, min_length=4, max_length=4)
    answer: str

    model_config = ConfigDict(extra="forbid")

class QuizList(RootModel):
    root: conlist(QuizQuestion, min_length=2, max_length=2)

    def __iter__(self):
        return iter(self.root)
    
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class SessionInfo(BaseModel):
    user: UserOut
    expires_at: datetime
    is_valid: bool

# Enhanced Assessment Agent Models
class AssessmentQuizQuestion(BaseModel):
    id: str
    question: str
    options: List[str] = Field(..., min_items=4, max_items=4)
    correct_answer: str
    difficulty_level: int = Field(..., ge=1, le=5)
    curriculum_topic: str
    language: str = "en"
    question_type: Literal["mcq", "fill_blank", "true_false"] = "mcq"
    hints: Optional[List[str]] = []
    explanation: Optional[str] = None

class StudentResponse(BaseModel):
    question_id: str
    student_id: str
    student_answer: str
    time_taken: int  # in seconds
    hints_used: int = 0
    confidence_level: Optional[int] = Field(None, ge=1, le=5)
    is_correct: bool
    timestamp: datetime = Field(default_factory=datetime.now)

class QuizSession(BaseModel):
    id: str
    student_id: str
    quiz_id: str
    questions: List[AssessmentQuizQuestion]
    responses: List[StudentResponse] = []
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: Literal["in_progress", "completed", "abandoned"] = "in_progress"
    score: Optional[float] = None

class StudentProgress(BaseModel):
    student_id: str
    curriculum_topic: str
    mastery_level: float = Field(..., ge=0.0, le=1.0)
    total_questions_attempted: int = 0
    correct_answers: int = 0
    average_time_per_question: float = 0.0
    misconceptions: List[str] = []
    last_updated: datetime = Field(default_factory=datetime.now)

class MisconductionAnalysis(BaseModel):
    question_id: str
    student_id: str
    misconception_type: str
    description: str
    suggested_remediation: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)

class QuizGenerationRequest(BaseModel):
    curriculum_topic: str
    difficulty_level: int = Field(..., ge=1, le=5)
    num_questions: int = Field(..., ge=1, le=20)
    language: str = "en"
    question_types: List[Literal["mcq", "fill_blank", "true_false"]] = ["mcq"]
    student_id: Optional[str] = None

class QuizAnalytics(BaseModel):
    quiz_id: str
    total_attempts: int
    average_score: float
    completion_rate: float
    average_time: float
    difficulty_distribution: dict
    common_misconceptions: List[str]

# Enhanced Quiz Session History Models
class QuizAttemptAnswer(BaseModel):
    question_index: int
    question: str
    selected_answer: str
    correct_answer: str
    is_correct: bool
    time_taken: Optional[float] = None  # in seconds

class QuizAttempt(BaseModel):
    id: Optional[str] = None
    user_id: str
    quiz_id: str
    quiz_title: str
    answers: List[QuizAttemptAnswer]
    score: int
    total_questions: int
    percentage: float
    time_taken: Optional[float] = None  # total time in seconds
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    status: Literal["in_progress", "completed", "abandoned"] = "in_progress"

class QuizHistoryResponse(BaseModel):
    attempts: List[QuizAttempt]
    total_attempts: int
    average_score: float
    best_score: float
    total_time_spent: float  # in minutes

class UserQuizStats(BaseModel):
    user_id: str
    total_quizzes_taken: int
    total_questions_answered: int
    correct_answers: int
    accuracy_rate: float
    average_score: float
    total_time_spent: float  # in minutes
    favorite_topics: List[str]
    recent_activity: List[QuizAttempt]

# User Session History Models
class UserSession(BaseModel):
    id: Optional[str] = None
    user_id: str
    session_token: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    login_timestamp: datetime = Field(default_factory=datetime.now)
    logout_timestamp: Optional[datetime] = None
    last_activity: datetime = Field(default_factory=datetime.now)
    duration_minutes: Optional[float] = None
    is_active: bool = True
    device_type: Optional[str] = None  # mobile, desktop, tablet
    browser: Optional[str] = None
    location: Optional[str] = None  # city, country if available

class SessionHistoryResponse(BaseModel):
    sessions: List[UserSession]
    total_sessions: int
    current_page: int
    total_pages: int
    has_next: bool
    has_previous: bool

class SessionStatsResponse(BaseModel):
    total_sessions: int
    total_time_spent: float  # in minutes
    average_session_duration: float  # in minutes
    most_active_device: Optional[str] = None
    most_active_browser: Optional[str] = None
    recent_locations: List[str] = []



class User(BaseModel):
    id: str
    name: str
    email: str

class QuizQuestion(BaseModel):
    question: str
    options: List[str] = Field(..., min_items=4, max_items=4)
    answer: str

class QuizData(BaseModel):
    title: Optional[str] = None
    estimatedTime: Optional[str] = None
    questions: List[QuizQuestion]
    currentQuestionIndex: Optional[int] = None

class UserMessage(BaseModel):
    role: Literal["user"]
    content: str
class AssistantMessage(BaseModel):
    role: Literal["assistant"]
    content: str

class QuizMessage(BaseModel):
    role: Literal["quiz"]
    content: QuizData

ChatMessage = Union[UserMessage, AssistantMessage, QuizMessage]

class SessionCreate(BaseModel):
    messages: List[ChatMessage] = Field(..., min_items=1)

class SessionOut(BaseModel):
    id: str
    user_id: str
    messages: List[ChatMessage]
    created_at: Optional[str] = None

class SessionSummary(BaseModel):
    id: str
    user_id: str
    title: Optional[str] = None
    created_at: Optional[str] = None

def main():
    ob = QuizList.model_validate(
        [
            {
                "question": "What is the capital of France?",   
                "options": ["Paris", "London", "Paris", "London"],
                "answer": "Paris"
            },
            {
                "question": "What is the capital of France?",   
                "options": ["Paris", "London", "Paris", "London"],
                "answer": "Paris"
            },
            {
                "question": "What is the capital of France?",   
                "options": ["Paris", "London", "Paris", "London"],
                "answer": "Paris"
            },
            {
                "question": "What is the capital of France?",   
                "options": ["Paris", "London", "Paris", "London"],
                "answer": "Paris"
            },
            {
                "question": "What is the capital of France?",   
                "options": ["Paris", "London", "Paris", "London"],
                "answer": "Paris"
            }
        ]
    )
    print(ob)

# OpenAI Agents SDK Session Integration Models
class OpenAISessionMessage(BaseModel):
    """Message model for OpenAI Sessions integration"""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None

class OpenAISessionData(BaseModel):
    """Enhanced session data model for OpenAI Sessions"""
    session_id: str
    user_id: str
    messages: List[OpenAISessionMessage] = []
    context: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
    session_type: Literal["chat", "quiz", "assessment"] = "chat"
    metadata: Optional[Dict[str, Any]] = None

class ChatHistoryEntry(BaseModel):
    """Chat history entry for Recent Sessions display"""
    session_id: str
    title: str
    last_message: str
    timestamp: datetime
    message_count: int
    session_type: Literal["chat", "quiz", "assessment"] = "chat"
    preview: Optional[str] = None

class RecentSessionsResponse(BaseModel):
    """Response model for Recent Sessions"""
    sessions: List[ChatHistoryEntry]
    total_count: int
    has_more: bool

class SessionCreateRequest(BaseModel):
    """Request model for creating new OpenAI Sessions"""
    initial_message: Optional[str] = None
    session_type: Literal["chat", "quiz", "assessment"] = "chat"
    context: Optional[Dict[str, Any]] = None

class SessionUpdateRequest(BaseModel):
    """Request model for updating OpenAI Sessions"""
    message: OpenAISessionMessage
    context: Optional[Dict[str, Any]] = None

def main():
    ob = QuizList.model_validate(
        [
            {
                "question": "What is the capital of France?",   
                "options": ["Paris", "London", "Paris", "London"],
                "answer": "Paris"
            },
            {
                "question": "What is the capital of France?",   
                "options": ["Paris", "London", "Paris", "London"],
                "answer": "Paris"
            },
            {
                "question": "What is the capital of France?",   
                "options": ["Paris", "London", "Paris", "London"],
                "answer": "Paris"
            },
            {
                "question": "What is the capital of France?",   
                "options": ["Paris", "London", "Paris", "London"],
                "answer": "Paris"
            },
            {
                "question": "What is the capital of France?",   
                "options": ["Paris", "London", "Paris", "London"],
                "answer": "Paris"
            }
        ]
    )
    print(ob)

if __name__ == "__main__":
    main()