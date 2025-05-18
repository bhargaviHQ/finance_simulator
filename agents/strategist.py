from langchain_groq import ChatGroq
from utils.config import GROQ_API_KEY
from utils.logger import logger
from typing import List, Dict
import json
import time
import re

class StrategistAgent:
    def __init__(self):
        self.llm = ChatGroq(model_name="llama-3.1-8b-instant", api_key=GROQ_API_KEY)

    def generate_recommendations(self, preferences: Dict, market_data: List[Dict]) -> List[Dict]:
        """Generate stock recommendations based on preferences and market data."""
        if not market_data:
            logger.error("No market data provided for recommendations")
            return []
        
        valid_symbols = {item["symbol"] for item in market_data if "symbol" in item}
        if not valid_symbols:
            logger.error("No valid symbols in market data")
            return []

        for attempt in range(3):
            try:
                logger.info(f"Attempt {attempt + 1}: Generating recommendations with preferences: {preferences}")
                prompt = f"""
You are a stock market expert. Generate up to 3 stock recommendations based on:
- User Preferences: {preferences}
- Market Data: {market_data}

Consider:
- Risk appetite, investment goals, time horizon, investment amount, and style.
- Real-time prices, 5 years of financials (income, balance, cash flows).
- News sentiment, P/E ratio, debt-to-equity ratio for each stock.
- Only these stocks: {', '.join(valid_symbols)}

For each recommendation, provide:
- Symbol: Stock ticker (from: {', '.join(valid_symbols)}, use 'Symbol' key)
- Company: Company name
- Action: Buy, Sell, or Hold
- Quantity: Number of shares (based on investment amount and price)
- Reason: Why this action fits the preferences (3-4 sentences, include financial ratios)
- Caution: Potential risks (1-2 sentences)
- NewsSentiment: Positive, Negative, or Neutral

Score each stock (0-100) based on alignment with preferences, financial health, and sentiment. Return top 3 by score.

Return the response as a JSON list of dictionaries wrapped in ```json``` delimiters.
Ensure valid JSON with keys: Symbol, Company, Action, Quantity, Reason, Caution, NewsSentiment, Score.
Example:
```json
[
    {{
        "Symbol": "AAPL",
        "Company": "Apple Inc.",
        "Action": "Buy",
        "Quantity": 10,
        "Reason": "Strong cash flow, low debt-to-equity (0.5), and positive news support growth.",
        "Caution": "High P/E (30) may limit upside.",
        "NewsSentiment": "Positive",
        "Score": 85
    }}
]
```
**Important**: Always use 'Symbol' (uppercase 'S'), wrap in ```json```, and ensure valid JSON.
"""
                response = self.llm.invoke(prompt)
                raw_response = response.content.strip()
                logger.debug(f"Raw LLM response: {raw_response}")

                # Try extracting JSON with delimiters
                json_match = re.search(r'```json\n(.*?)\n```', raw_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    # Fallback: Extract raw JSON
                    json_start = raw_response.find('[')
                    json_end = raw_response.rfind(']') + 1
                    if json_start != -1 and json_end != 0:
                        json_str = raw_response[json_start:json_end].strip()
                        logger.warning(f"Attempt {attempt + 1}: No JSON delimiters, extracted raw JSON: {json_str}")
                    else:
                        logger.error(f"Attempt {attempt + 1}: No JSON block found")
                        if attempt < 2:
                            time.sleep(5 * (2 ** attempt))
                            continue
                        return []

                try:
                    rec_list = json.loads(json_str)
                    if not isinstance(rec_list, list):
                        raise ValueError("Response is not a list")
                    for rec in rec_list:
                        if not all(key in rec for key in ["Symbol", "Company", "Action", "Quantity", "Reason", "Caution", "NewsSentiment", "Score"]):
                            raise ValueError(f"Invalid recommendation format: {rec}")
                        if rec["Symbol"] not in valid_symbols:
                            raise ValueError(f"Invalid symbol {rec['Symbol']}")
                        if rec["Action"] not in ["Buy", "Sell", "Hold"]:
                            raise ValueError(f"Invalid action {rec['Action']}")
                        if not isinstance(rec["Quantity"], int) or rec["Quantity"] < 0:
                            raise ValueError(f"Invalid quantity {rec['Quantity']}")
                        if not isinstance(rec["Score"], (int, float)) or rec["Score"] < 0 or rec["Score"] > 100:
                            raise ValueError(f"Invalid score {rec['Score']}")
                    # Sort by score and take top 3
                    rec_list = sorted(rec_list, key=lambda x: x["Score"], reverse=True)[:3]
                    logger.info(f"Successfully generated {len(rec_list)} recommendations")
                    return rec_list
                except json.JSONDecodeError as e:
                    logger.error(f"Attempt {attempt + 1}: Failed to parse JSON: {str(e)}")
                    if attempt < 2:
                        time.sleep(5 * (2 ** attempt))
                        continue
                    return []
                except ValueError as e:
                    logger.error(f"Attempt {attempt + 1}: Invalid format: {str(e)}")
                    if attempt < 2:
                        time.sleep(5 * (2 ** attempt))
                        continue
                    return []
            except Exception as e:
                if "429" in str(e):
                    logger.error(f"Attempt {attempt + 1}: Rate limit exceeded (429)")
                    if attempt < 2:
                        time.sleep(10 * (2 ** attempt))
                        continue
                logger.error(f"Attempt {attempt + 1}: Failed to generate recommendations: {str(e)}")
                if attempt < 2:
                    time.sleep(5 * (2 ** attempt))
                    continue
                return []
        logger.error("All attempts to generate recommendations failed")
        return []