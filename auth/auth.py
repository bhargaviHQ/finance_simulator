import bcrypt
import uuid
from data.mysql_db import get_db_connection
from utils.logger import logger

def hash_password(password):
    # Hash the password and decode to string for MySQL storage
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    # Encode the stored hashed password string back to bytes
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def sign_up(email, password, username):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        # Check if email exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return False
        user_id = str(uuid.uuid4())
        hashed_password = hash_password(password)
        cursor.execute("""
            INSERT INTO users (id, email, password, username, balance)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, email, hashed_password, username, 100000.0))
        connection.commit()
        logger.info(f"User signed up: {email}")
        return True
    except Exception as e:
        logger.error(f"Sign-up failed: {str(e)}")
        return False
    finally:
        cursor.close()
        connection.close()

def sign_in(email, password):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, email, password, username, balance FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user and check_password(password, user["password"]):
            logger.info(f"User signed in: {email}")
            return {
                "id": user["id"],
                "email": user["email"],
                "username": user["username"],
                "balance": user["balance"]
            }
        logger.warning(f"Invalid credentials for email: {email}")
        return None
    except Exception as e:
        logger.error(f"Sign-in failed: {str(e)}")
        return None
    finally:
        cursor.close()
        connection.close()

def get_user(user_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, email, username, balance FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {str(e)}")
        return None
    finally:
        cursor.close()
        connection.close()