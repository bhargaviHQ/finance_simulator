from decimal import Decimal
from langchain_groq import ChatGroq
from utils.config import GROQ_API_KEY
from utils.logger import logger
from typing import List, Dict, Tuple
import json
import time
import decimal
import math

class ReasoningAgent:
    def __init__(self):
        # Using deepseek-coder for better reasoning capabilities
        self.llm = ChatGroq(model_name="deepseek-r1-distill-llama-70b", api_key=GROQ_API_KEY)
        # Define allowed stocks
        self.ALLOWED_STOCKS = [
            "UNH", "TSLA", "QCOM", "ORCL", "NVDA", "NFLX", "MSFT", "META", "LLY", "JNJ",
            "INTC", "IBM", "GOOGL", "GM", "F", "CSCO", "AMZN", "AMD", "ADBE", "AAPL"
        ]

    def _convert_to_float(self, value) -> float:
        """Safely convert a value to float, handling Decimal types."""
        try:
            if isinstance(value, Decimal):
                return float(value)
            elif isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                # Remove commas and convert to float
                return float(value.replace(',', ''))
            return 0.0
        except (ValueError, TypeError, decimal.InvalidOperation):
            return 0.0

    def _safe_numeric_operation(self, value1, value2, operation: str) -> float:
        """Safely perform numeric operations between values that might be Decimal or float."""
        try:
            # Convert both values to float
            float1 = self._convert_to_float(value1)
            float2 = self._convert_to_float(value2)
            
            if operation == 'multiply':
                return float1 * float2
            elif operation == 'divide':
                return float1 / float2 if float2 != 0 else 0.0
            elif operation == 'add':
                return float1 + float2
            elif operation == 'subtract':
                return float1 - float2
            else:
                return 0.0
        except Exception as e:
            logger.error(f"Error in numeric operation: {str(e)}")
            return 0.0

    def _get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol, handling different data types."""
        try:
            from scripts.fetch_stock_prices import fetch_stock_prices
            stock_data = fetch_stock_prices()
            price_data = stock_data.get(symbol, {})
            current_price = price_data.get("current_price", 0.0)
            return self._convert_to_float(current_price)
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {str(e)}")
            return 0.0

    def _parse_json_response(self, response: str) -> Dict:
        """Safely parse JSON response from the model."""
        try:
            # First try direct JSON parsing
            return json.loads(response)
        except json.JSONDecodeError:
            try:
                # Look for JSON-like content between triple backticks
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                
                # Look for content between curly braces
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
                
                # If still no valid JSON, create a basic structure
                logger.warning("Could not parse JSON response, creating basic structure")
                return {"analysis": response}
            except Exception as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return {"error": "Failed to parse response", "raw_response": response}

    def analyze_investment_scenario(self, preferences: Dict, is_trade: bool = False) -> Tuple[List[Dict], str, List[str]]:
        """
        Perform a detailed analysis of the investment scenario with step-by-step reasoning.
        Returns: (recommendations, insights, reasoning_steps)
        """
        reasoning_steps = []
        
        try:
            # Add investment amount to prompt for better quantity calculation
            investment_amount = self._convert_to_float(preferences.get('investment_amount', 0.0))
            reasoning_steps.append(f"Investment amount specified: ${investment_amount:.2f}")
            
            # Combined analysis prompt that includes initial analysis, market context, and recommendations
            comprehensive_prompt = f"""You are an expert investment advisor performing a detailed market analysis and generating recommendations.

Context:
User Preferences: {json.dumps(preferences, indent=2)}
Investment Budget: ${investment_amount:.2f} (This is the maximum amount available for investment)

STRICT STOCK SELECTION RULES:
You MUST ONLY select from these exact stock symbols - no exceptions:
{', '.join(self.ALLOWED_STOCKS)}

Each recommended stock MUST be from this list. Any other stocks will be rejected.

QUANTITY CALCULATION RULES:
1. Calculate the optimal number of shares based on the current stock price and investment amount
2. The total cost (quantity * price) MUST NOT exceed the investment amount
3. Aim to use a significant portion of the investment amount while staying within limits
4. Consider stock price volatility when deciding quantity
5. Round quantity to 2 decimal places for fractional shares

Task 1 - Initial Analysis:
Analyze the user preferences and provide a detailed assessment in this format:
{{
    "risk_profile": {{
        "assessment": "Detailed risk assessment",
        "alignment": "How preferences align with risk",
        "concerns": ["List of risk-related concerns"]
    }},
    "timeline_analysis": {{
        "implications": "Investment timeline implications",
        "milestones": ["Key timeline considerations"],
        "constraints": ["Any timing constraints"]
    }},
    "goal_alignment": {{
        "primary_goals": ["List of main goals"],
        "strategy_fit": "How well current market aligns",
        "adjustments": ["Needed adjustments"]
    }}
}}

