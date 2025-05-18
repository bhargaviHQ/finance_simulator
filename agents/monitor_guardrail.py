from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from utils.config import GROQ_API_KEY

class MonitorGuardrailAgent:
    def __init__(self):
        self.llm = ChatGroq(model_name="llama-guard-3-8b", api_key=GROQ_API_KEY)  # Specialized for guardrails

    def monitor(self, action, user_id):
        prompt = PromptTemplate(
            input_variables=["action", "user_id"],
            template="Check if {action} is safe and compliant for user {user_id}."
        )
        response = self.llm(prompt.format(action=action, user_id=user_id))
        return response.content == "Safe"