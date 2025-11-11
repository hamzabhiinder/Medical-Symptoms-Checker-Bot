# from fastapi import FastAPI, Request, Header, HTTPException, Depends
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# import firebase_admin
# from firebase_admin import credentials, firestore
# import openai
# import os
# from datetime import datetime
# from typing import List, Optional, Dict, Any
# from functools import wraps

# # ------------------------------------------------------------
# # Initialize FastAPI app
# # ------------------------------------------------------------
# app = FastAPI(
#     title="Medical Symptom Checker API",
#     version="2.0",
#     description="An AI-powered medical chatbot with user medical profile integration"
# )

# # Enable CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Change to your frontend domain in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ------------------------------------------------------------
# # Initialize Firebase
# # ------------------------------------------------------------
# cred = credentials.Certificate("path/to/serviceAccountKey.json")
# firebase_admin.initialize_app(cred)
# db = firestore.client()

# # ------------------------------------------------------------
# # Initialize OpenAI
# # ------------------------------------------------------------
# openai.api_key = os.environ.get("OPENAI_API_KEY")

# # ------------------------------------------------------------
# # Dependency for user_id validation
# # ------------------------------------------------------------
# async def require_user_id(request: Request, x_user_id: Optional[str] = Header(None)) -> str:
#     if x_user_id:
#         return x_user_id
#     try:
#         body = await request.json()
#         if "user_id" in body:
#             return body["user_id"]
#     except:
#         pass
#     raise HTTPException(status_code=401, detail="user_id is required in headers or body")

# # ------------------------------------------------------------
# # Helper Models
# # ------------------------------------------------------------
# class ChatRequest(BaseModel):
#     message: str
#     conversation_history: Optional[List[Dict[str, Any]]] = []

# class ProfileRequest(BaseModel):
#     date_of_birth: Optional[str]
#     gender: Optional[str]
#     ethnicity: Optional[str]
#     home_address: Optional[str]
#     city: Optional[str]
#     state: Optional[str]
#     zip_code: Optional[str]
#     phone_number: Optional[str]
#     height: Optional[str]
#     weight: Optional[str]
#     had_surgeries: Optional[bool] = False
#     been_hospitalized: Optional[bool] = False
#     high_blood_pressure: Optional[bool] = False
#     diabetes: Optional[bool] = False
#     heart_disease: Optional[bool] = False
#     known_allergies: Optional[bool] = False
#     smokes_tobacco: Optional[bool] = False
#     consumes_alcohol: Optional[bool] = False
#     uses_recreational_drugs: Optional[bool] = False
#     recent_weight_changes: Optional[bool] = False
#     recent_fever: Optional[bool] = False
#     cancer_history: Optional[bool] = False
#     family_history_serious_illness: Optional[bool] = False

# class MedicationRequest(BaseModel):
#     medicine_name: str
#     dosage: Optional[str] = ""
#     frequency: Optional[str] = ""

# # ------------------------------------------------------------
# # MedicalChatbot class (same as Flask version, adapted)
# # ------------------------------------------------------------
# class MedicalChatbot:
#     def __init__(self):
#         self.model = "gpt-4-turbo-preview"

#     def get_user_medical_history(self, user_id):
#         try:
#             doc_ref = db.collection("users").document(user_id)
#             doc = doc_ref.get()
#             return doc.to_dict() if doc.exists else None
#         except Exception as e:
#             print(f"Error fetching user data: {e}")
#             return None

#     def get_user_medications(self, user_id):
#         try:
#             meds_ref = db.collection("users").document(user_id).collection("medications")
#             medications = meds_ref.stream()
#             med_list = [
#                 {
#                     "name": med.to_dict().get("medicine_name", ""),
#                     "dosage": med.to_dict().get("dosage", ""),
#                     "frequency": med.to_dict().get("frequency", "")
#                 }
#                 for med in medications
#             ]
#             return med_list
#         except Exception as e:
#             print(f"Error fetching medications: {e}")
#             return []

#     def calculate_age(self, dob_string):
#         try:
#             if not dob_string:
#                 return "Not specified"
#             dob = datetime.strptime(dob_string, "%m/%d/%Y")
#             today = datetime.now()
#             return str(today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day)))
#         except:
#             return "Not specified"