Task 2 - Market Analysis:
Based on the initial analysis, evaluate current market conditions in this format:
{{
    "market_overview": {{
        "sentiment": "Overall market sentiment",
        "trends": ["Key market trends"],
        "economic_indicators": ["Important indicators"]
    }},
    "sector_analysis": {{
        "strong_sectors": ["List with reasons"],
        "weak_sectors": ["List with reasons"],
        "opportunities": ["Emerging opportunities"]
    }},
    "risk_factors": {{
        "market_risks": ["Current market risks"],
        "sector_risks": ["Sector-specific risks"],
        "mitigation_strategies": ["Risk mitigation approaches"]
    }}
}}

Task 3 - Stock Recommendations:
Generate EXACTLY 3 recommendations using ONLY these allowed symbols: {', '.join(self.ALLOWED_STOCKS)}
For each recommendation:
1. Get current stock price
2. Calculate maximum possible shares = investment_amount / current_price
3. Determine optimal quantity considering:
   - Market volatility
   - Risk profile
   - Investment goals
   - Round to 2 decimal places

Format each recommendation as:
[
    {{
        "Symbol": "MUST be one of the allowed symbols listed above",
        "Company": "Full company name",
        "Action": "Buy or Sell",
        "Quantity": "Calculated optimal number of shares based on investment amount",
        "CurrentPrice": "Current stock price",
        "TotalCost": "Quantity * CurrentPrice (must be <= investment_amount)",
        "Reason": "Clear, specific reasoning including quantity justification",
        "Caution": "Specific risk factors",
        "NewsSentiment": "Positive/Negative/Neutral",
        "Score": "0-100 numeric score"
    }}
]

CRITICAL: Each Symbol MUST be one of: {', '.join(self.ALLOWED_STOCKS)}
Any other symbols will be rejected automatically.

Task 4 - Market Insights:
Provide a comprehensive market insight summary focusing on:
1. How the recommendations align with user preferences
2. Current market opportunities and challenges
3. Specific action steps and monitoring points
4. Risk management strategies

Return your complete analysis as a JSON object with these exact keys:
{{
    "initial_analysis": Task 1 result,
    "market_analysis": Task 2 result,
    "recommendations": Task 3 result,
    "insights": "Task 4 result as a formatted string"
}}

FINAL VALIDATION CHECKLIST:
1. Each recommended Symbol MUST be from: {', '.join(self.ALLOWED_STOCKS)}
2. Exactly 3 recommendations required
3. All numeric values must be valid numbers
4. For each recommendation:
   - Quantity * CurrentPrice <= {investment_amount}
   - Quantity > 0
   - Quantity rounded to 2 decimal places
5. Consider user's {preferences.get('additional_preferences', '')}
6. Focus on {preferences.get('investment_style', 'balanced')} approach
7. Target {preferences.get('investment_goals', 'growth')} objectives
8. Maintain {preferences.get('risk_appetite', 'medium')} risk profile

