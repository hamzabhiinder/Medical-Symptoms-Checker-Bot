import streamlit as st
from openai import OpenAI
import os
from datetime import datetime

# ---------------------------
# CONFIGURATION
# ---------------------------
st.set_page_config(page_title="AI Medical Assistant", page_icon="💊", layout="wide")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------
# SAMPLE USER DATA (Replace with Firebase later)
# ---------------------------
user_data = {
    "user_id": "pGSZNP7t8odnxmOIpRbDcuthbbM2",
    "user_name": "Scott Grody",
    "user_bio": [
        {"question": "what is your date of birth?", "answer": "Patient's date of birth is 07/06/1946."},
        {"question": "what is your gender", "answer": "Patient identifies as Male."},
        {"question": "what is your ethnicity", "answer": "Patient's ethnicity is Caucasian."},
        {"question": "what is your height", "answer": "Patient's height is 5'10\"."},
        {"question": "what is your weight", "answer": "Patient's weight is 175 lbs."}
    ],
    "medical_history": [
        {"question": "Have you had any surgeries in the past?", "answer": "No"},
        {"question": "Have you ever been hospitalized?", "answer": "Yes, I have been hospitalized previously."},
        {"question": "Do you have high blood pressure?", "answer": "No"},
        {"question": "Do you have diabetes?", "answer": "Yes, I have diabetes."},
        {"question": "Do you have heart disease?", "answer": "No"},
        {"question": "Do you have any known allergies?", "answer": "Yes, I have known allergies."},
        {"question": "Do you currently smoke tobacco?", "answer": "No"},
        {"question": "Do you consume alcohol?", "answer": "Yes, I consume alcohol."},
        {"question": "Do you use recreational drugs?", "answer": "No"},
        {"question": "Have you experienced any recent weight changes?", "answer": "Yes, I have experienced recent weight changes."},
        {"question": "Have you had a fever in the past month?", "answer": "No"},
        {"question": "Do you have a history of cancer?", "answer": "Yes, I have a history of cancer."},
        {"question": "Is there any family history of serious illness?", "answer": "No"}
    ]
}

# ---------------------------
# HELPER FUNCTIONS
# ---------------------------
def calculate_age(dob_string):
    """Calculate age from date of birth"""
    try:
        date_str = dob_string.split("is ")[-1].replace(".", "").strip()
        dob = datetime.strptime(date_str, "%m/%d/%Y")
        today = datetime.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age
    except:
        return None

def prepare_patient_context(data):
    """Prepare patient context from user_data"""
    context = f"**PATIENT PROFILE: {data['user_name']}**\n\n"
    
    # Bio Information
    context += "**Patient Information:**\n"
    for item in data['user_bio']:
        if 'date of birth' in item['question'].lower():
            age = calculate_age(item['answer'])
            if age:
                context += f"- Age: {age} years old\n"
        elif 'gender' in item['question'].lower():
            gender = item['answer'].split("as ")[-1].replace(".", "").strip()
            context += f"- Gender: {gender}\n"
        elif 'height' in item['question'].lower():
            height = item['answer'].split("is ")[-1].replace(".", "").strip()
            context += f"- Height: {height}\n"
        elif 'weight' in item['question'].lower():
            weight = item['answer'].split("is ")[-1].replace(".", "").strip()
            context += f"- Weight: {weight}\n"
    
    context += "\n**Medical History:**\n"
    
    # Key conditions
    conditions = []
    for item in data['medical_history']:
        answer = item['answer'].lower()
        question = item['question'].lower()
        
        if 'yes' in answer:
            if 'diabetes' in question:
                conditions.append("Diabetes")
            elif 'cancer' in question:
                conditions.append("History of Cancer")
            elif 'blood pressure' in question:
                conditions.append("High Blood Pressure")
            elif 'heart disease' in question:
                conditions.append("Heart Disease")
            elif 'allergies' in question:
                conditions.append("Known Allergies")
            elif 'hospitalized' in question:
                conditions.append("Previous Hospitalization")
            elif 'alcohol' in question:
                conditions.append("Consumes Alcohol")
            elif 'weight changes' in question:
                conditions.append("Recent Weight Changes")
    
    if conditions:
        for condition in conditions:
            context += f"- {condition}\n"
    else:
        context += "- No major conditions reported\n"
    
    return context

# ---------------------------
# SYSTEM PROMPT
# ---------------------------
SYSTEM_PROMPT = """
You are a professional AI medical assistant. Your job is to help patients understand their symptoms and provide guidance.

{patient_context}

**YOUR APPROACH:**

1. **Ask Questions First** (4-5 follow-up questions):
   - Ask ONE specific question at a time about their symptoms
   - Consider their medical history when asking
   - Examples: "When did this start?", "How severe is the pain (1-10)?", "Does anything make it better or worse?"

2. **Then Provide Guidance**:
   
   **Possible Causes:**
   - List likely causes based on symptoms and medical history
   - Use simple language
   
   **What You Can Do:**
   - Safe self-care steps
   - Home remedies
   - Lifestyle tips
   
   **When to See a Doctor:**
   - List warning signs
   - Be extra cautious with patients who have diabetes, cancer history, or other conditions

**SAFETY RULES:**

⚠️ **EMERGENCY** - If patient mentions: chest pain, trouble breathing, severe bleeding, stroke signs, suicidal thoughts
→ Say: "⚠️ This is an EMERGENCY! Call 911 or go to ER immediately!"

- Never diagnose - say "might be" or "could be related to"
- Always use patient's first name
- Be empathetic and supportive
- Only help with health questions

**Remember:** Given {patient_name}'s medical history (diabetes, cancer history), be more cautious and recommend seeing a doctor sooner.
"""

# ---------------------------
# STREAMLIT UI
# ---------------------------
st.title("💊 AI Medical Assistant")
st.markdown(f"### Welcome, {user_data['user_name']}!")

# Sidebar - Patient Profile
with st.sidebar:
    st.header("👤 Patient Profile")
    st.markdown(f"**Name:** {user_data['user_name']}")
    
    # Calculate age
    for item in user_data['user_bio']:
        if 'date of birth' in item['question'].lower():
            age = calculate_age(item['answer'])
            if age:
                st.markdown(f"**Age:** {age} years")
    
    st.markdown("---")
    st.subheader("🏥 Key Medical Info")
    
    # Show key conditions
    conditions = []
    for item in user_data['medical_history']:
        if 'yes' in item['answer'].lower():
            if 'diabetes' in item['question'].lower():
                conditions.append("✓ Diabetes")
            elif 'cancer' in item['question'].lower():
                conditions.append("✓ History of Cancer")
            elif 'allergies' in item['question'].lower():
                conditions.append("✓ Known Allergies")
    
    if conditions:
        for condition in conditions:
            st.markdown(condition)
    
    st.markdown("---")
    if st.button("🔄 New Conversation"):
        st.session_state.messages = None
        st.rerun()

# Initialize chat
if "messages" not in st.session_state:
    patient_context = prepare_patient_context(user_data)
    system_prompt = SYSTEM_PROMPT.format(
        patient_context=patient_context,
        patient_name=user_data['user_name'].split()[0]
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

