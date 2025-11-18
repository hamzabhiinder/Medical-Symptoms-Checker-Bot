import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime

# ---------------------------
# CONFIGURATION
# ---------------------------
st.set_page_config(page_title="AI Medical Assistant", page_icon="💊", layout="wide")

# ------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------
load_dotenv()
GPT_API_KEY = os.getenv("OPENAI_API_KEY")
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS_JSON")
# Initialize OpenAI client
client = OpenAI(api_key=GPT_API_KEY)

# ---------------------------
# FIREBASE INITIALIZATION
# ---------------------------
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------------------
# HELPER FUNCTIONS
# ---------------------------

def get_user_medical_history_and_medicine_summary(uid: str):
    # 1. Get medical history
    user_ref = db.collection("users").document(uid)
    doc = user_ref.get()

    if not doc.exists:
        return {"error": "User not found"}

    data = doc.to_dict()

    summaries = []
    if "answers" in data:
        for item in data["answers"]:
            sum_ans = item.get("summarizedAnswer")
            if sum_ans:
                summaries.append(sum_ans)

    # 2. Get medicine information
    meds_ref = db.collection("medicines")
    meds_query = meds_ref.where("userId", "==", uid).stream()

    medicines = []
    for med_doc in meds_query:
        med = med_doc.to_dict()
        medicines.append({
            "name": med.get("name"),
            "dosage": med.get("dosage"),
            "frequency": med.get("frequency")
        })

    # 3. Final response
    return {
        "user_id": uid,
        "medical_history": summaries,
        "medicines": medicines
    }

def create_embedding(text):
    """Create embeddings using OpenAI API"""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        st.error(f"Error creating embedding: {e}")
        return None

def calculate_age(dob_string):
    """Calculate age from date of birth string"""
    try:
        # Parse DOB from medical history (format: "Patient's date of birth is 07/06/1946.")
        if "date of birth" in dob_string.lower():
            date_str = dob_string.split("is ")[-1].replace(".", "").strip()
            dob = datetime.strptime(date_str, "%m/%d/%Y")
            today = datetime.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age
    except:
        pass
    return None

def extract_key_medical_info(medical_data):
    """Extract key information from medical history"""
    info = {
        'age': None,
        'gender': None,
        'conditions': [],
        'surgeries': [],
        'allergies': [],
        'lifestyle': []
    }
    
    if not medical_data or 'medical_history' not in medical_data:
        return info
    
    for item in medical_data['medical_history']:
        item_lower = item.lower()
        
        # Age/DOB
        if 'date of birth' in item_lower:
            info['age'] = calculate_age(item)
        
        # Gender
        if 'identifies as' in item_lower:
            if 'male' in item_lower:
                info['gender'] = 'Male'
            elif 'female' in item_lower:
                info['gender'] = 'Female'
        
        # Medical Conditions
        if any(cond in item_lower for cond in ['diabetes', 'blood pressure', 'heart disease', 'cancer', 'carcinoma']):
            info['conditions'].append(item)
        
        # Surgeries
        if 'surgery' in item_lower or 'laser' in item_lower or 'hospitalized' in item_lower:
            info['surgeries'].append(item)
        
        # Allergies
        if 'allerg' in item_lower and 'does not have' not in item_lower:
            info['allergies'].append(item)
        
        # Lifestyle
        if any(word in item_lower for word in ['smoke', 'alcohol', 'drug', 'weight change']):
            info['lifestyle'].append(item)
    
    return info

