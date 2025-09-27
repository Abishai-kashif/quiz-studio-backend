from agents_service import source_validator_agent, content_generator_agent, tutor_agent, assessment_agent
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Response, Request, Cookie
from agents import Runner, TResponseInputItem, trace
from fastapi.responses import StreamingResponse, JSONResponse
from openai.types.responses import ResponseTextDeltaEvent
from fastapi.middleware.cors import CORSMiddleware
from agents import enable_verbose_stdout_logging
from models import (SessionOut, SessionSummary, UserCreate, UserOut, Token, TokenResponse, 
                   RefreshTokenRequest, SessionInfo, AssessmentQuizQuestion, StudentResponse, 
                   QuizSession, StudentProgress, QuizGenerationRequest, QuizAnalytics,
                   QuizAttempt, QuizAttemptAnswer, QuizHistoryResponse, UserQuizStats,
                   UserSession, SessionHistoryResponse, SessionStatsResponse,
                   OpenAISessionData, OpenAISessionMessage, ChatHistoryEntry, 
                   RecentSessionsResponse, SessionCreateRequest, SessionUpdateRequest)
from openai_sessions_service import openai_sessions_service
from pymongo_get_database import get_database
from pymongo.errors import DuplicateKeyError
from datetime import timedelta, datetime
from dotenv import load_dotenv
from typing import Optional, Annotated
from jose import jwt, JWTError
from fastapi import status
from bson import ObjectId
from utils import Utils
import json
import os
from agents import AgentOutputSchema

load_dotenv(override=True)

db = get_database()
if db is not None:
    users_collection = db["users"]
    sessions_collection = db["sessions"]
    quizzes_collection = db["quizzes"]
    quiz_sessions_collection = db["quiz_sessions"]
    student_responses_collection = db["student_responses"]
    student_progress_collection = db["student_progress"]
    quiz_attempts_collection = db["quiz_attempts"]
    user_sessions_collection = db["user_sessions"]
    print("📊 Database collections initialized successfully!")
else:
    print("⚠️  Running without database - some features may be limited")
    users_collection = None
    sessions_collection = None
    quizzes_collection = None
    quiz_sessions_collection = None
    student_responses_collection = None
    student_progress_collection = None
    quiz_attempts_collection = None
    user_sessions_collection = None
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
ACCESS_TOKEN_EXPIRE_MINUTES=os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
SECRET_KEY=os.getenv("SECRET_KEY")
ALGORITHM=os.getenv("ALGORITHM")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Response-Mode"]
)

@app.get("/")
async def root():
    return {"message": "Welcome to the AI Quiz Generator API!"}

# @app.get("/users/sessions/{user_id}", response_model=list[SessionSummary])
# async def fetch_sessions(user_id: str):
#     print("USERID>>>>>>>>> ", user_id)
#     # fetch sessions for the user
#     sessions_cursor = sessions_collection.find({"user_id": ObjectId(user_id)})
#     sessions = []
#     async for session in sessions_cursor:
#         sessions.append(Utils.session_helper(session))

#     return sessions

@app.get("/sessions/{user_id}", response_model=list[SessionSummary])
async def fetch_sessions_alias(user_id: str):
    # Alias for clients calling /sessions/{user_id}
    print("\n\nuser_id >>>>>>>> ", user_id, "\n\n")
    sessions_cursor = sessions_collection.find({"user_id": ObjectId(user_id)})
    print("sessions_cursor >>>>>>>. ", sessions_cursor)
    print("sessions_cursor22 >>>>>>>. ", list(sessions_cursor))
    sessions = []
    for session in sessions_cursor:
        print("\n\n[00session000]:>>> \n\n", session, "\n\n")
        sessions.append(Utils.session_helper(session))

    return sessions


@app.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(user: UserCreate, response: Response, request: Request):
    """
    Creates a new user and returns access and refresh tokens.
    Sets HTTP-only cookies for secure token storage.
    """
    print(f"🔄 Signup attempt for email: {user.email}")

    # Check if user already exists
    existing = Utils.get_user_by_email(user.email)
    if existing:
        print(f"❌ Email already registered: {user.email}")
        raise HTTPException(status_code=400, detail="Email already registered")

    doc = {
        "name": user.name,
        "email": user.email, 
        "password": Utils.get_password_hash(user.password),
        "created_at": datetime.utcnow()
    }

    print(f"📝 Attempting to save user to MongoDB: {user.email}")
    
    try:
        result = users_collection.insert_one(doc)
        inserted_id = result.inserted_id
        print(f"✅ User successfully saved to MongoDB with ID: {inserted_id}")
        
        # Verify the user was actually saved
        saved_user = users_collection.find_one({"_id": inserted_id})
        if saved_user:
            print(f"✅ Verification: User {user.email} found in database")
        else:
            print(f"❌ Verification failed: User {user.email} not found in database")
            
    except DuplicateKeyError:
        print(f"❌ Duplicate key error for email: {user.email}")
        raise HTTPException(status_code=400, detail="Email already registered")
    except Exception as e:
        print(f"❌ Database insert failed: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error") from e

    # Create tokens
    token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = Utils.create_access_token(data={"sub": user.email}, expires_delta=token_expires)
    refresh_token = Utils.create_refresh_token(user.email)

    # Create session record
    user_id = str(inserted_id)
    session_id = await create_user_session(user_id, access_token, request)
    print(f"🔐 Session created for new user {user.email}: {session_id}")

    # Set HTTP-only cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,  # Use HTTPS in production
        samesite="lax",
        max_age=int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    )
    
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token,
        httponly=True,
        secure=True,  # Use HTTPS in production
        samesite="lax",
        max_age=30 * 24 * 60 * 60  # 30 days
    )

    print(f"🎉 Signup completed successfully for: {user.email}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    }
    

@app.post("/login", response_model=TokenResponse)
async def login(user_credentials: dict, response: Response, request: Request):
    """
    Authenticates user and returns access and refresh tokens.
    Sets HTTP-only cookies for secure token storage.
    Expects JSON body with email and password fields.
    """
    email = user_credentials.get("email")
    password = user_credentials.get("password")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    db_user = Utils.get_user_by_email(email)

    if not db_user or not Utils.verify_password(password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Revoke existing refresh tokens for this user
    Utils.revoke_all_user_tokens(email)

    # Create new tokens
    token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = Utils.create_access_token(data={"sub": db_user["email"]}, expires_delta=token_expires)
    refresh_token = Utils.create_refresh_token(email)

    # Create session record
    user_id = str(db_user["_id"])
    session_id = await create_user_session(user_id, access_token, request)
    print(f"🔐 Session created for user {email}: {session_id}")

    # Set HTTP-only cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,  # Use HTTPS in production
        samesite="lax",
        max_age=int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    )
    
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token,
        httponly=True,
        secure=True,  # Use HTTPS in production
        samesite="lax",
        max_age=30 * 24 * 60 * 60  # 30 days
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    }


