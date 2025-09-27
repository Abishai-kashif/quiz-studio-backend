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
from jose import jwt, JWTError
import os
import secrets

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
db = get_database()

if db is not None:
    users_collection = db["users"]
    refresh_tokens_collection = db["refresh_tokens"]
else:
    users_collection = None
    refresh_tokens_collection = None

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
        if users_collection is None:
            return None
        return users_collection.find_one({"email": email})

    @staticmethod
    def get_user_by_password(password: str):
        if users_collection is None:
            return None
        hashed_pass = Utils.get_password_hash(password)
        return users_collection.find_one({"password": hashed_pass})

    @staticmethod
    def create_refresh_token(user_email: str) -> str:
        """Create a secure refresh token for the user"""
        refresh_token = secrets.token_urlsafe(64)
        
        if refresh_tokens_collection is not None:
            # Store refresh token in database with expiration (30 days)
            expires_at = datetime.utcnow() + timedelta(days=30)
            refresh_tokens_collection.insert_one({
                "token": refresh_token,
                "user_email": user_email,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
                "is_active": True
            })
        
        return refresh_token

    @staticmethod
    def validate_refresh_token(refresh_token: str) -> str | None:
        """Validate refresh token and return user email if valid"""
        if refresh_tokens_collection is None:
            return None
            
        token_doc = refresh_tokens_collection.find_one({
            "token": refresh_token,
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        return token_doc["user_email"] if token_doc else None

    @staticmethod
    def revoke_refresh_token(refresh_token: str) -> bool:
        """Revoke a refresh token"""
        if refresh_tokens_collection is None:
            return False
            
        result = refresh_tokens_collection.update_one(
            {"token": refresh_token},
            {"$set": {"is_active": False, "revoked_at": datetime.utcnow()}}
        )
        
        return result.modified_count > 0

    @staticmethod
    def revoke_all_user_tokens(user_email: str) -> int:
        """Revoke all refresh tokens for a user"""
        if refresh_tokens_collection is None:
            return 0
            
        result = refresh_tokens_collection.update_many(
            {"user_email": user_email, "is_active": True},
            {"$set": {"is_active": False, "revoked_at": datetime.utcnow()}}
        )
        
        return result.modified_count

    @staticmethod
    def verify_access_token(token: str) -> dict | None:
        """Verify and decode access token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                return None
            return {"email": email, "exp": payload.get("exp")}
        except JWTError:
            return None

if __name__ == "__main__":
    assert Utils.is_url("https://www.google.com") is True
    