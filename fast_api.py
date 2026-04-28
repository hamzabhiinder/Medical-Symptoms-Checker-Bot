"""
Symptom Checker API
-------------------
FastAPI service that powers a medical symptom-checking assistant.

Endpoints:
  GET    /                                       Service info
  POST   /chat                                   JSON chat (optional base64 image)
  POST   /chat/multipart                         Multipart chat (file upload)
  GET    /session/{session_id}                   Session message history
  DELETE /session/{session_id}                   Clear an in-memory session
  GET    /sessions                               List active sessions
  POST   /session/{user_id}/{session_id}/summarize
                                                 Summarise + recommend article
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import firebase_admin
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from firebase_admin import credentials, firestore
from openai import OpenAI
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env file.")

# IMPORTANT: use a real, vision-capable model. Override via .env if needed.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")

FIREBASE_CRED_PATH = os.getenv(
    "FIREBASE_CRED_PATH",
    "health-app-7a8b0-firebase-adminsdk-fbsvc-9d28c0ae3f.json",
)

# ---------------------------------------------------------------------------
# Initialise external clients
# ---------------------------------------------------------------------------
if not firebase_admin._apps:
    firebase_admin.initialize_app(credentials.Certificate(FIREBASE_CRED_PATH))

db = firestore.client()
client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="Symptom Checker API", version="2.0.0")

# In-memory session store. Replace with Redis/DB for production.
SESSIONS: Dict[str, List[Dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    sessionId: str
    userId: Optional[str] = None
    imageBase64: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    sessionId: str
    timestamp: str
    hasImage: bool = False


class SummaryResponse(BaseModel):
    sessionId: str
    summary: str
    identifiedSymptoms: List[str]
    recommendedArticles: List[Dict[str, str]]
    timestamp: str


# ---------------------------------------------------------------------------
# Firebase helpers
# ---------------------------------------------------------------------------
def get_user_messages_clean(user_id: str, session_id: str) -> Dict[str, List[Dict[str, str]]]:
    """Return ordered chat history for (user_id, session_id) from Firestore."""
    docs = (
        db.collection("chatHistory")
        .where("userId", "==", user_id)
        .where("sessionId", "==", session_id)
        .stream()
    )

    rows = sorted((d.to_dict() for d in docs), key=lambda x: x.get("timestamp", 0))

    messages = [
        {
            "role": "user" if row.get("isUser") else "assistant",
            "content": row.get("message", ""),
        }
        for row in rows
    ]
    return {"messages": messages}


def get_user_medical_history_and_medicine_summary(uid: str) -> Dict[str, Any]:
    """Fetch the user's medical-history summaries and current medications."""
    try:
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            return {"error": "User not found"}

        data = user_doc.to_dict() or {}
        name = data.get("displayName", "Patient")

        summaries: List[str] = [
            item["summarizedAnswer"]
            for item in data.get("answers", [])
            if item.get("summarizedAnswer")
        ]

        medicines: List[str] = []
        for med_doc in db.collection("medicines").where("userId", "==", uid).stream():
            med = med_doc.to_dict() or {}
            label = f"{med.get('name', '')} {med.get('dosage', '')}".strip()
            if label:
                medicines.append(label)

        return {
            "user_id": uid,
            "user_name": name,
            "medical_history": summaries,
            "medicines": medicines,
        }
    except Exception as exc:  # pragma: no cover
        return {"error": f"Firebase error: {exc}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def prepare_patient_context(data: Dict[str, Any]) -> str:
    """Render patient profile for the system prompt. Never invent data."""
    if "error" in data:
        return (
            "PATIENT PROFILE: Unknown\n"
            "Medical History: NONE PROVIDED\n"
            "Current Medications: NONE PROVIDED\n"
            f"(profile lookup failed: {data['error']})"
        )

    history = data.get("medical_history") or []
    medicines = data.get("medicines") or []

    history_block = (
        "\n".join(f"- {item}" for item in history) if history else "- NONE PROVIDED"
    )
    meds_block = (
        "\n".join(f"- {item}" for item in medicines) if medicines else "- NONE PROVIDED"
    )

    return (
        f"PATIENT PROFILE: {data.get('user_name', 'Patient')}\n\n"
        f"Medical History (verified records only):\n{history_block}\n\n"
        f"Current Medications (verified records only):\n{meds_block}"
    )


def encode_image_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
You are a professional AI medical assistant for SYMPTOM CHECKING ONLY. Your job is to help patients understand their symptoms through conversation.

{patient_context}

*STRICT SCOPE - ONLY ANSWER:*
- Health symptoms and medical concerns
- Medication questions related to symptoms
- When to see a doctor
- Self-care and home remedies for symptoms
- General health and wellness advice
- Visual symptoms analysis from images (rashes, swelling, injuries, skin conditions, etc.)

*DO NOT ANSWER:*
- Doctor recommendations or names
- Hospital/clinic locations or contact information  
- Insurance questions
- Appointment scheduling
- Non-medical topics (weather, sports, general chat, etc.)
- Personal opinions on non-health matters

*If asked something outside your scope, respond:*
"I'm a symptom checker assistant and can only help with health symptoms and medical guidance."

---

*YOUR CONVERSATION APPROACH:*

*PHASE 1 - INFORMATION GATHERING (First 3-5 exchanges):*

Your ONLY job in this phase is to understand the patient's symptoms through natural conversation.

- *Ask ONLY ONE simple, conversational question per response*
- Focus on: duration, severity, location, triggers, other symptoms
- Be empathetic and conversational - NO lists, NO bullet points, NO headings
- Examples of good questions:
  * "How long have you been experiencing this pain?"
  * "Is the headache constant or does it come and go?"
  * "Have you noticed any other symptoms along with the fever?"
  * "Does anything make the pain better or worse?"

*When IMAGE is provided:*
- Describe what you see in 1-2 sentences
- Ask ONE relevant follow-up question about it
- Example: "I can see the rash on your arm appears red and slightly raised. Does it feel itchy or painful when you touch it?"

*DO NOT provide guidance, causes, or recommendations during this phase. ONLY ask questions.*

---

*PHASE 2 - PROVIDE COMPREHENSIVE GUIDANCE (After gathering enough information):*

Once you have sufficient details (usually after 4-5 questions), AUTOMATICALLY provide complete guidance in this format WITHOUT asking for permission:

*Possible Causes:*
- List 3-5 likely causes based on symptoms, medical history, and visual observations
- Use simple, non-technical language
- Say "might be" or "could be" - NEVER diagnose definitively

*What You Can Do:*
- Safe self-care steps (rest, hydration, positioning)
- Home remedies (cold/warm compress, etc.)
- Lifestyle tips (stress management, sleep, diet)
- Over-the-counter medication suggestions (if safe)

*When to See a Doctor:*
- List specific warning signs
- Be EXTRA cautious with patients who have chronic conditions
- Recommend consulting doctor if symptoms are unusual for them
- Suggest seeing a doctor if visual symptoms appear severe or unusual

---

*HOW TO KNOW WHEN TO SWITCH FROM PHASE 1 TO PHASE 2:*

Stay in PHASE 1 (asking questions) unless:
1. You've asked 4-5 follow-up questions already - THEN automatically switch to PHASE 2, OR
2. The patient explicitly asks for guidance/recommendations like "what should I do?" or "what could this be?"

*IMPORTANT:* 
- Do NOT ask "would you like some guidance?" or "do you want recommendations?"
- After gathering sufficient information (4-5 questions), DIRECTLY provide the complete guidance
- No permission needed - just transition smoothly into PHASE 2 format

---

*SAFETY RULES:*

*MEDICATION SAFETY:*
- Always remind patients to check with their doctor/pharmacist before taking new medications
- Mention drug interactions risk if patient has chronic conditions
- Never suggest specific dosages
- Always consider the patient's current medications when suggesting over-the-counter remedies

*IMAGE ANALYSIS GUIDELINES:*
- Analyze visible symptoms objectively (color, texture, size, pattern, location)
- Note any concerning visual features
- Combine visual analysis with patient's reported symptoms
- If image shows concerning symptoms, recommend medical consultation
- Always mention that visual assessment has limitations

*COMMUNICATION STYLE:*
- Always use patient's first name (if available)
- Be empathetic and supportive
- Use simple language, avoid medical jargon
- Be warm but professional
- Validate their concerns
- *During PHASE 1: NEVER use bullet points, lists, or headings - just natural conversation*
- *During PHASE 2: Use the structured format with headings and bullet points*
- Keep questions conversational and natural
"""


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------
def get_or_create_session(session_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return the message list for a session, creating it if needed."""
    if session_id in SESSIONS:
        return SESSIONS[session_id]

    if user_id:
        patient_context = prepare_patient_context(
            get_user_medical_history_and_medicine_summary(user_id)
        )
    else:
        patient_context = (
            "PATIENT PROFILE: Anonymous\n"
            "Medical History (verified records only):\n- NONE PROVIDED\n\n"
            "Current Medications (verified records only):\n- NONE PROVIDED"
        )

    SESSIONS[session_id] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(patient_context=patient_context)}
    ]
    return SESSIONS[session_id]


