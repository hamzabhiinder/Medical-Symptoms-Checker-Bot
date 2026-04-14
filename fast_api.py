
# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel
# from openai import OpenAI
# import os
# from dotenv import load_dotenv
# import firebase_admin
# from firebase_admin import credentials, firestore
# import json
# from typing import Optional, List, Dict
# from datetime import datetime
# import uvicorn

# # ---------------------------
# # CONFIGURATION
# # ---------------------------
# load_dotenv()

# app = FastAPI(title="Symptom Checker API", version="1.0.0")

# # Initialize Firebase (only once)
# if not firebase_admin._apps:
#     cred = credentials.Certificate("health-app-7a8b0-firebase-adminsdk-fbsvc-9d28c0ae3f.json")
#     firebase_admin.initialize_app(cred)

# db = firestore.client()

# # Initialize OpenAI client
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# # Local session storage (in-memory)
# # In production, use Redis or database
# SESSIONS: Dict[str, List[Dict]] = {}

# # ---------------------------
# # PYDANTIC MODELS
# # ---------------------------
# class ChatRequest(BaseModel):
#     message: str
#     sessionId: str
#     userId: Optional[str] = None  # Optional: agar user data chahiye ho

# class ChatResponse(BaseModel):
#     reply: str
#     sessionId: str
#     timestamp: str

# # ---------------------------
# # FIREBASE FUNCTIONS
# # ---------------------------
# def get_user_medical_history_and_medicine_summary(uid: str):
#     """Fetch user data from Firebase"""
#     try:
#         # Get medical history
#         user_ref = db.collection("users").document(uid)
#         doc = user_ref.get()
        
#         if not doc.exists:
#             return {"error": "User not found"}
        
#         data = doc.to_dict()
#         name = data.get("displayName", "Patient")
        
#         # Get summarized answers
#         summaries = []
#         if "answers" in data:
#             for item in data["answers"]:
#                 sum_ans = item.get("summarizedAnswer")
#                 if sum_ans:
#                     summaries.append(sum_ans)
        
#         # Get medicines
#         ref = db.collection("medicines")
#         query = ref.where("userId", "==", uid)
#         medicines = []
#         for doc in query.stream():
#             med_data = doc.to_dict()
#             medicine = f"{med_data.get('name', '')} {med_data.get('dosage', '')}".strip()
#             if medicine:
#                 medicines.append(medicine)
        
#         return {
#             "user_id": uid,
#             "user_name": name,
#             "medical_history": summaries,
#             "medicines": medicines
#         }
    
#     except Exception as e:
#         return {"error": f"Firebase error: {str(e)}"}

# # ---------------------------
# # HELPER FUNCTIONS
# # ---------------------------
# def prepare_patient_context(data):
#     """Prepare patient context from Firebase data"""
#     if "error" in data:
#         return f"**ERROR:** {data['error']}"
    
#     context = f"**PATIENT PROFILE: {data['user_name']}**\n\n"
    
#     # Medical History
#     context += "**Medical History:**\n"
#     if data.get('medical_history'):
#         for summary in data['medical_history']:
#             context += f"- {summary}\n"
#     else:
#         context += "- No medical history available\n"
    
#     # Medicines
#     context += "\n**Current Medications:**\n"
#     if data.get('medicines'):
#         for medicine in data['medicines']:
#             context += f"- {medicine}\n"
#     else:
#         context += "- No medications on record\n"
    
#     return context

# # ---------------------------
# # SYSTEM PROMPT
# # ---------------------------
# SYSTEM_PROMPT = """
# You are a professional AI medical assistant for SYMPTOM CHECKING ONLY. Your job is to help patients understand their symptoms and provide health guidance.

# {patient_context}

# **STRICT SCOPE - ONLY ANSWER:**
# - Health symptoms and medical concerns
# - Medication questions related to symptoms
# - When to see a doctor
# - Self-care and home remedies for symptoms
# - General health and wellness advice

# **DO NOT ANSWER:**
# - Doctor recommendations or names
# - Hospital/clinic locations or contact information  
# - Insurance questions
# - Appointment scheduling
# - Non-medical topics (weather, sports, general chat, etc.)
# - Personal opinions on non-health matters

# **If asked something outside your scope, respond:**
# "I'm a symptom checker assistant and can only help with health symptoms and medical guidance. For [their question], please contact your healthcare provider directly or check their website/customer service."

# ---

# **YOUR APPROACH:**

# 1. **Step 1: Information Gathering**
#     - **CRITICAL: Ask ONLY ONE question per response - never ask multiple questions**
#     - Ask the most important follow-up question based on symptoms and medical history
#     - Continue for 3-5 exchanges until you have sufficient context
#     - Questions should be specific: duration, severity, other symptoms, triggers
#     - Example: "How long did the pain last?" NOT "How long did it last? Was it sharp or dull?"
    
# 2. **Step 2: Provide Guidance**:
   
#    **Possible Causes:**
#    - List 3-5 likely causes based on symptoms and medical history
#    - Use simple, non-technical language
#    - Say "might be" or "could be" - NEVER diagnose definitively
   
#    **What You Can Do:**
#    - Safe self-care steps (rest, hydration, positioning)
#    - Home remedies (cold/warm compress, etc.)
#    - Lifestyle tips (stress management, sleep, diet)
#    - Over-the-counter medication suggestions (if safe)
   
#    **When to See a Doctor:**
#    - List specific warning signs
#    - Be EXTRA cautious with patients who have chronic conditions
#    - Recommend consulting doctor if symptoms are unusual for them

# ---

# **SAFETY RULES:**

# **EMERGENCY SYMPTOMS** - If patient mentions ANY of these:
# - Chest pain or pressure
# - Difficulty breathing or shortness of breath
# - Severe bleeding that won't stop
# - Stroke signs (face drooping, arm weakness, speech difficulty)
# - Severe head injury or sudden severe headache
# - Suicidal thoughts or severe mental health crisis
# - Loss of consciousness
# - Severe allergic reaction

# → **Immediately respond:** "Please call 911 or go to the nearest emergency room RIGHT NOW. Do not wait!"

# **MEDICATION SAFETY:**
# - Always remind patients to check with their doctor/pharmacist before taking new medications
# - Mention drug interactions risk if patient has chronic conditions
# - Never suggest specific dosages
# - For patients with diabetes, kidney issues, or heart conditions - be extra cautious about medication suggestions
# - **IMPORTANT:** Always consider the patient's current medications when suggesting over-the-counter remedies to avoid dangerous interactions

# **COMMUNICATION STYLE:**
# - Always use patient's first name
# - Be empathetic and supportive
# - Use simple language, avoid medical jargon
# - Be warm but professional
# - Validate their concerns
# - **NEVER use bullet points or lists when asking questions**
# - **Ask ONLY ONE question at a time, then wait for the patient's answer**
# - Keep questions conversational and natural
# """

# # ---------------------------
# # SESSION MANAGEMENT
# # ---------------------------
# def get_or_create_session(session_id: str, user_id: Optional[str] = None) -> List[Dict]:
#     """Get existing session or create new one with system prompt"""
#     if session_id not in SESSIONS:
#         # Create new session
#         patient_context = ""
#         if user_id:
#             patient_data = get_user_medical_history_and_medicine_summary(user_id)
#             patient_context = prepare_patient_context(patient_data)
#         else:
#             patient_context = "**PATIENT PROFILE: General Patient**\n\nNo specific medical history available."
        
#         system_prompt = SYSTEM_PROMPT.format(patient_context=patient_context)
#         SESSIONS[session_id] = [
#             {"role": "system", "content": system_prompt}
#         ]
    
#     return SESSIONS[session_id]

# def save_message(session_id: str, role: str, content: str):
#     """Save message to session"""
#     if session_id in SESSIONS:
#         SESSIONS[session_id].append({"role": role, "content": content})

# # ---------------------------
# # API ENDPOINTS
# # ---------------------------
# @app.get("/")
# def read_root():
#     return {
#         "message": "Symptom Checker API",
#         "version": "1.0.0",
#         "endpoints": {
#             "/chat": "POST - Send message and get response",
#             "/session/{sessionId}": "GET - Get session history",
#             "/session/{sessionId}": "DELETE - Clear session"
#         }
#     }

# @app.post("/chat", response_model=ChatResponse)
# async def chat(request: ChatRequest):
#     """
#     Main chat endpoint
    
#     Parameters:
#     - message: User's message
#     - sessionId: Unique session identifier
#     - userId: (Optional) Firebase user ID for medical history
#     """
#     try:
#         # Get or create session
#         session_messages = get_or_create_session(request.sessionId, request.userId)
        
#         # Add user message
#         save_message(request.sessionId, "user", request.message)
        
#         # Generate AI response
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=session_messages,
#             temperature=0.7,
#             max_tokens=600
#         )
        
#         reply = response.choices[0].message.content
        
#         # Save assistant message
#         save_message(request.sessionId, "assistant", reply)
        
