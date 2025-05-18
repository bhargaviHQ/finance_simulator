from data.mysql_db import get_db_connection
from utils.logger import logger
import mysql.connector

def ensure_badges_column():
    """Ensure the badges column exists in the users table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'badges' AND TABLE_SCHEMA = 'stock_data'
        """)
        if not cursor.fetchone():
            logger.info("Adding badges column to users table")
            cursor.execute("ALTER TABLE users ADD COLUMN badges VARCHAR(255) DEFAULT 'None'")
            conn.commit()
            logger.info("Badges column added successfully")
        else:
            logger.debug("Badges column already exists")
        cursor.close()
        conn.close()
    except mysql.connector.Error as e:
        logger.error(f"Failed to ensure badges column: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error ensuring badges column: {str(e)}")
        raise

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
        # Ensure badges column exists
        ensure_badges_column()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Initialize badges if NULL
        cursor.execute("SELECT badges FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        current_badges = result[0] if result and result[0] is not None else 'None'
        if current_badges == 'None':
            # Example: Award "First Trade" badge (extend as needed)
            new_badges = 'First Trade'
            cursor.execute("UPDATE users SET badges = %s WHERE id = %s", (new_badges, user_id))
            logger.info(f"Initialized badges for user {user_id}: {new_badges}")

        # Insert trade
        cursor.execute("""
            INSERT INTO trades (id, user_id, symbol, amount, price, type, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            trade["id"],
            user_id,
            trade["symbol"],
            trade["amount"],
            trade["price"],
            trade["type"],
            trade["timestamp"]
        ))

        # Update user balance
        cursor.execute("""
            UPDATE users 
            SET balance = balance - %s 
            WHERE id = %s
        """, (trade["amount"], user_id))

        conn.commit()
        logger.info(f"Trade added for user {user_id}: {trade['symbol']}, ${trade['amount']}, Badges: {new_badges if current_badges == 'None' else current_badges}")
        return True
    except mysql.connector.Error as e:
        logger.error(f"Failed to add trade for user {user_id}: SQL Error: {str(e)}")
        if conn.is_connected():
            conn.rollback()
        return False
    except Exception as e:
        logger.error(f"Unexpected error adding trade for user {user_id}: {str(e)}")
        if conn.is_connected():
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