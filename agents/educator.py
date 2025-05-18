from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from utils.config import GROQ_API_KEY

class EducatorAgent:
    def __init__(self):
        self.llm = ChatGroq(model_name="gemma2-9b-it", api_key=GROQ_API_KEY)  # Balanced for education

    def provide_education(self, strategy):
        prompt = PromptTemplate(
            input_variables=["strategy"],
            template="Explain the {strategy} investment strategy and provide starter prompts for users."
        )
        response = self.llm.invoke(prompt.format(strategy=strategy))
        return response.content