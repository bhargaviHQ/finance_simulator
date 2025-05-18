from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field
from utils.config import GROQ_API_KEY
import json
import re
from utils.logger import logger
from langchain_core.exceptions import LangChainException
import time

class InvestmentPersona(BaseModel):
    risk_appetite: str = Field(..., description="Risk appetite (low, medium, high)")
    investment_goals: str = Field(..., description="Investment goals (retirement, growth, income)")
    time_horizon: str = Field(..., description="Time horizon (short, medium, long)")
    investment_amount: float = Field(..., description="Investment amount")
    investment_style: str = Field(..., description="Investment style (value, growth, index)")

class PreferenceParserAgent:
    def __init__(self):
        try:
            self.llm = ChatGroq(model_name="llama-3.1-8b-instant", api_key=GROQ_API_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize ChatGroq: {str(e)}")
            raise

    def parse_preferences(self, text: str) -> dict:
        prompt = PromptTemplate(
            input_variables=["text"],
            template="""
You are an expert investment advisor tasked with generating a complete investment persona based on user input. The persona must include exactly the following fields:
- risk_appetite: Must be one of 'low', 'medium', 'high'.
- investment_goals: Must be one of 'retirement', 'growth', 'income'.
- time_horizon: Must be one of 'short' (1-3 years), 'medium' (3-7 years), 'long' (7+ years).
- investment_amount: A positive float (e.g., 5000.0). Use 10000.0 if not specified.
- investment_style: Must be one of 'value', 'growth', 'index'.

**User Input**: {text}

**Instructions**:
1. Carefully analyze the user input to extract values for each field.
2. Map input terms to the required options:
   - Risk: 'safe', 'secure', 'cautious' → 'low'; 'aggressive', 'risky' → 'high'; else 'medium'.
   - Goals: 'retirement', 'long-term savings' → 'retirement'; 'wealth', 'expansion' → 'growth'; 'dividends', 'passive' → 'income'; else 'growth'.
   - Time: '1-3 years', 'short-term' → 'short'; '3-7 years' → 'medium'; '7+ years', 'long-term' → 'long'; else 'medium'.
   - Amount: Extract any numeric value with '$' or 'dollars' (e.g., '$5000' → 5000.0); else 10000.0.
   - Style: 'value' → 'value'; 'growth' → 'growth'; 'index', 'passive' → 'index'; else 'index'.
3. If a field is unclear, use these defaults:
   - risk_appetite: 'medium'
   - investment_goals: 'growth'
   - time_horizon: 'medium'
   - investment_amount: 10000.0
   - investment_style: 'index'
4. Output **only** a valid JSON object with the exact keys: risk_appetite, investment_goals, time_horizon, investment_amount, investment_style. Do not include markdown, code blocks, or additional text.

**Examples**:
- Input: "I want to invest $5000 safely for retirement."
  Output: {
    "risk_appetite": "low",
    "investment_goals": "retirement",
    "time_horizon": "medium",
    "investment_amount": 5000.0,
    "investment_style": "index"
  }
- Input: "Invest $10000 aggressively for 10 years."
  Output: {
    "risk_appetite": "high",
    "investment_goals": "growth",
    "time_horizon": "long",
    "investment_amount": 10000.0,
    "investment_style": "growth"
  }

**User Input**: {text}

Output the investment persona as a valid JSON object.
"""
        )
        defaults = {
            "risk_appetite": "medium",
            "investment_goals": "growth",
            "time_horizon": "medium",
            "investment_amount": 10000.0,
            "investment_style": "index"
        }
        raw_response = None
        try:
            if not text or text.isspace():
                logger.warning("Empty or whitespace input provided; returning defaults")
                return defaults

            # Normalize input
            text = text.strip().lower()
            logger.info(f"Normalized input: {text}")

            # Call LLM with retry
            for attempt in range(3):
                try:
                    response = self.llm.invoke(prompt.format(text=text))
                    raw_response = response.content
                    logger.debug(f"Raw LLM response (attempt {attempt + 1}): {raw_response}")
                    break
                except LangChainException as e:
                    if attempt < 2:
                        logger.warning(f"LLM API error on attempt {attempt + 1}: {str(e)}; retrying...")
                        time.sleep(2 ** attempt)
                        continue
                    logger.error(f"LLM API failed after {attempt + 1} attempts: {str(e)}")
                    return defaults

            # Check for empty or invalid response
            if not raw_response or raw_response.isspace():
                logger.error("LLM returned empty or whitespace response")
                return defaults

            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', raw_response)
            if not json_match:
                logger.error(f"No valid JSON found in response: {raw_response}")
                # Fallback: Manual parsing
                preferences = defaults.copy()
                if "safe" in text or "secure" in text or "cautious" in text:
                    preferences["risk_appetite"] = "low"
                elif "aggressive" in text or "risky" in text:
                    preferences["risk_appetite"] = "high"
                if "retirement" in text or "long-term savings" in text:
                    preferences["investment_goals"] = "retirement"
                elif "wealth" in text or "expansion" in text:
                    preferences["investment_goals"] = "growth"
                elif "dividends" in text or "passive" in text:
                    preferences["investment_goals"] = "income"
                if "1-3 years" in text or "short-term" in text:
                    preferences["time_horizon"] = "short"
                elif "3-7 years" in text:
                    preferences["time_horizon"] = "medium"
                elif "7+ years" in text or "long-term" in text:
                    preferences["time_horizon"] = "long"
                amount_match = re.search(r'\$?(\d+\.?\d*)', text)
                if amount_match:
                    try:
                        preferences["investment_amount"] = float(amount_match.group(1))
                    except ValueError:
                        pass
                if "value" in text:
                    preferences["investment_style"] = "value"
                elif "growth" in text:
                    preferences["investment_style"] = "growth"
                elif "index" in text or "passive" in text:
                    preferences["investment_style"] = "index"
                logger.info(f"Fallback preferences: {preferences}")
                return preferences

            cleaned_response = json_match.group(0)
            logger.debug(f"Extracted JSON: {cleaned_response}")

            # Parse JSON
            try:
                preferences_json = json.loads(cleaned_response)
                logger.debug(f"Parsed JSON: {preferences_json}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {raw_response}, Error: {str(e)}")
                return defaults

            # Validate with Pydantic
            try:
                preferences = InvestmentPersona.parse_obj(preferences_json)
                logger.info(f"Validated preferences: {preferences.dict()}")
                return preferences.dict()
            except ValueError as e:
                logger.error(f"Pydantic validation error: {str(e)}, Parsed JSON: {preferences_json}")
                return defaults

        except Exception as e:
            logger.error(f"Unexpected error parsing preferences: {str(e)}, Raw response: {raw_response or 'No response'}")
            return defaults