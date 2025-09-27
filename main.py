from agents_service import source_validator_agent, content_generator_agent, tutor_agent
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from agents import Runner, TResponseInputItem, trace
from fastapi.responses import StreamingResponse, JSONResponse
from openai.types.responses import ResponseTextDeltaEvent
from fastapi.middleware.cors import CORSMiddleware
from agents import enable_verbose_stdout_logging
from models import SessionOut, SessionSummary, UserCreate, UserOut, Token
from pymongo_get_database import get_database
from pymongo.errors import DuplicateKeyError
from datetime import timedelta
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

    # existing = Utils.get_user_by_email(user.email)
    # if existing:
    #     raise HTTPException(status_code=400, detail="Email already registered")

    # existing = Utils.get_user_by_password(user.password)

    # if existing:
    #     raise HTTPException(status_code=400, detail="Your password must be unique")

    doc = {
        "name": user.name,
        "email": user.email, 
        "password": Utils.get_password_hash(user.password),
    }

    try:
        result = users_collection.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")
    except Exception as e:
        print("Insert failed:", type(e).__name__, e)
        raise HTTPException(status_code=500, detail="Internal Server Error") from e

    inserted_id = result.inserted_id
    print("Inserted id:", inserted_id)

    token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    token = Utils.create_access_token(data={"sub": user.email}, expires_delta=token_expires)

    # return token shape that matches Token model
    return {"access_token": token, "token_type": "bearer"}
    

# @app.post("/login", response_model=Token)
# def login(form_data: OAuth2PasswordRequestForm = Depends()):

#     db_user = Utils.get_user_by_email(form_data.username)

#     if not db_user or not Utils.verify_password(form_data.password, db_user["password"]):
#         raise HTTPException(status_code=401, detail="Invalid email or password")

#     token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
#     token = Utils.create_access_token(data={"sub": db_user["email"]}, expires_delta=token_expires)
#     return {"access_token": token, "token_type": "bearer"}


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


# if __name__ == "__main__":
#     async def main():
#         result = Runner.run_streamed(starting_agent=quiz_generator_agent, input="python programming")

#         async for event in result.stream_events():
#             if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
#                 print(json.dumps({
#                     "type": event.type,
#                     "delta": event.data.delta
#                 }) + "\n")


#     asyncio.run(main())