#     def format_medical_context(self, user_data, medications):
#         if not user_data:
#             return "No medical history available."
#         meds_text = "None reported"
#         if medications:
#             meds_text = "\n".join([
#                 f"- {m['name']} ({m.get('dosage','')}) taken {m.get('frequency','')}"
#                 for m in medications
#             ])
#         return f"""
# Patient Medical Profile:
# - Age: {self.calculate_age(user_data.get('date_of_birth', ''))}
# - Gender: {user_data.get('gender', 'Not specified')}
# - Height: {user_data.get('height', 'Not specified')}
# - Weight: {user_data.get('weight', 'Not specified')}
# - Location: {user_data.get('city', '')}, {user_data.get('state', '')}

# Current Medications:
# {meds_text}
# """

#     def create_system_prompt(self):
#         return """
#         You are a professional medical symptom checker assistant powered by evidence-based medical data.
#         Your responses should be comprehensive yet clear, following this specific structure: 
#         RESPONSE STRUCTURE: After gathering sufficient information about the patient's symptoms,
#           provide your assessment in this exact format: 
#           **Possible Causes:** List the most likely conditions or causes based on the symptoms and patient's medical profile. Consider: 
#           - Patient's existing conditions (diabetes, hypertension, etc.) 
#           - Current medications and potential side effects - Age, gender, and lifestyle factors 
#           - Symptom patterns and duration 
#           **What You Can Do Now:** Provide practical, evidence-based self-care recommendations: 
#           - Home remedies and comfort measures 
#           - Over-the-counter medications (if appropriate) 
#           - Lifestyle modifications 
#           - Warning signs to watch for - Consider drug interactions with current medications 
#           **When to See a Doctor:** Clearly specify when professional medical attention is needed: 
#           - Timeframes (immediate, within 24 hours, within a week) 
#           - Specific warning signs 
#           - Symptom progression indicators 
#           - Emergency situations 
#           **Note:** "These answers are evidence-based, derived from millions of medical data points and tailored using your profile and medications when available. They are not a substitute for a doctor's diagnosis or treatment plan." 
#           IMPORTANT GUIDELINES: 
#           1. Ask clarifying questions FIRST before giving the structured assessment 
#           2. Consider patient's medications for potential interactions or side effects 
#           3. Factor in chronic conditions when assessing symptoms 
#           4. Be specific about warning signs based on their medical history 
#           5. Always recommend professional consultation for serious symptoms 
#           6. In case of EMERGENCY symptoms (chest pain, difficulty breathing, severe bleeding, loss of consciousness), immediately advise calling emergency services 
#           EMERGENCY SYMPTOMS REQUIRING IMMEDIATE ATTENTION: 
#           - Chest pain or pressure 
#           - Difficulty breathing or shortness of breath 
#           - Severe bleeding 
#           - Loss of consciousness 
#           - Stroke symptoms (facial drooping, arm weakness, speech difficulty) 
#           - Severe allergic reactions 
#           - Signs of heart attack 
#           - Suicidal thoughts or severe mental health crisis 
#           CONVERSATION FLOW: 
#           1. First response: Ask relevant questions to understand symptoms better 
#           2. Gather information: Duration, severity, triggers, associated symptoms 
#           3. Consider context: Review patient's medical history and medications 
#           4. Provide assessment: Use the structured format above 
#           5. Offer follow-up: Ask if they need clarification or have more symptoms Be empathetic, professional, and thorough. Prioritize patient safety above all.
#           """

#     def detect_emergency(self, message):
#         keywords = ['chest pain', 'can\'t breathe', 'loss of consciousness', 'stroke', 'heart attack', 'seizure']
#         return any(k in message.lower() for k in keywords)

#     def parse_medical_response(self, text):
#         if "**Possible Causes:**" in text:
#             return {"type": "assessment", "raw_text": text}
#         return {"type": "conversation", "message": text}

#     def chat(self, user_id, message, conversation_history=[]):
#         if self.detect_emergency(message):
#             return {
#                 "success": True,
#                 "is_emergency": True,
#                 "response": {
#                     "type": "emergency",
#                     "message": "⚠️ Possible emergency symptoms detected. Please contact emergency services immediately."
#                 }
#             }
#         user_data = self.get_user_medical_history(user_id)
#         medications = self.get_user_medications(user_id)
#         context = self.format_medical_context(user_data, medications)