Return ONLY the JSON object, no other text."""

            response = self.llm.invoke(comprehensive_prompt)
            complete_analysis = self._parse_json_response(response.content)

            # Extract components from the comprehensive analysis
            recommendations = complete_analysis.get("recommendations", [])
            insights = complete_analysis.get("insights", "Analysis failed to generate insights.")
            
            # Validate recommendations
            validated_recommendations = []
            required_fields = ["Symbol", "Company", "Action", "Quantity", "Reason", "Caution", "NewsSentiment", "Score"]
            
            for rec in recommendations:
                if all(field in rec for field in required_fields):
                    try:
                        # Validate stock symbol
                        if rec["Symbol"] not in self.ALLOWED_STOCKS:
                            logger.error(f"Model suggested invalid stock: {rec['Symbol']}. Must be one of: {', '.join(self.ALLOWED_STOCKS)}")
                            continue

                        # Get current price and validate quantity
                        current_price = self._get_current_price(rec["Symbol"])
                        quantity = self._convert_to_float(rec["Quantity"])
                        total_cost = current_price * quantity

                        if current_price <= 0:
                            logger.error(f"Invalid price for {rec['Symbol']}: {current_price}")
                            continue

                        if quantity <= 0:
                            logger.error(f"Invalid quantity for {rec['Symbol']}: {quantity}")
                            continue

                        if total_cost > investment_amount:
                            # Adjust quantity to fit investment amount
                            quantity = math.floor((investment_amount / current_price) * 100) / 100  # Round to 2 decimal places
                            logger.info(f"Adjusted quantity for {rec['Symbol']} from {rec['Quantity']} to {quantity} to fit investment amount")
                            rec["Quantity"] = quantity
                            total_cost = current_price * quantity

                        rec["CurrentPrice"] = current_price
                        rec["TotalCost"] = total_cost
                        rec["Quantity"] = quantity

                        if (0 <= rec["Score"] <= 100 and
                            rec["Action"] in ["Buy", "Sell"] and
                            rec["NewsSentiment"] in ["Positive", "Negative", "Neutral"]):
                            validated_recommendations.append(rec)
                        else:
                            logger.warning(f"Skipping recommendation with invalid values: {rec}")
                    except Exception as e:
                        logger.error(f"Error validating recommendation: {str(e)}")
                        continue
                else:
                    logger.warning(f"Skipping invalid recommendation missing required fields: {rec}")

            if not validated_recommendations:
                validated_recommendations = [{
                    "Symbol": "ERROR",
                    "Company": "Error in Recommendation",
                    "Action": "None",
                    "Quantity": 0,
                    "Reason": "Failed to generate valid recommendation",
                    "Caution": "Please try again",
                    "NewsSentiment": "Neutral",
                    "Score": 0
                }]

            # Update reasoning steps
            reasoning_steps.extend([
                "✅ Completed initial preference and risk assessment",
                "✅ Analyzed market conditions and sector performance",
                f"✅ Generated {len(validated_recommendations)} validated recommendations"
            ])
            for rec in validated_recommendations:
                formatted_output = (
                        f"🧩 {rec['Company']} ({rec['Symbol']})\n"
                        f"  - Action: {rec['Action']}\n"
                        f"  - Current Price: ${rec['CurrentPrice']:.2f}\n"
                        f"  - Quantity: {rec['Quantity']}\n"
                        f"  - Total Cost: ${rec['TotalCost']:.2f}\n"
                        f"  - Reason: {rec['Reason']}\n"
                        f"  - Caution: {rec['Caution']}\n"
                        f"  - News Sentiment: {rec['NewsSentiment']}\n"
                        f"  - Score: {rec['Score']}\n"
                    )
                reasoning_steps.append(formatted_output)
            reasoning_steps.extend([
                "✅ Validated investment amounts and share quantities",
                "✅ Compiled final market insights and guidance"
            ])
            return validated_recommendations, insights, reasoning_steps

        except Exception as e:
            logger.error(f"Reasoning analysis failed: {str(e)}")
            return [], "Analysis failed due to technical issues.", reasoning_steps

    def validate_trade(self, recommendation: Dict, preferences: Dict) -> Tuple[bool, str, List[str]]:
        """
        Validate a specific trade recommendation with detailed reasoning steps.
        Returns: (is_valid, explanation, reasoning_steps)
        """
        reasoning_steps = []
        
        try:
            # Validate stock symbol first
            if recommendation["Symbol"] not in self.ALLOWED_STOCKS:
                return False, f"Invalid stock symbol: {recommendation['Symbol']} is not in the allowed list", reasoning_steps

            # Validate trade amount
            current_price = self._get_current_price(recommendation["Symbol"])
            if current_price <= 0:
                return False, f"Could not get valid price for {recommendation['Symbol']}", reasoning_steps

            quantity = self._convert_to_float(recommendation["Quantity"])
            total_cost = current_price * quantity

            if recommendation["Action"].lower() == "buy":
                max_investment = self._convert_to_float(preferences.get("investment_amount", float('inf')))
                if total_cost > max_investment:
                    return False, f"Total cost (${total_cost:.2f}) exceeds investment amount (${max_investment:.2f})", reasoning_steps

            # Combined trade validation prompt
            reasoning_steps.append("✅ Performing comprehensive trade validation...")
            validation_prompt = f"""You are an expert trading advisor performing a complete trade validation analysis.

Context:
Trade Details: {json.dumps(recommendation, indent=2)}
User Preferences: {json.dumps(preferences, indent=2)}
Allowed Stocks: {json.dumps(self.ALLOWED_STOCKS, indent=2)}

Perform a comprehensive trade validation analysis covering:

Task 1 - Risk and Market Analysis:
{{
    "risk_assessment": {{
        "score": "1-100 numeric risk score",
        "factors": ["Risk factors"],
        "alignment": "Risk alignment analysis",
        "market_conditions": "Current market state",
        "technical_indicators": ["Key technical signals"]
    }},
    "portfolio_impact": {{
        "diversification": "Impact on portfolio diversity",
        "sector_exposure": "Sector concentration analysis",
        "volatility_impact": "Effect on portfolio volatility"
    }}
}}