@app.get("/me", response_model=UserOut)
def read_users_me(request: Request, token: str = Depends(oauth2_scheme)):
    # Try to get token from cookie first, then fallback to Authorization header
    access_token = request.cookies.get("access_token")
    if not access_token:
        access_token = token
    
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db_user = Utils.get_user_by_email(email)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserOut(id=str(db_user["_id"]), email=db_user["email"], name=db_user["name"])


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, response: Response):
    """
    Refreshes access token using refresh token from HTTP-only cookie.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")
    
    # Validate refresh token
    email = Utils.validate_refresh_token(refresh_token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    # Check if user still exists
    db_user = Utils.get_user_by_email(email)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create new access token
    token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    new_access_token = Utils.create_access_token(data={"sub": email}, expires_delta=token_expires)
    
    # Set new access token cookie
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    )
    
    return {
        "access_token": new_access_token,
        "refresh_token": refresh_token,  # Keep existing refresh token
        "token_type": "bearer",
        "expires_in": int(ACCESS_TOKEN_EXPIRE_MINUTES) * 60
    }


@app.get("/auth/session", response_model=SessionInfo)
async def validate_session(request: Request):
    """
    Validates current session and returns user info if authenticated.
    """
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="No active session")
    
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid session")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    db_user = Utils.get_user_by_email(email)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user": {
            "id": str(db_user["_id"]),
            "email": db_user["email"],
            "name": db_user["name"]
        },
        "expires_at": datetime.fromtimestamp(payload.get("exp")),
        "is_valid": True
    }


@app.post("/auth/logout")
async def logout(request: Request, response: Response):
    """
    Logs out user by clearing cookies and revoking refresh token.
    """
    # End the session
    access_token = request.cookies.get("access_token")
    if access_token:
        await end_user_session(access_token)
        print(f"🔐 Session ended for token: {access_token[:20]}...")
    
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        # Revoke the refresh token
        Utils.revoke_refresh_token(refresh_token)
    
    # Clear cookies
    response.delete_cookie(key="access_token", httponly=True, secure=True, samesite="lax")
    response.delete_cookie(key="refresh_token", httponly=True, secure=True, samesite="lax")
    
    return {"message": "Successfully logged out"}


@app.get("/users", response_model=UserOut)
def read_users_me(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db_user = Utils.get_user_by_email(email)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserOut(id=str(db_user["_id"]), email=db_user["email"], name=db_user["name"])

@app.post("/chat")
async def chat(
    session: list[TResponseInputItem]
):
    # print('\n\nsession\n', session, '\n\n')
    # session = [
    #     {'content': "👋 Hello Abishai! I'm your AI learning assistant. I'm here to help you learn any topic through personalized conversations and interactive quizzes.", 'role': 'assistant'}, 
    #     {'content': 'Hi', 'role': 'user'}, 
    #     {'content': 'How can I help you today? Are there any specific topics you want to learn, or would you like me to suggest something?', 'role': 'assistant'}, 
    #     {'content': 'Explain me about python programming.', 'role': 'user'}, 
    #     {'content': "Okay! Let's learn about Python. To start, Python is a versatile and widely-used programming language known for its clear syntax and readability. To get started, what do you know about Python, if anything? Have you heard of it before, or used any other programming languages?", 'role': 'assistant'}, 
    #     {'content': 'About lists in python', 'role': 'user'}, 
    #     {'content': "Great, let's dive into Python lists! Lists are fundamental data structures in Python used to store an ordered collection of items. To begin, can you describe in your own words what a list is and what you might use it for?", 'role': 'assistant'}, 
    #     {'content': 'now generate a quiz on it.', 'role': 'user'}
    # ]

    with trace("Chat Session"):
        result = Runner.run_streamed(starting_agent=tutor_agent, input=session)

        async def event_generator():
            async for event in result.stream_events():
                if event.type == 'raw_response_event' and isinstance(event.data, ResponseTextDeltaEvent):
                    yield json.dumps({
                        "type": event.type,
                        "delta": event.data.delta
                    }) + "\n"

        return StreamingResponse(
            event_generator(), media_type="application/json",
            headers={"Cache-Control": "no-cache",  "X-Response-Mode": "stream"}
        )

@app.post("/quizzes")
async def main(
    source: str | None = Form(None), 
    file: UploadFile | None = File(None)
):
    if (not source and not file):
        return JSONResponse(
            content={"status": "error", "message": "Please provide a source (text or URL) or upload a file."},
            headers={"X-Response-Mode": "error"}
        )
    
    if (source and file):
        return JSONResponse(
            content={"status": "error", "message": "Please provide either a source (text or URL) or upload a file, not both."},
            headers={"X-Response-Mode": "error"}
        )

    if (file):
        if (file.content_type == "application/pdf"):
            source = await Utils.read_pdf(file=file)
            source = await Utils.get_markdown(source)

    is_url = Utils.is_url(text=source) 
    is_valid_source = False

    if (not is_url):
        result = await Runner.run(starting_agent=source_validator_agent, input=source)
        is_valid_source = result.final_output.is_valid

    if (is_url or not is_valid_source):
        result = await Runner.run(starting_agent=content_generator_agent, input=source)
        source = result.final_output

        # result = await Runner.run(starting_agent=source_validator_agent, input=source)
        # is_valid_source = result.final_output.is_valid

    # if (not is_valid_source):
    #     return JSONResponse(
    #         content={"status": "error", "message": "Provided source is not valid. Please provide a valid text or URL."},
    #         headers={"X-Response-Mode": "error"}
    #     ) 
        
    result = Runner.run_streamed(starting_agent=tutor_agent, input=source)

    async def event_generator():
        """
        Generator function to yield events from the result stream.
        This allows for real-time updates to the client.
        """
        async for event in result.stream_events():
            if (event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent)):
                yield json.dumps({
                    "type": event.type,
                    "delta": event.data.delta
                }) + "\n"

            # elif (event.type == "run_item_stream_event"):
            #     if event.item.type == "tool_call_output_item":
            #         output = event.item.output

            #         yield json.dumps({
            #             "type": event.item.type,
            #             "tool_result": output
            #         }) + "\n"
            
    return StreamingResponse(
        event_generator(), media_type="application/json",
        headers={"Cache-Control": "no-cache",  "X-Response-Mode": "stream"}
    )

# Assessment Agent API Endpoints

@app.post("/api/assessment/generate-quiz")
async def generate_quiz(request: QuizGenerationRequest, token: str = Depends(oauth2_scheme)):
    """Generate an adaptive quiz based on curriculum topic and difficulty level"""
    try:
        # Verify user token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Generate quiz using assessment agent
        quiz_prompt = f"""
        Generate a quiz with the following specifications:
        - Topic: {request.curriculum_topic}
        - Difficulty Level: {request.difficulty_level}/5
        - Number of Questions: {request.num_questions}
        - Language: {request.language}
        - Question Types: {', '.join(request.question_types)}
        
        Create questions that are curriculum-aligned and appropriate for the specified difficulty level.
        """
        
        result = await Runner.run(starting_agent=assessment_agent, input=quiz_prompt)
        
        # Store quiz in database
        quiz_doc = {
            "curriculum_topic": request.curriculum_topic,
            "difficulty_level": request.difficulty_level,
            "language": request.language,
            "questions": result.final_output if hasattr(result, 'final_output') else [],
            "created_by": email,
            "created_at": datetime.now()
        }
        
        quiz_result = quizzes_collection.insert_one(quiz_doc)
        quiz_id = str(quiz_result.inserted_id)
        
        return {
            "quiz_id": quiz_id,
            "questions": quiz_doc["questions"],
            "metadata": {
                "topic": request.curriculum_topic,
                "difficulty": request.difficulty_level,
                "language": request.language
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {str(e)}")

@app.post("/api/assessment/submit-answer")
async def submit_answer(response: StudentResponse, token: str = Depends(oauth2_scheme)):
    """Submit a student's answer and get immediate feedback"""
    try:
        # Verify user token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Store student response
        response_doc = response.dict()
        response_doc["submitted_at"] = datetime.now()
        
        student_responses_collection.insert_one(response_doc)
        
        # Analyze response for misconceptions if incorrect
        feedback = {"is_correct": response.is_correct}
        
        if not response.is_correct:
            # Use assessment agent to analyze misconception
            analysis_prompt = f"""
            Analyze this incorrect response:
            Question ID: {response.question_id}
            Student Answer: {response.student_answer}
            Time Taken: {response.time_taken} seconds
            Hints Used: {response.hints_used}
            
            Identify potential misconceptions and provide remediation suggestions.
            """
            
            analysis_result = await Runner.run(starting_agent=assessment_agent, input=analysis_prompt)
            feedback["misconception_analysis"] = analysis_result.final_output if hasattr(analysis_result, 'final_output') else "Analysis pending"
        
        return feedback
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer submission failed: {str(e)}")

