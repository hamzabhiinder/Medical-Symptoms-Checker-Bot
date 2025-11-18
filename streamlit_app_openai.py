import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from collections import Counter
import re

# ---------------------------
# CONFIGURATION
# ---------------------------
st.set_page_config(page_title="AI Medical Assistant", page_icon="💊", layout="wide")

# Load environment variables
load_dotenv()
GPT_API_KEY = os.getenv("OPENAI_API_KEY")


# Initialize OpenAI client
client = OpenAI(api_key=GPT_API_KEY)

# ---------------------------
# FIREBASE INITIALIZATION
# ---------------------------
if not firebase_admin._apps:
    cred = credentials.Certificate('C:\\Users\\CurveSystem 52\\Desktop\\IMRAN_WORK\\credentials\\health-app-7a8b0-firebase-adminsdk-fbsvc-9d28c0ae3f.json')
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------------------
# CACHE FOR PERFORMANCE
# ---------------------------
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_user_medical_history_and_medicine_summary(uid: str):
    """Cached function to get user medical data"""
    try:
        # 1. Get medical history
        user_ref = db.collection("users").document(uid)
        doc = user_ref.get()

        if not doc.exists:
            return None

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
                "name": med.get("name", ""),
                "dosage": med.get("dosage", ""),
                "frequency": med.get("frequency", "1")
            })

        # 3. Final response
        return {
            "user_id": uid,
            "medical_history": summaries,
            "medicines": medicines
        }
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

# ---------------------------
# FAST KEYWORD-BASED MATCHING
# ---------------------------

def extract_keywords(text):
    """Extract important medical keywords from text"""
    # Convert to lowercase
    text = text.lower()
    
    # Remove punctuation but keep hyphens in medical terms
    text = re.sub(r'[^\w\s-]', ' ', text)
    
    # Medical-specific keywords to prioritize
    high_priority_keywords = [
        'pain', 'fever', 'diabetes', 'blood pressure', 'heart', 'cancer',
        'allergy', 'medication', 'surgery', 'hospitalized', 'symptom',
        'headache', 'nausea', 'vomit', 'dizzy', 'chest', 'breathing',
        'cough', 'throat', 'stomach', 'back', 'joint', 'muscle',
        'rash', 'bleeding', 'swelling', 'infection'
    ]
    
    # Split into words
    words = text.split()
    
    # Filter meaningful words (length > 3)
    keywords = [w for w in words if len(w) > 3]
    
    # Boost high-priority medical terms
    boosted_keywords = []
    for keyword in keywords:
        if any(priority in keyword for priority in high_priority_keywords):
            boosted_keywords.extend([keyword] * 3)  # Triple weight
        else:
            boosted_keywords.append(keyword)
    
    return boosted_keywords

def calculate_relevance_score(query_keywords, text):
    """Fast keyword matching score"""
    text_lower = text.lower()
    
    # Count keyword matches
    matches = sum(1 for keyword in query_keywords if keyword in text_lower)
    
    # Normalize by query length
    if len(query_keywords) > 0:
        score = matches / len(query_keywords)
    else:
        score = 0
    
    return score

def get_relevant_context_fast(query, medical_data):
    """Fast context retrieval using keyword matching"""
    if not medical_data:
        return ""
    
    # Extract keywords from query
    query_keywords = extract_keywords(query)
    
    # Prepare chunks with relevance scores
    scored_chunks = []
    
    # Score medical history items
    if 'medical_history' in medical_data:
        for item in medical_data['medical_history']:
            score = calculate_relevance_score(query_keywords, item)
            scored_chunks.append({
                'text': item,
                'type': 'history',
                'score': score
            })
    
    # Score medicine information
    if 'medicines' in medical_data:
        for med in medical_data['medicines']:
            med_text = f"Taking {med['name']} ({med['dosage']}) {med['frequency']} times daily"
            score = calculate_relevance_score(query_keywords, med_text)
            scored_chunks.append({
                'text': med_text,
                'type': 'medicine',
                'score': score
            })
    
    # Sort by relevance
    scored_chunks.sort(key=lambda x: x['score'], reverse=True)
    
    # Build context with top relevant items
    context = "**Most Relevant Patient Information:**\n\n"
    
    relevant_items = [chunk for chunk in scored_chunks[:8] if chunk['score'] > 0.2]
    
    if relevant_items:
        for chunk in relevant_items:
            emoji = "💊" if chunk['type'] == 'medicine' else "📋"
            context += f"{emoji} {chunk['text']}\n"
        return context
    else:
        # If no relevant match, return compact summary
        return prepare_compact_context(medical_data)

