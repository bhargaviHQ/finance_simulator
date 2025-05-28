from langchain_groq import ChatGroq
from utils.config import GROQ_API_KEY
from utils.logger import logger
from typing import List, Dict
import json

class GroqEnhancerAgent:
    def __init__(self):
        self.llm = ChatGroq(model_name="mixtral-8x7b-32768", api_key=GROQ_API_KEY)  # Using mixtral model as compound-beta might not be available

    def enhance_recommendations(self, recommendations: List[Dict], preferences: Dict) -> List[Dict]:
        """Enhance stock recommendations using Groq's model based on user preferences and additional details."""
        if not recommendations:
            logger.warning("No recommendations to enhance")
            return []

        additional_details = preferences.get("additional_details", "")
        if not additional_details:
            logger.info("No additional details provided, returning original recommendations")
            return recommendations

        try:
            logger.info("Enhancing recommendations with Groq")
            prompt = f"""You are an expert investment advisor. Enhance these stock recommendations based on the user's preferences and additional details.

User Preferences:
{json.dumps(preferences, indent=2)}

Current Recommendations:
{json.dumps(recommendations, indent=2)}

Task:
1. Analyze the additional details provided by the user
2. For each recommendation:
   - Enhance the "Reason" with more specific insights related to the user's additional details
   - Update the "Caution" with more personalized risk factors
   - Adjust the "Score" if needed based on alignment with additional details
3. Keep the same format but make recommendations more personalized

Return the enhanced recommendations as a JSON array with the same structure.
Each recommendation should have: Symbol, Company, Action, Quantity, Reason, Caution, NewsSentiment, Score.
"""

            response = self.llm.invoke(prompt)
            enhanced_recs = json.loads(response.content)
            logger.info("Successfully enhanced recommendations with Groq")
            
            # Validate enhanced recommendations
            for rec in enhanced_recs:
                required_keys = ["Symbol", "Company", "Action", "Quantity", "Reason", "Caution", "NewsSentiment", "Score"]
                if not all(key in rec for key in required_keys):
                    logger.error(f"Invalid enhanced recommendation format: {rec}")
                    return recommendations
                
                # Ensure Score is within bounds
                rec["Score"] = max(0, min(100, rec["Score"]))

            return enhanced_recs

        except Exception as e:
            logger.error(f"Failed to enhance recommendations with Groq: {str(e)}")
            return recommendations

    def generate_market_insights(self, preferences: Dict) -> str:
        """Generate additional market insights based on user preferences and details."""
        try:
            additional_details = preferences.get("additional_details", "")
            prompt = f"""As an investment advisor, provide brief but valuable market insights based on these preferences:

User Preferences:
{json.dumps(preferences, indent=2)}

Generate 2-3 concise paragraphs covering:
1. Market conditions relevant to the user's interests
2. Potential opportunities given their preferences
3. Key risks to watch for

Focus on practical, actionable insights that align with their investment style and goals."""

            response = self.llm.invoke(prompt)
            insights = response.content
            logger.info("Successfully generated market insights")
            return insights

        except Exception as e:
            logger.error(f"Failed to generate market insights: {str(e)}")
            return "Unable to generate market insights at this time." 