@app.get("/api/assessment/student-progress/{student_id}")
async def get_student_progress(student_id: str, token: str = Depends(oauth2_scheme)):
    """Get comprehensive student progress analytics"""
    try:
        # Verify user token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Fetch student progress from database
        progress_cursor = student_progress_collection.find({"student_id": student_id})
        progress_data = []
        
        for progress in progress_cursor:
            progress["_id"] = str(progress["_id"])
            progress_data.append(progress)
        
        # Calculate overall statistics
        if progress_data:
            total_topics = len(progress_data)
            avg_mastery = sum(p["mastery_level"] for p in progress_data) / total_topics
            total_questions = sum(p["total_questions_attempted"] for p in progress_data)
            total_correct = sum(p["correct_answers"] for p in progress_data)
            overall_accuracy = total_correct / total_questions if total_questions > 0 else 0
            
            return {
                "student_id": student_id,
                "overall_stats": {
                    "average_mastery": round(avg_mastery, 2),
                    "total_topics": total_topics,
                    "total_questions_attempted": total_questions,
                    "overall_accuracy": round(overall_accuracy, 2)
                },
                "topic_progress": progress_data
            }
        else:
            return {
                "student_id": student_id,
                "overall_stats": {
                    "average_mastery": 0.0,
                    "total_topics": 0,
                    "total_questions_attempted": 0,
                    "overall_accuracy": 0.0
                },
                "topic_progress": []
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Progress retrieval failed: {str(e)}")

@app.post("/api/assessment/analyze-misconceptions")
async def analyze_misconceptions(student_id: str, topic: str = None, token: str = Depends(oauth2_scheme)):
    """Analyze student misconceptions across topics or for a specific topic"""
    try:
        # Verify user token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Build query filter
        query_filter = {"student_id": student_id, "is_correct": False}
        if topic:
            # Find questions related to the topic
            quiz_filter = {"curriculum_topic": topic}
            quizzes = quizzes_collection.find(quiz_filter)
            question_ids = []
            for quiz in quizzes:
                for question in quiz.get("questions", []):
                    question_ids.append(question.get("id"))
            
            if question_ids:
                query_filter["question_id"] = {"$in": question_ids}
        
        # Fetch incorrect responses
        incorrect_responses = list(student_responses_collection.find(query_filter))
        
        if not incorrect_responses:
            return {
                "student_id": student_id,
                "topic": topic,
                "misconceptions": [],
                "recommendations": ["Continue practicing to identify areas for improvement"]
            }
        
        # Use assessment agent to analyze patterns
        analysis_prompt = f"""
        Analyze misconception patterns for student {student_id}:
        
        Incorrect Responses: {len(incorrect_responses)}
        Topic Focus: {topic if topic else "All topics"}
        
        Response Data: {json.dumps([{
            "question_id": r["question_id"],
            "student_answer": r["student_answer"],
            "time_taken": r["time_taken"],
            "hints_used": r["hints_used"]
        } for r in incorrect_responses[:10]], indent=2)}
        
        Identify common misconception patterns and provide specific remediation strategies.
        """
        
        analysis_result = await Runner.run(starting_agent=assessment_agent, input=analysis_prompt)
        
        return {
            "student_id": student_id,
            "topic": topic,
            "total_incorrect_responses": len(incorrect_responses),
            "analysis": analysis_result.final_output if hasattr(analysis_result, 'final_output') else "Analysis completed",
            "recommendations": [
                "Review fundamental concepts",
                "Practice with guided examples",
                "Focus on time management",
                "Use hints strategically"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Misconception analysis failed: {str(e)}")

@app.get("/api/assessment/quiz-analytics/{quiz_id}")
async def get_quiz_analytics(quiz_id: str, token: str = Depends(oauth2_scheme)):
    """Get analytics for a specific quiz"""
    try:
        # Verify user token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Fetch quiz sessions for this quiz
        quiz_sessions = list(quiz_sessions_collection.find({"quiz_id": quiz_id}))
        
        if not quiz_sessions:
            return {
                "quiz_id": quiz_id,
                "total_attempts": 0,
                "analytics": "No attempts yet"
            }
        
        # Calculate analytics
        total_attempts = len(quiz_sessions)
        completed_sessions = [s for s in quiz_sessions if s["status"] == "completed"]
        completion_rate = len(completed_sessions) / total_attempts if total_attempts > 0 else 0
        
        scores = [s.get("score", 0) for s in completed_sessions if s.get("score") is not None]
        average_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "quiz_id": quiz_id,
            "total_attempts": total_attempts,
            "completion_rate": round(completion_rate, 2),
            "average_score": round(average_score, 2),
            "completed_attempts": len(completed_sessions),
            "analytics": {
                "high_performers": len([s for s in scores if s >= 0.8]),
                "needs_improvement": len([s for s in scores if s < 0.6]),
                "score_distribution": {
                    "excellent": len([s for s in scores if s >= 0.9]),
                    "good": len([s for s in scores if 0.7 <= s < 0.9]),
                    "fair": len([s for s in scores if 0.5 <= s < 0.7]),
                    "poor": len([s for s in scores if s < 0.5])
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quiz analytics failed: {str(e)}")


# Session tracking helper functions
def extract_device_info(user_agent: str) -> tuple[str, str]:
    """Extract device type and browser from user agent string"""
    user_agent_lower = user_agent.lower()
    
    # Determine device type
    if 'mobile' in user_agent_lower or 'android' in user_agent_lower or 'iphone' in user_agent_lower:
        device_type = 'mobile'
    elif 'tablet' in user_agent_lower or 'ipad' in user_agent_lower:
        device_type = 'tablet'
    else:
        device_type = 'desktop'
    
    # Determine browser
    if 'chrome' in user_agent_lower:
        browser = 'Chrome'
    elif 'firefox' in user_agent_lower:
        browser = 'Firefox'
    elif 'safari' in user_agent_lower:
        browser = 'Safari'
    elif 'edge' in user_agent_lower:
        browser = 'Edge'
    else:
        browser = 'Unknown'
    
    return device_type, browser

async def create_user_session(user_id: str, session_token: str, request: Request) -> str:
    """Create a new user session record"""
    if user_sessions_collection is None:
        return None
    
    user_agent = request.headers.get("user-agent", "")
    device_type, browser = extract_device_info(user_agent)
    
    session_data = {
        "user_id": user_id,
        "session_token": session_token,
        "ip_address": request.client.host if request.client else None,
        "user_agent": user_agent,
        "login_timestamp": datetime.utcnow(),
        "last_activity": datetime.utcnow(),
        "is_active": True,
        "device_type": device_type,
        "browser": browser
    }
    
    try:
        result = user_sessions_collection.insert_one(session_data)
        return str(result.inserted_id)
    except Exception as e:
        print(f"❌ Failed to create session: {e}")
        return None

async def update_session_activity(session_token: str):
    """Update the last activity timestamp for a session"""
    if user_sessions_collection is None:
        return
    
    try:
        user_sessions_collection.update_one(
            {"session_token": session_token, "is_active": True},
            {"$set": {"last_activity": datetime.utcnow()}}
        )
    except Exception as e:
        print(f"❌ Failed to update session activity: {e}")

async def end_user_session(session_token: str):
    """End a user session by setting logout timestamp and calculating duration"""
    if user_sessions_collection is None:
        return
    
    try:
        session = user_sessions_collection.find_one({"session_token": session_token, "is_active": True})
        if session:
            logout_time = datetime.utcnow()
            login_time = session.get("login_timestamp", logout_time)
            duration_minutes = (logout_time - login_time).total_seconds() / 60
            
            user_sessions_collection.update_one(
                {"session_token": session_token},
                {
                    "$set": {
                        "logout_timestamp": logout_time,
                        "duration_minutes": duration_minutes,
                        "is_active": False
                    }
                }
            )
    except Exception as e:
        print(f"❌ Failed to end session: {e}")

async def get_current_user(request: Request) -> dict:
    """Get current user from JWT token (cookie or header)"""
    # Try to get token from cookie first, then fallback to Authorization header
    access_token = request.cookies.get("access_token")
    if not access_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header.split(" ")[1]
    
    if not access_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db_user = Utils.get_user_by_email(email)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    return db_user


@app.post("/api/quiz/store")
async def store_quiz(quiz_data: dict, request: Request):
    """Store a quiz generated by the LLM in the database for the authenticated user"""
    try:
        # Get current user
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        print(f"📝 Storing quiz for user {current_user['email']}: {quiz_data.get('title', 'Untitled Quiz')}")
        
        # Prepare quiz document for storage
        quiz_doc = {
            "title": quiz_data.get("title", "Generated Quiz"),
            "estimated_time": quiz_data.get("estimatedTime", "5 minutes"),
            "questions": quiz_data.get("questions", []),
            "current_question_index": quiz_data.get("currentQuestionIndex", 0),
            "user_id": ObjectId(user_id),  # Associate quiz with user
            "created_at": datetime.now(),
            "created_by": "llm_generated",
            "status": "generated",
            "type": "llm_quiz"
        }
        
        # Store in MongoDB
        if quizzes_collection is not None:
            result = quizzes_collection.insert_one(quiz_doc)
            quiz_id = str(result.inserted_id)
            print(f"✅ Quiz stored successfully with ID: {quiz_id} for user: {current_user['email']}")
            
            return {
                "success": True,
                "quiz_id": quiz_id,
                "message": "Quiz stored successfully"
            }
        else:
            print("⚠️ Database not available - quiz not stored")
            return {
                "success": False,
                "message": "Database not available"
            }
            
    except Exception as e:
        print(f"❌ Error storing quiz: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to store quiz: {str(e)}")


@app.get("/api/quiz/list")
async def list_stored_quizzes(request: Request):
    """Retrieve all stored quizzes for the authenticated user"""
    try:
        # Get current user
        current_user = await get_current_user(request)
        user_id = ObjectId(str(current_user["_id"]))
        
        if quizzes_collection is not None:
            # Only get quizzes for the current user
            quizzes = list(quizzes_collection.find(
                {"user_id": user_id}, 
                {"_id": 1, "title": 1, "created_at": 1, "estimated_time": 1}
            ))
            
            # Convert ObjectId to string for JSON serialization
            for quiz in quizzes:
                quiz["_id"] = str(quiz["_id"])
                
            print(f"📋 Retrieved {len(quizzes)} quizzes for user: {current_user['email']}")
            return {
                "success": True,
                "quizzes": quizzes
            }
        else:
            return {
                "success": False,
                "message": "Database not available",
                "quizzes": []
            }
            
    except Exception as e:
        print(f"❌ Error retrieving quizzes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve quizzes: {str(e)}")


@app.get("/api/quiz/{quiz_id}")
async def get_quiz_by_id(quiz_id: str, request: Request):
    """Retrieve a specific quiz by its ID for the authenticated user"""
    try:
        # Get current user
        current_user = await get_current_user(request)
        user_id = ObjectId(str(current_user["_id"]))
        
        if quizzes_collection is not None:
            # Only get quiz if it belongs to the current user
            quiz = quizzes_collection.find_one({
                "_id": ObjectId(quiz_id),
                "user_id": user_id
            })
            
            if quiz:
                quiz["_id"] = str(quiz["_id"])
                quiz["user_id"] = str(quiz["user_id"])  # Convert ObjectId to string
                return {
                    "success": True,
                    "quiz": quiz
                }
            else:
                raise HTTPException(status_code=404, detail="Quiz not found or access denied")
        else:
            raise HTTPException(status_code=503, detail="Database not available")
            
    except Exception as e:
        print(f"❌ Error retrieving quiz: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve quiz: {str(e)}")


# Quiz Session History Endpoints
@app.post("/api/quiz/attempt/start")
async def start_quiz_attempt(quiz_id: str, request: Request):
    """Start a new quiz attempt for the authenticated user"""
    try:
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        # Get the quiz details
        if quizzes_collection is not None:
            quiz = quizzes_collection.find_one({
                "_id": ObjectId(quiz_id),
                "user_id": ObjectId(user_id)
            })
            
            if not quiz:
                raise HTTPException(status_code=404, detail="Quiz not found or access denied")
            
            # Create new quiz attempt
            attempt = QuizAttempt(
                user_id=user_id,
                quiz_id=quiz_id,
                quiz_title=quiz.get("title", "Untitled Quiz"),
                answers=[],
                score=0,
                total_questions=len(quiz.get("questions", [])),
                percentage=0.0,
                status="in_progress"
            )
            
            # Store in database
            attempt_dict = attempt.dict()
            attempt_dict["started_at"] = attempt.started_at
            result = quiz_attempts_collection.insert_one(attempt_dict)
            attempt_id = str(result.inserted_id)
            
            print(f"🎯 Started quiz attempt {attempt_id} for user {current_user['email']}")
            
            return {
                "success": True,
                "attempt_id": attempt_id,
                "quiz": {
                    "id": quiz_id,
                    "title": quiz.get("title"),
                    "questions": quiz.get("questions"),
                    "total_questions": len(quiz.get("questions", []))
                }
            }
        else:
            raise HTTPException(status_code=503, detail="Database not available")
            
    except Exception as e:
        print(f"❌ Error starting quiz attempt: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start quiz attempt: {str(e)}")


@app.post("/api/quiz/attempt/{attempt_id}/complete")
async def complete_quiz_attempt(attempt_id: str, attempt_data: QuizAttempt, request: Request):
    """Complete a quiz attempt with answers and score"""
    try:
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        if quiz_attempts_collection is not None:
            # Verify the attempt belongs to the current user
            existing_attempt = quiz_attempts_collection.find_one({
                "_id": ObjectId(attempt_id),
                "user_id": user_id
            })
            
            if not existing_attempt:
                raise HTTPException(status_code=404, detail="Quiz attempt not found or access denied")
            
            # Update the attempt with completion data
            update_data = {
                "answers": [answer.dict() for answer in attempt_data.answers],
                "score": attempt_data.score,
                "percentage": attempt_data.percentage,
                "time_taken": attempt_data.time_taken,
                "completed_at": datetime.now(),
                "status": "completed"
            }
            
            quiz_attempts_collection.update_one(
                {"_id": ObjectId(attempt_id)},
                {"$set": update_data}
            )
            
            print(f"✅ Completed quiz attempt {attempt_id} for user {current_user['email']} - Score: {attempt_data.score}/{attempt_data.total_questions}")
            
            return {
                "success": True,
                "message": "Quiz attempt completed successfully",
                "score": attempt_data.score,
                "percentage": attempt_data.percentage
            }
        else:
            raise HTTPException(status_code=503, detail="Database not available")
            
    except Exception as e:
        print(f"❌ Error completing quiz attempt: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to complete quiz attempt: {str(e)}")


@app.get("/api/quiz/history")
async def get_quiz_history(request: Request, limit: int = 50, offset: int = 0):
    """Get quiz attempt history for the authenticated user"""
    try:
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        if quiz_attempts_collection is not None:
            # Get user's quiz attempts with pagination
            attempts_cursor = quiz_attempts_collection.find(
                {"user_id": user_id}
            ).sort("started_at", -1).skip(offset).limit(limit)
            
            attempts = []
            total_time = 0
            scores = []
            
            for attempt_doc in attempts_cursor:
                # Convert ObjectId to string and create a clean dict for QuizAttempt
                clean_attempt = {
                    "id": str(attempt_doc["_id"]),
                    "user_id": attempt_doc["user_id"],
                    "quiz_title": attempt_doc["quiz_title"],
                    "score": attempt_doc["score"],
                    "total_questions": attempt_doc["total_questions"],
                    "percentage": attempt_doc["percentage"],
                    "time_taken": attempt_doc.get("time_taken"),
                    "started_at": attempt_doc["started_at"],
                    "completed_at": attempt_doc.get("completed_at"),
                    "status": attempt_doc["status"],
                    "answers": attempt_doc.get("answers", [])
                }
                attempt = QuizAttempt(**clean_attempt)
                attempts.append(attempt)
                
                if attempt.time_taken:
                    total_time += attempt.time_taken
                if attempt.status == "completed":
                    scores.append(attempt.percentage)
            
            # Calculate statistics
            total_attempts = len(attempts)
            average_score = sum(scores) / len(scores) if scores else 0
            best_score = max(scores) if scores else 0
            total_time_minutes = total_time / 60  # Convert to minutes
            
            history = QuizHistoryResponse(
                attempts=attempts,
                total_attempts=total_attempts,
                average_score=average_score,
                best_score=best_score,
                total_time_spent=total_time_minutes
            )
            
            print(f"📊 Retrieved quiz history for user {current_user['email']}: {total_attempts} attempts")
            
            return {
                "success": True,
                "history": history.dict()
            }
        else:
            raise HTTPException(status_code=503, detail="Database not available")
            
    except Exception as e:
        print(f"❌ Error retrieving quiz history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve quiz history: {str(e)}")


@app.get("/api/quiz/stats")
async def get_user_quiz_stats(request: Request):
    """Get comprehensive quiz statistics for the authenticated user"""
    try:
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        if quiz_attempts_collection is not None:
            # Get all completed attempts for the user
            completed_attempts = list(quiz_attempts_collection.find({
                "user_id": user_id,
                "status": "completed"
            }).sort("started_at", -1))
            
            if not completed_attempts:
                return {
                    "success": True,
                    "stats": {
                        "user_id": user_id,
                        "total_quizzes_taken": 0,
                        "total_questions_answered": 0,
                        "correct_answers": 0,
                        "accuracy_rate": 0,
                        "average_score": 0,
                        "total_time_spent": 0,
                        "favorite_topics": [],
                        "recent_activity": []
                    }
                }
            
            # Calculate comprehensive statistics
            total_quizzes = len(completed_attempts)
            total_questions = sum(attempt["total_questions"] for attempt in completed_attempts)
            total_correct = sum(attempt["score"] for attempt in completed_attempts)
            total_time = sum(attempt.get("time_taken", 0) for attempt in completed_attempts)
            
            accuracy_rate = (total_correct / total_questions * 100) if total_questions > 0 else 0
            average_score = sum(attempt["percentage"] for attempt in completed_attempts) / total_quizzes
            total_time_minutes = total_time / 60
            
            # Get recent activity (last 10 attempts)
            recent_activity = []
            for attempt_doc in completed_attempts[:10]:
                # Convert ObjectId to string and create a clean dict for QuizAttempt
                clean_attempt = {
                    "id": str(attempt_doc["_id"]),
                    "user_id": attempt_doc["user_id"],
                    "quiz_title": attempt_doc["quiz_title"],
                    "score": attempt_doc["score"],
                    "total_questions": attempt_doc["total_questions"],
                    "percentage": attempt_doc["percentage"],
                    "time_taken": attempt_doc.get("time_taken"),
                    "started_at": attempt_doc["started_at"],
                    "completed_at": attempt_doc.get("completed_at"),
                    "status": attempt_doc["status"],
                    "answers": attempt_doc.get("answers", [])
                }
                recent_activity.append(QuizAttempt(**clean_attempt))
            
            # Extract favorite topics (from quiz titles)
            topics = [attempt["quiz_title"] for attempt in completed_attempts]
            favorite_topics = list(set(topics))[:5]  # Top 5 unique topics
            
            stats = UserQuizStats(
                user_id=user_id,
                total_quizzes_taken=total_quizzes,
                total_questions_answered=total_questions,
                correct_answers=total_correct,
                accuracy_rate=accuracy_rate,
                average_score=average_score,
                total_time_spent=total_time_minutes,
                favorite_topics=favorite_topics,
                recent_activity=recent_activity
            )
            
            print(f"📈 Generated quiz stats for user {current_user['email']}: {total_quizzes} quizzes, {accuracy_rate:.1f}% accuracy")
            
            return {
                "success": True,
                "stats": stats.dict()
            }
        else:
            raise HTTPException(status_code=503, detail="Database not available")
            
    except Exception as e:
        print(f"❌ Error retrieving quiz stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve quiz stats: {str(e)}")


# Session History API Endpoints
@app.get("/api/sessions/history", response_model=SessionHistoryResponse)
async def get_session_history(
    request: Request,
    page: int = 1,
    limit: int = 10
):
    """Get user session history with pagination"""
    try:
        # Get current user
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        if user_sessions_collection is None:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Calculate pagination
        skip = (page - 1) * limit
        
        # Get total count
        total_sessions = user_sessions_collection.count_documents({"user_id": user_id})
        
        # Get sessions with pagination, sorted by login_timestamp descending
        sessions_cursor = user_sessions_collection.find(
            {"user_id": user_id}
        ).sort("login_timestamp", -1).skip(skip).limit(limit)
        
        sessions = []
        for session_doc in sessions_cursor:
            # Convert ObjectId to string and create clean dict
            clean_session = {
                "id": str(session_doc["_id"]),
                "user_id": session_doc["user_id"],
                "session_token": session_doc["session_token"][:20] + "...",  # Truncate for security
                "ip_address": session_doc.get("ip_address"),
                "user_agent": session_doc.get("user_agent"),
                "login_timestamp": session_doc["login_timestamp"],
                "logout_timestamp": session_doc.get("logout_timestamp"),
                "last_activity": session_doc["last_activity"],
                "duration_minutes": session_doc.get("duration_minutes"),
                "is_active": session_doc["is_active"],
                "device_type": session_doc.get("device_type"),
                "browser": session_doc.get("browser"),
                "location": session_doc.get("location")
            }
            sessions.append(UserSession(**clean_session))
        
        # Calculate pagination info
        total_pages = (total_sessions + limit - 1) // limit
        has_next = page < total_pages
        has_previous = page > 1
        
        response = SessionHistoryResponse(
            sessions=sessions,
            total_sessions=total_sessions,
            current_page=page,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous
        )
        
        print(f"📊 Retrieved {len(sessions)} sessions for user {current_user['email']} (page {page})")
        
        return response
        
    except Exception as e:
        print(f"❌ Error retrieving session history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session history: {str(e)}")


@app.get("/api/sessions/stats", response_model=SessionStatsResponse)
async def get_session_stats(request: Request):
    """Get user session statistics"""
    try:
        # Get current user
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        if user_sessions_collection is None:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Get all sessions for the user
        sessions = list(user_sessions_collection.find({"user_id": user_id}))
        
        if not sessions:
            return SessionStatsResponse(
                total_sessions=0,
                total_time_spent=0,
                average_session_duration=0,
                most_active_device=None,
                most_active_browser=None,
                recent_locations=[]
            )
        
        # Calculate statistics
        total_sessions = len(sessions)
        
        # Calculate total time spent (only for completed sessions)
        completed_sessions = [s for s in sessions if s.get("duration_minutes") is not None]
        total_time_spent = sum(s.get("duration_minutes", 0) for s in completed_sessions)
        average_session_duration = total_time_spent / len(completed_sessions) if completed_sessions else 0
        
        # Find most active device and browser
        device_counts = {}
        browser_counts = {}
        locations = set()
        
        for session in sessions:
            device = session.get("device_type")
            if device:
                device_counts[device] = device_counts.get(device, 0) + 1
            
            browser = session.get("browser")
            if browser:
                browser_counts[browser] = browser_counts.get(browser, 0) + 1
            
            location = session.get("location")
            if location:
                locations.add(location)
        
        most_active_device = max(device_counts, key=device_counts.get) if device_counts else None
        most_active_browser = max(browser_counts, key=browser_counts.get) if browser_counts else None
        recent_locations = list(locations)[:5]  # Limit to 5 recent locations
        
        stats = SessionStatsResponse(
            total_sessions=total_sessions,
            total_time_spent=total_time_spent,
            average_session_duration=average_session_duration,
            most_active_device=most_active_device,
            most_active_browser=most_active_browser,
            recent_locations=recent_locations
        )
        
        print(f"📈 Generated session stats for user {current_user['email']}: {total_sessions} sessions, {total_time_spent:.1f} minutes total")
        
        return stats
        
    except Exception as e:
        print(f"❌ Error retrieving session stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session stats: {str(e)}")


# OpenAI Sessions API Endpoints
@app.post("/api/sessions/create", response_model=OpenAISessionData)
async def create_openai_session(
    request: Request,
    session_request: SessionCreateRequest
):
    """Create a new OpenAI Session for chat"""
    try:
        # Get current user
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        # Create session using OpenAI Sessions service
        session_data = await openai_sessions_service.create_session(user_id, session_request)
        
        print(f"✅ Created new OpenAI session {session_data.session_id} for user {current_user['email']}")
        
        return session_data
        
    except Exception as e:
        print(f"❌ Error creating OpenAI session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@app.post("/api/sessions/{session_id}/message", response_model=OpenAISessionData)
async def send_message_to_session(
    session_id: str,
    request: Request,
    update_request: SessionUpdateRequest
):
    """Send a message to an existing OpenAI Session"""
    try:
        # Get current user
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        # Update session with new message
        session_data = await openai_sessions_service.update_session(session_id, user_id, update_request)
        
        print(f"✅ Updated OpenAI session {session_id} with new message for user {current_user['email']}")
        
        return session_data
        
    except Exception as e:
        print(f"❌ Error updating OpenAI session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update session: {str(e)}")


@app.get("/api/sessions/recent", response_model=RecentSessionsResponse)
async def get_recent_sessions(
    request: Request,
    limit: int = 10,
    offset: int = 0
):
    """Get recent chat sessions for the current user"""
    try:
        print(f"🔍 Getting recent sessions with limit={limit}, offset={offset}")
        
        # Get current user
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        print(f"🔍 User ID: {user_id}")
        
        # Get recent sessions
        recent_sessions = await openai_sessions_service.get_recent_sessions(user_id, limit, offset)
        
        print(f"✅ Retrieved {len(recent_sessions.sessions)} recent sessions for user {current_user['email']}")
        
        return recent_sessions
        
    except Exception as e:
        print(f"❌ Error retrieving recent sessions: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve recent sessions: {str(e)}")


@app.get("/api/sessions/{session_id}", response_model=OpenAISessionData)
async def get_openai_session(
    session_id: str,
    request: Request
):
    """Get a specific OpenAI Session by ID"""
    try:
        # Get current user
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        # Get session
        session_data = await openai_sessions_service.get_session(session_id, user_id)
        
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        print(f"✅ Retrieved OpenAI session {session_id} for user {current_user['email']}")
        
        return session_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving OpenAI session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session: {str(e)}")


@app.delete("/api/sessions/{session_id}")
async def delete_openai_session(
    session_id: str,
    request: Request
):
    """Delete an OpenAI Session"""
    try:
        # Get current user
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        # Delete session
        success = await openai_sessions_service.delete_session(session_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        print(f"✅ Deleted OpenAI session {session_id} for user {current_user['email']}")
        
        return {"success": True, "message": "Session deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting OpenAI session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@app.get("/api/sessions/stats")
async def get_user_session_stats(request: Request):
    """Get session statistics for the current user"""
    try:
        # Get current user
        current_user = await get_current_user(request)
        user_id = str(current_user["_id"])
        
        # Get session stats
        stats = await openai_sessions_service.get_user_session_stats(user_id)
        
        print(f"✅ Retrieved session stats for user {current_user['email']}")
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        print(f"❌ Error retrieving session stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session stats: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting LearnXai Backend Server...")
    print("📊 MongoDB Connection: Configured")
    print("🔐 Authentication: JWT Enabled")
    print("🌐 Server URL: http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)