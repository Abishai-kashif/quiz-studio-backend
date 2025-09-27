from agents_service import source_validator_agent, content_generator_agent, tutor_agent, assessment_agent
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from agents import Runner, TResponseInputItem, trace
from fastapi.responses import StreamingResponse, JSONResponse
from openai.types.responses import ResponseTextDeltaEvent
from fastapi.middleware.cors import CORSMiddleware
from agents import enable_verbose_stdout_logging
from models import (SessionOut, SessionSummary, UserCreate, UserOut, Token, 
                   AssessmentQuizQuestion, StudentResponse, QuizSession, 
                   StudentProgress, QuizGenerationRequest, QuizAnalytics)
from pymongo_get_database import get_database
from pymongo.errors import DuplicateKeyError
from datetime import timedelta, datetime
from dotenv import load_dotenv
from typing import Optional
from jose import jwt, JWTError
from fastapi import status
from bson import ObjectId
from utils import Utils
import json
import os
from agents import AgentOutputSchema

load_dotenv(override=True)

db = get_database()
users_collection = db["users"]
sessions_collection = db["sessions"]
quizzes_collection = db["quizzes"]
quiz_sessions_collection = db["quiz_sessions"]
student_responses_collection = db["student_responses"]
student_progress_collection = db["student_progress"]
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


@app.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(user: UserCreate):
    """
    Creates a new user and returns an access token.
    Response model is Token (access_token + token_type).
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

    token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    token = Utils.create_access_token(data={"sub": user.email}, expires_delta=token_expires)

    print(f"🎉 Signup completed successfully for: {user.email}")
    # return token shape that matches Token model
    return {"access_token": token, "token_type": "bearer"}
    

@app.post("/login", response_model=Token)
async def login(user_credentials: dict):
    """
    Authenticates user and returns an access token.
    Expects JSON body with email and password fields.
    """
    email = user_credentials.get("email")
    password = user_credentials.get("password")
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    db_user = Utils.get_user_by_email(email)

    if not db_user or not Utils.verify_password(password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    token = Utils.create_access_token(data={"sub": db_user["email"]}, expires_delta=token_expires)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/me", response_model=UserOut)
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


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting LearnXai Backend Server...")
    print("📊 MongoDB Connection: Configured")
    print("🔐 Authentication: JWT Enabled")
    print("🌐 Server URL: http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)