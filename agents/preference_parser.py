from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field
from utils.config import GROQ_API_KEY
import json
from utils.logger import logger

class InvestmentPersona(BaseModel):
    risk_appetite: str = Field(..., description="Risk appetite (low, medium, high)")
    investment_goals: str = Field(..., description="Investment goals (retirement, growth, income)")
    time_horizon: str = Field(..., description="Time horizon (short, medium, long)")
    investment_amount: float = Field(..., description="Investment amount")
    investment_style: str = Field(..., description="Investment style (value, growth, index)")

class PreferenceParserAgent:
    def __init__(self):
        self.llm = ChatGroq(model_name="llama-3.1-8b-instant", api_key=GROQ_API_KEY)

    def parse_preferences(self, text: str) -> dict:
        prompt = PromptTemplate(
            input_variables=["text"],
            template="""
You are an expert investment advisor tasked with generating a complete investment persona based on user input. The persona must include the following fields:
- risk_appetite: Risk appetite, one of 'low', 'medium', 'high'.
- investment_goals: Investment goals, one of 'retirement', 'growth', 'income'.
- time_horizon: Time horizon, one of 'short' (1-3 years), 'medium' (3-7 years), 'long' (7+ years).
- investment_amount: Investment amount (float, e.g., 5000.0).
- investment_style: Investment style, one of 'value', 'growth', 'index'.

**User Input**: {text}

**Instructions**:
1. Analyze the user input to determine the values for each field.
2. If a field is not specified or unclear, use the following defaults:
   - risk_appetite: 'medium'
   - investment_goals: 'growth'
   - time_horizon: 'medium'
   - investment_amount: 10000.0
   - investment_style: 'index'
3. For ambiguous inputs, infer reasonable values based on context. For example:
   - If the user mentions 'safe' or 'secure', set risk_appetite to 'low'.
   - If the user mentions 'saving for later', set investment_goals to 'retirement'.
   - If no amount is specified, use 10000.0.
4. Ensure all fields are populated and conform to the specified options or format.
5. Output the persona as a JSON object.

**Examples**:
- Input: "I want to invest $5000 safely."
  Output: ```json
  {
    "risk_appetite": "low",
    "investment_goals": "growth",
    "time_horizon": "medium",
    "investment_amount": 5000.0,
    "investment_style": "index"
  }
  ```
- Input: "Looking for long-term growth."
  Output: ```json
  {
    "risk_appetite": "medium",
    "investment_goals": "growth",
    "time_horizon": "long",
    "investment_amount": 10000.0,
    "investment_style": "growth"
  }
  ```
- Input: ""
  Output: ```json
  {
    "risk_appetite": "medium",
    "investment_goals": "growth",
    "time_horizon": "medium",
    "investment_amount": 10000.0,
    "investment_style": "index"
  }
  ```

**Output**:
Return the investment persona in JSON format.
"""
        )
        try:
            response = self.llm.invoke(prompt.format(text=text))
            preferences_json = json.loads(response.content)
            preferences = InvestmentPersona.parse_obj(preferences_json)
            return preferences.dict()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {response.content}")
            return {
                "risk_appetite": "medium",
                "investment_goals": "growth",
                "time_horizon": "medium",
                "investment_amount": 10000.0,
                "investment_style": "index"
            }
        except Exception as e:
            logger.error(f"Error parsing preferences: {str(e)}")
            return {
                "risk_appetite": "medium",
                "investment_goals": "growth",
                "time_horizon": "medium",
                "investment_amount": 10000.0,
                "investment_style": "index"
            }