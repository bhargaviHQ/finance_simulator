from data.mysql_db import get_db_connection
from utils.logger import logger
import mysql.connector

def mask_balance(balance: float) -> str:
    """Mask the balance to obscure the exact amount (e.g., $123,456.78 -> $12X,XXX.XX)."""
    try:
        balance_str = f"{balance:.2f}"
        if len(balance_str) < 3:
            return "$XX,XXX.XX"
        integer_part, decimal_part = balance_str.split(".")
        if len(integer_part) <= 2:
            return f"${integer_part}X,XXX.{decimal_part}"
        masked = f"${integer_part[:2]}X,XXX.{decimal_part}"
        return masked
    except Exception as e:
        logger.error(f"Failed to mask balance {balance}: {str(e)}")
        return "$XX,XXX.XX"

def update_leaderboard(user_id: str, username: str, balance: float):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET balance = %s
            WHERE id = %s
        """, (balance, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Leaderboard updated for user {user_id}: Balance ${balance}")
    except mysql.connector.Error as e:
        logger.error(f"Failed to update leaderboard for user {user_id}: SQL Error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating leaderboard for user {user_id}: {str(e)}")
        raise
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def get_leaderboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT username, balance
            FROM users 
            ORDER BY balance DESC 
            LIMIT 10
        """)
        leaderboard = cursor.fetchall()
        # Mask balances in the leaderboard
        for entry in leaderboard:
            entry["balance"] = mask_balance(entry["balance"])
        cursor.close()
        conn.close()
        logger.info("Leaderboard retrieved")
        return leaderboard
    except mysql.connector.Error as e:
        logger.error(f"Failed to get leaderboard: SQL Error: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error getting leaderboard: {str(e)}")
        return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()