#         return ChatResponse(
#             reply=reply,
#             sessionId=request.sessionId,
#             timestamp=datetime.now().isoformat()
#         )
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# @app.get("/session/{session_id}")
# def get_session(session_id: str):
#     """Get session history (excluding system prompt)"""
#     if session_id not in SESSIONS:
#         raise HTTPException(status_code=404, detail="Session not found")
    
#     # Return only user and assistant messages
#     messages = [msg for msg in SESSIONS[session_id] if msg["role"] != "system"]
    
#     return {
#         "sessionId": session_id,
#         "messageCount": len(messages),
#         "messages": messages
#     }

# @app.delete("/session/{session_id}")
# def clear_session(session_id: str):
#     """Clear/delete a session"""
#     if session_id in SESSIONS:
#         del SESSIONS[session_id]
#         return {"message": f"Session {session_id} cleared successfully"}
#     else:
#         raise HTTPException(status_code=404, detail="Session not found")

# @app.get("/sessions")
# def list_sessions():
#     """List all active sessions"""
#     return {
#         "activeSessions": list(SESSIONS.keys()),
#         "count": len(SESSIONS)
#     }

# # ---------------------------
# # RUN SERVER
# # ---------------------------
# if __name__ == "__main__":
   
#     uvicorn.run(app, host="0.0.0.0", port=8000)




# # v2


# from fastapi import FastAPI, HTTPException, File, UploadFile, Form
# from pydantic import BaseModel
# from openai import OpenAI
# import os
# from dotenv import load_dotenv
# import firebase_admin
# from firebase_admin import credentials, firestore
# import json
# import base64
# from typing import Optional, List, Dict
# from datetime import datetime

# # ---------------------------
# # CONFIGURATION
# # ---------------------------
# load_dotenv()

# app = FastAPI(title="Symptom Checker API", version="1.0.0")

# # Initialize Firebase (only once)
# if not firebase_admin._apps:
#     cred = credentials.Certificate("health-app-7a8b0-firebase-adminsdk-fbsvc-9d28c0ae3f.json")
#     firebase_admin.initialize_app(cred)

# db = firestore.client()

# # Initialize OpenAI client
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# # Local session storage (in-memory)
# # In production, use Redis or database
# SESSIONS: Dict[str, List[Dict]] = {}

# # ---------------------------
# # PYDANTIC MODELS
# # ---------------------------
# class ChatRequest(BaseModel):
#     message: str
#     sessionId: str
#     userId: Optional[str] = None
#     imageBase64: Optional[str] = None  # Base64 encoded image

# class ChatResponse(BaseModel):
#     reply: str
#     sessionId: str
#     timestamp: str
#     hasImage: bool = False

# # ---------------------------
# # FIREBASE FUNCTIONS
# # ---------------------------
# def get_user_medical_history_and_medicine_summary(uid: str):
#     """Fetch user data from Firebase"""
#     try:
#         # Get medical history
#         user_ref = db.collection("users").document(uid)
#         doc = user_ref.get()
        
#         if not doc.exists:
#             return {"error": "User not found"}
        
#         data = doc.to_dict()
#         name = data.get("displayName", "Patient")
        
#         # Get summarized answers
#         summaries = []
#         if "answers" in data:
#             for item in data["answers"]:
#                 sum_ans = item.get("summarizedAnswer")
#                 if sum_ans:
#                     summaries.append(sum_ans)
        
#         # Get medicines
#         ref = db.collection("medicines")
#         query = ref.where("userId", "==", uid)
#         medicines = []
#         for doc in query.stream():
#             med_data = doc.to_dict()
#             medicine = f"{med_data.get('name', '')} {med_data.get('dosage', '')}".strip()
#             if medicine:
#                 medicines.append(medicine)
        
#         return {
#             "user_id": uid,
#             "user_name": name,
#             "medical_history": summaries,
#             "medicines": medicines
#         }
    
#     except Exception as e:
#         return {"error": f"Firebase error: {str(e)}"}

# # ---------------------------
# # HELPER FUNCTIONS
# # ---------------------------
# def prepare_patient_context(data):
#     """Prepare patient context from Firebase data"""
#     if "error" in data:
#         return f"**ERROR:** {data['error']}"
    
#     context = f"**PATIENT PROFILE: {data['user_name']}**\n\n"
    
#     # Medical History
#     context += "**Medical History:**\n"
#     if data.get('medical_history'):
#         for summary in data['medical_history']:
#             context += f"- {summary}\n"
#     else:
#         context += "- No medical history available\n"
    
#     # Medicines
#     context += "\n**Current Medications:**\n"
#     if data.get('medicines'):
#         for medicine in data['medicines']:
#             context += f"- {medicine}\n"
#     else:
#         context += "- No medications on record\n"
    
#     return context

# def encode_image_to_base64(image_bytes: bytes) -> str:
#     """Convert image bytes to base64 string"""
#     return base64.b64encode(image_bytes).decode('utf-8')

# # ---------------------------
# # SYSTEM PROMPT
# # ---------------------------
# SYSTEM_PROMPT = """
# You are a professional AI medical assistant for SYMPTOM CHECKING ONLY. Your job is to help patients understand their symptoms and provide health guidance.

# {patient_context}

# **STRICT SCOPE - ONLY ANSWER:**
# - Health symptoms and medical concerns
# - Medication questions related to symptoms
# - When to see a doctor
# - Self-care and home remedies for symptoms
# - General health and wellness advice
# - Visual symptoms analysis from images (rashes, swelling, injuries, skin conditions, etc.)

# **DO NOT ANSWER:**
# - Doctor recommendations or names
# - Hospital/clinic locations or contact information  
# - Insurance questions
# - Appointment scheduling
# - Non-medical topics (weather, sports, general chat, etc.)
# - Personal opinions on non-health matters

# **If asked something outside your scope, respond:**
# "I'm a symptom checker assistant and can only help with health symptoms and medical guidance. For [their question], please contact your healthcare provider directly or check their website/customer service."

# ---

# **YOUR APPROACH:**

# 1. **Step 1: Information Gathering**
#     - **CRITICAL: Ask ONLY ONE question per response - never ask multiple questions**
#     - Ask the most important follow-up question based on symptoms and medical history
#     - Continue for 3-5 exchanges until you have sufficient context
#     - Questions should be specific: duration, severity, other symptoms, triggers
#     - Example: "How long did the pain last?" NOT "How long did it last? Was it sharp or dull?"
    
#     **When IMAGE is provided:**
#     - Carefully analyze the visual symptoms shown in the image
#     - Describe what you observe (color, size, location, pattern, etc.)
#     - Combine image observations with the patient's text description
#     - Ask relevant follow-up questions based on visual findings
#     - Example: "I can see the rash on your arm. Does it feel itchy or painful?"
    
# 2. **Step 2: Provide Guidance**:
   
#    **Possible Causes:**
#    - List 3-5 likely causes based on symptoms, medical history, and visual observations (if image provided)
#    - Use simple, non-technical language
#    - Say "might be" or "could be" - NEVER diagnose definitively
   
#    **What You Can Do:**
#    - Safe self-care steps (rest, hydration, positioning)
#    - Home remedies (cold/warm compress, etc.)
#    - Lifestyle tips (stress management, sleep, diet)
#    - Over-the-counter medication suggestions (if safe)
   
#    **When to See a Doctor:**
#    - List specific warning signs
#    - Be EXTRA cautious with patients who have chronic conditions
#    - Recommend consulting doctor if symptoms are unusual for them
#    - Suggest seeing a doctor if visual symptoms appear severe or unusual

# ---

# **SAFETY RULES:**

# **MEDICATION SAFETY:**
# - Always remind patients to check with their doctor/pharmacist before taking new medications
# - Mention drug interactions risk if patient has chronic conditions
# - Never suggest specific dosages
# - For patients with diabetes, kidney issues, or heart conditions - be extra cautious about medication suggestions
# - **IMPORTANT:** Always consider the patient's current medications when suggesting over-the-counter remedies to avoid dangerous interactions

# **IMAGE ANALYSIS GUIDELINES:**
# - Analyze visible symptoms objectively (color, texture, size, pattern, location)
# - Note any concerning visual features (unusual discoloration, rapid spreading, severe swelling)
# - Combine visual analysis with patient's reported symptoms
# - If image shows concerning symptoms, recommend medical consultation
# - Always mention that visual assessment has limitations and in-person examination is ideal

# **COMMUNICATION STYLE:**
# - Always use patient's first name (if available)
# - Be empathetic and supportive
# - Use simple language, avoid medical jargon
# - Be warm but professional
# - Validate their concerns
# - **NEVER use bullet points or lists when asking questions**
# - **Ask ONLY ONE question at a time, then wait for the patient's answer**
# - Keep questions conversational and natural
# - When analyzing images, be descriptive but gentle in your observations
# """