def prepare_medical_context(medical_data):
    """Convert medical data into a structured, readable context"""
    if not medical_data:
        return ""
    
    context = "**PATIENT'S MEDICAL PROFILE:**\n\n"
    
    # Extract structured info
    info = extract_key_medical_info(medical_data)
    
    # Basic Demographics
    context += "**Demographics:**\n"
    if info['age']:
        context += f"- Age: {info['age']} years old\n"
    if info['gender']:
        context += f"- Gender: {info['gender']}\n"
    context += "\n"
    
    # Current Medical Conditions
    if info['conditions']:
        context += "**Existing Medical Conditions:**\n"
        for condition in info['conditions']:
            context += f"- {condition}\n"
        context += "\n"
    
    # Past Surgeries/Hospitalizations
    if info['surgeries']:
        context += "**Past Surgeries & Hospitalizations:**\n"
        for surgery in info['surgeries']:
            context += f"- {surgery}\n"
        context += "\n"
    
    # Current Medications
    if 'medicines' in medical_data and medical_data['medicines']:
        context += "**Current Medications:**\n"
        for med in medical_data['medicines']:
            frequency_text = f"{med['frequency']}x per day" if med['frequency'] != '1' else "once daily"
            context += f"- {med['name']} ({med['dosage']}) - {frequency_text}\n"
        context += "\n"
    
    # Allergies
    if info['allergies']:
        context += "**Known Allergies:**\n"
        for allergy in info['allergies']:
            context += f"- {allergy}\n"
        context += "\n"
    else:
        context += "**Allergies:** No known allergies\n\n"
    
    # Lifestyle Factors
    if info['lifestyle']:
        context += "**Lifestyle Factors:**\n"
        for factor in info['lifestyle']:
            context += f"- {factor}\n"
        context += "\n"
    
    # Family History
    family_history = [item for item in medical_data.get('medical_history', []) 
                     if 'family history' in item.lower() or 'father' in item.lower() or 'mother' in item.lower()]
    if family_history:
        context += "**Family Medical History:**\n"
        for item in family_history:
            context += f"- {item}\n"
    
    return context

def get_relevant_context(query, medical_data):
    """Use embeddings to find relevant medical context based on current query"""
    if not medical_data:
        return ""
    
    # Create query embedding
    query_embedding = create_embedding(query)
    if not query_embedding:
        return prepare_medical_context(medical_data)
    
    chunks = []

    if 'medical_history' in medical_data:
        for item in medical_data['medical_history']:
            embedding = create_embedding(item)
            if embedding:
                chunks.append({
                    'text': item,
                    'type': 'history',
                    'embedding': embedding
                })
    
    # Add medicine information
    if 'medicines' in medical_data:
        for med in medical_data['medicines']:
            med_text = f"Taking {med['name']} ({med['dosage']}) {med['frequency']} times daily"
            embedding = create_embedding(med_text)
            if embedding:
                chunks.append({
                    'text': med_text,
                    'type': 'medicine',
                    'embedding': embedding
                })
    
    # Calculate similarity scores
    similarities = []
    for chunk in chunks:
        similarity = cosine_similarity(
            [query_embedding],
            [chunk['embedding']]
        )[0][0]
        similarities.append({
            'text': chunk['text'],
            'type': chunk['type'],
            'score': similarity
        })
    
    # Sort by relevance
    similarities.sort(key=lambda x: x['score'], reverse=True)
    
    # Build context with most relevant information
    context = "**Most Relevant Patient Information for Current Query:**\n\n"
    
    relevant_found = False
    for chunk in similarities[:7]:  # Top 7 most relevant
        if chunk['score'] > 0.25:  # Relevance threshold
            relevant_found = True
            emoji = "💊" if chunk['type'] == 'medicine' else "📋"
            context += f"{emoji} {chunk['text']}\n"
    
    if not relevant_found:
        # If no highly relevant info, return full context
        return prepare_medical_context(medical_data)
    
    return context

