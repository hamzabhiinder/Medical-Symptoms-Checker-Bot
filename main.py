import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
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
# DATA FETCHING WITH CACHE
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
        name = data.get("displayName", "")

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
            "user_name": name,
            "medical_history": summaries,
            "medicines": medicines,
        }
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

# ---------------------------
# SAVE CHAT MESSAGE TO FIREBASE
# ---------------------------
def save_chat_message(uid: str, message: str, is_user: bool):
    """Save chat message to Firebase chatHistory collection"""
    try:
        chat_ref = db.collection("chatHistory")
        chat_ref.add({
            "userId": uid,
            "message": message,
            "isUser": is_user,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
    except Exception as e:
        st.error(f"Error saving message: {e}")

# ---------------------------
# KEYWORD EXTRACTION & MATCHING
# ---------------------------
def extract_keywords(text):
    """Extract important medical keywords from text"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', ' ', text)
    
    high_priority_keywords = [
        'pain', 'fever', 'diabetes', 'blood pressure', 'heart', 'cancer',
        'allergy', 'medication', 'surgery', 'hospitalized', 'symptom',
        'headache', 'nausea', 'vomit', 'dizzy', 'chest', 'breathing',
        'cough', 'throat', 'stomach', 'back', 'joint', 'muscle',
        'rash', 'bleeding', 'swelling', 'infection', 'runny nose',
        'cold', 'flu', 'fatigue', 'weakness'
    ]
    
    words = text.split()
    keywords = [w for w in words if len(w) > 3]
    
    boosted_keywords = []
    for keyword in keywords:
        if any(priority in keyword for priority in high_priority_keywords):
            boosted_keywords.extend([keyword] * 3)
        else:
            boosted_keywords.append(keyword)
    
    return boosted_keywords

def calculate_relevance_score(query_keywords, text):
    """Fast keyword matching score"""
    text_lower = text.lower()
    matches = sum(1 for keyword in query_keywords if keyword in text_lower)
    
    if len(query_keywords) > 0:
        score = matches / len(query_keywords)
    else:
        score = 0
    
    return score

def get_relevant_context_with_history(query, user_data):
    """Get relevant context including chat history"""
    if not user_data:
        return ""
    
    query_keywords = extract_keywords(query)
    scored_chunks = []
    
    # Score medical history
    if 'medical_history' in user_data:
        for item in user_data['medical_history']:
            score = calculate_relevance_score(query_keywords, item)
            scored_chunks.append({
                'text': item,
                'type': 'history',
                'score': score
            })
    
    # Score medicines
    if 'medicines' in user_data:
        for med in user_data['medicines']:
            med_text = f"Taking {med['name']} ({med['dosage']}) {med['frequency']} times daily"
            score = calculate_relevance_score(query_keywords, med_text)
            scored_chunks.append({
                'text': med_text,
                'type': 'medicine',
                'score': score
            })
    
    # Score recent chat history (last 10 messages)
    if 'chat_history' in user_data:
        recent_chats = user_data['chat_history'][-10:]
        for chat in recent_chats:
            score = calculate_relevance_score(query_keywords, chat['message'])
            scored_chunks.append({
                'text': f"{chat['sender']}: {chat['message']}",
                'type': 'chat',
                'score': score
            })
    
    # Sort by relevance
    scored_chunks.sort(key=lambda x: x['score'], reverse=True)
    
    # Build context
    context = "**Most Relevant Context for Current Query:**\n\n"
    relevant_items = [chunk for chunk in scored_chunks[:10] if chunk['score'] > 0.15]
    
    if relevant_items:
        for chunk in relevant_items:
            if chunk['type'] == 'medicine':
                emoji = "💊"
            elif chunk['type'] == 'chat':
                emoji = "💬"
            else:
                emoji = "📋"
            context += f"{emoji} {chunk['text']}\n"
        return context
    else:
        return prepare_compact_context(user_data)

def prepare_compact_context(user_data):
    """Prepare compact summary"""
    if not user_data:
        return ""
    
    context = "**Patient Profile Summary:**\n\n"
    info = extract_key_medical_info(user_data)
    
    # Name
    if user_data.get('user_name'):
        context += f"👤 Name: {user_data['user_name']}\n"
    
    # Demographics
    if info['age'] or info['gender']:
        demo = []
        if info['age']:
            demo.append(f"{info['age']}yo")
        if info['gender']:
            demo.append(info['gender'])
        context += f"📊 {' | '.join(demo)}\n"
    
    # Conditions
    if info['conditions']:
        conditions_list = ', '.join([c.split('Patient')[-1].strip() for c in info['conditions'][:3]])
        context += f"🏥 Conditions: {conditions_list}\n"
    
    # Medicines
    if 'medicines' in user_data and user_data['medicines']:
        med_count = len(user_data['medicines'])
        top_meds = [m['name'] for m in user_data['medicines'][:3]]
        context += f"💊 Medications ({med_count}): {', '.join(top_meds)}"
        if med_count > 3:
            context += f" +{med_count-3} more"
        context += "\n"
    
    # Recent chat context (last 3 exchanges)
    if 'chat_history' in user_data and user_data['chat_history']:
        context += f"\n**Recent Conversation Context:**\n"
        recent = user_data['chat_history'][-6:]  # Last 3 exchanges (6 messages)
        for chat in recent:
            sender_label = "Patient" if chat['sender'] == 'user' else "Assistant"
            context += f"- {sender_label}: {chat['message'][:100]}...\n"
    
    return context

# ---------------------------
# HELPER FUNCTIONS
# ---------------------------
def calculate_age(dob_string):
    """Calculate age from date of birth"""
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
def extract_key_medical_info(user_data):
    """Extract key medical information"""
    info = {
        'age': None,
        'gender': None,
        'conditions': [],
        'surgeries': [],
        'allergies': [],
        'lifestyle': []
    }
    
    if not user_data or 'medical_history' not in user_data:
        return info
    
    for item in user_data['medical_history']:
        item_lower = item.lower()
        
        if 'date of birth' in item_lower and not info['age']:
            info['age'] = calculate_age(item)
        
        if 'identifies as' in item_lower and not info['gender']:
            if 'male' in item_lower and 'female' not in item_lower:
                info['gender'] = 'Male'
            elif 'female' in item_lower:
                info['gender'] = 'Female'
        
        if any(cond in item_lower for cond in ['diabetes', 'blood pressure', 'heart disease', 'cancer', 'carcinoma']):
            info['conditions'].append(item)
        
        if 'surgery' in item_lower or 'laser' in item_lower or 'hospitalized' in item_lower:
            info['surgeries'].append(item)
        
        if 'allerg' in item_lower and 'does not have' not in item_lower:
            info['allergies'].append(item)
        
        if any(word in item_lower for word in ['smoke', 'alcohol', 'drug', 'weight change']):
            info['lifestyle'].append(item)
    
    return info

def prepare_medical_context(user_data):
    """Prepare full medical context for system prompt"""
    if not user_data:
        return ""
    
    user_name = user_data.get('user_name', 'Patient')
    context = f"**PATIENT PROFILE: {user_name}**\n\n"
    
    info = extract_key_medical_info(user_data)
    
    # Demographics
    context += "**Demographics:**\n"
    if info['age']:
        context += f"- Age: {info['age']} years old\n"
    if info['gender']:
        context += f"- Gender: {info['gender']}\n"
    context += "\n"
    
    # Conditions
    if info['conditions']:
        context += "**Medical Conditions:**\n"
        for condition in info['conditions']:
            context += f"- {condition}\n"
        context += "\n"
    
    # Surgeries
    if info['surgeries']:
        context += "**Past Surgeries:**\n"
        for surgery in info['surgeries']:
            context += f"- {surgery}\n"
        context += "\n"
    
    # Medications
    if user_data.get('medicines'):
        context += "**Current Medications:**\n"
        for med in user_data['medicines']:
            freq = f"{med['frequency']}x/day" if med['frequency'] != '1' else "once daily"
            context += f"- {med['name']} ({med['dosage']}) - {freq}\n"
        context += "\n"
    
    # Allergies
    if info['allergies']:
        context += "**Allergies:**\n"
        for allergy in info['allergies']:
            context += f"- {allergy}\n"
        context += "\n"
    else:
        context += "**Allergies:** No known allergies\n\n"
    
    # Lifestyle
    if info['lifestyle']:
        context += "**Lifestyle:**\n"
        for factor in info['lifestyle']:
            context += f"- {factor}\n"
        context += "\n"
    
    # Recent conversation summary
    if user_data.get('chat_history'):
        context += "**Recent Conversation Summary:**\n"
        recent = user_data['chat_history'][-6:]
        for chat in recent:
            sender = "Patient" if chat['sender'] == 'user' else "You"
            context += f"- {sender}: {chat['message']}\n"
        context += "\n"
    
    return context

# ---------------------------
# SYSTEM PROMPT
# ---------------------------
SYSTEM_PROMPT_TEMPLATE = """
You are a professional AI-powered medical assistant chatbot specialized in personalized healthcare guidance.

{medical_context}

**IMPORTANT:** Always address the patient by their first name to create a personalized experience.

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

8. **Use the patient's name** naturally in your responses for personalization.
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
                    user_data = get_user_medical_history_and_medicine_summary(user_id)
                    if user_data:
                        st.session_state.user_id = user_id
                        st.session_state.user_data = user_data
                        st.success("✅ Profile loaded!")
                        st.rerun()
                    else:
                        st.error("User ID not found.")
            else:
                st.warning("Please enter a User ID")
    else:
        user_name = st.session_state.user_data.get('user_name', 'User')
        st.success(f"✅ Welcome, {user_name}!")
        st.markdown(f"**ID:** `{st.session_state.user_id}`")
        
        if st.button("Logout", type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        st.markdown("---")
        
        # Display profile
        if 'user_data' in st.session_state:
            info = extract_key_medical_info(st.session_state.user_data)
            
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
                    for condition in info['conditions']:
                        st.write(f"• {condition}")
            
            # Medications
            if st.session_state.user_data.get('medicines'):
                med_count = len(st.session_state.user_data['medicines'])
                st.markdown(f"### 💊 Medications ({med_count})")
                with st.expander("View List"):
                    for med in st.session_state.user_data['medicines'][:10]:
                        st.write(f"• **{med['name']}** - {med['dosage']}")
                    if med_count > 10:
                        st.write(f"• ... and {med_count - 10} more")
            
            # Chat history count
            if st.session_state.user_data.get('chat_history'):
                chat_count = len(st.session_state.user_data['chat_history'])
                st.markdown(f"### 💬 Previous Messages: {chat_count}")

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
        medical_context = prepare_medical_context(st.session_state.user_data)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(medical_context=medical_context)
        st.session_state.messages = [
            {"role": "system", "content": system_prompt}
        ]
        st.session_state.question_count = 0
        
        # Load previous chat history into display
        if st.session_state.user_data.get('chat_history'):
            for chat in st.session_state.user_data['chat_history'][-10:]:  # Last 10 messages
                role = "user" if chat['sender'] == 'user' else "assistant"
                st.session_state.messages.append({
                    "role": role,
                    "content": chat['message']
                })
    
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
        
        # Save to Firebase
        save_chat_message(st.session_state.user_id, user_input, is_user=True)
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                # Get relevant context
                relevant_context = ""
                if st.session_state.question_count >= 2:
                    relevant_context = get_relevant_context_with_history(
                        user_input,
                        st.session_state.user_data
                    )
                
                # Prepare messages
                messages_for_api = st.session_state.messages.copy()
                
                if relevant_context:
                    context_message = {
                        "role": "system",
                        "content": f"\n{relevant_context}\n\nProvide personalized guidance."
                    }
                    messages_for_api.insert(-1, context_message)
                
                # API call
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages_for_api,
                        temperature=0.7,
                        max_tokens=800
                    )
                    
                    reply = response.choices[0].message.content
                    st.markdown(reply)
                    
                    # Save messages
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                    save_chat_message(st.session_state.user_id, reply, is_user=False)
                
                except Exception as e:
                    st.error(f"Error: {e}")
    
    # Helper buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 New Conversation"):
            # Clear cache for this user
            get_user_medical_history_and_medicine_summary.clear()
            # Reload data
            user_data = get_user_medical_history_and_medicine_summary(st.session_state.user_id)
            st.session_state.user_data = user_data
            
            medical_context = prepare_medical_context(user_data)
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(medical_context=medical_context)
            st.session_state.messages = [
                {"role": "system", "content": system_prompt}
            ]
            st.session_state.question_count = 0
            st.rerun()
    
    with col2:
        if st.button("🔃 Refresh Profile"):
            get_user_medical_history_and_medicine_summary.clear()
            user_data = get_user_medical_history_and_medicine_summary(st.session_state.user_id)
            st.session_state.user_data = user_data
            st.success("Profile refreshed!")
            st.rerun()