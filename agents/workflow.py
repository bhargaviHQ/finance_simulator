from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict
from agents.market_analyst import MarketAnalystAgent
from agents.strategist import StrategistAgent
from utils.logger import logger
import finnhub
from utils.config import FINNHUB_API_KEY
import time

class WorkflowState(TypedDict):
    preferences: Dict
    user_id: str
    market_data: List[Dict]
    recommendations: List[Dict]

finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
STOCK_LIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "JPM", "WMT", "V"]

def market_analysis_node(state: WorkflowState) -> WorkflowState:
    try:
        market_analyst = MarketAnalystAgent()
        market_data = []
        logger.info(f"Starting market analysis for {len(STOCK_LIST)} stocks")
        for symbol in STOCK_LIST:
            try:
                logger.info(f"Fetching data for {symbol}")
                analysis = market_analyst.analyze_stock(symbol)
                if analysis.get("analysis").startswith("Error"):
                    logger.warning(f"Analysis failed for {symbol}: {analysis['analysis']}")
                    continue
                market_data.append({
                    "symbol": symbol,
                    "company": analysis.get("company", symbol),
                    "price": analysis.get("price", 0.0),
                    "analysis": analysis.get("analysis", ""),
                    "financials": analysis.get("financials", {}),
                    "cik": analysis.get("cik", "")
                })
                logger.info(f"Successfully fetched data for {symbol}")
            except Exception as e:
                if "429" in str(e):
                    logger.error(f"Rate limit exceeded for {symbol}, retrying after delay")
                    time.sleep(5)
                    try:
                        analysis = market_analyst.analyze_stock(symbol)
                        market_data.append({
                            "symbol": symbol,
                            "company": analysis.get("company", symbol),
                            "price": analysis.get("price", 0.0),
                            "analysis": analysis.get("analysis", ""),
                            "financials": analysis.get("financials", {}),
                            "cik": analysis.get("cik", "")
                        })
                    except Exception as e2:
                        logger.error(f"Retry failed for {symbol}: {str(e2)}")
                        market_data.append({"symbol": symbol, "error": str(e2)})
                else:
                    logger.error(f"Failed to fetch data for {symbol}: {str(e)}")
                    market_data.append({"symbol": symbol, "error": str(e)})
        if not market_data:
            logger.error("No market data collected")
        else:
            logger.info(f"Collected market data for {len(market_data)} stocks")
        state["market_data"] = market_data
    except Exception as e:
        logger.error(f"Market analysis failed: {str(e)}")
        state["market_data"] = []
    return state

def strategist_node(state: WorkflowState) -> WorkflowState:
    try:
        logger.info("Starting strategist node")
        strategist = StrategistAgent()
        recommendations = strategist.generate_recommendations(
            state["preferences"], state["market_data"]
        )
        if not recommendations:
            logger.warning("No recommendations generated")
        else:
            logger.info(f"Generated {len(recommendations)} recommendations")
        state["recommendations"] = recommendations
    except Exception as e:
        logger.error(f"Recommendation generation failed: {str(e)}")
        state["recommendations"] = []
    return state

def run_workflow(preferences: Dict, user_id: str) -> Dict:
    logger.info(f"Running workflow for user {user_id} with preferences: {preferences}")
    workflow = StateGraph(WorkflowState)
    workflow.add_node("market_analysis", market_analysis_node)
    workflow.add_node("strategist", strategist_node)
    workflow.add_edge("market_analysis", "strategist")
    workflow.add_edge("strategist", END)
    workflow.set_entry_point("market_analysis")
    app = workflow.compile()
    initial_state = {
        "preferences": preferences,
        "user_id": user_id,
        "market_data": [],
        "recommendations": []
    }
    try:
        result = app.invoke(initial_state)
        if not result["recommendations"]:
            logger.warning("Workflow completed with no recommendations")
        else:
            logger.info(f"Workflow completed with {len(result['recommendations'])} recommendations")
        return {"recommendations": result["recommendations"]}
    except Exception as e:
        logger.error(f"Workflow failed: {str(e)}")
        return {"recommendations": []}