# ---------------------------
# SYSTEM PROMPT
# ---------------------------
SYSTEM_PROMPT_TEMPLATE = """
You are a professional AI-powered medical assistant chatbot specialized in personalized healthcare guidance.
Your role is to help users understand possible causes of their symptoms, suggest safe self-care measures, 
and guide them on when to seek professional medical attention.

You are not a doctor and must never provide a definitive diagnosis or prescribe medication.

{medical_context}

**CRITICAL INSTRUCTIONS FOR PERSONALIZATION:**

1. **Always Consider Patient's Medical Profile:**
   - Age and gender-specific health considerations
   - Existing medical conditions (diabetes, hypertension, heart disease, cancer history, etc.)
   - Current medications and potential interactions
   - Past surgeries and hospitalizations
   - Known allergies
   - Lifestyle factors (smoking, alcohol use, weight changes)
   - Family medical history

2. **Risk Assessment:**
   - Patients with chronic conditions (diabetes, heart disease) need more cautious guidance
   - Elderly patients may need to see doctors sooner for the same symptoms
   - Consider medication interactions when suggesting OTC remedies
   - Pay special attention to cancer survivors and those with compromised immunity

3. **Medication Awareness:**
   - ALWAYS check if suggested OTC remedies might interact with current medications
   - Be extra cautious with patients on blood thinners (Pradaxa), diabetes medications (Metformin, Glipizide), heart medications (Entresto)
   - Warn about potential interactions explicitly

---

**YOUR WORKFLOW:**

**Step 1: Intelligent Information Gathering**

When a user describes symptoms, ask ONE relevant follow-up question at a time.
Consider their medical history when formulating questions.

Key questions to consider:
- Duration and severity of symptoms
- Location and characteristics
- Associated symptoms
- Triggers or relieving factors
- Relationship to existing conditions or medications
- Any recent changes in medications or lifestyle

For patients with chronic conditions, ask:
- "Have you noticed any changes in your [diabetes/blood pressure/etc.] recently?"
- "Have you been taking your medications as prescribed?"
- "Is this symptom different from what you usually experience?"

Continue asking questions until you have sufficient context (typically 3-5 exchanges).

**Step 2: Provide Comprehensive, Personalized Response**

Once you have enough information, provide:

**Possible Causes:**
- List likely explanations based on symptoms AND medical history
- Prioritize causes relevant to their existing conditions
- Use empathetic, simple language
- Consider age and gender-specific factors

**What You Can Do Now:**
- Provide safe, practical self-care steps
- Suggest OTC remedies ONLY after checking for medication interactions
- If patient is on multiple medications, be more conservative
- Include lifestyle modifications relevant to their conditions
- For chronic condition patients, emphasize importance of monitoring
- ALWAYS state: "Before taking any new medication, even over-the-counter ones, please consult your healthcare provider or pharmacist, especially given your current medications."

**When to See a Doctor:**
- Be MORE CAUTIOUS with:
  * Elderly patients (age 65+)
  * Patients with diabetes, heart disease, or cancer history
  * Patients on blood thinners or multiple medications
  * Immunocompromised patients
- List specific red flags relevant to their condition
- Mention when to seek urgent vs routine care
- Consider that certain symptoms are more serious given their medical history

Always end with:
"Given your medical history, I recommend staying in close contact with your healthcare provider about these symptoms. Please don't hesitate to reach out to them if you're concerned."

---

**SAFETY RULES:**

1. **EMERGENCY OVERRIDE**: 
   For emergency symptoms (chest pain, difficulty breathing, severe bleeding, stroke symptoms, loss of consciousness, suicidal thoughts):
   "EMERGENCY! Given your medical history of [mention relevant conditions], this is especially serious. Please call emergency services or go to the nearest hospital IMMEDIATELY."

2. Never diagnose directly. Use phrases like "This could be related to..." or "It might be caused by..."

3. Be empathetic, warm, and supportive. Show genuine care.

4. Never ask for additional personal identifying information beyond what's already in their profile.

5. For non-medical questions:
   "I'm sorry, but I can only help with health-related questions. What symptoms or health concerns would you like to discuss?"

6. For questions about others:
   "For privacy and safety reasons, I can only provide information based on symptoms you're experiencing yourself."

7. Ask ONE question at a time. Be conversational and natural.

8. **MEDICATION INTERACTION PRIORITY:**
   - Before suggesting ANY remedy, mentally check their medication list
   - Common interactions to watch for:
     * NSAIDs (ibuprofen) with blood thinners, heart medications
     * Decongestants with blood pressure medications
     * Antacids with diabetes medications
     * Certain supplements with heart medications
   - When in doubt, recommend pharmacist consultation

9. **Chronic Condition Awareness:**
   - Symptoms that are minor for healthy people may be serious for those with chronic conditions
   - Recommend earlier medical consultation for high-risk patients
   - Emphasize importance of diabetes control, blood pressure monitoring, etc.

**Remember: Your goal is to provide personalized, safe, and actionable guidance that considers the complete patient profile.**
"""

