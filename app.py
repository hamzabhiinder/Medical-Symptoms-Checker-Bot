import streamlit as st
import requests

API_URL = "http://localhost:8000/chat"  # FastAPI endpoint

# ---------------------------
# STREAMLIT UI
# ---------------------------
st.set_page_config(page_title="AI Medical Assistant", page_icon="💬")
st.title("💬 AI Medical Assistant Chatbot")
st.write("Ask me about your symptoms or health concerns. I’ll help you understand them better.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Display past messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle new user input
if user_input := st.chat_input("Describe your symptoms..."):
    st.session_state["messages"].append({"role": "user", "content": user_input})

    # Show user message
    with st.chat_message("user"):
        st.markdown(user_input)

    # Get response from API
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(API_URL, json={"conversation": st.session_state["messages"]})
                if response.status_code == 200:
                    reply = response.json()["reply"]
                else:
                    reply = f"⚠️ Error: {response.status_code} - {response.text}"
            except Exception as e:
                reply = f"⚠️ Could not reach API: {e}"

            st.markdown(reply)
            st.session_state["messages"].append({"role": "assistant", "content": reply})