#         messages = [
#             {"role": "system", "content": self.create_system_prompt()},
#             {"role": "system", "content": f"Patient Context:\n{context}"}
#         ]
#         messages.extend(conversation_history)
#         messages.append({"role": "user", "content": message})

#         try:
#             response = openai.chat.completions.create(
#                 model=self.model,
#                 messages=messages,
#                 temperature=0.7,
#                 max_tokens=1500
#             )
#             text = response.choices[0].message.content
#             return {
#                 "success": True,
#                 "is_emergency": False,
#                 "response": self.parse_medical_response(text),
#                 "user_context_loaded": user_data is not None,
#                 "medications_loaded": len(medications) > 0
#             }
#         except Exception as e:
#             return {"success": False, "error": str(e)}

# # ------------------------------------------------------------
# # Initialize chatbot
# # ------------------------------------------------------------
# chatbot = MedicalChatbot()

# # ------------------------------------------------------------
# # Helper: Save conversation
# # ------------------------------------------------------------
# def save_conversation(user_id, message, response):
#     try:
#         db.collection("conversations").add({
#             "user_id": user_id,
#             "user_message": message,
#             "assistant_response": response,
#             "timestamp": firestore.SERVER_TIMESTAMP
#         })
#     except Exception as e:
#         print("Error saving conversation:", e)

# # ------------------------------------------------------------
# # Routes
# # ------------------------------------------------------------
# @app.post("/api/chat")
# async def chat(req: ChatRequest, user_id: str = Depends(require_user_id)):
#     result = chatbot.chat(user_id, req.message, req.conversation_history)
#     if result.get("success") and not result.get("is_emergency"):
#         save_conversation(user_id, req.message, result["response"])
#     return result


# @app.post("/api/user/profile")
# async def save_user_profile(req: ProfileRequest, user_id: str = Depends(require_user_id)):
#     user_ref = db.collection("users").document(user_id)
#     data = req.dict(exclude_unset=True)
#     data["updated_at"] = firestore.SERVER_TIMESTAMP
#     if user_ref.get().exists:
#         user_ref.update(data)
#         msg = "User profile updated successfully"
#     else:
#         data["created_at"] = firestore.SERVER_TIMESTAMP
#         user_ref.set(data)
#         msg = "User profile created successfully"
#     return {"success": True, "message": msg}


# @app.get("/api/user/profile")
# async def get_user_profile(user_id: str = Depends(require_user_id)):
#     user_data = chatbot.get_user_medical_history(user_id)
#     if not user_data:
#         raise HTTPException(status_code=404, detail="Profile not found")
#     user_data.pop("created_at", None)
#     user_data.pop("updated_at", None)
#     return {"success": True, "data": user_data}


# @app.post("/api/medications")
# async def add_medication(req: MedicationRequest, user_id: str = Depends(require_user_id)):
#     med_ref = db.collection("users").document(user_id).collection("medications").add({
#         "medicine_name": req.medicine_name,
#         "dosage": req.dosage,
#         "frequency": req.frequency,
#         "added_at": firestore.SERVER_TIMESTAMP
#     })
#     return {"success": True, "message": "Medication added", "medication_id": med_ref[1].id}


# @app.get("/api/medications")
# async def get_medications(user_id: str = Depends(require_user_id)):
#     meds = chatbot.get_user_medications(user_id)
#     return {"success": True, "count": len(meds), "medications": meds}


# @app.delete("/api/medications/{medication_id}")
# async def delete_medication(medication_id: str, user_id: str = Depends(require_user_id)):
#     db.collection("users").document(user_id).collection("medications").document(medication_id).delete()
#     return {"success": True, "message": "Medication deleted"}


# @app.get("/api/conversations/history")
# async def get_conversation_history(user_id: str = Depends(require_user_id), limit: int = 50):
#     conversations = db.collection("conversations")\
#         .where("user_id", "==", user_id)\
#         .order_by("timestamp", direction=firestore.Query.DESCENDING)\
#         .limit(limit)\
#         .stream()
#     result = []
#     for conv in conversations:
#         data = conv.to_dict()
#         if "timestamp" in data and data["timestamp"]:
#             data["timestamp"] = data["timestamp"].isoformat()
#         result.append(data)
#     return {"success": True, "count": len(result), "conversations": result}


# @app.get("/health")
# async def health():
#     return {
#         "status": "healthy",
#         "service": "Medical Symptom Checker API",
#         "version": "2.0",
#         "timestamp": datetime.now().isoformat()
#     }




# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from dotenv import load_dotenv
# import openai
# import os
# from datetime import datetime

# # ------------------------------------------------------------
# # Load environment variables from .env file
# # ------------------------------------------------------------
# load_dotenv()  # Make sure you have python-dotenv installed

# # ------------------------------------------------------------
# # Initialize FastAPI app
# # ------------------------------------------------------------
# app = FastAPI(
#     title="Simple Medical Chat API",
#     version="1.1",
#     description="An AI-powered medical chatbot using OpenAI model from .env"
# )

# # Enable CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Change to your frontend domain in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ------------------------------------------------------------
# # Initialize OpenAI
# # ------------------------------------------------------------
# openai.api_key = os.getenv("OPENAI_API_KEY")
# OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-o-mini")

# # ------------------------------------------------------------
# # Request Model
# # ------------------------------------------------------------
# class ChatRequest(BaseModel):
#     message: str
#     conversation_history: list = []

# # ------------------------------------------------------------
# # Chatbot Class
# # ------------------------------------------------------------
# class SimpleMedicalChatbot:
#     def __init__(self, model_name: str):
#         self.model = model_name

#     def create_system_prompt(self):
#         return """
#         You are a professional AI-powered medical assistant chatbot. 
#         Your role is to help users understand possible causes of their symptoms, 
#         suggest safe self-care measures, and guide them on when to seek professional medical attention. 
#         You are not a doctor and must never provide a definitive diagnosis or prescribe medication.

#         Always follow this response structure:

#         **Possible Causes:**  
#         List the most likely explanations for the user’s symptoms, based on general medical knowledge.  
#         Avoid using overly technical terms unless necessary. Keep tone simple and empathetic.  

#         **What You Can Do Now:**  
#         Provide practical, evidence-based self-care steps that are generally safe.  
#         Include guidance such as: rest, hydration, over-the-counter remedies (avoid brand names), and lifestyle adjustments.  
#         Always remind users to consult a healthcare provider before taking any new medication.  

#         **When to See a Doctor:**  
#         Clearly explain when the user should seek medical attention.  
#         Mention red flags and warning signs like symptom worsening, duration, severity, or new symptoms developing.  

#         Safety Rules:
#         1. If the user mentions emergency symptoms like chest pain, shortness of breath, severe bleeding, stroke symptoms, 
#         loss of consciousness, or suicidal thoughts — IMMEDIATELY respond:  
#         “⚠️ Emergency symptoms detected! Please call emergency services or visit the nearest hospital right now.”  
#         2. Never make a direct diagnosis (e.g., “You have pneumonia”).  
#         Instead, use phrases like “It might be related to...” or “It could be due to...”  
#         3. Be empathetic, reassuring, and supportive in every response.  
#         4. Respect user privacy and never ask for personal or identifying information.  
#         5. Always end responses with:  
#         “I’m here to help you understand your symptoms better. Please contact a doctor if your condition worsens.”  
#         """

#     def detect_emergency(self, message: str):
#         keywords = [
#             'chest pain', 'can’t breathe', 'shortness of breath',
#             'loss of consciousness', 'stroke', 'heart attack', 'seizure'
#         ]
#         return any(k in message.lower() for k in keywords)

#     def chat(self, message: str, conversation_history: list):
#         if self.detect_emergency(message):
#             return {
#                 "success": True,
#                 "is_emergency": True,
#                 "response": "⚠️ Emergency symptoms detected! Please call emergency services immediately."
#             }

#         messages = [
#             {"role": "system", "content": self.create_system_prompt()}
#         ]
#         messages.extend(conversation_history)
#         messages.append({"role": "user", "content": message})

#         try:
#             response = openai.chat.completions.create(
#                 model=self.model,
#                 messages=messages,
#                 temperature=0.7,
#                 max_tokens=1000
#             )
#             return {
#                 "success": True,
#                 "is_emergency": False,
#                 "response": response.choices[0].message.content
#             }
#         except Exception as e:
#             return {"success": False, "error": str(e)}

# # ------------------------------------------------------------
# # Initialize chatbot
# # ------------------------------------------------------------
# chatbot = SimpleMedicalChatbot(model_name=OPENAI_MODEL)

# # ------------------------------------------------------------
# # Routes
# # ------------------------------------------------------------
# @app.post("/api/chat")
# async def chat(req: ChatRequest):
#     return chatbot.chat(req.message, req.conversation_history)

