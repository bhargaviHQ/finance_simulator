from data.mysql_db import get_db_connection
from utils.logger import logger
import mysql.connector
from datetime import datetime

def get_balance(user_id: str) -> float:
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return float(result["balance"]) if result else 100000.0
    except Exception as e:
        logger.error(f"Failed to get balance for user {user_id}: {str(e)}")
        return 100000.0

def add_trade(user_id: str, trade: dict) -> bool:
    try:
        # Validate trade dictionary
        required_keys = ["id", "symbol", "amount", "price", "trade_type", "timestamp", "quantity"]
        missing_keys = [key for key in required_keys if key not in trade]
        if missing_keys:
            logger.error(f"Missing trade keys: {missing_keys}, Trade: {trade}")
            return False
        
        # Validate values
        if not isinstance(trade["amount"], (int, float)) or trade["amount"] <= 0:
            logger.error(f"Invalid amount: {trade['amount']}")
            return False
        if not isinstance(trade["price"], (int, float)) or trade["price"] <= 0:
            logger.error(f"Invalid price: {trade['price']}")
            return False
        if not isinstance(trade["quantity"], (int, float)) or trade["quantity"] <= 0:
            logger.error(f"Invalid quantity: {trade['quantity']}")
            return False
        if trade["trade_type"] not in ["buy", "sell"]:
            logger.error(f"Invalid trade type: {trade['trade_type']}")
            return False
        if not isinstance(trade["symbol"], str) or not trade["symbol"]:
            logger.error(f"Invalid symbol: {trade['symbol']}")
            return False
        try:
            datetime.strptime(trade["timestamp"], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            logger.error(f"Invalid timestamp format: {trade['timestamp']}")
            return False

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check balance for buy trades
        current_balance = get_balance(user_id)
        if trade["trade_type"] == "buy" and trade["amount"] > current_balance:
            logger.error(f"Insufficient balance for user {user_id}: {trade['amount']} > {current_balance}")
            return False

        # Insert trade
        cursor.execute("""
            INSERT INTO trades (id, user_id, symbol, amount, price, trade_type, timestamp, quantity)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            trade["id"],
            user_id,
            trade["symbol"],
            trade["amount"],
            trade["price"],
            trade["trade_type"],
            trade["timestamp"],
            trade["quantity"]
        ))

        # Update user balance
        balance_change = - trade["amount"] if trade["trade_type"] == "buy" else trade["amount"]
        cursor.execute("""
            UPDATE users 
            SET balance = balance + %s 
            WHERE id = %s
        """, (balance_change, user_id))

        conn.commit()
        logger.info(f"Trade added for user {user_id}: {trade['symbol']}, ${trade['amount']}, Type: {trade['trade_type']}, Quantity: {trade['quantity']}")
        return True
    except mysql.connector.Error as e:
        logger.error(f"Failed to add trade for user {user_id}: SQL Error: {str(e)}, Trade: {trade}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
        return False
    except Exception as e:
        logger.error(f"Unexpected error adding trade for user {user_id}: {str(e)}, Trade: {trade}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
        return False
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def get_portfolio(user_id: str) -> list:
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM trades WHERE user_id = %s", (user_id,))
        trades = cursor.fetchall()
        cursor.close()
        conn.close()
        logger.info(f"Retrieved portfolio for user {user_id}: {len(trades)} trades")
        return trades
    except Exception as e:
        logger.error(f"Failed to get portfolio for user {user_id}: {str(e)}")
        return []