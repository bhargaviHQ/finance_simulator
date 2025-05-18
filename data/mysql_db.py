import mysql.connector
from utils.config import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
from utils.logger import logger
import json
import uuid

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        return connection
    except Exception as e:
        logger.error(f"MySQL connection failed: {str(e)}")
        raise

def initialize_db():
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        # Create users table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                username VARCHAR(100) NOT NULL,
                balance FLOAT NOT NULL DEFAULT 100000.0,
                badges VARCHAR(255) DEFAULT 'None'
            )
        """)
        # Create preferences table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                risk_appetite VARCHAR(50),
                investment_goals VARCHAR(50),
                time_horizon VARCHAR(50),
                investment_amount FLOAT,
                investment_style VARCHAR(50),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Migrate preferences table to add new columns if missing
        cursor.execute("SHOW COLUMNS FROM preferences LIKE 'investment_goals'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE preferences ADD COLUMN investment_goals VARCHAR(50)")
        cursor.execute("SHOW COLUMNS FROM preferences LIKE 'investment_style'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE preferences ADD COLUMN investment_style VARCHAR(50)")
        # Create preference_history table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preference_history (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                preferences JSON NOT NULL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Create trades table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                amount FLOAT NOT NULL,
                price FLOAT NOT NULL,
                trade_type VARCHAR(10) NOT NULL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        connection.commit()
        logger.info("MySQL tables initialized and migrated")
    except Exception as e:
        logger.error(f"Failed to initialize MySQL tables: {str(e)}")
        raise
    finally:
        cursor.close()
        connection.close()

# Initialize database tables
initialize_db()

def save_user_preferences(user_id, preferences):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        # Save latest preferences
        pref_id = f"pref_{user_id}"[:36]  # Ensure ID is within 36 characters
        cursor.execute("""
            INSERT INTO preferences (id, user_id, risk_appetite, investment_goals, time_horizon, investment_amount, investment_style)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                risk_appetite=%s, investment_goals=%s, time_horizon=%s, investment_amount=%s, investment_style=%s
        """, (
            pref_id, user_id,
            preferences["risk_appetite"], preferences["investment_goals"], preferences["time_horizon"],
            preferences["investment_amount"], preferences["investment_style"],
            preferences["risk_appetite"], preferences["investment_goals"], preferences["time_horizon"],
            preferences["investment_amount"], preferences["investment_style"]
        ))
        # Save to preference history with UUID
        hist_id = str(uuid.uuid4())  # Generates a 36-character UUID
        cursor.execute("""
            INSERT INTO preference_history (id, user_id, preferences, timestamp)
            VALUES (%s, %s, %s, NOW())
        """, (
            hist_id, user_id, json.dumps(preferences)
        ))
        connection.commit()
        logger.info(f"Saved preferences for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to save preferences for user {user_id}: {str(e)}")
        raise
    finally:
        cursor.close()
        connection.close()

def get_user_preferences(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT risk_appetite, investment_goals, time_horizon, investment_amount, investment_style
            FROM preferences
            WHERE user_id = %s
        """, (user_id,))
        result = cursor.fetchone()
        return result if result else None
    except Exception as e:
        logger.error(f"Failed to get preferences for user {user_id}: {str(e)}")
        return None
    finally:
        cursor.close()
        connection.close()

def get_preference_history(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT preferences, timestamp
            FROM preference_history
            WHERE user_id = %s
            ORDER BY timestamp DESC
        """, (user_id,))
        history = cursor.fetchall()
        # Parse JSON preferences
        for entry in history:
            entry["preferences"] = json.loads(entry["preferences"])
        return history
    except Exception as e:
        logger.error(f"Failed to get preference history for user {user_id}: {str(e)}")
        return []
    finally:
        cursor.close()
        connection.close()

def save_trade(user_id, trade):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO trades (id, user_id, symbol, amount, price, trade_type, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            trade["id"], user_id, trade["symbol"], trade["amount"], trade["price"], trade["trade_type"],
            trade["timestamp"], trade["trade_type"]
        ))
        connection.commit()
    except Exception as e:
        logger.error(f"Failed to save trade for user {user_id}: {str(e)}")
        raise
    finally:
        cursor.close()
        connection.close()

def get_user_trades(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT symbol, amount, price, trade_type, timestamp FROM trades WHERE user_id = %s", (user_id,))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to get trades for user {user_id}: {str(e)}")
        return []
    finally:
        cursor.close()
        connection.close()