import streamlit as st
from openai import OpenAI
import os
from datetime import datetime
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# ---------------------------
# CONFIGURATION
# ---------------------------
st.set_page_config(page_title="AI Medical Assistant", page_icon="💊", layout="wide")

load_dotenv()

# Initialize Firebase (only once)
if not firebase_admin._apps:
    cred = credentials.Certificate("health-app-7a8b0-firebase-adminsdk-fbsvc-9d28c0ae3f.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------
# FIREBASE FUNCTIONS
# ---------------------------
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

# ---------------------------
# SYSTEM PROMPT
# ---------------------------
SYSTEM_PROMPT = """
You are a professional AI medical assistant for SYMPTOM CHECKING ONLY. Your job is to help patients understand their symptoms and provide health guidance.

{patient_context}

**STRICT SCOPE - ONLY ANSWER:**
- Health symptoms and medical concerns
- Medication questions related to symptoms
- When to see a doctor
- Self-care and home remedies for symptoms
- General health and wellness advice

**DO NOT ANSWER:**
- Doctor recommendations or names
- Hospital/clinic locations or contact information  
- Insurance questions
- Appointment scheduling
- Non-medical topics (weather, sports, general chat, etc.)
- Personal opinions on non-health matters

**If asked something outside your scope, respond:**
"I'm a symptom checker assistant and can only help with health symptoms and medical guidance. For [their question], please contact your healthcare provider directly or check their website/customer service."

---

**YOUR APPROACH:**

1. **Step 1: Information Gathering**
    - **CRITICAL: Ask ONLY ONE question per response - never ask multiple questions**
    - Ask the most important follow-up question based on symptoms and medical history
    - Continue for 3-5 exchanges until you have sufficient context
    - Questions should be specific: duration, severity, other symptoms, triggers
    - Example: "How long did the pain last?" NOT "How long did it last? Was it sharp or dull?"
    
2. **Step 2: Provide Guidance**:
   
   **Possible Causes:**
   - List 3-5 likely causes based on symptoms and medical history
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

---

**SAFETY RULES:**

⚠️ **EMERGENCY SYMPTOMS** - If patient mentions ANY of these:
- Chest pain or pressure
- Difficulty breathing or shortness of breath
- Severe bleeding that won't stop
- Stroke signs (face drooping, arm weakness, speech difficulty)
- Severe head injury or sudden severe headache
- Suicidal thoughts or severe mental health crisis
- Loss of consciousness
- Severe allergic reaction

→ **Immediately respond:** "⚠️ This sounds like an EMERGENCY! Please call 911 or go to the nearest emergency room RIGHT NOW. Do not wait!"

**MEDICATION SAFETY:**
- Always remind patients to check with their doctor/pharmacist before taking new medications
- Mention drug interactions risk if patient has chronic conditions
- Never suggest specific dosages
- For patients with diabetes, kidney issues, or heart conditions - be extra cautious about medication suggestions
- **IMPORTANT:** Always consider the patient's current medications when suggesting over-the-counter remedies to avoid dangerous interactions

**COMMUNICATION STYLE:**
- Always use patient's first name
- Be empathetic and supportive
- Use simple language, avoid medical jargon
- Be warm but professional
- Validate their concerns
- **NEVER use bullet points or lists when asking questions**
- **Ask ONLY ONE question at a time, then wait for the patient's answer**
- Keep questions conversational and natural

"""

# ---------------------------
# STREAMLIT UI
# ---------------------------
st.title("💊 Symptom Checker")

# Sidebar - User ID Input and Patient Profile
with st.sidebar:
    st.header("🔐 Patient Login")
    
    # User ID input
    user_id_input = st.text_input(
        "Enter Patient ID:",
        value=st.session_state.get("current_user_id", ""),
        placeholder="pGSZNP7t8odnxmOIpRbDcuthbbM2"
    )
    
    if st.button("Load Patient Data") or (user_id_input and "current_user_id" not in st.session_state):
        if user_id_input:
            with st.spinner("Loading patient data..."):
                patient_data = get_user_medical_history_and_medicine_summary(user_id_input)
                
                if "error" not in patient_data:
                    st.session_state.current_user_id = user_id_input
                    st.session_state.patient_data = patient_data
                    # Clear chat history when new patient is loaded
                    if "messages" in st.session_state:
                        del st.session_state.messages
                    st.success(f"✅ Loaded data for {patient_data['user_name']}")
                    st.rerun()
                else:
                    st.error(patient_data["error"])
        else:
            st.warning("Please enter a Patient ID")
    
    # Display patient profile if loaded
    if "patient_data" in st.session_state:
        st.markdown("---")
        st.header("👤 Patient Profile")
        st.markdown(f"**Name:** {st.session_state.patient_data['user_name']}")
        st.markdown(f"**ID:** {st.session_state.current_user_id}")
        
        # Show medication count
        med_count = len(st.session_state.patient_data.get('medicines', []))
        st.markdown(f"**Medications:** {med_count} active")
        
        # Show medical history count
        history_count = len(st.session_state.patient_data.get('medical_history', []))
        st.markdown(f"**Medical History:** {history_count} entries")
    
    st.markdown("---")
    if st.button("🔄 New Conversation"):
        if "messages" in st.session_state:
            del st.session_state.messages
        st.rerun()
    
    if st.button("🚪 Logout"):
        # Clear all session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Main chat area
if "patient_data" not in st.session_state:
    st.info("👈 Please enter a Patient ID in the sidebar to begin")
    st.stop()

# Initialize chat with patient context
if "messages" not in st.session_state:
    patient_context = prepare_patient_context(st.session_state.patient_data)
    system_prompt = SYSTEM_PROMPT.format(
        patient_context=patient_context,
        patient_name=st.session_state.patient_data['user_name'].split()[0]
    )
    st.session_state.messages = [
        {"role": "system", "content": system_prompt}
    ]

# Display chat history
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Chat input
if user_input := st.chat_input("💬 Describe your symptoms..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=st.session_state.messages,
                    temperature=0.7,
                    max_tokens=600
                )
                
                reply = response.choices[0].message.content
                st.markdown(reply)
                
                # Save assistant message
                st.session_state.messages.append({"role": "assistant", "content": reply})
            
            except Exception as e:
                st.error(f"Error: {e}")