def prepare_compact_context(medical_data):
    """Prepare a compact medical context summary"""
    if not medical_data:
        return ""
    
    context = "**Patient Profile Summary:**\n\n"
    
    # Get key info
    info = extract_key_medical_info(medical_data)
    
    # Demographics (1 line)
    if info['age'] or info['gender']:
        demo = []
        if info['age']:
            demo.append(f"{info['age']}yo")
        if info['gender']:
            demo.append(info['gender'])
        context += f"👤 {' | '.join(demo)}\n\n"
    
    # Conditions (compact)
    if info['conditions']:
        conditions_list = ', '.join([c.split('Patient')[-1].strip() for c in info['conditions'][:3]])
        context += f"🏥 Conditions: {conditions_list}\n\n"
    
    # Medicines (compact)
    if 'medicines' in medical_data and medical_data['medicines']:
        med_count = len(medical_data['medicines'])
        top_meds = [m['name'] for m in medical_data['medicines'][:3]]
        context += f"💊 Medications ({med_count}): {', '.join(top_meds)}"
        if med_count > 3:
            context += f" +{med_count-3} more"
        context += "\n\n"
    
    # Allergies
    if info['allergies']:
        context += f"⚠️ Allergies: Yes\n\n"
    
    return context

# ---------------------------
# HELPER FUNCTIONS (Optimized)
# ---------------------------

def calculate_age(dob_string):
    """Calculate age from date of birth string"""
    try:
        if "date of birth" in dob_string.lower():
            date_str = dob_string.split("is ")[-1].replace(".", "").strip()
            dob = datetime.strptime(date_str, "%m/%d/%Y")
            today = datetime.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age
    except:
        pass
    return None

@st.cache_data
def extract_key_medical_info(medical_data):
    """Cached extraction of key medical information"""
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
        if 'date of birth' in item_lower and not info['age']:
            info['age'] = calculate_age(item)
        
        # Gender
        if 'identifies as' in item_lower and not info['gender']:
            if 'male' in item_lower and 'female' not in item_lower:
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
    """Convert medical data into structured context"""
    if not medical_data:
        return ""
    
    context = "**PATIENT'S MEDICAL PROFILE:**\n\n"
    
    info = extract_key_medical_info(medical_data)
    
    # Demographics
    context += "**Demographics:**\n"
    if info['age']:
        context += f"- Age: {info['age']} years old\n"
    if info['gender']:
        context += f"- Gender: {info['gender']}\n"
    context += "\n"
    
    # Conditions
    if info['conditions']:
        context += "**Existing Medical Conditions:**\n"
        for condition in info['conditions'][:5]:
            context += f"- {condition}\n"
        context += "\n"
    
    # Surgeries
    if info['surgeries']:
        context += "**Past Surgeries & Hospitalizations:**\n"
        for surgery in info['surgeries'][:3]:
            context += f"- {surgery}\n"
        context += "\n"
    
    # Medications
    if 'medicines' in medical_data and medical_data['medicines']:
        context += "**Current Medications:**\n"
        for med in medical_data['medicines'][:10]:
            frequency_text = f"{med['frequency']}x/day" if med['frequency'] != '1' else "once daily"
            context += f"- {med['name']} ({med['dosage']}) - {frequency_text}\n"
        if len(medical_data['medicines']) > 10:
            context += f"- ... and {len(medical_data['medicines']) - 10} more\n"
        context += "\n"
    
    # Allergies
    if info['allergies']:
        context += "**Known Allergies:**\n"
        for allergy in info['allergies'][:3]:
            context += f"- {allergy}\n"
        context += "\n"
    else:
        context += "**Allergies:** No known allergies\n\n"
    
    # Lifestyle
    if info['lifestyle']:
        context += "**Lifestyle Factors:**\n"
        for factor in info['lifestyle'][:3]:
            context += f"- {factor}\n"
        context += "\n"
    
    return context

# ---------------------------
# SYSTEM PROMPT (Optimized)
# ---------------------------
SYSTEM_PROMPT_TEMPLATE = """
You are a professional AI-powered medical assistant chatbot specialized in personalized healthcare guidance.

{medical_context}

**YOUR WORKFLOW:**

**Step 1: Information Gathering**
Ask ONE relevant follow-up question at a time based on symptoms and medical history.
Continue for 3-5 exchanges until you have sufficient context.

**Step 2: Provide Response**
Once sufficient information is gathered, provide:

**Possible Causes:**
- List likely explanations based on symptoms AND medical history
- Use simple, empathetic language

**What You Can Do Now:**
- Safe, practical self-care steps
- OTC remedies (check for medication interactions first)
- Lifestyle modifications
- Always remind: "Consult your healthcare provider before taking new medications, especially given your current medications."

**When to See a Doctor:**
- Be more cautious with elderly, chronic condition patients, or those on multiple medications
- List specific red flags
- Mention urgent vs routine care

Always end with:
"Given your medical history, stay in close contact with your healthcare provider. Don't hesitate to reach out if concerned."

**SAFETY RULES:**

1. **EMERGENCY**: For chest pain, breathing difficulty, severe bleeding, stroke symptoms, loss of consciousness, suicidal thoughts:
   "⚠️ EMERGENCY! Given your medical history, this is serious. Call emergency services IMMEDIATELY."

2. Never diagnose directly. Use "might be related to..." or "could be caused by..."

3. Be empathetic and supportive.

4. For non-medical questions: "I can only help with health questions. What symptoms would you like to discuss?"

5. Ask ONE question at a time.

6. Check medication interactions before suggesting remedies.

7. Recommend earlier doctor consultation for high-risk patients.
"""