# # ---------------------------
# # SESSION MANAGEMENT
# # ---------------------------
# def get_or_create_session(session_id: str, user_id: Optional[str] = None) -> List[Dict]:
#     """Get existing session or create new one with system prompt"""
#     if session_id not in SESSIONS:
#         # Create new session
#         patient_context = ""
#         if user_id:
#             patient_data = get_user_medical_history_and_medicine_summary(user_id)
#             patient_context = prepare_patient_context(patient_data)
#         else:
#             patient_context = "**PATIENT PROFILE: General Patient**\n\nNo specific medical history available."
        
#         system_prompt = SYSTEM_PROMPT.format(patient_context=patient_context)
#         SESSIONS[session_id] = [
#             {"role": "system", "content": system_prompt}
#         ]
    
#     return SESSIONS[session_id]

# def save_message(session_id: str, role: str, content):
#     """Save message to session - content can be string or list (for images)"""
#     if session_id in SESSIONS:
#         SESSIONS[session_id].append({"role": role, "content": content})

# # ---------------------------
# # API ENDPOINTS
# # ---------------------------
# @app.get("/")
# def read_root():
#     return {
#         "message": "Symptom Checker API with Image Analysis",
#         "version": "1.0.0",
#         "endpoints": {
#             "/chat": "POST - Send message (with optional image) and get response",
#             "/session/{sessionId}": "GET - Get session history",
#             "/session/{sessionId}": "DELETE - Clear session",
#             "/sessions": "GET - List all active sessions"
#         }
#     }

# @app.post("/chat", response_model=ChatResponse)
# async def chat(request: ChatRequest):
#     """
#     Main chat endpoint with image support
    
#     Parameters:
#     - message: User's message describing symptoms
#     - sessionId: Unique session identifier
#     - userId: (Optional) Firebase user ID for medical history
#     - imageBase64: (Optional) Base64 encoded image for visual symptom analysis
#     """
#     try:
#         # Get or create session
#         session_messages = get_or_create_session(request.sessionId, request.userId)
        
#         # Prepare user message content
#         has_image = False
#         if request.imageBase64:
#             has_image = True
#             # Create message with image
#             user_content = [
#                 {
#                     "type": "text",
#                     "text": request.message
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{request.imageBase64}"
#                     }
#                 }
#             ]
#         else:
#             # Text-only message
#             user_content = request.message
        
#         # Add user message
#         save_message(request.sessionId, "user", user_content)
        
#         # Generate AI response
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",  # Supports vision
#             messages=session_messages,
#             temperature=0.7,
#             max_tokens=800  # Increased for image analysis
#         )
        
#         reply = response.choices[0].message.content
        
#         # Save assistant message
#         save_message(request.sessionId, "assistant", reply)
        
#         return ChatResponse(
#             reply=reply,
#             sessionId=request.sessionId,
#             timestamp=datetime.now().isoformat(),
#             hasImage=has_image
#         )
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# @app.post("/chat/multipart")
# async def chat_multipart(
#     message: str = Form(...),
#     sessionId: str = Form(...),
#     userId: Optional[str] = Form(None),
#     image: Optional[UploadFile] = File(None)
# ):
#     """
#     Alternative endpoint using multipart/form-data for direct file upload
#     """
#     try:
#         # Get or create session
#         session_messages = get_or_create_session(sessionId, userId)
        
#         # Prepare user message content
#         has_image = False
#         if image:
#             has_image = True
#             # Read and encode image
#             image_bytes = await image.read()
#             image_base64 = encode_image_to_base64(image_bytes)
            
#             user_content = [
#                 {
#                     "type": "text",
#                     "text": message
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{image_base64}"
#                     }
#                 }
#             ]
#         else:
#             user_content = message
        
#         # Add user message
#         save_message(sessionId, "user", user_content)
        
#         # Generate AI response
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=session_messages,
#             temperature=0.7,
#             max_tokens=800
#         )
        
#         reply = response.choices[0].message.content
        
#         # Save assistant message
#         save_message(sessionId, "assistant", reply)
        
#         return ChatResponse(
#             reply=reply,
#             sessionId=sessionId,
#             timestamp=datetime.now().isoformat(),
#             hasImage=has_image
#         )
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# @app.get("/session/{session_id}")
# def get_session(session_id: str):
#     """Get session history (excluding system prompt)"""
#     if session_id not in SESSIONS:
#         raise HTTPException(status_code=404, detail="Session not found")
    
#     # Return only user and assistant messages
#     messages = []
#     for msg in SESSIONS[session_id]:
#         if msg["role"] != "system":
#             # Simplify content for display
#             if isinstance(msg["content"], list):
#                 # Extract text from multi-part content
#                 text_content = next((item["text"] for item in msg["content"] if item["type"] == "text"), "")
#                 messages.append({
#                     "role": msg["role"],
#                     "content": text_content,
#                     "hasImage": True
#                 })
#             else:
#                 messages.append({
#                     "role": msg["role"],
#                     "content": msg["content"],
#                     "hasImage": False
#                 })
    
#     return {
#         "sessionId": session_id,
#         "messageCount": len(messages),
#         "messages": messages
#     }

# @app.delete("/session/{session_id}")
# def clear_session(session_id: str):
#     """Clear/delete a session"""
#     if session_id in SESSIONS:
#         del SESSIONS[session_id]
#         return {"message": f"Session {session_id} cleared successfully"}
#     else:
#         raise HTTPException(status_code=404, detail="Session not found")

# @app.get("/sessions")
# def list_sessions():
#     """List all active sessions"""
#     return {
#         "activeSessions": list(SESSIONS.keys()),
#         "count": len(SESSIONS)
#     }

# # ---------------------------
# # RUN SERVER
# # ---------------------------
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)



# # v3
# from fastapi import FastAPI, HTTPException, File, UploadFile, Form
# from pydantic import BaseModel
# from openai import OpenAI
# import os
# from dotenv import load_dotenv
# import firebase_admin
# from firebase_admin import credentials, firestore
# import json
# import base64
# from typing import Optional, List, Dict
# from datetime import datetime
# import uvicorn

# # ---------------------------
# # CONFIGURATION
# # ---------------------------
# load_dotenv()

# app = FastAPI(title="Symptom Checker API", version="1.0.0")

# # Initialize Firebase (only once)
# if not firebase_admin._apps:
#     cred = credentials.Certificate("health-app-7a8b0-firebase-adminsdk-fbsvc-9d28c0ae3f.json")
#     firebase_admin.initialize_app(cred)

# db = firestore.client()

# # Initialize OpenAI client
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# # Local session storage (in-memory)
# SESSIONS: Dict[str, List[Dict]] = {}

# # ---------------------------
# # PYDANTIC MODELS
# # ---------------------------
# class ChatRequest(BaseModel):
#     message: str
#     sessionId: str
#     userId: Optional[str] = None
#     imageBase64: Optional[str] = None  # Base64 encoded image

# class ChatResponse(BaseModel):
#     reply: str
#     sessionId: str
#     timestamp: str
#     hasImage: bool = False

# class SummaryResponse(BaseModel):
#     sessionId: str
#     summary: str
#     identifiedSymptoms: List[str]
#     recommendedArticles: List[Dict[str, str]]
#     timestamp: str


# # ---------------------------
# # FIREBASE FUNCTIONS
# # ---------------------------
# def get_user_medical_history_and_medicine_summary(uid: str):
#     """Fetch user data from Firebase"""
#     try:
#         # Get medical history
#         user_ref = db.collection("users").document(uid)
#         doc = user_ref.get()
        
#         if not doc.exists:
#             return {"error": "User not found"}
        
#         data = doc.to_dict()
#         name = data.get("displayName", "Patient")
        
#         # Get summarized answers
#         summaries = []
#         if "answers" in data:
#             for item in data["answers"]:
#                 sum_ans = item.get("summarizedAnswer")
#                 if sum_ans:
#                     summaries.append(sum_ans)
        
#         # Get medicines
#         ref = db.collection("medicines")
#         query = ref.where("userId", "==", uid)
#         medicines = []
#         for doc in query.stream():
#             med_data = doc.to_dict()
#             medicine = f"{med_data.get('name', '')} {med_data.get('dosage', '')}".strip()
#             if medicine:
#                 medicines.append(medicine)
        
#         return {
#             "user_id": uid,
#             "user_name": name,
#             "medical_history": summaries,
#             "medicines": medicines
#         }
    
#     except Exception as e:
#         return {"error": f"Firebase error: {str(e)}"}

# # ---------------------------
# # HELPER FUNCTIONS
# # ---------------------------
# def prepare_patient_context(data):
#     """Prepare patient context from Firebase data"""
#     if "error" in data:
#         return f"**ERROR:** {data['error']}"
    
#     context = f"**PATIENT PROFILE: {data['user_name']}**\n\n"
    
#     # Medical History
#     context += "**Medical History:**\n"
#     if data.get('medical_history'):
#         for summary in data['medical_history']:
#             context += f"- {summary}\n"
#     else:
#         context += "- No medical history available\n"
    