# @app.get("/health")
# async def health():
#     return {
#         "status": "healthy",
#         "service": "Simple Medical Chat API",
#         "model": OPENAI_MODEL,
#         "version": "1.1",
#         "timestamp": datetime.now().isoformat()
#     }


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app)




from dotenv import load_dotenv
import streamlit as st
import json
import google.generativeai as genai
import re
import os
from datetime import datetime

# ------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEN_API_KEY")
GEMINI_MODEL = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")

# # ------------------------------------------------------------
# # Initialize FastAPI app
# # ------------------------------------------------------------
# app = FastAPI(
#     title="Simple Medical Chat API (Gemini)",
#     version="1.1",
#     description="An AI‑powered medical chatbot using Gemini model"
# )

# # Enable CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Change to your frontend domain in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ------------------------------------------------------------
# # Initialize Gemini
# # ------------------------------------------------------------
# genai.configure(api_key=GEMINI_API_KEY)

# # ------------------------------------------------------------
# # Request Model
# # ------------------------------------------------------------
# class ChatRequest(BaseModel):
#     message: str
#     conversation_history: list = []

# # ------------------------------------------------------------
# # Chatbot Class
# # ------------------------------------------------------------
# class SimpleMedicalChatbot:
#     def __init__(self, model_name: str):
#         self.model  = genai.GenerativeModel(model_name)

#     def create_system_prompt(self):
#         return """
#         You are a professional AI‑powered medical assistant chatbot. 
#         Your role is to help users understand possible causes of their symptoms, 
#         suggest safe self‑care measures, and guide them on when to seek professional medical attention. 
#         You are not a doctor and must never provide a definitive diagnosis or prescribe medication.

#         Always follow this response structure:

#         **Possible Causes:**  
#         List the most likely explanations for the user’s symptoms, based on general medical knowledge.  
#         Avoid using overly technical terms unless necessary. Keep tone simple and empathetic.  

#         **What You Can Do Now:**  
#         Provide practical, evidence‑based self‑care steps that are generally safe.  
#         Include guidance such as: rest, hydration, over‑the‑counter remedies (avoid brand names), and lifestyle adjustments.  
#         Always remind users to consult a healthcare provider before taking any new medication.  

#         **When to See a Doctor:**  
#         Clearly explain when the user should seek medical attention.  
#         Mention red flags and warning signs like symptom worsening, duration, severity, or new symptoms developing.  

#         Safety Rules:
#         1. If the user mentions emergency symptoms like chest pain, shortness of breath, severe bleeding, stroke symptoms, 
#         loss of consciousness, or suicidal thoughts — IMMEDIATELY respond:  
#         “⚠️ Emergency symptoms detected! Please call emergency services or visit the nearest hospital right now.”  
#         2. Never make a direct diagnosis (e.g., “You have pneumonia”).  
#         Instead, use phrases like “It might be related to…” or “It could be due to…”  
#         3. Be empathetic, reassuring, and supportive in every response.  
#         4. Respect user privacy and never ask for personal or identifying information.  
#         5. Always end responses with:  
#         “I’m here to help you understand your symptoms better. Please contact a doctor if your condition worsens.”  
#         """

#     def detect_emergency(self, message: str):
#         keywords = [
#             'chest pain', 'shortness of breath', 'can’t breathe',
#             'loss of consciousness', 'stroke', 'heart attack', 'seizure'
#         ]
#         return any(k in message.lower() for k in keywords)

#     def chat(self, message: str, conversation_history: list):
#         if self.detect_emergency(message):
#             return {
#                 "success": True,
#                 "is_emergency": True,
#                 "response": "⚠️ Emergency symptoms detected! Please call emergency services immediately."
#             }

#         # Build Gemini request
#         system_instr = {"role": "system", "parts": [{"text": self.create_system_prompt()}]}

#         # Convert conversation history into contents list
#         contents = []
#         for msg in conversation_history:
#             role = msg.get("role", "user")
#             contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})


#         # Then add latest user message
#         contents.append({"role": "user", "parts": [{"text": message}]})

#         try:
#             # Attempt to use the 'chat' method of Gemini SDK (if this is the correct method)
#             response = self.model.generate_content(
#                 generation_config=genai.types.GenerationConfig(
#                 temperature=0.8,
#                 max_output_tokens=500
#                 ),
#                 contents=contents,
                