# ---------------------------
# STREAMLIT UI
# ---------------------------
st.title("💊 AI Medical Assistant")
st.markdown("### Your Personalized Health Companion")

# Custom CSS
st.markdown("""
<style>
    .stTextInput>div>div>input {
        background-color: #f0f2f6;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("👤 Patient Profile")
    
    if 'user_id' not in st.session_state:
        st.info("Please enter your User ID to begin")
        user_id = st.text_input("User ID:", key="user_id_input", placeholder="Enter your user ID")
        
        if st.button("Login", type="primary"):
            if user_id:
                with st.spinner("Loading profile..."):
                    medical_data = get_user_medical_history_and_medicine_summary(user_id)
                    if medical_data and "error" not in medical_data:
                        st.session_state.user_id = user_id
                        st.session_state.medical_data = medical_data
                        st.success("✅ Profile loaded!")
                        st.rerun()
                    else:
                        st.error("User ID not found.")
            else:
                st.warning("Please enter a User ID")
    else:
        st.success(f"✅ Logged in")
        st.markdown(f"**ID:** `{st.session_state.user_id}`")
        
        if st.button("Logout", type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        st.markdown("---")
        
        # Display medical profile
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
                st.markdown("### 🏥 Conditions")
                with st.expander("View Details"):
                    for condition in info['conditions'][:5]:
                        st.write(f"• {condition}")
            
            # Medications
            if 'medicines' in st.session_state.medical_data and st.session_state.medical_data['medicines']:
                med_count = len(st.session_state.medical_data['medicines'])
                st.markdown(f"### 💊 Medications ({med_count})")
                with st.expander("View List"):
                    for med in st.session_state.medical_data['medicines'][:10]:
                        st.write(f"• **{med['name']}** - {med['dosage']}")
                    if med_count > 10:
                        st.write(f"• ... and {med_count - 10} more")
            
            # Allergies
            if info['allergies']:
                st.markdown("### ⚠️ Allergies")
                with st.expander("View Details"):
                    for allergy in info['allergies']:
                        st.write(f"• {allergy}")

# Main chat interface
if 'user_id' not in st.session_state:
    st.info("👈 Please login with your User ID in the sidebar")
    st.markdown("""
    ### How This Works:
    1. **Login** with your user ID
    2. **Describe** your symptoms
    3. **Answer** follow-up questions
    4. **Receive** personalized guidance
    
    ⚕️ Not a substitute for professional medical advice.
    """)
else:
    # Initialize chat
    if "messages" not in st.session_state:
        medical_context = prepare_medical_context(st.session_state.medical_data)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(medical_context=medical_context)
        st.session_state.messages = [
            {"role": "system", "content": system_prompt}
        ]
        st.session_state.question_count = 0
    
    # Display chat history
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # Chat input
    if user_input := st.chat_input("💬 Describe your symptoms..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.question_count += 1
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                # Get relevant context (FAST - no embeddings)
                relevant_context = ""
                if st.session_state.question_count >= 2:
                    relevant_context = get_relevant_context_fast(
                        user_input, 
                        st.session_state.medical_data
                    )
                
                # Prepare messages
                messages_for_api = st.session_state.messages.copy()
                
                # Add context
                if relevant_context:
                    context_message = {
                        "role": "system",
                        "content": f"\n{relevant_context}\n\nProvide personalized guidance based on this information."
                    }
                    messages_for_api.insert(-1, context_message)
                
                # API call
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages_for_api,
                        temperature=0.7,
                        max_tokens=800,
                        stream=False  # Set to True for streaming if needed
                    )
                    
                    reply = response.choices[0].message.content
                    st.markdown(reply)
                    
                    # Save message
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.warning("Please try again.")
    
    # Helper buttons
    if st.button("🔄 New Conversation"):
        medical_context = prepare_medical_context(st.session_state.medical_data)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(medical_context=medical_context)
        st.session_state.messages = [
            {"role": "system", "content": system_prompt}
        ]
        st.session_state.question_count = 0
        st.rerun()