#     # Medicines
#     context += "\n**Current Medications:**\n"
#     if data.get('medicines'):
#         for medicine in data['medicines']:
#             context += f"- {medicine}\n"
#     else:
#         context += "- No medications on record\n"
    
#     return context

# def encode_image_to_base64(image_bytes: bytes) -> str:
#     """Convert image bytes to base64 string"""
#     return base64.b64encode(image_bytes).decode('utf-8')

# # ---------------------------
# # SYSTEM PROMPT
# # ---------------------------
# SYSTEM_PROMPT = """
# You are a professional AI medical assistant for SYMPTOM CHECKING ONLY. Your job is to help patients understand their symptoms and provide health guidance.

# {patient_context}

# **STRICT SCOPE - ONLY ANSWER:**
# - Health symptoms and medical concerns
# - Medication questions related to symptoms
# - When to see a doctor
# - Self-care and home remedies for symptoms
# - General health and wellness advice
# - Visual symptoms analysis from images (rashes, swelling, injuries, skin conditions, etc.)

# **DO NOT ANSWER:**
# - Doctor recommendations or names
# - Hospital/clinic locations or contact information  
# - Insurance questions
# - Appointment scheduling
# - Non-medical topics (weather, sports, general chat, etc.)
# - Personal opinions on non-health matters

# **If asked something outside your scope, respond:**
# "I'm a symptom checker assistant and can only help with health symptoms and medical guidance. For [their question], please contact your healthcare provider directly or check their website/customer service."

# ---

# **YOUR APPROACH:**

# 1. **Step 1: Information Gathering**
#     - **CRITICAL: Ask ONLY ONE question per response - never ask multiple questions**
#     - Ask the most important follow-up question based on symptoms and medical history
#     - Continue for 3-5 exchanges until you have sufficient context
#     - Questions should be specific: duration, severity, other symptoms, triggers
#     - Example: "How long did the pain last?" NOT "How long did it last? Was it sharp or dull?"
    
#     **When IMAGE is provided:**
#     - Carefully analyze the visual symptoms shown in the image
#     - Describe what you observe (color, size, location, pattern, etc.)
#     - Combine image observations with the patient's text description
#     - Ask relevant follow-up questions based on visual findings
#     - Example: "I can see the rash on your arm. Does it feel itchy or painful?"
    
# 2. **Step 2: Provide Guidance**:
   
#    **Possible Causes:**
#    - List 3-5 likely causes based on symptoms, medical history, and visual observations (if image provided)
#    - Use simple, non-technical language
#    - Say "might be" or "could be" - NEVER diagnose definitively
   
#    **What You Can Do:**
#    - Safe self-care steps (rest, hydration, positioning)
#    - Home remedies (cold/warm compress, etc.)
#    - Lifestyle tips (stress management, sleep, diet)
#    - Over-the-counter medication suggestions (if safe)
   
#    **When to See a Doctor:**
#    - List specific warning signs
#    - Be EXTRA cautious with patients who have chronic conditions
#    - Recommend consulting doctor if symptoms are unusual for them
#    - Suggest seeing a doctor if visual symptoms appear severe or unusual

# ---

# **SAFETY RULES:**

# **MEDICATION SAFETY:**
# - Always remind patients to check with their doctor/pharmacist before taking new medications
# - Mention drug interactions risk if patient has chronic conditions
# - Never suggest specific dosages
# - For patients with diabetes, kidney issues, or heart conditions - be extra cautious about medication suggestions
# - **IMPORTANT:** Always consider the patient's current medications when suggesting over-the-counter remedies to avoid dangerous interactions

# **IMAGE ANALYSIS GUIDELINES:**
# - Analyze visible symptoms objectively (color, texture, size, pattern, location)
# - Note any concerning visual features (unusual discoloration, rapid spreading, severe swelling)
# - Combine visual analysis with patient's reported symptoms
# - If image shows concerning symptoms, recommend medical consultation
# - Always mention that visual assessment has limitations and in-person examination is ideal

# **COMMUNICATION STYLE:**
# - Always use patient's first name (if available)
# - Be empathetic and supportive
# - Use simple language, avoid medical jargon
# - Be warm but professional
# - Validate their concerns
# - **NEVER use bullet points or lists when asking questions**
# - **Ask ONLY ONE question at a time, then wait for the patient's answer**
# - Keep questions conversational and natural
# - When analyzing images, be descriptive but gentle in your observations
# """

# # ---------------------------
# # SESSION MANAGEMENT
# # ---------------------------
# def get_or_create_session(session_id: str, user_id: Optional[str] = None) -> List[Dict]:
#     """Get existing session or create new one with system prompt"""
#     if session_id not in SESSIONS:
#         # Create new session
#         patient_context = ""
#         if user_id:
#             patient_data = get_user_medical_history_and_medicine_summary(user_id)
#             patient_context = prepare_patient_context(patient_data)
#         else:
#             patient_context = "**PATIENT PROFILE: General Patient**\n\nNo specific medical history available."
        
#         system_prompt = SYSTEM_PROMPT.format(patient_context=patient_context)
#         SESSIONS[session_id] = [
#             {"role": "system", "content": system_prompt}
#         ]
    
#     return SESSIONS[session_id]

# def save_message(session_id: str, role: str, content):
#     """Save message to session - content can be string or list (for images)"""
#     if session_id in SESSIONS:
#         SESSIONS[session_id].append({"role": role, "content": content})

# # ---------------------------
# # API ENDPOINTS
# # ---------------------------
# @app.get("/")
# def read_root():
#     return {
#         "message": "Symptom Checker API with Image Analysis",
#         "version": "1.0.0",
#         "endpoints": {
#             "/chat": "POST - Send message (with optional image) and get response",
#             "/chat/multipart": "POST - Send message with direct file upload",
#             "/session/{sessionId}": "GET - Get session history",
#             "/session/{sessionId}": "DELETE - Clear session",
#             "/session/{sessionId}/summarize": "POST - Summarize session and get article recommendations",
#             "/sessions": "GET - List all active sessions"
#         }
#     }

# @app.post("/chat", response_model=ChatResponse)
# async def chat(request: ChatRequest):
#     """
#     Main chat endpoint with image support
    
#     Parameters:
#     - message: User's message describing symptoms
#     - sessionId: Unique session identifier
#     - userId: (Optional) Firebase user ID for medical history
#     - imageBase64: (Optional) Base64 encoded image for visual symptom analysis
#     """
#     try:
#         # Get or create session
#         session_messages = get_or_create_session(request.sessionId, request.userId)
        
#         # Prepare user message content
#         has_image = False
#         if request.imageBase64:
#             has_image = True
#             # Create message with image
#             user_content = [
#                 {
#                     "type": "text",
#                     "text": request.message
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{request.imageBase64}"
#                     }
#                 }
#             ]
#         else:
#             # Text-only message
#             user_content = request.message
        
#         # Add user message
#         save_message(request.sessionId, "user", user_content)
        
#         # Generate AI response
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",  # Supports vision
#             messages=session_messages,
#             temperature=0.7,
#             max_tokens=800  # Increased for image analysis
#         )
        
#         reply = response.choices[0].message.content
        
#         # Save assistant message
#         save_message(request.sessionId, "assistant", reply)
        
#         return ChatResponse(
#             reply=reply,
#             sessionId=request.sessionId,
#             timestamp=datetime.now().isoformat(),
#             hasImage=has_image
#         )
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# @app.post("/chat/multipart")
# async def chat_multipart(
#     message: str = Form(...),
#     sessionId: str = Form(...),
#     userId: Optional[str] = Form(None),
#     image: Optional[UploadFile] = File(None)
# ):
#     """
#     Alternative endpoint using multipart/form-data for direct file upload
#     """
#     try:
#         # Get or create session
#         session_messages = get_or_create_session(sessionId, userId)
        
#         # Prepare user message content
#         has_image = False
#         if image:
#             has_image = True
#             # Read and encode image
#             image_bytes = await image.read()
#             image_base64 = encode_image_to_base64(image_bytes)
            
#             user_content = [
#                 {
#                     "type": "text",
#                     "text": message
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{image_base64}"
#                     }
#                 }
#             ]
#         else:
#             user_content = message
        
#         # Add user message
#         save_message(sessionId, "user", user_content)
        
#         # Generate AI response
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=session_messages,
#             temperature=0.7,
#             max_tokens=800
#         )
        
#         reply = response.choices[0].message.content
        
#         # Save assistant message
#         save_message(sessionId, "assistant", reply)
        
#         return ChatResponse(
#             reply=reply,
#             sessionId=sessionId,
#             timestamp=datetime.now().isoformat(),
#             hasImage=has_image
#         )
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# @app.post("/session/{session_id}/summarize", response_model=SummaryResponse)
# async def summarize_session(session_id: str):
#     """
#     Summarize session conversation and recommend relevant medical articles
    
#     Parameters:
#     - session_id: Session to summarize
    
#     Returns:
#     - Conversation summary
#     - Identified symptoms
#     - Recommended articles based on symptoms
#     """
#     try:
#         if session_id not in SESSIONS:
#             raise HTTPException(status_code=404, detail="Session not found")
        
