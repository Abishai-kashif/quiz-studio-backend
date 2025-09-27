"""
OpenAI Agents SDK Sessions Service
Handles user session management and chat history using OpenAI Sessions
"""

import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pymongo_get_database import get_database
from models import (
    OpenAISessionData, 
    OpenAISessionMessage, 
    ChatHistoryEntry, 
    RecentSessionsResponse,
    SessionCreateRequest,
    SessionUpdateRequest
)
from bson import ObjectId
import json

class OpenAISessionsService:
    """Service for managing OpenAI Sessions and chat history"""
    
    def __init__(self):
        self.db = get_database()
        self.sessions_collection = self.db["openai_sessions"] if self.db is not None else None
        self.chat_history_collection = self.db["chat_history"] if self.db is not None else None
        
        # For now, we'll use simple responses instead of OpenAI Agents SDK
        # This can be enhanced later with proper OpenAI integration
        self.default_responses = {
            "greeting": "Hello! I'm LearnXai, your educational assistant. How can I help you learn today?",
            "learning": "That's a great topic to learn about! I'd be happy to help you understand it better.",
            "quiz": "I can create personalized quizzes for you. What subject would you like to focus on?",
            "default": "I'm here to help you learn! Feel free to ask me any questions about your studies."
        }
    
    async def create_session(self, user_id: str, request: SessionCreateRequest) -> OpenAISessionData:
        """Create a new OpenAI Session for a user"""
        session_id = str(ObjectId())
        
        # Initialize session data
        session_data = OpenAISessionData(
            session_id=session_id,
            user_id=user_id,
            session_type=request.session_type,
            context=request.context or {},
            messages=[]
        )
        
        # Add initial message if provided
        if request.initial_message:
            initial_msg = OpenAISessionMessage(
                role="user",
                content=request.initial_message
            )
            session_data.messages.append(initial_msg)
            
            # Generate AI response based on message content
            response_content = self._generate_response(request.initial_message)
            
            ai_response = OpenAISessionMessage(
                role="assistant",
                content=response_content,
                metadata={"session_id": session_id}
            )
            session_data.messages.append(ai_response)
        
        # Store session in database
        if self.sessions_collection is not None:
            session_dict = session_data.model_dump()
            session_dict["_id"] = session_id
            self.sessions_collection.insert_one(session_dict)
        
        return session_data
    
    async def update_session(self, session_id: str, user_id: str, request: SessionUpdateRequest) -> OpenAISessionData:
        """Update an existing OpenAI Session with new message"""
        if self.sessions_collection is None:
            raise Exception("Database not available")
        
        # Get existing session
        session_doc = self.sessions_collection.find_one({
            "_id": session_id,
            "user_id": user_id
        })
        
        if not session_doc:
            raise Exception("Session not found")
        
        # Convert to session data
        session_data = OpenAISessionData(**session_doc)
        
        # Add new message
        session_data.messages.append(request.message)
        session_data.updated_at = datetime.now()
        
        # If it's a user message, get AI response
        if request.message.role == "user":
            # Generate AI response based on message content
            response_content = self._generate_response(request.message.content)
            
            ai_response = OpenAISessionMessage(
                role="assistant",
                content=response_content,
                metadata={"session_id": session_id}
            )
            session_data.messages.append(ai_response)
        
        # Update context if provided
        if request.context:
            session_data.context.update(request.context)
        
        # Save updated session
        session_dict = session_data.model_dump()
        self.sessions_collection.update_one(
            {"_id": session_id},
            {"$set": session_dict}
        )
        
        return session_data
    
    def _generate_response(self, user_message: str) -> str:
        """Generate a simple AI response based on user message content"""
        message_lower = user_message.lower()
        
        # Simple keyword-based responses
        if any(word in message_lower for word in ["hello", "hi", "hey", "greetings"]):
            return self.default_responses["greeting"]
        elif any(word in message_lower for word in ["learn", "study", "understand", "explain"]):
            return self.default_responses["learning"]
        elif any(word in message_lower for word in ["quiz", "test", "exam", "practice"]):
            return self.default_responses["quiz"]
        elif any(word in message_lower for word in ["machine learning", "ml", "ai", "artificial intelligence"]):
            return "Machine learning is a fascinating field! It involves training algorithms to learn patterns from data. Would you like me to explain specific concepts like supervised learning, neural networks, or data preprocessing?"
        elif any(word in message_lower for word in ["python", "programming", "code", "coding"]):
            return "Python is an excellent programming language for beginners and experts alike! It's widely used in data science, web development, and automation. What specific Python topics would you like to explore?"
        elif any(word in message_lower for word in ["math", "mathematics", "calculus", "algebra"]):
            return "Mathematics is the foundation of many fields! Whether you're interested in algebra, calculus, statistics, or discrete math, I can help break down complex concepts into understandable parts."
        elif any(word in message_lower for word in ["help", "assist", "support"]):
            return "I'm here to help you learn! You can ask me about any subject, request explanations of concepts, or ask me to create practice quizzes. What would you like to focus on today?"
        else:
            return f"That's an interesting topic! I'd be happy to help you learn more about it. Could you tell me what specific aspect you'd like to explore or what questions you have?"
    
    async def get_session(self, session_id: str, user_id: str) -> Optional[OpenAISessionData]:
        """Get a specific session by ID"""
        if self.sessions_collection is None:
            return None
        
        session_doc = self.sessions_collection.find_one({
            "_id": session_id,
            "user_id": user_id
        })
        
        if session_doc:
            return OpenAISessionData(**session_doc)
        return None
    
    async def get_recent_sessions(self, user_id: str, limit: int = 10, offset: int = 0) -> RecentSessionsResponse:
        """Get recent chat sessions for a user"""
        if self.sessions_collection is None:
            return RecentSessionsResponse(sessions=[], total_count=0, has_more=False)
        
        # Get sessions sorted by updated_at
        sessions_cursor = self.sessions_collection.find(
            {"user_id": user_id}
        ).sort("updated_at", -1).skip(offset).limit(limit + 1)
        
        sessions = list(sessions_cursor)
        has_more = len(sessions) > limit
        if has_more:
            sessions = sessions[:-1]  # Remove the extra session used for has_more check
        
        # Convert to ChatHistoryEntry format
        chat_entries = []
        for session in sessions:
            # Get the last message for preview
            last_message = ""
            if session.get("messages"):
                last_msg = session["messages"][-1]
                last_message = last_msg.get("content", "")[:100] + "..." if len(last_msg.get("content", "")) > 100 else last_msg.get("content", "")
            
            # Generate title from first user message or use default
            title = "New Chat"
            if session.get("messages"):
                for msg in session["messages"]:
                    if msg.get("role") == "user":
                        title = msg.get("content", "")[:50] + "..." if len(msg.get("content", "")) > 50 else msg.get("content", "")
                        break
            
            entry = ChatHistoryEntry(
                session_id=str(session["_id"]),
                title=title,
                last_message=last_message,
                timestamp=session.get("updated_at", session.get("created_at", datetime.now())),
                message_count=len(session.get("messages", [])),
                session_type=session.get("session_type", "chat"),
                preview=last_message
            )
            chat_entries.append(entry)
        
        # Get total count
        total_count = self.sessions_collection.count_documents({"user_id": user_id})
        
        return RecentSessionsResponse(
            sessions=chat_entries,
            total_count=total_count,
            has_more=has_more
        )
    
    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a session"""
        if self.sessions_collection is None:
            return False
        
        result = self.sessions_collection.delete_one({
            "_id": session_id,
            "user_id": user_id
        })
        
        return result.deleted_count > 0
    
    async def get_user_session_stats(self, user_id: str) -> Dict[str, Any]:
        """Get session statistics for a user"""
        if self.sessions_collection is None:
            return {}
        
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "total_sessions": {"$sum": 1},
                "total_messages": {"$sum": {"$size": "$messages"}},
                "avg_messages_per_session": {"$avg": {"$size": "$messages"}},
                "last_activity": {"$max": "$updated_at"}
            }}
        ]
        
        result = list(self.sessions_collection.aggregate(pipeline))
        
        if result:
            stats = result[0]
            return {
                "total_sessions": stats.get("total_sessions", 0),
                "total_messages": stats.get("total_messages", 0),
                "avg_messages_per_session": round(stats.get("avg_messages_per_session", 0), 2),
                "last_activity": stats.get("last_activity")
            }
        
        return {
            "total_sessions": 0,
            "total_messages": 0,
            "avg_messages_per_session": 0,
            "last_activity": None
        }

# Global service instance
openai_sessions_service = OpenAISessionsService()