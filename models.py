from pydantic import BaseModel, conlist, ConfigDict, RootModel, EmailStr, Field
from fastapi import UploadFile
from typing import Optional, Literal, List, Union

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