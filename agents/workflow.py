from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict
from agents.reasoning_agent import ReasoningAgent
from utils.logger import logger
import finnhub
from utils.config import FINNHUB_API_KEY
import time

class WorkflowState(TypedDict):
    preferences: Dict
    user_id: str
    recommendations: List[Dict]
    market_insights: str
    reasoning_steps: List[str]

finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
STOCK_LIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "JPM", "WMT", "V"]

def run_workflow(preferences: Dict, user_id: str, is_trade: bool = False) -> Dict:
    """Run the investment recommendation workflow with step-by-step reasoning."""
    try:
        reasoning_agent = ReasoningAgent()

        # Initialize state
        state = WorkflowState(
            preferences=preferences,
            user_id=user_id,
            recommendations=[],
            market_insights="",
            reasoning_steps=[]
        )

        # Run the analysis
        recommendations, insights, steps = reasoning_agent.analyze_investment_scenario(
            preferences,
            is_trade=is_trade
        )

        if not recommendations:
            logger.warning("No recommendations generated")
            return {
                "recommendations": [],
                "market_insights": "Unable to generate recommendations at this time.",
                "reasoning_steps": steps
            }

        # If this is a trade request, validate the recommendations
        if is_trade:
            valid_recommendations = []
            validation_steps = []
            for rec in recommendations:
                is_valid, explanation, val_steps = reasoning_agent.validate_trade(rec, preferences)
                if is_valid:
                    valid_recommendations.append(rec)
                validation_steps.extend(val_steps)
            recommendations = valid_recommendations
            steps.extend(validation_steps)

        return {
            "recommendations": recommendations,
            "market_insights": insights,
            "reasoning_steps": steps
        }

    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}")
        return {
            "recommendations": [],
            "market_insights": f"Analysis failed: {str(e)}",
            "reasoning_steps": ["Error occurred during analysis"]
        }