import urllib.parse
from fastapi import UploadFile
from PyPDF2 import PdfReader
from agents import Runner
from agents_service import markdown_generator_agent
from passlib.context import CryptContext
from datetime import datetime, timedelta
from models import SessionOut
from pymongo_get_database import get_database
from dotenv import load_dotenv
from jose import jwt
import os

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
db = get_database()

users_collection = db["users"]

class Utils:
    @staticmethod
    def is_url(text: str) -> bool:
        """
        Returns true if the provided text is a url, false otherwise.
        """
        parsed = urllib.parse.urlparse(text)
        return bool(parsed.netloc) and bool(parsed.scheme)

    @staticmethod
    async def read_pdf(file: UploadFile) -> str:        
        reader = PdfReader(file.file)

        content = ""
        for page in reader.pages:
            content += page.extract_text() or ""

        return content
    
    @staticmethod
    def session_helper(session: dict) -> SessionOut:
        return {
            "id": str(session["_id"]),
            "user_id": str(session["user_id"]),
            "messages": session["messages"],
            "created_at": session["created_at"].isoformat(),
        }

    async def get_markdown(text: str) -> str:
        result = await Runner.run(starting_agent=markdown_generator_agent, input=text)
        return result.final_output
    
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)


    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def get_user_by_email(email: str):
        return users_collection.find_one({"email": email})

    @staticmethod
    def get_user_by_password(password: str):
        hashed_pass = Utils.get_password_hash(password)
        return users_collection.find_one({"password": hashed_pass})

if __name__ == "__main__":
    assert Utils.is_url("https://www.google.com") is True
    