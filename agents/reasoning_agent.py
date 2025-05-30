from decimal import Decimal
from langchain_groq import ChatGroq
from utils.config import GROQ_API_KEY
from utils.logger import logger
from typing import List, Dict, Tuple
import json
import time
import decimal
import math
import re

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
                # Clean up common issues in the response
                cleaned_response = response
                
                # Remove any markdown code block markers
                cleaned_response = re.sub(r'```json\s*|\s*```', '', cleaned_response)
                
                # Try to find the first complete JSON object
                start_idx = cleaned_response.find('{')
                if start_idx != -1:
                    # Track brackets to find matching end
                    stack = []
                    in_string = False
                    escape_char = False
                    
                    for i in range(start_idx, len(cleaned_response)):
                        char = cleaned_response[i]
                        
                        # Handle escape characters
                        if char == '\\' and not escape_char:
                            escape_char = True
                            continue
                        
                        # Handle strings
                        if char == '"' and not escape_char:
                            in_string = not in_string
                        
                        # Track brackets only when not in a string
                        if not in_string:
                            if char == '{':
                                stack.append(char)
                            elif char == '}':
                                if stack:
                                    stack.pop()
                                    # If we've found the matching end brace
                                    if not stack:
                                        try:
                                            json_str = cleaned_response[start_idx:i+1]
                                            parsed = json.loads(json_str)
                                            logger.info("Successfully parsed JSON after cleanup")
                                            return parsed
                                        except json.JSONDecodeError:
                                            logger.warning("Failed to parse extracted JSON object")
                                            # Continue searching in case there are more JSON objects
                                            continue
                        
                        escape_char = False
                
                # If we haven't found a valid JSON object yet, try a more aggressive cleanup
                # Remove all whitespace and newlines outside of strings
                cleaned_response = re.sub(r'\s+(?=(?:[^"]*"[^"]*")*[^"]*$)', '', cleaned_response)
                
                # Try one more time with the aggressively cleaned response
                try:
                    start_idx = cleaned_response.find('{')
                    end_idx = cleaned_response.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        json_str = cleaned_response[start_idx:end_idx + 1]
                        return json.loads(json_str)
                except:
                    pass
                
                # If all else fails, create a basic structure
                logger.warning("Could not parse JSON response, creating basic structure")
                return {
                    "error": "Failed to parse response",
                    "raw_response": response,
                    "recommendations": [],
                    "insights": "Analysis failed to generate valid insights.",
                    "market_analysis": {},
                    "investment_strategy": {}
                }
            except Exception as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                return {
                    "error": "Failed to parse response",
                    "raw_response": response,
                    "recommendations": [],
                    "insights": "Analysis failed to generate valid insights.",
                    "market_analysis": {},
                    "investment_strategy": {}
                }

    def _get_thinking_process(self, preferences: Dict) -> List[str]:
        """Capture the model's inner thought process with detailed numerical analysis."""
        # Get current price data for calculations
        try:
            from scripts.fetch_stock_prices import fetch_stock_prices
            stock_data = fetch_stock_prices()
        except Exception as e:
            logger.error(f"Failed to fetch stock prices for thinking process: {str(e)}")
            stock_data = {}

        investment_amount = self._convert_to_float(preferences.get('investment_amount', 0.0))
        
        thinking_prompt = f"""You are an expert investment advisor. Think through the investment scenario step by step, sharing your detailed inner monologue with specific numerical analysis.

User Preferences: {json.dumps(preferences, indent=2)}
Available Investment Amount: ${investment_amount:.2f}

Current Market Data:
{json.dumps({symbol: {"price": data.get("current_price", 0.0)} for symbol, data in stock_data.items()}, indent=2)}

I want you to think through this investment scenario in great detail, sharing your complete thought process with specific numerical calculations and practical considerations. Imagine you're explaining your thinking to a colleague. Consider:

1. Initial Portfolio Analysis:
   - How many shares of different stocks could we buy with ${investment_amount:.2f}?
   - What would be the optimal allocation percentages?
   - How should we divide the investment across different risk levels?

2. Risk-Return Calculations:
   - Calculate potential returns under different scenarios
   - Analyze historical volatility and price ranges
   - Consider risk-adjusted return metrics

3. Investment Strategy Formation:
   - Calculate specific position sizes and entry points
   - Analyze price-to-earnings ratios and other metrics
   - Consider dollar-cost averaging vs. lump sum investment

4. Market Context & Valuation:
   - Compare current prices to moving averages
   - Analyze sector-specific metrics and trends
   - Calculate relative valuations between similar stocks

5. Practical Implementation:
   - Calculate exact number of shares for each recommendation
   - Consider transaction costs and timing
   - Plan for rebalancing and adjustment triggers

Format your response as a detailed stream of consciousness, with each thought starting with "🤔 Thinking: ".
Be thorough and include specific numbers, calculations, and percentages in your reasoning.

Example format:
🤔 Thinking: With an investment amount of $10,000 and AAPL trading at $150, we could buy approximately 66 shares. However, given the user's risk profile of 'low', we should probably allocate only 30% ($3,000) to any single stock...
🤔 Thinking: Looking at the P/E ratios, MSFT at 35x earnings is trading at a premium to the sector average of 28x. This suggests we might want to limit our position size to 20% of the portfolio, or about $2,000...
🤔 Thinking: The user's time horizon of 5 years means we can withstand some volatility. If we assume a conservative 8% annual return, the $10,000 investment could grow to approximately $14,693 over 5 years...

Make each thought detailed and complete, explaining your full reasoning process with specific numbers and calculations. Don't just state what you're thinking, but explain WHY you're thinking it and how the numbers support your reasoning.

Return ONLY the list of thoughts, no other text."""

        try:
            response = self.llm.invoke(thinking_prompt)
            thoughts = [line.strip() for line in response.content.split('\n') if line.strip().startswith('🤔')]
            if not thoughts:
                return ["🤔 Thinking: Starting detailed investment analysis with numerical calculations..."]
            
            # Ensure we have at least 5 detailed thoughts
            if len(thoughts) < 5:
                logger.warning("Generated fewer than 5 thoughts, requesting more detailed analysis")
                # Try one more time with explicit request for more detail
                response = self.llm.invoke(thinking_prompt + "\n\nPlease provide at least 5 detailed thoughts with specific numerical analysis.")
                thoughts = [line.strip() for line in response.content.split('\n') if line.strip().startswith('🤔')]
            
            return thoughts
        except Exception as e:
            logger.error(f"Failed to generate thinking process: {str(e)}")
            return ["🤔 Thinking: Starting detailed investment analysis with numerical calculations..."]

    def analyze_investment_scenario(self, preferences: Dict, is_trade: bool = False) -> Tuple[List[Dict], str, List[str], List[str]]:
        """
        Perform a detailed analysis of the investment scenario with step-by-step reasoning.
        Returns: (recommendations, insights, reasoning_steps, thinking_process)
        """
        reasoning_steps = []
        thinking_process = self._get_thinking_process(preferences)
        
        try:
            # Fetch current stock data
            from scripts.fetch_stock_prices import fetch_stock_prices
            stock_data = fetch_stock_prices()
            
            # Add investment amount to prompt for better quantity calculation
            investment_amount = self._convert_to_float(preferences.get('investment_amount', 0.0))
            reasoning_steps.append(f"Investment amount specified: ${investment_amount:.2f}")
            
            # Combined analysis prompt that includes initial analysis, market context, and recommendations
            comprehensive_prompt = f"""You are an expert investment advisor performing a detailed market analysis and generating recommendations.

IMPORTANT: You must return ONLY a valid JSON object with no additional text, comments, or explanations.
ANY TEXT OUTSIDE THE JSON OBJECT WILL CAUSE ERRORS.

Input Parameters:
- User Preferences: {json.dumps(preferences, indent=2)}
- Investment Budget: ${investment_amount:.2f}
- Current Market Data: {json.dumps({symbol: {"price": data.get("current_price", 0.0)} for symbol, data in stock_data.items()}, indent=2)}
- Allowed Stocks: {json.dumps(self.ALLOWED_STOCKS)}

Required JSON Structure:
{{
    "market_analysis": {{
        "market_summary": {{
            "current_state": "Detailed market state with specific metrics and trends",
            "key_indices": {{
                "SP500": "Current level, YTD performance, key support/resistance levels, and trend analysis",
                "NASDAQ": "Current level, YTD performance, sector weightings, and momentum indicators",
                "VIX": "Current level, historical context, and volatility trend analysis",
                "market_breadth": "Advance/decline ratio, new highs vs lows, and market internals",
                "sector_rotation": "Current sector leadership and rotation trends"
            }},
            "market_sentiment": "Detailed sentiment analysis with specific indicators (Fear & Greed, Put/Call ratio, etc.)",
            "technical_overview": {{
                "short_term_trend": "Detailed analysis of 10-20 day price action",
                "medium_term_trend": "50-day moving average analysis and market structure",
                "long_term_trend": "200-day moving average and major trend analysis",
                "momentum_indicators": "RSI, MACD, and other key technical signals",
                "volume_analysis": "Trading volume trends and significant levels"
            }}
        }},
        "economic_indicators": {{
            "gdp_growth": "Latest GDP figures with detailed breakdown and forward projections",
            "inflation_rate": "CPI, PPI, and core inflation metrics with trend analysis",
            "interest_rates": "Federal funds rate, yield curve analysis, and future rate expectations",
            "employment_data": "Latest employment statistics, wage growth, and labor market trends",
            "consumer_metrics": {{
                "consumer_confidence": "Latest readings and trend analysis",
                "retail_sales": "Recent data and forward-looking indicators",
                "housing_market": "Housing starts, sales, and price trends",
                "personal_income": "Income growth and spending patterns"
            }},
            "business_metrics": {{
                "manufacturing": "PMI and industrial production data",
                "services": "Services PMI and business activity indices",
                "corporate_profits": "Earnings trends and projections",
                "capex_trends": "Capital expenditure and investment trends"
            }}
        }},
        "sector_analysis": {{
            "technology": {{
                "performance": "Detailed YTD and relative performance metrics",
                "key_drivers": ["Specific growth catalysts", "Market share analysis", "Innovation trends"],
                "risks": ["Detailed regulatory risks", "Competition analysis", "Market-specific challenges"],
                "opportunities": ["Growth areas", "Merger & acquisition activity", "New market potential"],
                "subsector_trends": ["Software", "Hardware", "Semiconductors", "Cloud Computing"],
                "valuation_metrics": {{
                    "average_pe": "Sector P/E ratio compared to historical average",
                    "revenue_growth": "Sector revenue growth rate",
                    "profit_margins": "Sector profit margin trends",
                    "cash_flow_metrics": "Free cash flow yield and trends"
                }}
            }},
            "healthcare": {{
                "performance": "Detailed YTD and relative performance metrics",
                "key_drivers": ["Demographics", "Innovation", "Policy changes", "Market expansion"],
                "risks": ["Regulatory environment", "Pricing pressures", "Research & development risks"],
                "opportunities": ["New treatments", "Market expansion", "Technology integration"],
                "subsector_trends": ["Biotech", "Pharmaceuticals", "Medical Devices", "Healthcare Services"],
                "valuation_metrics": {{
                    "average_pe": "Sector P/E ratio compared to historical average",
                    "revenue_growth": "Sector revenue growth rate",
                    "profit_margins": "Sector profit margin trends",
                    "cash_flow_metrics": "Free cash flow yield and trends"
                }}
            }}
        }},
        "global_factors": {{
            "geopolitical_events": ["Major political developments", "Trade relations", "Regional conflicts"],
            "currency_markets": {{
                "dollar_strength": "USD index trend analysis",
                "major_pairs": "EUR, JPY, GBP movement analysis",
                "impact": "Effect on corporate earnings"
            }},
            "commodity_markets": {{
                "oil_prices": "Current trends and impact analysis",
                "precious_metals": "Gold and silver price trends",
                "industrial_metals": "Copper and other base metals analysis"
            }},
            "international_markets": {{
                "emerging_markets": "Performance and trend analysis",
                "developed_markets": "Major market performance",
                "global_trade": "Trade volume and trend analysis"
            }}
        }}
    }},
    "investment_strategy": {{
        "allocation_plan": {{
            "recommended_splits": "Detailed allocation percentages with rationale",
            "rationale": "Comprehensive strategy explanation with market context",
            "risk_management": "Specific risk mitigation strategies and stop-loss levels"
        }},
        "entry_strategy": {{
            "timing": "Specific entry points with technical levels",
            "position_sizing": "Detailed position size calculations",
            "price_targets": "Multiple price targets with rationale"
        }},
        "portfolio_impact": {{
            "diversification": "Impact on portfolio diversification",
            "risk_metrics": "Beta, Sharpe ratio, and other risk measures",
            "correlation_analysis": "Correlation with existing holdings"
        }}
    }},
    "recommendations": [
        {{
            "Symbol": "string (must be from allowed list)",
            "Company": "string",
            "Action": "Buy or Sell",
            "Quantity": "number",
            "CurrentPrice": "number",
            "TotalCost": "number",
            "Reason": "string",
            "Caution": "string",
            "NewsSentiment": "Positive/Negative/Neutral",
            "Score": "number (0-100)",
            "Metrics": {{
                "PE_Ratio": "string",
                "PEG_Ratio": "string",
                "Debt_to_Equity": "string",
                "Quick_Ratio": "string",
                "Profit_Margin": "string",
                "Revenue_Growth": "string"
            }},
            "Technical_Analysis": {{
                "MA_Status": "string",
                "RSI": "string",
                "Volume_Analysis": "string",
                "Support_Resistance": ["string"]
            }},
            "Analyst_Consensus": {{
                "Buy_Ratings": "number",
                "Hold_Ratings": "number",
                "Sell_Ratings": "number",
                "Price_Targets": {{
                    "Low": "number",
                    "High": "number",
                    "Average": "number"
                }}
            }},
            "Risk_Assessment": {{
                "Volatility": "Beta and historical volatility metrics",
                "Liquidity": "Average daily volume and spread analysis",
                "Company_Specific": ["Key company risks"],
                "Industry_Position": "Market share and competitive analysis"
            }}
        }}
    ],
    "insights": "Comprehensive market insight summary with specific data points and actionable conclusions"
}}

REQUIREMENTS:
1. Return ONLY the JSON object above
2. Do not include any text before or after the JSON
3. Do not use markdown code blocks
4. Ensure all numeric fields are actual numbers, not strings
5. Ensure all arrays are properly closed
6. Ensure all objects have matching braces
7. Use only the allowed stock symbols
8. Include exactly 3 recommendations
9. Format all currency values as numbers without $ signs
10. Use proper JSON syntax with double quotes for strings

The response must be a single, valid JSON object that can be parsed by json.loads().
"""

            response = self.llm.invoke(comprehensive_prompt)
            complete_analysis = self._parse_json_response(response.content)

            # Extract components from the comprehensive analysis
            recommendations = complete_analysis.get("recommendations", [])
            insights = complete_analysis.get("insights", "Analysis failed to generate insights.")
            
            # Validate recommendations
            validated_recommendations = []
            required_fields = {
                "Symbol": "",
                "Company": "Unknown Company",
                "Action": "None",
                "Quantity": 0,
                "CurrentPrice": 0.0,
                "TotalCost": 0.0,
                "Reason": "No reason provided",
                "Caution": "No caution provided",
                "NewsSentiment": "Neutral",
                "Score": 0
            }
            
            for rec in recommendations:
                try:
                    # Create a new recommendation with all required fields
                    validated_rec = {field: rec.get(field, default) for field, default in required_fields.items()}
                    
                    # Convert numeric fields to proper types
                    try:
                        validated_rec["Score"] = int(float(str(validated_rec["Score"]).replace(',', '')))
                        validated_rec["Quantity"] = self._convert_to_float(validated_rec["Quantity"])
                        validated_rec["CurrentPrice"] = self._convert_to_float(validated_rec["CurrentPrice"])
                        validated_rec["TotalCost"] = self._convert_to_float(validated_rec["TotalCost"])
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error converting numeric fields: {str(e)}")
                        continue
                    
                    # Validate stock symbol
                    if validated_rec["Symbol"] not in self.ALLOWED_STOCKS:
                        logger.error(f"Model suggested invalid stock: {validated_rec['Symbol']}. Must be one of: {', '.join(self.ALLOWED_STOCKS)}")
                        continue

                    # Get current price and validate quantity
                    current_price = self._get_current_price(validated_rec["Symbol"])
                    quantity = validated_rec["Quantity"]
                    total_cost = current_price * quantity

                    if current_price <= 0:
                        logger.error(f"Invalid price for {validated_rec['Symbol']}: {current_price}")
                        continue

                    if quantity <= 0:
                        logger.error(f"Invalid quantity for {validated_rec['Symbol']}: {quantity}")
                        continue

                    if total_cost > investment_amount:
                        # Adjust quantity to fit investment amount
                        quantity = math.floor((investment_amount / current_price) * 100) / 100  # Round to 2 decimal places
                        logger.info(f"Adjusted quantity for {validated_rec['Symbol']} from {validated_rec['Quantity']} to {quantity} to fit investment amount")

                    # Update the recommendation with validated values
                    validated_rec.update({
                        "CurrentPrice": current_price,
                        "TotalCost": total_cost,
                        "Quantity": quantity
                    })

                    # Validate score and other fields after type conversion
                    score = validated_rec["Score"]
                    if not isinstance(score, (int, float)):
                        logger.error(f"Invalid score type: {type(score)}")
                        continue
                        
                    if not (0 <= score <= 100):
                        logger.error(f"Score out of range: {score}")
                        continue
                        
                    if validated_rec["Action"] not in ["Buy", "Sell"]:
                        logger.error(f"Invalid action: {validated_rec['Action']}")
                        continue
                        
                    if validated_rec["NewsSentiment"] not in ["Positive", "Negative", "Neutral"]:
                        logger.error(f"Invalid sentiment: {validated_rec['NewsSentiment']}")
                        continue
                        
                    validated_recommendations.append(validated_rec)
                except Exception as e:
                    logger.error(f"Error validating recommendation: {str(e)}")
                    continue

            if not validated_recommendations:
                validated_recommendations = [{
                    "Symbol": "ERROR",
                    "Company": "Error in Recommendation",
                    "Action": "None",
                    "Quantity": 0,
                    "CurrentPrice": 0.0,
                    "TotalCost": 0.0,
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
            return validated_recommendations, insights, reasoning_steps, thinking_process

        except Exception as e:
            logger.error(f"Reasoning analysis failed: {str(e)}")
            return [], "Analysis failed due to technical issues.", reasoning_steps, thinking_process

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
            reasoning_steps.append("✓ Performing comprehensive trade validation...")
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

Important:
1. Format all numbers with proper spacing
2. Use clear bullet points for lists
3. Keep all text on one line for each point
4. Avoid special characters that might break formatting
5. Use simple punctuation (periods, commas)
6. Format prices as "$X.XX"
7. Use clear line breaks between sections

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

            def format_list(items: List[str]) -> str:
                """Format a list of items with proper line breaks and bullets."""
                return "\\n".join(f"• {item.strip()}" for item in items if item.strip())

            # Compile explanation based on the comprehensive analysis
            if is_valid:
                execution = validation_result.get("execution", {}).get("execution_strategy", {})
                explanation = f"""🎯 Trade Validation Summary:
Confidence Score: {validation.get('confidence', 'N/A')}/100

Primary Reasons:
{format_list(validation.get('primary_reasons', []))}

Key Concerns:
{format_list(validation.get('concerns', []))}

Execution Strategy:
Entry Points:
{format_list(execution.get('entry_points', []))}

Risk Management:
• Stop Loss: {execution.get('risk_management', {}).get('stop_loss', 'Not specified')}
• Take Profit: {execution.get('risk_management', {}).get('take_profit', 'Not specified')}

Monitoring Points:
{format_list(execution.get('monitoring', []))}"""
            else:
                explanation = f"""❌ Trade Rejected:

Reasons:
{format_list(validation.get('primary_reasons', ['Invalid trade']))}

Suggested Changes:
• Quantity: {validation.get('modifications', {}).get('quantity', 'No suggestion')}
• Timing: {validation.get('modifications', {}).get('timing', 'No suggestion')}

Key Concerns:
{format_list(validation.get('concerns', []))}"""

            # Clean up the explanation text
            explanation = (explanation
                         .replace('\n\n\n', '\n\n')  # Remove extra line breaks
                         .replace('•  ', '• ')       # Fix bullet point spacing
                         .replace('\\n', '\n')       # Replace escaped newlines
                         .strip())                   # Remove trailing whitespace

            # Update reasoning steps
            reasoning_steps.append(explanation)
            reasoning_steps.extend([
                "✓ Completed comprehensive trade validation",
                "✓ Analyzed risk and market conditions",
                "✓ Generated execution strategy" if is_valid else "✓ Identified validation issues"
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