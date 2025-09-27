from pydantic import BaseModel, conlist, ConfigDict, RootModel, EmailStr, Field
from fastapi import UploadFile
from typing import Optional, Literal, List, Union
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

if __name__ == "__main__":
    main()