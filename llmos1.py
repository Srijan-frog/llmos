import streamlit as st
from openai import AzureOpenAI, OpenAIError
import os
from datetime import datetime
import requests
import json

# Define the subscription key and endpoint for the Bing Search API
subscription_key = "xxx"  # Use your Bing API subscription key
endpoint = "https://api.bing.microsoft.com/v7.0/search"

# Function to get top 5 search results from Bing
def get_top_search_results(query):
    headers = {"Ocp-Apim-Subscription-Key": subscription_key}
    params = {"q": query, "count": 5}
    
    # Send a GET request to the Bing Search API
    response = requests.get(endpoint, headers=headers, params=params)
    
    if response.status_code == 200:
        search_results = response.json()
        results = []
        for web_page in search_results.get("webPages", {}).get("value", []):
            result = {
                "name": web_page["name"],
                "url": web_page["url"],
                "snippet": web_page["snippet"],
                "date_last_visited": web_page.get("dateLastCrawled", "N/A"),
            }
            results.append(result)
        return results
    else:
        return f"Error: {response.status_code}, {response.text}"

# Define the LLMOSAssistant class
class LLMOSAssistant:
    def __init__(self, azure_endpoint, api_key, api_version="2024-02-15-preview", model="gpt-4o", temperature=0.7, max_tokens=400):
        try:
            self.client = AzureOpenAI(azure_endpoint=azure_endpoint, api_key=api_key, api_version=api_version)
            self.model = model
            self.temperature = temperature
            self.max_tokens = max_tokens
            self.system_message = """You are the most advanced AI system in the world called 'LLM-OS'.
            Your goal is to assist the user in the best way possible.
            You have access to the internet through Bing API.
            When the user sends a message, first **think** and determine if:
            - You can answer this on your own
            - You need to search the internet
            Always answer *based on internet search* when internet search results are used.
            Refer to chat history always.
            If the user's message is unclear, ask clarifying questions to get more information.
            Carefully read the information you have gathered and provide a clear and concise answer to the user.
            Do not use phrases like 'based on my knowledge' or 'depending on the information' or 'based on the provided data'.
            """
        except OpenAIError as e:
            st.error(f"Failed to initialize Azure OpenAI client: {e}")

    def get_response(self, messages):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=messages
            )
            return response.choices[0].message.content
        except OpenAIError as e:
            st.error(f"Failed to get response from Azure OpenAI: {e}")
            return "I'm sorry, but I'm unable to respond at the moment."

    def search_and_respond(self, query,history):
        print("H:",history)
          # Clean the chat history
        # Filter out messages where role is 'system'
        cleaned_history = [message for message in history if message.get('role') != 'system']
        print("CH:",cleaned_history)
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        optimized_query_prompt = (
        f"Optimize an internet search query and phrase a question using the user query '{query}', conversation history '{cleaned_history}', "
        f"and the current date and time '{current_datetime}'. Just give the final question as response and nothing else."
        )
        optimized_query = self.get_response([
        {"role": "system", "content": self.system_message},
        {"role": "user", "content": optimized_query_prompt}
        ])
        print(optimized_query)
         # Step 1: Perform the search using Bing API
        search_results = get_top_search_results(optimized_query)
        #write code here for internet search with history : ask llm to frame 'internet search query' based on history and user query + date time
        # Step 2: Format the results for the assistant
        print(search_results)
        formatted_results = "\n".join([f"Title: {result['name']}\nURL: {result['url']}\nSnippet: {result['snippet']}\n"
                                      for result in search_results])
        
        # Step 3: Send the formatted search results along with the user query to LLM
        response = self.get_response([ 
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": f"Find relevant answer to '{query}' Using this data {formatted_results} and chat history{history}. Answer '{query}'"}
        ])
        return response

# Initialize Streamlit app with a sidebar for configuration
st.set_page_config(page_title="LLM-OS Chat Assistant", page_icon="🤖", layout="centered")
st.title("🤖 LLM-OS Chat Assistant")
st.write("You are interacting with the LLM-OS, the world's most advanced AI system!")

# Set up session state for chat history
if "messages" not in st.session_state:
    assistant = LLMOSAssistant(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "your-azure-endpoint"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY", "your-api-key")
    )
    st.session_state.messages = [{"role": "system", "content": assistant.system_message}]

# Load Azure OpenAI configuration from environment variables
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "xxx") 
api_key = os.getenv("AZURE_OPENAI_API_KEY", "xxx") 
# Create the LLM OS Assistant instance
assistant = LLMOSAssistant(azure_endpoint, api_key)

# Add a checkbox to the sidebar for enabling/disabling internet search
with st.sidebar:
    st.header("Select Tools")
    enable_internet_search = st.checkbox("Web Search", value=False)

# Define containers for a clean layout
with st.container():
    # Input section for new prompt
    st.subheader("💬 New Query")
    user_input = st.text_input("Enter Query:", placeholder="Ask the LLM-OS assistant anything...")
    if st.button("Execute") and user_input:
        # Add user command to session state
        st.session_state.messages.append({"role": "user", "content": user_input})

        if enable_internet_search:
            
            assistant_response = assistant.search_and_respond(query=user_input,history=st.session_state.messages)
             
        else:
            
            assistant_response = assistant.get_response(st.session_state.messages)
            
            

        # Add LLM-OS response to session state
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})

    # Show response section with latest message
    st.subheader("🤖 LLM-OS Response")
    if st.session_state.messages:
        if st.session_state.messages[-1]["role"] == "assistant":
            st.write(st.session_state.messages[-1]["content"])

# Chat history in a collapsible expander
with st.expander("📜 Chat History", expanded=True):
    st.subheader("Conversation History")
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.write(f"**User:** {message['content']}")
        elif message["role"] == "assistant":
            st.write(f"**LLM-OS:** {message['content']}")

# Optionally, add a clear command history button
if st.button("Clear Chat History"):
    st.session_state.messages = [{"role": "system", "content": assistant.system_message}]
    st.write("Chat history cleared.")
