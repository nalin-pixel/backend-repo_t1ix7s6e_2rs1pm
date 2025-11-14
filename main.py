import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import db, create_document, get_documents
from schemas import Conversation, ChatMessage

app = FastAPI(title="Responsible AI App Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# -------- Responsible AI minimal endpoints --------

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str
    model: Optional[str] = None
    tone: Optional[str] = None
    language: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    conversation_id: str

@app.post("/api/conversations", response_model=dict)
async def create_conversation(payload: Conversation):
    try:
        conv_id = create_document("conversation", payload)
        return {"id": conv_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations", response_model=List[dict])
async def list_conversations(limit: int = 20):
    try:
        docs = get_documents("conversation", {}, limit)
        # Convert ObjectId to string for _id
        for d in docs:
            d["id"] = str(d.pop("_id")) if "_id" in d else None
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Minimal safe echo assistant for demo purposes.
    In production, call your LLM provider here.
    """
    # Safety guardrails (very simple demo)
    user_text = (req.message or "").strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    blocked = ["illegal", "violence", "self-harm"]
    if any(word in user_text.lower() for word in blocked):
        safe_reply = "I can't assist with that. If you're in danger or feeling unsafe, please seek professional help or contact local authorities."
    else:
        safe_reply = f"You said: {user_text}. This is a demo assistant."

    # Store conversation message
    message = ChatMessage(role="user", content=user_text, model=req.model, tone=req.tone, language=req.language)
    assistant_msg = ChatMessage(role="assistant", content=safe_reply)

    conv = Conversation(title=user_text[:40] or "New Chat", messages=[message, assistant_msg])

    try:
        conv_id = create_document("conversation", conv)
    except Exception:
        # If DB not available, return ephemeral response
        conv_id = "ephemeral"

    return ChatResponse(reply=safe_reply, conversation_id=conv_id)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