#         # Get session messages (exclude system prompt)
#         session_messages = [msg for msg in SESSIONS[session_id] if msg["role"] != "system"]
        
#         if len(session_messages) == 0:
#             raise HTTPException(status_code=400, detail="No conversation to summarize")
        
#         # Format conversation for summary
#         conversation_text = ""
#         for msg in session_messages:
#             role = "Patient" if msg["role"] == "user" else "Assistant"
#             content = msg["content"]
            
#             # Handle multi-part content (with images)
#             if isinstance(content, list):
#                 text_content = next((item["text"] for item in content if item["type"] == "text"), "")
#                 conversation_text += f"{role}: {text_content}\n"
#             else:
#                 conversation_text += f"{role}: {content}\n"
        
#         # Create summary prompt
#         summary_prompt = f"""
# Analyze this medical conversation and provide:

# 1. A concise summary of the patient's symptoms and concerns (2-3 sentences)
# 2. A list of identified symptoms (comma-separated)
# 3. Recommend 5 relevant medical articles based on symptoms with titles and brief descriptions

# Conversation:
# {conversation_text}

# Respond ONLY in this JSON format:
# {{
#     "summary": "Brief summary here",
#     "symptoms": ["symptom1", "symptom2", "symptom3"],
#     "articles": [
#         {{
#             "title": "Article title",
#             "description": "Brief description",
#             "relevance": "Why this is relevant",
#             "url": "https://www.healthline.com/health/..."
#         }}
#     ]
# }}

# Make sure article URLs are real and relevant to the symptoms. Use reputable sources like:
# - healthline.com
# - mayoclinic.org
# - webmd.com
# - medicalnewstoday.com
# - nih.gov
# """
        
#         # Generate summary using OpenAI
#         summary_response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": "You are a medical AI that summarizes patient symptoms and recommends relevant health articles from reputable sources."
#                 },
#                 {
#                     "role": "user",
#                     "content": summary_prompt
#                 }
#             ],
#             temperature=0.5,
#             max_tokens=1000
#         )
        
#         # Parse response
#         response_text = summary_response.choices[0].message.content
        
#         # Clean JSON if wrapped in code blocks
#         response_text = response_text.strip()
#         if response_text.startswith("```json"):
#             response_text = response_text.replace("```json", "").replace("```", "").strip()
        
#         summary_data = json.loads(response_text)
        
#         return SummaryResponse(
#             sessionId=session_id,
#             summary=summary_data["summary"],
#             identifiedSymptoms=summary_data["symptoms"],
#             recommendedArticles=summary_data["articles"],
#             timestamp=datetime.now().isoformat()
#         )
    
#     except json.JSONDecodeError as e:
#         raise HTTPException(status_code=500, detail=f"Failed to parse summary response: {str(e)}")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

# # ---------------------------
# # RUN SERVER
# # ---------------------------
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)



# # v4 add article recommendation api,chat api

# from fastapi import FastAPI, HTTPException, File, UploadFile, Form
# from pydantic import BaseModel
# from openai import OpenAI
# import os
# from dotenv import load_dotenv
# import firebase_admin
# from firebase_admin import credentials, firestore
# import json
# import base64
# from typing import Optional, List, Dict
# from datetime import datetime
# import uvicorn

# # ---------------------------
# # CONFIGURATION
# # ---------------------------
# load_dotenv()

# app = FastAPI(title="Symptom Checker API", version="1.0.0")

# # Initialize Firebase (only once)
# if not firebase_admin._apps:
#     cred = credentials.Certificate("health-app-7a8b0-firebase-adminsdk-fbsvc-9d28c0ae3f.json")
#     firebase_admin.initialize_app(cred)

# db = firestore.client()

# # Initialize OpenAI client
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# # Local session storage (in-memory)
# # In production, use Redis or database
# SESSIONS: Dict[str, List[Dict]] = {}

# # ---------------------------
# # PYDANTIC MODELS
# # ---------------------------
# class ChatRequest(BaseModel):
#     message: str
#     sessionId: str
#     userId: Optional[str] = None
#     imageBase64: Optional[str] = None  # Base64 encoded image

# class ChatResponse(BaseModel):
#     reply: str
#     sessionId: str
#     timestamp: str
#     hasImage: bool = False

# # ---------------------------
# # SUMMARY & RECOMMENDATIONS
# # ---------------------------
# class SummaryResponse(BaseModel):
#     sessionId: str
#     summary: str
#     identifiedSymptoms: List[str]
#     recommendedArticles: List[Dict[str, str]]
#     timestamp: str


# # ---------------------------
# # FIREBASE FUNCTIONS
# # ---------------------------
# def get_user_medical_history_and_medicine_summary(uid: str):
#     """Fetch user data from Firebase"""
#     try:
#         # Get medical history
#         user_ref = db.collection("users").document(uid)
#         doc = user_ref.get()
        
#         if not doc.exists:
#             return {"error": "User not found"}
        
#         data = doc.to_dict()
#         name = data.get("displayName", "Patient")
        
#         # Get summarized answers
#         summaries = []
#         if "answers" in data:
#             for item in data["answers"]:
#                 sum_ans = item.get("summarizedAnswer")
#                 if sum_ans:
#                     summaries.append(sum_ans)
        
#         # Get medicines
#         ref = db.collection("medicines")
#         query = ref.where("userId", "==", uid)
#         medicines = []
#         for doc in query.stream():
#             med_data = doc.to_dict()
#             medicine = f"{med_data.get('name', '')} {med_data.get('dosage', '')}".strip()
#             if medicine:
#                 medicines.append(medicine)
        
#         return {
#             "user_id": uid,
#             "user_name": name,
#             "medical_history": summaries,
#             "medicines": medicines
#         }
    
#     except Exception as e:
#         return {"error": f"Firebase error: {str(e)}"}

# # ---------------------------
# # HELPER FUNCTIONS
# # ---------------------------
# def prepare_patient_context(data):
#     """Prepare patient context from Firebase data"""
#     if "error" in data:
#         return f"**ERROR:** {data['error']}"
    
#     context = f"**PATIENT PROFILE: {data['user_name']}**\n\n"
    
#     # Medical History
#     context += "**Medical History:**\n"
#     if data.get('medical_history'):
#         for summary in data['medical_history']:
#             context += f"- {summary}\n"
#     else:
#         context += "- No medical history available\n"
    
#     # Medicines
#     context += "\n**Current Medications:**\n"
#     if data.get('medicines'):
#         for medicine in data['medicines']:
#             context += f"- {medicine}\n"
#     else:
#         context += "- No medications on record\n"
    
#     return context

# def encode_image_to_base64(image_bytes: bytes) -> str:
#     """Convert image bytes to base64 string"""
#     return base64.b64encode(image_bytes).decode('utf-8')

# # ---------------------------
# # SYSTEM PROMPT
# # ---------------------------
# SYSTEM_PROMPT = """
# You are a professional AI medical assistant for SYMPTOM CHECKING ONLY. Your job is to help patients understand their symptoms and provide health guidance.

# {patient_context}

# **STRICT SCOPE - ONLY ANSWER:**
# - Health symptoms and medical concerns
# - Medication questions related to symptoms
# - When to see a doctor
# - Self-care and home remedies for symptoms
# - General health and wellness advice
# - Visual symptoms analysis from images (rashes, swelling, injuries, skin conditions, etc.)

# **DO NOT ANSWER:**
# - Doctor recommendations or names
# - Hospital/clinic locations or contact information  
# - Insurance questions
# - Appointment scheduling
# - Non-medical topics (weather, sports, general chat, etc.)
# - Personal opinions on non-health matters

# **If asked something outside your scope, respond:**
# "I'm a symptom checker assistant and can only help with health symptoms and medical guidance. For [their question], please contact your healthcare provider directly or check their website/customer service."

# ---

# **YOUR APPROACH:**

# 1. **Step 1: Information Gathering**
#     - **CRITICAL: Ask ONLY ONE question per response - never ask multiple questions**
#     - Ask the most important follow-up question based on symptoms and medical history
#     - Continue for 3-5 exchanges until you have sufficient context
#     - Questions should be specific: duration, severity, other symptoms, triggers
#     - Example: "How long did the pain last?" NOT "How long did it last? Was it sharp or dull?"
    
#     **When IMAGE is provided:**
#     - Carefully analyze the visual symptoms shown in the image
#     - Describe what you observe (color, size, location, pattern, etc.)
#     - Combine image observations with the patient's text description
#     - Ask relevant follow-up questions based on visual findings
#     - Example: "I can see the rash on your arm. Does it feel itchy or painful?"
    
# 2. **Step 2: Provide Guidance**:
   
#    **Possible Causes:**
#    - List 3-5 likely causes based on symptoms, medical history, and visual observations (if image provided)
#    - Use simple, non-technical language
#    - Say "might be" or "could be" - NEVER diagnose definitively
   