Task 2 - Trade Validation:
{{
    "validation_result": {{
        "is_valid": true/false,
        "confidence": "1-100 numeric score",
        "primary_reasons": ["Main decision factors"],
        "concerns": ["Key concerns"],
        "modifications": {{
            "quantity": "Suggested quantity changes",
            "timing": "Timing recommendations",
            "conditions": ["Additional conditions"]
        }}
    }}
}}

Task 3 - Execution Plan:
{{
    "execution_strategy": {{
        "entry_points": ["Specific entry criteria"],
        "exit_points": ["Exit conditions"],
        "monitoring": ["Key metrics to watch"],
        "risk_management": {{
            "stop_loss": "Recommended stop-loss",
            "take_profit": "Profit targets",
            "position_sizing": "Size recommendations"
        }}
    }}
}}

Return your complete analysis as a JSON object with these exact keys:
{{
    "analysis": Task 1 result,
    "validation": Task 2 result,
    "execution": Task 3 result
}}

Important considerations:
- Verify the stock is in the allowed list
- Account for user's additional preferences: {preferences.get('additional_preferences', '')}
- Consider market volatility and timing
- Evaluate against user's risk tolerance
- Assess portfolio fit and diversification
- Validate quantity and price levels
- Ensure trade amount fits within investment_amount

Return ONLY the JSON object, no other text."""

            response = self.llm.invoke(validation_prompt)
            validation_result = self._parse_json_response(response.content)
            
            # Extract validation decision
            validation = validation_result.get("validation", {}).get("validation_result", {})
            is_valid = validation.get("is_valid", False)
            
            # Additional validation for trade execution
            if is_valid:
                try:
                    total_cost = current_price * quantity
                    if recommendation["Action"].lower() == "buy":
                        max_investment = self._convert_to_float(preferences.get("investment_amount", float('inf')))
                        if total_cost > max_investment:
                            is_valid = False
                            validation["concerns"].append(
                                f"Total cost (${total_cost:.2f}) exceeds investment amount (${max_investment:.2f})"
                            )
                except Exception as e:
                    logger.error(f"Error validating trade costs: {str(e)}")
            
            # Compile explanation based on the comprehensive analysis
            if is_valid:
                execution = validation_result.get("execution", {}).get("execution_strategy", {})
                explanation = f"""🥁Trade Validation Summary:
• Confidence: {validation.get('confidence', 'N/A')}/100
• Primary Reasons: {', '.join(validation.get('primary_reasons', []))}
• Key Concerns: {', '.join(validation.get('concerns', []))}

Execution Strategy:
• Entry Points: {', '.join(execution.get('entry_points', ['Not specified']))}
• Stop Loss: {execution.get('risk_management', {}).get('stop_loss', 'Not specified')}
• Take Profit: {execution.get('risk_management', {}).get('take_profit', 'Not specified')}
• Monitoring Points: {', '.join(execution.get('monitoring', ['None specified']))}"""
            else:

                explanation = f"""Trade Rejected:
• Reasons: {', '.join(validation.get('primary_reasons', ['Invalid trade']))}
• Suggested Changes:
  - Quantity: {validation.get('modifications', {}).get('quantity', 'No suggestion')}
  - Timing: {validation.get('modifications', {}).get('timing', 'No suggestion')}
• Key Concerns: {', '.join(validation.get('concerns', []))}"""

            # Update reasoning steps
            reasoning_steps.append(explanation)
            reasoning_steps.extend([
                "✅     Completed comprehensive trade validation",
                "✅ Analyzed risk and market conditions",
                "✅ Generated execution strategy" if is_valid else "Identified validation issues"
            ])

            return is_valid, explanation, reasoning_steps

        except Exception as e:
            logger.error(f"Trade validation failed: {str(e)}")
            return False, f"Validation failed: {str(e)}", reasoning_steps

    def analyze_market_conditions(self, preferences: Dict) -> Dict:
        """
        Analyze current market conditions and generate insights.
        """
        try:
            market_prompt = """Analyze current market conditions and provide detailed insights.
Return analysis in this exact JSON format:
{
    "market_sentiment": {
        "overall": "Bullish/Bearish/Neutral",
        "factors": ["List of key sentiment factors"],
        "sector_outlook": {"sector_name": "outlook"}
    },
    "risk_factors": ["List of current market risks"],
    "opportunities": ["List of current opportunities"],
    "recommendations": ["List of actionable recommendations"]
}

Return ONLY the JSON object, no other text."""

            response = self.llm.invoke(market_prompt)
            return self._parse_json_response(response.content)
        except Exception as e:
            logger.error(f"Market analysis failed: {str(e)}")
            return {
                "error": "Failed to analyze market conditions",
                "details": str(e)
            } 