#             )

#             # The returned object may have `.text` or `.candidates[0].content.text`
#             response_text = response.text if hasattr(response, "text") else response["candidates"][0]["content"]["text"]

#             return {
#                 "success": True,
#                 "is_emergency": False,
#                 "response": response_text
#             }
#         except Exception as e:
#             return {"success": False, "error": str(e)}
# # ------------------------------------------------------------
# # Initialize chatbot
# # ------------------------------------------------------------
# chatbot = SimpleMedicalChatbot(model_name=GEMINI_MODEL)

# # ------------------------------------------------------------
# # Routes
# # ------------------------------------------------------------
# @app.post("/api/chat")
# async def chat_endpoint(req: ChatRequest):
#     return chatbot.chat(req.message, req.conversation_history)

# @app.get("/health")
# async def health():
#     return {
#         "status": "healthy",
#         "service": "Simple Medical Chat API (Gemini)",
#         "model": GEMINI_MODEL,
#         "version": "1.1",
#         "timestamp": datetime.now().isoformat()
#     }

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app)






# =========================
genai.configure(api_key=GEMINI_API_KEY)


# =========================
# 🔹 SYSTEM PROMPT
# =========================
SYSTEM_PROMPT = """
You are a professional AI-powered medical assistant chatbot.  
Your role is to help users understand possible causes of their symptoms,  
suggest safe self-care measures, and guide them on when to seek professional medical attention.  
You are not a doctor and must never provide a definitive diagnosis or prescribe medication.

Always follow this response structure:

**Possible Causes:**  
List the most likely explanations for the user’s symptoms, based on general medical knowledge.  
Avoid using overly technical terms unless necessary. Keep tone simple and empathetic.  

**What You Can Do Now:**  
Provide practical, evidence-based self-care steps that are generally safe.  
Include guidance such as: rest, hydration, over-the-counter remedies (avoid brand names), and lifestyle adjustments.  
Always remind users to consult a healthcare provider before taking any new medication.  

**When to See a Doctor:**  
Clearly explain when the user should seek medical attention.  
Mention red flags and warning signs like symptom worsening, duration, severity, or new symptoms developing.  

---

### **Safety Rules:**
1. If the user mentions emergency symptoms like chest pain, shortness of breath, severe bleeding, stroke symptoms, 
loss of consciousness, or suicidal thoughts — IMMEDIATELY respond:  
“⚠️ Emergency symptoms detected! Please call emergency services or visit the nearest hospital right now.”  

2. Never make a direct diagnosis (e.g., “You have pneumonia”).  
Instead, use phrases like “It might be related to…” or “It could be due to…”  

3. Be empathetic, reassuring, and supportive in every response.  

4. Respect user privacy and never ask for personal or identifying information.  

5. Always end responses with:  
“I’m here to help you understand your symptoms better. Please contact a doctor if your condition worsens.”  

---

### **Additional Rules (as requested):**
6. If the user asks **irrelevant or non-medical questions** (e.g., about entertainment, politics, coding, etc.),  
politely reply:  
“I'm sorry, but I can only help with health-related questions. Could you please tell me what symptoms or health concerns you’d like to discuss?”  

7. If the user asks for **information about another person’s health**,  
respond:  
“For privacy and safety reasons, I can only provide general health information based on the details you share about yourself.”  

---


"""


# =========================
# 🔹 GEMINI CHAT
# =========================
def gemini_chat(messages):
    """Call Gemini with conversation history"""
    model = genai.GenerativeModel(GEMINI_MODEL)
    
    formatted_msgs = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        formatted_msgs.append({"role": role, "parts": [m["content"]]})
    
    response = model.generate_content(
        formatted_msgs,
        generation_config=genai.types.GenerationConfig(
            temperature=0.8,
            max_output_tokens=500
        ),
    )
    return response.text

 

def generate_answer(history):
 
    # Enhanced context message with clearer instructions
 
    # Build conversation sequence
    messages = [
        {"role": "user", "content": SYSTEM_PROMPT},
        {"role": "assistant", "content": "Understood! I'm Lume, ready to help you with Symptoms Checker."},] + history
 
    # Generate response
    return gemini_chat(messages)

def get_initial_greeting():
    """Generate personalized initial greeting"""
    return f"""How can I assist you today?"""