#    **What You Can Do:**
#    - Safe self-care steps (rest, hydration, positioning)
#    - Home remedies (cold/warm compress, etc.)
#    - Lifestyle tips (stress management, sleep, diet)
#    - Over-the-counter medication suggestions (if safe)
   
#    **When to See a Doctor:**
#    - List specific warning signs
#    - Be EXTRA cautious with patients who have chronic conditions
#    - Recommend consulting doctor if symptoms are unusual for them
#    - Suggest seeing a doctor if visual symptoms appear severe or unusual

# ---

# **SAFETY RULES:**

# **MEDICATION SAFETY:**
# - Always remind patients to check with their doctor/pharmacist before taking new medications
# - Mention drug interactions risk if patient has chronic conditions
# - Never suggest specific dosages
# - For patients with diabetes, kidney issues, or heart conditions - be extra cautious about medication suggestions
# - **IMPORTANT:** Always consider the patient's current medications when suggesting over-the-counter remedies to avoid dangerous interactions

# **IMAGE ANALYSIS GUIDELINES:**
# - Analyze visible symptoms objectively (color, texture, size, pattern, location)
# - Note any concerning visual features (unusual discoloration, rapid spreading, severe swelling)
# - Combine visual analysis with patient's reported symptoms
# - If image shows concerning symptoms, recommend medical consultation
# - Always mention that visual assessment has limitations and in-person examination is ideal

# **COMMUNICATION STYLE:**
# - Always use patient's first name (if available)
# - Be empathetic and supportive
# - Use simple language, avoid medical jargon
# - Be warm but professional
# - Validate their concerns
# - **NEVER use bullet points or lists when asking questions**
# - **Ask ONLY ONE question at a time, then wait for the patient's answer**
# - Keep questions conversational and natural
# - When analyzing images, be descriptive but gentle in your observations
# """

# # ---------------------------
# # SESSION MANAGEMENT
# # ---------------------------
# def get_or_create_session(session_id: str, user_id: Optional[str] = None) -> List[Dict]:
#     """Get existing session or create new one with system prompt"""
#     if session_id not in SESSIONS:
#         # Create new session
#         patient_context = ""
#         if user_id:
#             patient_data = get_user_medical_history_and_medicine_summary(user_id)
#             patient_context = prepare_patient_context(patient_data)
#         else:
#             patient_context = "**PATIENT PROFILE: General Patient**\n\nNo specific medical history available."
        
#         system_prompt = SYSTEM_PROMPT.format(patient_context=patient_context)
#         SESSIONS[session_id] = [
#             {"role": "system", "content": system_prompt}
#         ]
    
#     return SESSIONS[session_id]

# def save_message(session_id: str, role: str, content):
#     """Save message to session - content can be string or list (for images)"""
#     if session_id in SESSIONS:
#         SESSIONS[session_id].append({"role": role, "content": content})

# # ---------------------------
# # API ENDPOINTS
# # ---------------------------
# @app.get("/")
# def read_root():
#     return {
#         "message": "Symptom Checker API with Image Analysis",
#         "version": "1.0.0",
#         "endpoints": {
#             "/chat": "POST - Send message (with optional image) and get response",
#             "/chat/multipart": "POST - Send message with direct file upload",
#             "/session/{sessionId}": "GET - Get session history",
#             "/session/{sessionId}": "DELETE - Clear session",
#             "/session/{sessionId}/summarize": "POST - Summarize session and get article recommendations",
#             "/sessions": "GET - List all active sessions"
#         }
#     }

# @app.post("/chat", response_model=ChatResponse)
# async def chat(request: ChatRequest):
#     """
#     Main chat endpoint with image support
    
#     Parameters:
#     - message: User's message describing symptoms
#     - sessionId: Unique session identifier
#     - userId: (Optional) Firebase user ID for medical history
#     - imageBase64: (Optional) Base64 encoded image for visual symptom analysis
#     """
#     try:
#         # Get or create session
#         session_messages = get_or_create_session(request.sessionId, request.userId)
        
#         # Prepare user message content
#         has_image = False
#         if request.imageBase64:
#             has_image = True
#             # Create message with image
#             user_content = [
#                 {
#                     "type": "text",
#                     "text": request.message
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{request.imageBase64}"
#                     }
#                 }
#             ]
#         else:
#             # Text-only message
#             user_content = request.message
        
#         # Add user message
#         save_message(request.sessionId, "user", user_content)
        
#         # Generate AI response
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",  # Supports vision
#             messages=session_messages,
#             temperature=0.7,
#             max_tokens=800  # Increased for image analysis
#         )
        
#         reply = response.choices[0].message.content
        
#         # Save assistant message
#         save_message(request.sessionId, "assistant", reply)
        
#         return ChatResponse(
#             reply=reply,
#             sessionId=request.sessionId,
#             timestamp=datetime.now().isoformat(),
#             hasImage=has_image
#         )
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# @app.post("/chat/multipart")
# async def chat_multipart(
#     message: str = Form(...),
#     sessionId: str = Form(...),
#     userId: Optional[str] = Form(None),
#     image: Optional[UploadFile] = File(None)
# ):
#     """
#     Alternative endpoint using multipart/form-data for direct file upload
#     """
#     try:
#         # Get or create session
#         session_messages = get_or_create_session(sessionId, userId)
        
#         # Prepare user message content
#         has_image = False
#         if image:
#             has_image = True
#             # Read and encode image
#             image_bytes = await image.read()
#             image_base64 = encode_image_to_base64(image_bytes)
            
#             user_content = [
#                 {
#                     "type": "text",
#                     "text": message
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{image_base64}"
#                     }
#                 }
#             ]
#         else:
#             user_content = message
        
#         # Add user message
#         save_message(sessionId, "user", user_content)
        
#         # Generate AI response
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=session_messages,
#             temperature=0.7,
#             max_tokens=800
#         )
        
#         reply = response.choices[0].message.content
        
#         # Save assistant message
#         save_message(sessionId, "assistant", reply)
        
#         return ChatResponse(
#             reply=reply,
#             sessionId=sessionId,
#             timestamp=datetime.now().isoformat(),
#             hasImage=has_image
#         )
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# @app.get("/session/{session_id}")
# def get_session(session_id: str):
#     """Get session history (excluding system prompt)"""
#     if session_id not in SESSIONS:
#         raise HTTPException(status_code=404, detail="Session not found")
    
#     # Return only user and assistant messages
#     messages = []
#     for msg in SESSIONS[session_id]:
#         if msg["role"] != "system":
#             # Simplify content for display
#             if isinstance(msg["content"], list):
#                 # Extract text from multi-part content
#                 text_content = next((item["text"] for item in msg["content"] if item["type"] == "text"), "")
#                 messages.append({
#                     "role": msg["role"],
#                     "content": text_content,
#                     "hasImage": True
#                 })
#             else:
#                 messages.append({
#                     "role": msg["role"],
#                     "content": msg["content"],
#                     "hasImage": False
#                 })
    
#     return {
#         "sessionId": session_id,
#         "messageCount": len(messages),
#         "messages": messages
#     }

# @app.post("/session/{session_id}/summarize", response_model=SummaryResponse)
# async def summarize_session(session_id: str):
#     """
#     Summarize session conversation and recommend relevant medical articles
    
#     Parameters:
#     - session_id: Session to summarize
    
#     Returns:
#     - Conversation summary
#     - Identified symptoms
#     - Recommended articles based on symptoms
#     """
#     try:
#         if session_id not in SESSIONS:
#             raise HTTPException(status_code=404, detail="Session not found")
        
#         # Get session messages (exclude system prompt)
#         session_messages = [msg for msg in SESSIONS[session_id] if msg["role"] != "system"]
        
#         if len(session_messages) == 0:
#             raise HTTPException(status_code=400, detail="No conversation to summarize")
        
#         # Format conversation for summary
#         conversation_text = ""
#         for msg in session_messages:
#             role = "Patient" if msg["role"] == "user" else "Assistant"
#             content = msg["content"]
            
#             # Handle multi-part content (with images)
#             if isinstance(content, list):
#                 text_content = next((item["text"] for item in content if item["type"] == "text"), "")
#                 conversation_text += f"{role}: {text_content}\n"
#             else:
#                 conversation_text += f"{role}: {content}\n"
        
#         # Create summary prompt
#         summary_prompt = f"""
# Analyze this medical conversation and provide:

# 1. A concise summary of the patient's symptoms and concerns (2-3 sentences)
# 2. A list of identified symptoms (comma-separated, be specific)
# 3. Recommend TOP 3 most relevant medical articles based ONLY on the identified symptoms

# Conversation:
# {conversation_text}

# Respond ONLY in this JSON format:
# {{
#     "summary": "Brief summary here",
#     "symptoms": ["symptom1", "symptom2", "symptom3"],
#     "articles": [
#         {{
#             "title": "Article title",
#             "description": "Brief description (1-2 sentences)",
#             "relevance": "Why this is most relevant to the symptoms",
#             "url": "https://www.healthline.com/health/..."
#         }}
#     ]
# }}

