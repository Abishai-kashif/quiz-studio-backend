from pydantic import BaseModel, conlist, ConfigDict, RootModel
from fastapi import UploadFile
from typing import Optional, TypeVar, Union
from typing_extensions import TypeAlias

ContentType: TypeAlias = Union[str, UploadFile]

class SourceValidatorOutput(BaseModel):
    is_valid: bool

class Body(BaseModel):
    source: str

class QuizQuestion(BaseModel):
    question: str
    options: conlist(str, min_length=4, max_length=4)
    answer: str

    model_config = ConfigDict(extra="forbid")

class QuizList(RootModel):
    root: conlist(QuizQuestion, min_length=2, max_length=2)

    def __iter__(self):
        return iter(self.root)

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