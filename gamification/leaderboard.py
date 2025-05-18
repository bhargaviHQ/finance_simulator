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

def update_leaderboard(user_id: str, username: str, balance: float):
    try:
        # Ensure badges column exists
        ensure_badges_column()

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
            SELECT username, balance, COALESCE(badges, 'None') AS badges 
            FROM users 
            ORDER BY balance DESC 
            LIMIT 10
        """)
        leaderboard = cursor.fetchall()
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