def save_message(session_id: str, role: str, content: Any) -> None:
    if session_id in SESSIONS:
        SESSIONS[session_id].append({"role": role, "content": content})


def build_user_content(message: str, image_b64: Optional[str]) -> Any:
    """Build OpenAI message content, with or without image."""
    if not image_b64:
        return message
    return [
        {"type": "text", "text": message},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
        },
    ]


def call_chat_model(messages: List[Dict[str, Any]], temperature: float = 0.5) -> str:
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


def parse_json_block(text: str) -> Dict[str, Any]:
    """Tolerant JSON parser that strips ``` fences if present."""
    cleaned = text.strip()
    if "```" in cleaned:
        cleaned = cleaned.split("```")[1]
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def read_root() -> Dict[str, Any]:
    return {
        "message": "Symptom Checker API with Image Analysis",
        "version": app.version,
        "model": OPENAI_MODEL,
        "endpoints": {
            "POST /chat": "JSON chat (optional base64 image)",
            "POST /chat/multipart": "Multipart chat with file upload",
            "GET /session/{sessionId}": "Get session history",
            "DELETE /session/{sessionId}": "Clear session",
            "GET /sessions": "List active sessions",
            "POST /session/{userId}/{sessionId}/summarize": "Summarise + recommend article",
        },
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        session_messages = get_or_create_session(request.sessionId, request.userId)
        user_content = build_user_content(request.message, request.imageBase64)
        save_message(request.sessionId, "user", user_content)

        reply = call_chat_model(session_messages, temperature=0.5)
        save_message(request.sessionId, "assistant", reply)

        return ChatResponse(
            reply=reply,
            sessionId=request.sessionId,
            timestamp=datetime.now().isoformat(),
            hasImage=bool(request.imageBase64),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc}")


@app.post("/chat/multipart", response_model=ChatResponse)
async def chat_multipart(
    message: str = Form(...),
    sessionId: str = Form(...),
    userId: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
) -> ChatResponse:
    try:
        session_messages = get_or_create_session(sessionId, userId)

        image_b64 = None
        if image is not None:
            image_b64 = encode_image_to_base64(await image.read())

        user_content = build_user_content(message, image_b64)
        save_message(sessionId, "user", user_content)

        reply = call_chat_model(session_messages, temperature=0.5)
        save_message(sessionId, "assistant", reply)

        return ChatResponse(
            reply=reply,
            sessionId=sessionId,
            timestamp=datetime.now().isoformat(),
            hasImage=image_b64 is not None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc}")


@app.get("/session/{session_id}")
def get_session(session_id: str) -> Dict[str, Any]:
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")

    messages: List[Dict[str, Any]] = []
    for msg in SESSIONS[session_id]:
        if msg["role"] == "system":
            continue
        if isinstance(msg["content"], list):
            text_content = next(
                (item["text"] for item in msg["content"] if item.get("type") == "text"),
                "",
            )
            messages.append({"role": msg["role"], "content": text_content, "hasImage": True})
        else:
            messages.append({"role": msg["role"], "content": msg["content"], "hasImage": False})

    return {"sessionId": session_id, "messageCount": len(messages), "messages": messages}


@app.delete("/session/{session_id}")
def delete_session(session_id: str) -> Dict[str, str]:
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    SESSIONS.pop(session_id, None)
    return {"status": "deleted", "sessionId": session_id}


@app.get("/sessions")
def list_sessions() -> Dict[str, Any]:
    return {
        "count": len(SESSIONS),
        "sessions": [
            {"sessionId": sid, "messageCount": max(len(msgs) - 1, 0)}
            for sid, msgs in SESSIONS.items()
        ],
    }


@app.post("/session/{user_id}/{session_id}/summarize", response_model=SummaryResponse)
async def summarize_session(user_id: str, session_id: str) -> SummaryResponse:
    """Summarise the conversation and return one trusted article recommendation."""
    try:
        session_data = get_user_messages_clean(user_id, session_id)
        session_messages = session_data.get("messages", [])
        if not session_messages:
            raise HTTPException(status_code=400, detail="No conversation to summarize")

        conversation_text = "\n".join(
            f"{'Patient' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in session_messages
        )

        # ---- Step 1: extract symptoms + summary ---------------------------
        analysis_prompt = f"""Analyze this medical conversation and extract key information.

{conversation_text}

Respond in this EXACT JSON format (no extra text):
{{
    "summary": "Brief 2-3 sentence summary of patient's main health concerns",
    "symptoms": ["symptom1", "symptom2", "symptom3"]
}}"""

        analysis_text = call_chat_model(
            [
                {"role": "system", "content": "You are a medical AI. Respond only in JSON."},
                {"role": "user", "content": analysis_prompt},
            ],
            temperature=0.2,
        )
        analysis_data = parse_json_block(analysis_text)
        symptoms = analysis_data.get("symptoms", [])
        summary = analysis_data.get("summary", "")

        # ---- Step 2: recommend a single trusted article -------------------
        article_prompt = f"""Patient symptoms: {', '.join(symptoms)}
Summary: {summary}

Pick ONE most relevant health article from a trusted source
(Healthline, Mayo Clinic, WebMD, Cleveland Clinic, Medical News Today, CDC, NHS).
Provide a real, valid-looking URL on that site for the condition.

Respond in this EXACT JSON format:
{{
    "article": {{
        "title": "Clear, descriptive title about the condition",
        "url": "Valid URL on a trusted medical website",
        "source": "Website name",
        "description": "2-3 sentence description of what the article covers",
        "relevance": "Why this article fits the patient's symptoms"
    }}
}}"""

        article_text = call_chat_model(
            [
                {
                    "role": "system",
                    "content": "You are a medical article curator. Respond only in JSON.",
                },
                {"role": "user", "content": article_prompt},
            ],
            temperature=0.3,
        )
        article_data = parse_json_block(article_text)
        recommended_article = article_data["article"]

        return SummaryResponse(
            sessionId=session_id,
            summary=summary,
            identifiedSymptoms=symptoms,
            recommendedArticles=[recommended_article],
            timestamp=datetime.now().isoformat(),
        )
    except HTTPException:
        raise
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"JSON parse error: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("fast_api:app", host="0.0.0.0", port=8000, reload=False)