# IMPORTANT:
# - Recommend EXACTLY 3 articles
# - Each article must be directly related to the PRIMARY symptoms discussed
# - Prioritize articles that cover the main condition or symptom
# - Use real URLs from reputable sources like healthline.com, mayoclinic.org, webmd.com, medicalnewstoday.com, or nih.gov
# - Focus on educational articles about the symptoms, not general wellness content
# """
        
#         # Generate summary using OpenAI
#         summary_response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": "You are a medical AI that summarizes patient conversations and recommends relevant health articles from reputable sources."
#                 },
#                 {
#                     "role": "user",
#                     "content": summary_prompt
#                 }
#             ],
#             temperature=0.5,
#             max_tokens=1000
#         )
        
#         # Parse response
#         response_text = summary_response.choices[0].message.content
        
#         # Clean JSON if wrapped in code blocks
#         response_text = response_text.strip()
#         if response_text.startswith("```json"):
#             response_text = response_text.replace("```json", "").replace("```", "").strip()
        
#         summary_data = json.loads(response_text)
        
#         return SummaryResponse(
#             sessionId=session_id,
#             summary=summary_data["summary"],
#             identifiedSymptoms=summary_data["symptoms"],
#             recommendedArticles=summary_data["articles"],
#             timestamp=datetime.now().isoformat()
#         )
    
#     except json.JSONDecodeError as e:
#         raise HTTPException(status_code=500, detail=f"Failed to parse summary response: {str(e)}")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

# # ---------------------------
# # RUN SERVER
# # ---------------------------
# if __name__ == "__main__":

#     uvicorn.run(app, host="0.0.0.0", port=8000)




# v5 add article recommendation api,chat api

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import json
import base64
from typing import Optional, List, Dict
from datetime import datetime
import uvicorn

# ---------------------------
# CONFIGURATION
# ---------------------------
load_dotenv()

app = FastAPI(title="Symptom Checker API", version="1.0.0")

# Initialize Firebase (only once)
if not firebase_admin._apps:
    cred = credentials.Certificate("health-app-7a8b0-firebase-adminsdk-fbsvc-9d28c0ae3f.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Local session storage (in-memory)
# In production, use Redis or database
SESSIONS: Dict[str, List[Dict]] = {}

# ---------------------------
# PYDANTIC MODELS
# ---------------------------
class ChatRequest(BaseModel):
    message: str
    sessionId: str
    userId: Optional[str] = None
    imageBase64: Optional[str] = None  # Base64 encoded image

class ChatResponse(BaseModel):
    reply: str
    sessionId: str
    timestamp: str
    hasImage: bool = False

# ---------------------------
# SUMMARY & RECOMMENDATIONS
# ---------------------------
class SummaryResponse(BaseModel):
    sessionId: str
    summary: str
    identifiedSymptoms: List[str]
    recommendedArticles: List[Dict[str, str]]
    timestamp: str


# ---------------------------
# FIREBASE FUNCTIONS
# ---------------------------
# -----------------------
# Get all chatHistory documents
# -----------------------
def get_user_messages_clean(user_id: str,session_id: str):
    ref = db.collection("chatHistory")
    query = ref.where("userId", "==", user_id).where("sessionId", "==", session_id)
    
    all_data = []
    for doc in query.stream():
        data = doc.to_dict()
        all_data.append(data)
    
    sorted_data = sorted(all_data, key=lambda x: x['timestamp'])
    # print(sorted_data)    

    
    messages = []
    for data in sorted_data:
        role = "user" if data.get("isUser") else "assistant"
        messages.append({
            "role": role,
            "content": data.get("message", ""),
        })
    
    return {"messages": messages}
    

def get_user_medical_history_and_medicine_summary(uid: str):
    """Fetch user data from Firebase"""
    try:
        # Get medical history
        user_ref = db.collection("users").document(uid)
        doc = user_ref.get()
        
        if not doc.exists:
            return {"error": "User not found"}
        
        data = doc.to_dict()
        name = data.get("displayName", "Patient")
        
        # Get summarized answers
        summaries = []
        if "answers" in data:
            for item in data["answers"]:
                sum_ans = item.get("summarizedAnswer")
                if sum_ans:
                    summaries.append(sum_ans)
        
        # Get medicines
        ref = db.collection("medicines")
        query = ref.where("userId", "==", uid)
        medicines = []
        for doc in query.stream():
            med_data = doc.to_dict()
            medicine = f"{med_data.get('name', '')} {med_data.get('dosage', '')}".strip()
            if medicine:
                medicines.append(medicine)
        
        return {
            "user_id": uid,
            "user_name": name,
            "medical_history": summaries,
            "medicines": medicines
        }
    
    except Exception as e:
        return {"error": f"Firebase error: {str(e)}"}

# ---------------------------
# HELPER FUNCTIONS
# ---------------------------
def prepare_patient_context(data):
    """Prepare patient context from Firebase data"""
    if "error" in data:
        return f"**ERROR:** {data['error']}"
    
    context = f"**PATIENT PROFILE: {data['user_name']}**\n\n"
    
    # Medical History
    context += "**Medical History:**\n"
    if data.get('medical_history'):
        for summary in data['medical_history']:
            context += f"- {summary}\n"
    else:
        context += "- No medical history available\n"
    
    # Medicines
    context += "\n**Current Medications:**\n"
    if data.get('medicines'):
        for medicine in data['medicines']:
            context += f"- {medicine}\n"
    else:
        context += "- No medications on record\n"
    
    return context

def encode_image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 string"""
    return base64.b64encode(image_bytes).decode('utf-8')

# ---------------------------
# SYSTEM PROMPT
# ---------------------------

SYSTEM_PROMPT = """
You are a professional AI medical assistant for SYMPTOM CHECKING ONLY. Your job is to help patients understand their symptoms through conversation.

{patient_context}

**STRICT SCOPE - ONLY ANSWER:**
- Health symptoms and medical concerns
- Medication questions related to symptoms
- When to see a doctor
- Self-care and home remedies for symptoms
- General health and wellness advice
- Visual symptoms analysis from images (rashes, swelling, injuries, skin conditions, etc.)

**DO NOT ANSWER:**
- Doctor recommendations or names
- Hospital/clinic locations or contact information  
- Insurance questions
- Appointment scheduling
- Non-medical topics (weather, sports, general chat, etc.)
- Personal opinions on non-health matters

**If asked something outside your scope, respond:**
"I'm a symptom checker assistant and can only help with health symptoms and medical guidance."

---

**YOUR CONVERSATION APPROACH:**

**PHASE 1 - INFORMATION GATHERING (First 3-5 exchanges):**

Your ONLY job in this phase is to understand the patient's symptoms through natural conversation.

- **Ask ONLY ONE simple, conversational question per response**
- Focus on: duration, severity, location, triggers, other symptoms
- Be empathetic and conversational - NO lists, NO bullet points, NO headings
- Examples of good questions:
  * "How long have you been experiencing this pain?"
  * "Is the headache constant or does it come and go?"
  * "Have you noticed any other symptoms along with the fever?"
  * "Does anything make the pain better or worse?"

**When IMAGE is provided:**
- Describe what you see in 1-2 sentences
- Ask ONE relevant follow-up question about it
- Example: "I can see the rash on your arm appears red and slightly raised. Does it feel itchy or painful when you touch it?"

**DO NOT provide guidance, causes, or recommendations during this phase. ONLY ask questions.**

---

**PHASE 2 - PROVIDE COMPREHENSIVE GUIDANCE (After gathering enough information):**

Once you have sufficient details (usually after 4-5 questions), AUTOMATICALLY provide complete guidance in this format WITHOUT asking for permission:

**Possible Causes:**
- List 3-5 likely causes based on symptoms, medical history, and visual observations
- Use simple, non-technical language
- Say "might be" or "could be" - NEVER diagnose definitively

**What You Can Do:**
- Safe self-care steps (rest, hydration, positioning)
- Home remedies (cold/warm compress, etc.)
- Lifestyle tips (stress management, sleep, diet)
- Over-the-counter medication suggestions (if safe)

**When to See a Doctor:**
- List specific warning signs
- Be EXTRA cautious with patients who have chronic conditions
- Recommend consulting doctor if symptoms are unusual for them
- Suggest seeing a doctor if visual symptoms appear severe or unusual

---

**HOW TO KNOW WHEN TO SWITCH FROM PHASE 1 TO PHASE 2:**

Stay in PHASE 1 (asking questions) unless:
1. You've asked 4-5 follow-up questions already - THEN automatically switch to PHASE 2, OR
2. The patient explicitly asks for guidance/recommendations like "what should I do?" or "what could this be?"

**IMPORTANT:** 
- Do NOT ask "would you like some guidance?" or "do you want recommendations?"
- After gathering sufficient information (4-5 questions), DIRECTLY provide the complete guidance
- No permission needed - just transition smoothly into PHASE 2 format

---

**SAFETY RULES:**

**MEDICATION SAFETY:**
- Always remind patients to check with their doctor/pharmacist before taking new medications
- Mention drug interactions risk if patient has chronic conditions
- Never suggest specific dosages
- Always consider the patient's current medications when suggesting over-the-counter remedies

**IMAGE ANALYSIS GUIDELINES:**
- Analyze visible symptoms objectively (color, texture, size, pattern, location)
- Note any concerning visual features
- Combine visual analysis with patient's reported symptoms
- If image shows concerning symptoms, recommend medical consultation
- Always mention that visual assessment has limitations

**COMMUNICATION STYLE:**
- Always use patient's first name (if available)
- Be empathetic and supportive
- Use simple language, avoid medical jargon
- Be warm but professional
- Validate their concerns
- **During PHASE 1: NEVER use bullet points, lists, or headings - just natural conversation**
- **During PHASE 2: Use the structured format with headings and bullet points**
- Keep questions conversational and natural
"""

# ---------------------------
# SESSION MANAGEMENT
# ---------------------------
def get_or_create_session(session_id: str, user_id: Optional[str] = None) -> List[Dict]:
    """Get existing session or create new one with system prompt"""
    if session_id not in SESSIONS:
        # Create new session
        patient_context = ""
        if user_id:
            patient_data = get_user_medical_history_and_medicine_summary(user_id)
            patient_context = prepare_patient_context(patient_data)
        else:
            patient_context = "**PATIENT PROFILE: General Patient**\n\nNo specific medical history available."
        
        system_prompt = SYSTEM_PROMPT.format(patient_context=patient_context)
        SESSIONS[session_id] = [
            {"role": "system", "content": system_prompt}
        ]
    
    return SESSIONS[session_id]

def save_message(session_id: str, role: str, content):
    """Save message to session - content can be string or list (for images)"""
    if session_id in SESSIONS:
        SESSIONS[session_id].append({"role": role, "content": content})

# ---------------------------
# API ENDPOINTS
# ---------------------------
@app.get("/")
def read_root():
    return {
        "message": "Symptom Checker API with Image Analysis",
        "version": "1.0.0",
        "endpoints": {
            "/chat": "POST - Send message (with optional image) and get response",
            "/chat/multipart": "POST - Send message with direct file upload",
            "/session/{sessionId}": "GET - Get session history",
            "/session/{sessionId}": "DELETE - Clear session",
            "/session/{sessionId}/summarize": "POST - Summarize session and get article recommendations",
            "/sessions": "GET - List all active sessions"
        }
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint with image support
    
    Parameters:
    - message: User's message describing symptoms
    - sessionId: Unique session identifier
    - userId: (Optional) Firebase user ID for medical history
    - imageBase64: (Optional) Base64 encoded image for visual symptom analysis
    """
    try:
        # Get or create session
        session_messages = get_or_create_session(request.sessionId, request.userId)
        
        # Prepare user message content
        has_image = False
        if request.imageBase64:
            has_image = True
            # Create message with image
            user_content = [
                {
                    "type": "text",
                    "text": request.message
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{request.imageBase64}"
                    }
                }
            ]
        else:
            # Text-only message
            user_content = request.message
        
        # Add user message
        save_message(request.sessionId, "user", user_content)
        
        # Generate AI response
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Supports vision
            messages=session_messages,
            temperature=0.7,
            max_tokens=800  # Increased for image analysis
        )
        
        reply = response.choices[0].message.content
        
        # Save assistant message
        save_message(request.sessionId, "assistant", reply)
        
        return ChatResponse(
            reply=reply,
            sessionId=request.sessionId,
            timestamp=datetime.now().isoformat(),
            hasImage=has_image
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/chat/multipart")
async def chat_multipart(
    message: str = Form(...),
    sessionId: str = Form(...),
    userId: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """
    Alternative endpoint using multipart/form-data for direct file upload
    """
    try:
        # Get or create session
        session_messages = get_or_create_session(sessionId, userId)
        
        # Prepare user message content
        has_image = False
        if image:
            has_image = True
            # Read and encode image
            image_bytes = await image.read()
            image_base64 = encode_image_to_base64(image_bytes)
            
            user_content = [
                {
                    "type": "text",
                    "text": message
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                }
            ]
        else:
            user_content = message
        
        # Add user message
        save_message(sessionId, "user", user_content)
        
        # Generate AI response
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=session_messages,
            temperature=0.7,
            max_tokens=800
        )
        
        reply = response.choices[0].message.content
        
        # Save assistant message
        save_message(sessionId, "assistant", reply)
        
        return ChatResponse(
            reply=reply,
            sessionId=sessionId,
            timestamp=datetime.now().isoformat(),
            hasImage=has_image
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/session/{session_id}")
def get_session(session_id: str):
    """Get session history (excluding system prompt)"""
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Return only user and assistant messages
    messages = []
    for msg in SESSIONS[session_id]:
        if msg["role"] != "system":
            # Simplify content for display
            if isinstance(msg["content"], list):
                # Extract text from multi-part content
                text_content = next((item["text"] for item in msg["content"] if item["type"] == "text"), "")
                messages.append({
                    "role": msg["role"],
                    "content": text_content,
                    "hasImage": True
                })
            else:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "hasImage": False
                })
    
    return {
        "sessionId": session_id,
        "messageCount": len(messages),
        "messages": messages
    }