# ---------------------------
# STREAMLIT UI
# ---------------------------
st.title("💊 AI Medical Assistant")
st.markdown("### Your Personalized Health Companion")

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 24px;
        font-weight: bold;
        color: #2c3e50;
    }
    .info-box {
        background-color: #f0f8ff;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #3498db;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar for user authentication and medical profile
with st.sidebar:
    st.header("👤 Patient Profile")
    
    # User ID input
    if 'user_id' not in st.session_state:
        st.info("Please enter your User ID to begin")
        user_id = st.text_input("User ID:", key="user_id_input", placeholder="Enter your user ID")
        
        if st.button("Login", type="primary"):
            if user_id:
                with st.spinner("Loading your medical profile..."):
                    medical_data = get_user_medical_history_and_medicine_summary(user_id)
                    if medical_data:
                        st.session_state.user_id = user_id
                        st.session_state.medical_data = medical_data
                        st.success("✅ Profile loaded successfully!")
                        st.rerun()
                    else:
                        st.error("User ID not found. Please check and try again.")
            else:
                st.warning("Please enter a valid User ID")
    else:
        st.success(f"✅ Logged in")
        st.markdown(f"**User ID:** `{st.session_state.user_id}`")
        
        if st.button("Logout", type="secondary"):
            # Clear session
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        st.markdown("---")
        
        # Display medical profile summary
        if 'medical_data' in st.session_state and st.session_state.medical_data:
            info = extract_key_medical_info(st.session_state.medical_data)
            
            # Demographics
            st.markdown("### 📊 Demographics")
            if info['age']:
                st.write(f"**Age:** {info['age']} years")
            if info['gender']:
                st.write(f"**Gender:** {info['gender']}")
            
            # Conditions
            if info['conditions']:
                st.markdown("### 🏥 Medical Conditions")
                with st.expander("View Conditions"):
                    for condition in info['conditions'][:5]:
                        st.write(f"• {condition}")
            
            # Medications
            if 'medicines' in st.session_state.medical_data:
                st.markdown(f"### 💊 Medications ({len(st.session_state.medical_data['medicines'])})")
                with st.expander("View Medications"):
                    for med in st.session_state.medical_data['medicines']:
                        st.write(f"• **{med['name']}** - {med['dosage']}")
            
            # Allergies
            if info['allergies']:
                st.markdown("### ⚠️ Allergies")
                with st.expander("View Allergies"):
                    for allergy in info['allergies']:
                        st.write(f"• {allergy}")

# Main chat interface
if 'user_id' not in st.session_state:
    st.info("👈 Please login with your User ID in the sidebar to start chatting")
    st.markdown("""
    ### How This Works:
    1. **Login** with your user ID
    2. **Describe** your symptoms
    3. **Answer** a few follow-up questions
    4. **Receive** personalized health guidance based on your medical history
    
    ⚕️ Remember: This is not a substitute for professional medical advice.
    """)


else:
    # Initialize chat history
    if "messages" not in st.session_state:
        medical_context = prepare_medical_context(st.session_state.medical_data)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(medical_context=medical_context)
        st.session_state.messages = [
            {"role": "system", "content": system_prompt}
        ]
        st.session_state.question_count = 0
    
    # Display chat messages
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Chat input
    if user_input := st.chat_input("💬 Describe your symptoms or ask a health question..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.question_count += 1
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Generate assistant response
        with st.chat_message("assistant"):
            with st.spinner("🔍 Analyzing your symptoms with your medical history..."):
                # Get relevant context using RAG
                relevant_context = ""
                if 'medical_data' in st.session_state and st.session_state.medical_data:
                    relevant_context = get_relevant_context(user_input, st.session_state.medical_data)
                
                # Prepare messages with context
                messages_for_api = st.session_state.messages.copy()
                
                # Add relevant context as a system message before the user's query
                if relevant_context and st.session_state.question_count >= 2:
                    # Only add context after first exchange to keep conversation natural
                    context_message = {
                        "role": "system",
                        "content": f"\n{relevant_context}\n\nUse this information to provide personalized guidance for the user's current query."
                    }
                    messages_for_api.insert(-1, context_message)
                
                # Call OpenAI API
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages_for_api,
                        temperature=0.7,
                        max_tokens=1000
                    )
                    
                    reply = response.choices[0].message.content
                    st.markdown(reply)
                    
                    # Save assistant message
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                
                except Exception as e:
                    st.error(f"Error generating response: {e}")
                    st.warning("Please try again or rephrase your question.")
    
    # Helper buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("🔄 Start New Conversation"):
            # Keep system message but clear chat history
            medical_context = prepare_medical_context(st.session_state.medical_data)
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(medical_context=medical_context)
            st.session_state.messages = [
                {"role": "system", "content": system_prompt}
            ]
            st.session_state.question_count = 0
            st.rerun()