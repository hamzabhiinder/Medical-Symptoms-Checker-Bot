import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
# ---------------------------
# CONFIGURATION
# ---------------------------
st.set_page_config(page_title="AI Medical Assistant", page_icon="💬")

# ------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEN_API_KEY")
GEMINI_MODEL = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")

# Your Gemini API key (set this as an environment variable for security)
genai.configure(api_key=GEMINI_API_KEY)
# Initialize the model
model = genai.GenerativeModel(GEMINI_MODEL)


# System Prompt
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

Safety Rules:
1. If the user mentions emergency symptoms like chest pain, shortness of breath, severe bleeding, stroke symptoms,
loss of consciousness, or suicidal thoughts — IMMEDIATELY respond:
“⚠️ Emergency symptoms detected! Please call emergency services or visit the nearest hospital right now.”  
2. Never make a direct diagnosis (e.g., “You have pneumonia”).  
Instead, use phrases like “It might be related to…” or “It could be due to…”  
3. Be empathetic, reassuring, and supportive in every response.  
4. Respect user privacy and never ask for personal or identifying information.  
5. Always end responses with:
“I’m here to help you understand your symptoms better. Please contact a doctor if your condition worsens.”  

Additional Rules:
6. If the user asks irrelevant or non-medical questions, politely reply:
“I'm sorry, but I can only help with health-related questions. Could you please tell me what symptoms or health concerns you’d like to discuss?”  

7. If the user asks for information about another person’s health, respond:
“For privacy and safety reasons, I can only provide general health information based on the details you share about yourself.”
"""


# ---------------------------
# STREAMLIT UI
# ---------------------------
st.title("💬 AI Medical Assistant Chatbot")
st.write("Ask me about your symptoms or health concerns. I’ll help you understand them better.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User input
if user_input := st.chat_input("Describe your symptoms..."):
    # Save user message
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)

    # Combine messages into one context
    conversation = "\n".join(
        [f"{m['role'].capitalize()}: {m['content']}" for m in st.session_state.messages]
    )

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            prompt = f"{SYSTEM_PROMPT}\n\nConversation:\n{conversation}\n\nAssistant:"
            response = model.generate_content(prompt)
            reply = response.text

        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})