@app.post("/session/{user_id}/{session_id}/summarize", response_model=SummaryResponse)
async def summarize_session(user_id:str,session_id: str):
    """
    Summarize session and recommend articles using GPT only (no web search API)
    """
    try:
        # Firebase se messages fetch karo
        session_data = get_user_messages_clean(user_id, session_id)
        session_messages = session_data.get("messages", [])
        
        if len(session_messages) == 0:
            raise HTTPException(status_code=400, detail="No conversation to summarize")
        
        # Format conversation (baaki sab same hai)
        conversation_text = ""
        for msg in session_messages:
            role = "Patient" if msg["role"] == "user" else "Assistant"
            content = msg["content"]
            conversation_text += f"{role}: {content}\n"
        
        # Step 1: Extract symptoms and summary using GPT
        analysis_prompt = f"""
Analyze this medical conversation and extract key information:

{conversation_text}

Respond in this EXACT JSON format (no extra text):
{{
    "summary": "Brief 2-3 sentence summary of patient's main health concerns",
    "symptoms": ["symptom1", "symptom2", "symptom3"]
}}
"""
        
        analysis_response = client.chat.completions.create(
            model="gpt-4o",  # Using GPT-4o for better accuracy
            messages=[
                {"role": "system", "content": "You are a medical AI. Respond only in JSON format."},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        analysis_text = analysis_response.choices[0].message.content.strip()
        if "```" in analysis_text:
            analysis_text = analysis_text.split("```")[1].replace("json", "").strip()
        
        analysis_data = json.loads(analysis_text)
        symptoms = analysis_data["symptoms"]
        summary = analysis_data["summary"]
        
        # Step 2: Use GPT to generate article links and titles based on symptoms
        article_prompt = f"""
Based on these patient symptoms and summary:

Symptoms: {', '.join(symptoms)}
Summary: {summary}

Generate 1 MOST RELEVANT health article with a REAL and VALID URL.

INSTRUCTIONS:
1. Analyze the patient's PRIMARY health concern from the conversation
2. Choose the BEST trusted medical website for this condition:
   - Healthline
   - Mayo Clinic
   - WebMD
   - Cleveland Clinic
   - Medical News Today
   - CDC
   - NHS

3. Generate a REAL, VALID URL that follows the standard format for that website
4. Ensure the URL is for a legitimate health article about the condition

Respond in this EXACT JSON format:
{{
    "article": {{
        "title": "Clear, descriptive title about the condition",
        "url": "Valid URL from a trusted medical website",
        "source": "Website name",
        "description": "2-3 sentences explaining what this article covers",
        "relevance": "Why this article is most helpful for the patient's symptoms"
    }}
}}

IMPORTANT: 
- Return only 1 article
- URL must be valid and follow the website's standard format
- Choose the most appropriate medical source for the condition
"""
        
        article_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a medical article curator. Generate valid URLs from trusted medical websites based on patient symptoms. Respond only in JSON format."},
                {"role": "user", "content": article_prompt}
            ],
            temperature=0.4,
            max_tokens=700
        )
        
        article_text = article_response.choices[0].message.content.strip()
        if "```" in article_text:
            article_text = article_text.split("```")[1].replace("json", "").strip()
        
        article_data = json.loads(article_text)
        recommended_article = article_data["article"]  # Single article now
        
        return SummaryResponse(
            sessionId=session_id,
            summary=summary,
            identifiedSymptoms=symptoms,
            recommendedArticles=[recommended_article],  # Return as array with 1 item
            timestamp=datetime.now().isoformat()
        )
    
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"JSON parse error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")



# ---------------------------
# RUN SERVER
# ---------------------------
if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8000)