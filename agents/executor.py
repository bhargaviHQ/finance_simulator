from utils.logger import logger
from typing import Dict

class ExecutorAgent:
    def execute_trade(self, recommendation: Dict, user_id: str) -> Dict:
        """Execute a trade based on the recommendation."""
        try:
            # Handle both 'Symbol' and 'symbol'
            symbol_key = 'Symbol' if 'Symbol' in recommendation else 'symbol'
            if symbol_key not in recommendation:
                logger.error(f"No symbol key in recommendation: {recommendation}")
                raise KeyError("symbol")

            trade = {
                "user_id": user_id,
                "symbol": recommendation[symbol_key],
                "quantity": recommendation.get("Quantity", 0),
                "trade_type": recommendation.get("Action", "").lower()
            }
            if trade["trade_type"] not in ["buy", "sell"]:
                logger.error(f"Invalid trade action: {trade['trade_type']}")
                raise ValueError(f"Invalid action: {trade['trade_type']}")
            if trade["quantity"] <= 0:
                logger.error(f"Invalid trade quantity: {trade['quantity']}")
                raise ValueError(f"Invalid quantity: {trade['quantity']}")

            logger.info(f"Executing trade: {trade}")
            return trade
        except Exception as e:
            logger.error(f"Trade execution failed: {str(e)}")
            raise