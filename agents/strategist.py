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
        STOCK_LIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "JPM", "WMT", "V"]
        """Generate stock recommendations based on preferences and market data."""
        if not market_data:
            logger.error("No market data provided for recommendations")
            return []
        
        valid_symbols = {item["symbol"].upper() for item in market_data if "symbol" in item}
        if not valid_symbols:
            logger.warning("Empty market_data, using STOCK_LIST as fallback for valid_symbols")
            valid_symbols = {symbol.upper() for symbol in STOCK_LIST}
        logger.debug(f"Valid symbols: {valid_symbols}")
        if not valid_symbols:
            logger.error("No valid symbols in market data")
            return []

        for attempt in range(3):
            try:
                logger.info(f"Attempt {attempt + 1}: Generating recommendations with preferences: {preferences}")
                prompt = f"""
You are a stock market expert. Generate up to 3 to 5 stock recommendations based on:
- User Preferences: {preferences}
- Market Data: {market_data}

Consider:
- Risk appetite, investment goals, time horizon, investment amount, and style.
- Real-time prices, 5 years of financials (income, balance, cash flows).
- News sentiment, P/E ratio, debt-to-equity ratio for each stock.
- Ensure the total cost (Quantity * price) is less than or equal to investment_amount in {preferences}
- Only these stocks: {', '.join(valid_symbols)}

For each recommendation, provide:
- Symbol: Stock ticker (from: {', '.join(valid_symbols)}, use 'Symbol' key)
- Company: Company name
- Action: Buy, Sell, or Hold
- Quantity: Number of shares (integer,decimal,float,upto 2 decimal places only if decimal, calculated as floor(investment_amount / price) to ensure total cost <= investment_amount in {preferences})
- Reason: Why this action fits the preferences (3-4 sentences, include financial ratios)
- Caution: Potential risks (1-2 sentences)
- NewsSentiment: Positive, Negative, or Neutral

Score each stock (0-100) based on alignment with preferences, financial health, and sentiment. Return top 3 by score.
Ensure the total cost (Quantity * price) does not exceed the investment_amount in preferences.

Return the response as a JSON list of dictionaries wrapped in ```json``` delimiters.
Ensure the total cost (Quantity * price) is less than or equal to investment_amount in preferences.
Ensure valid JSON with keys: Symbol, Company, Action, Quantity, Reason, Caution, NewsSentiment, Score.
Example:
```json
[
    {{
        "Symbol": "AAPL",
        "Company": "Apple Inc.",
        "Action": "Buy",
        "Quantity": 0.59,
        "Reason": "Strong cash flow, low debt-to-equity (0.5), and positive news support growth.",
        "Caution": "High P/E (30) may limit upside.",
        "NewsSentiment": "Positive",
        "Score": 85
    }}
]
```
**Important**: Always use 'Symbol' (uppercase 'S'), wrap in ```json```, ensure valid JSON, and ensure Quantity * price <= investment_amount.
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
                        if rec["Symbol"].upper() not in valid_symbols:
                            raise ValueError(f"Invalid symbol {rec['Symbol']}")
                        if rec["Action"] not in ["Buy", "Sell", "Hold"]:
                            raise ValueError(f"Invalid action {rec['Action']}")
                        #if not isinstance(rec["Quantity"], int) or rec["Quantity"] < 0 or rec["Quantity"] > 50:
                        if rec["Quantity"] < 0 or rec["Quantity"] > 50:
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
    
    def select_best_recommendation(self, recommendations: List[Dict], preferences: Dict, market_data: List[Dict]) -> Dict:
        STOCK_LIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "JPM", "WMT", "V"]
        """Select the best recommendation from a list based on user preferences and market data."""
        if not recommendations:
            logger.error("No recommendations provided for selection")
            return {}
        valid_symbols = {item["symbol"].upper() for item in market_data if "symbol" in item}
        if not valid_symbols:
            logger.warning("Empty market_data, using STOCK_LIST as fallback for valid_symbols")
            valid_symbols = {symbol.upper() for symbol in STOCK_LIST}
        logger.debug(f"Valid symbols: {valid_symbols}")
        #valid_symbols = {item["symbol"].upper() for item in market_data if "symbol" in item}
        investment_amount = preferences.get("investment_amount", float('inf'))

        for attempt in range(3):
            try:
                logger.info(f"Attempt {attempt + 1}: Selecting best recommendation")
                prompt = f"""
    You are a stock market expert tasked with selecting the best stock recommendation from a list.
    User Preferences: {preferences}
    Market Data: {market_data}
    Recommendations: {recommendations}

    Evaluate each recommendation based on:
    - Alignment with user preferences (risk appetite, investment goals, time horizon, investment style).
    - Recommendation attributes: Score (0-100), Reason, Caution, NewsSentiment.
    - Market data: Stock price, P/E ratio, debt-to-equity ratio, financial health.
    - For 'Buy' actions, ensure total cost (Quantity * price) <= investment_amount ({investment_amount}).

    Select the single best recommendation that maximizes alignment with preferences while balancing risk and reward.
    Provide the selected recommendation as a JSON object (copy the original recommendation dictionary exactly).
    Include a brief explanation (2-3 sentences) in the 'SelectionReason' key explaining why this recommendation was chosen.

    Return the response as a valid JSON object wrapped in ```json``` delimiters, with keys: SelectedRecommendation, SelectionReason.
    Ensure the JSON is properly formatted with correct syntax, including balanced braces and quotes.
    Example:
    ```json
    {{
        "SelectedRecommendation": {{
            "Symbol": "AAPL",
            "Company": "Apple Inc.",
            "Action": "Buy",
            "Quantity": 2,
            "Reason": "Strong cash flow, low debt-to-equity (0.5), and positive news support growth.",
            "Caution": "High P/E (30) may limit upside.",
            "NewsSentiment": "Positive",
            "Score": 85
        }},
        "SelectionReason": "Selected AAPL due to its high score, strong financials, and alignment with the user's low-risk appetite and long-term growth goals."
    }}
    ```
    **Important**: Return only valid JSON wrapped in ```json``` delimiters. Do not include additional text outside the JSON. Verify total cost for 'Buy' actions and ensure the selected recommendation is copied exactly from the provided list.
    """
                response = self.llm.invoke(prompt)
                raw_response = response.content.strip()
                logger.debug(f"Raw LLM response for selection (attempt {attempt + 1}): {raw_response}")

                # Extract JSON
                json_match = re.search(r'```json\s*(.*?)\s*```', raw_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    # Try finding JSON object or array
                    json_start = min(raw_response.find('{'), raw_response.find('['))
                    json_end = max(raw_response.rfind('}') + 1, raw_response.rfind(']') + 1)
                    if json_start != -1 and json_end != 0 and json_start < json_end:
                        json_str = raw_response[json_start:json_end].strip()
                        logger.warning(f"Attempt {attempt + 1}: No JSON delimiters, extracted raw JSON: {json_str}")
                    else:
                        # Try to find any JSON-like content
                        json_str = raw_response.strip()
                        if not (json_str.startswith('{') or json_str.startswith('[')):
                            json_str = '{' + json_str + '}' if 'SelectedRecommendation' in json_str else json_str
                        logger.error(f"Attempt {attempt + 1}: No JSON block found, attempting to parse: {json_str}")
                        if attempt < 2:
                            time.sleep(5 * (2 ** attempt))
                            continue
                        return {}

                try:
                    result = json.loads(json_str)
                    if not isinstance(result, dict) or "SelectedRecommendation" not in result or "SelectionReason" not in result:
                        raise ValueError("Invalid response format")
                    
                    selected_rec = result["SelectedRecommendation"]
                    if not all(key in selected_rec for key in ["Symbol", "Company", "Action", "Quantity", "Reason", "Caution", "NewsSentiment", "Score"]):
                        raise ValueError(f"Invalid recommendation format: {selected_rec}")
                    if selected_rec["Symbol"].upper() not in valid_symbols:
                        raise ValueError(f"Invalid symbol {selected_rec['Symbol']}")
                    if selected_rec["Action"] not in ["Buy", "Sell", "Hold"]:
                        raise ValueError(f"Invalid action {selected_rec['Action']}")
                    if selected_rec["Quantity"] < 0 or selected_rec["Quantity"] > 50:
                        raise ValueError(f"Invalid quantity {selected_rec['Quantity']}")
                    if not isinstance(selected_rec["Score"], (int, float)) or selected_rec["Score"] < 0 or selected_rec["Score"] > 100:
                        raise ValueError(f"Invalid score {selected_rec['Score']}")
                    if selected_rec["Action"] == "Buy":
                        price = next((item["price"] for item in market_data if item["symbol"].upper() == selected_rec["Symbol"].upper()), 0.0)
                        total_cost = selected_rec["Quantity"] * price
                        if total_cost > investment_amount:
                            raise ValueError(f"Total cost {total_cost} for {selected_rec['Symbol']} exceeds investment_amount {investment_amount}")

                    logger.info(f"Successfully selected recommendation: {selected_rec['Symbol']}")
                    return selected_rec
                except json.JSONDecodeError as e:
                    logger.error(f"Attempt {attempt + 1}: Failed to parse JSON: {str(e)}, raw response: {raw_response}")
                    if attempt < 2:
                        time.sleep(5 * (2 ** attempt))
                        continue
                    return {}
                except ValueError as e:
                    logger.error(f"Attempt {attempt + 1}: Invalid format: {str(e)}, raw response: {raw_response}")
                    if attempt < 2:
                        time.sleep(5 * (2 ** attempt))
                        continue
                    return {}
            except Exception as e:
                if "429" in str(e):
                    logger.error(f"Attempt {attempt + 1}: Rate limit exceeded (429)")
                    if attempt < 2:
                        time.sleep(10 * (2 ** attempt))
                        continue
                logger.error(f"Attempt {attempt + 1}: Failed to select recommendation: {str(e)}, raw response: {raw_response}")
                if attempt < 2:
                    time.sleep(5 * (2 ** attempt))
                    continue
                return {}
        logger.error("All attempts to select recommendation failed")
        return {}