# =========================
# 🔹 CONVERSATION HANDLER
# =========================
def handle_conversation(user_input):

    # Initialize control flags
    if "awaiting_field" not in st.session_state:
        st.session_state.awaiting_field = None  # 'name'|'email'|'contact' or None
    if "awaiting_confirmation" not in st.session_state:
        st.session_state.awaiting_confirmation = False

    text = user_input.strip()


    # 2) If bot asked for a specific missing field and user replies
    if st.session_state.awaiting_field:
        field = st.session_state.awaiting_field
       

    # 5) Default RAG flow
    with st.spinner(""):
    
        try:
            answer = generate_answer(st.session_state.messages)
            return answer
        except Exception as e:
            print(f"Error: {e}")
            return "Hmm, I hit a small snag there. Mind rephrasing that?"
        




# =========================
# 🔹 STREAMLIT UI
# =========================
def main():
    st.set_page_config(
        page_title="Lume - Repu Media Intelligence",
        page_icon="🤖",
        layout="centered"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        .stApp {
            max-width: auto;
            margin: 0 auto;
        }
        .stChatMessage {
            padding: 1rem;
            border-radius: 0.5rem;
        }
        </style>
    """, unsafe_allow_html=True)

    session_id=str(uuid.uuid4())[:16]
   
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "conversation_ended" not in st.session_state:
        st.session_state.conversation_ended = False
    
    # =========================
    # 🔹 SIDEBAR FORM
    # =========================
    with st.sidebar:
        st.title("🤖 Lume AI Assistant")
        st.caption("Your friendly guide to Repu Media Intelligence")
        st.markdown("Please fill in your details to start chatting")
        
        with st.form("user_info_form"):
            name = st.text_input(
                "Name *",
                value=st.session_state.user_info.get("name", ""),
                placeholder="Enter your full name"
            )
            
            email = st.text_input(
                "Email *",
                value=st.session_state.user_info.get("email", ""),
                placeholder="lume@example.com"
            )
                        
            contact = st.text_input(
                "Contact Number (optional)",
                value=st.session_state.user_info.get("contact", ""),
                placeholder="03XXXXXXXXX or +923XXXXXXXXX"
            )
            
            st.markdown("*All fields are required")
            
            submitted = st.form_submit_button("Submit & Start Chat", type="primary", use_container_width=True)
            
            if submitted:
                errors = []
                
                # Validate name
                if not name or len(name.strip()) < 2:
                    errors.append("❌ Please enter a valid name")
                
                # Validate email
                if not email or not validate_email(email):
                    errors.append("❌ Please enter a valid email address")
                                
                # Validate contact
                if contact and not validate_contact(contact):
                    errors.append("❌ Please enter a valid Pakistani phone number (e.g., 03XXXXXXXXX)")
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    # Save user info
                    st.session_state.user_info = {
                        "session_id":session_id ,
                        "name": name.strip(),
                        "email": email.strip(),
                        "contact": contact.strip(),
                        "submitted": True
                    }
                    
                    print(st.session_state.user_info)

                    # Save to Google Sheets (uncomment when ready)
                    save_to_sheets(st.session_state.user_info)
                    
                    # Initialize chat with greeting
                    st.session_state.messages = [
                        {
                            "role": "assistant",
                            "content": f"Hello {name}! 👋\n I'm Lume, How can I assist you today?"
                        }
                    ]
                    
                    st.success("✅ Information saved! You can now start chatting.")
                    st.rerun()
        
        # Show current info if submitted
        if st.session_state.user_info.get("submitted"):
            
            if st.button("🔄 Reset & Start Over", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        
        
    # =========================
    # 🔹 MAIN CHAT AREA
    # =========================
    
   
    # Check if user has submitted form
    if not st.session_state.user_info.get("submitted"):
        st.info("👈 Please fill in your information in the sidebar to start chatting!")
        st.stop()
    
    # Display chat history
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    
    # Check if conversation has ended
    if st.session_state.conversation_ended:
        st.warning("💬 Conversation ended. Click the reset button in the sidebar to start a new chat!")
        st.stop()
    
    # User input
    user_input = st.chat_input("Type your message...")
    
    if user_input:
        # Show user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Generate response
        reply = handle_conversation(user_input)
        
        # Show assistant response
        st.session_state.messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)
        
        st.rerun()

if __name__ == "__main__":

    main()