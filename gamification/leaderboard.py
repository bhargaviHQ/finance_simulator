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
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT u.username, u.balance
            FROM users u
            WHERE EXISTS (
                SELECT 1 FROM trades t WHERE t.user_id = u.id
            )
            ORDER BY u.balance DESC
            LIMIT 10
        """)

        leaderboard = cursor.fetchall()

        for user in leaderboard:
            user["masked_balance"] = mask_balance(user["balance"])

        return leaderboard
    except Exception as e:
        logging.error("Error getting leaderboard: %s", e)
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
