import finnhub
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timezone, timedelta
import time
import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv
from cachetools import TTLCache
from pathlib import Path

# Ensure logs directory exists
LOG_DIR = Path("finance_simulator/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "fetch_stock_prices.log"

# Configure logging
logger = logging.getLogger('fetch_stock_prices')
logger.setLevel(logging.INFO)
try:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1000000, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
except PermissionError as e:
    print(f"Warning: Cannot write to log file {LOG_FILE}: {str(e)}. Logging to console.")
    logger.addHandler(logging.StreamHandler())

# Load environment variables
load_dotenv()

# Configuration
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'stock_data')

STOCK_LIST = [
    "UNH", "TSLA", "QCOM", "ORCL", "NVDA", "NFLX", "MSFT", "META", "LLY", "JNJ",
    "INTC", "IBM", "GOOGL", "GM", "F", "CSCO", "AMZN", "AMD", "ADBE", "AAPL"
]

# Cache for stock prices (24-hour TTL)
price_cache = TTLCache(maxsize=100, ttl=86400)

def get_db_connection(attempts=3, delay=5):
    """Establish MySQL database connection with retries."""
    for attempt in range(attempts):
        try:
            conn = mysql.connector.connect(
                host=MYSQL_HOST,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
            logger.debug("Database connection established")
            return conn
        except Error as e:
            logger.error(f"Attempt {attempt + 1}/{attempts} - Failed to connect to database: {str(e)}")
            if attempt < attempts - 1:
                time.sleep(delay)
    logger.error("Failed to connect to database after all attempts")
    return None

def get_stock_price_from_db(symbol: str) -> dict:
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT open_price, close_price, high_price, low_price, current_price, last_updated
            FROM stock_prices
            WHERE symbol = %s
        """, (symbol,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            last_updated = result["last_updated"]
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=timezone.utc)
            if last_updated >= datetime.now(timezone.utc) - timedelta(hours=1):
                logger.info(f"Fetched recent price for {symbol} from DB")
                return {
                    "o": float(result["open_price"]),
                    "c": float(result["current_price"]),
                    "h": float(result["high_price"]),
                    "l": float(result["low_price"]),
                    "pc": float(result["close_price"])
                }
        logger.info(f"No recent price for {symbol} in DB")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch price from DB for {symbol}: {str(e)}")
        return None

def update_stock_price_in_db(symbol: str, quote: dict):
    """Update or insert stock price in the database."""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO stock_prices (symbol, open_price, close_price, high_price, low_price, current_price, timestamp, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                open_price = %s,
                close_price = %s,
                high_price = %s,
                low_price = %s,
                current_price = %s,
                timestamp = %s,
                last_updated = %s
        """, (
            symbol, quote["o"], quote["pc"], quote["h"], quote["l"], quote["c"], datetime.now(timezone.utc), datetime.now(timezone.utc),
            quote["o"], quote["pc"], quote["h"], quote["l"], quote["c"], datetime.now(timezone.utc), datetime.now(timezone.utc)
        ))
        conn.commit()
        logger.info(f"Updated price for {symbol} in DB: ${quote['c']:.2f}")
    except Error as e:
        logger.error(f"Failed to update price in DB for {symbol}: {str(e)}")
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def fetch_stock_prices():
    """Fetch stock prices from Finnhub and store in database, handling rate limits."""
    stock_data = {}
    try:
        finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
        logger.info("Initialized Finnhub client")
    except Exception as e:
        logger.error(f"Failed to initialize Finnhub client: {str(e)}")
        print(f"Error: Failed to initialize Finnhub client: {str(e)}")
        return stock_data

    for symbol in STOCK_LIST:
        try:
            cache_key = f"price_{symbol}"
            if cache_key in price_cache:
                logger.debug(f"Using cached price for {symbol}: ${price_cache[cache_key]['current_price']:.2f}")
                stock_data[symbol] = price_cache[cache_key]
                continue

            db_quote = get_stock_price_from_db(symbol)
            if db_quote:
                stock_data[symbol] = {
                    "current_price": db_quote["c"],
                    "high_price": db_quote["h"],
                    "low_price": db_quote["l"],
                    "previous_close": db_quote["pc"]
                }
                price_cache[cache_key] = stock_data[symbol]
                continue

            for attempt in range(5):
                try:
                    quote = finnhub_client.quote(symbol)
                    if not isinstance(quote.get("c"), (int, float)) or quote["c"] <= 0:
                        logger.warning(f"Invalid price data for {symbol}: {quote}")
                        quote = {"o": 0.0, "c": 0.0, "h": 0.0, "l": 0.0, "pc": 0.0}
                    stock_data[symbol] = {
                        "current_price": float(quote["c"]),
                        "high_price": float(quote["h"]),
                        "low_price": float(quote["l"]),
                        "previous_close": float(quote["pc"])
                    }
                    price_cache[cache_key] = stock_data[symbol]
                    update_stock_price_in_db(symbol, quote)
                    logger.info(f"Fetched and stored price for {symbol}: ${quote['c']:.2f}")
                    break
                except Exception as e:
                    if "429" in str(e):
                        delay = min(60, 10 * (2 ** attempt))
                        logger.warning(f"Rate limit for {symbol}, retrying in {delay}s (attempt {attempt + 1}/5)")
                        time.sleep(delay)
                        if attempt == 4:
                            logger.error(f"Rate limit exceeded for {symbol}, falling back to DB")
                            db_quote = get_stock_price_from_db(symbol)
                            if db_quote:
                                stock_data[symbol] = {
                                    "current_price": db_quote["c"],
                                    "high_price": db_quote["h"],
                                    "low_price": db_quote["l"],
                                    "previous_close": db_quote["pc"]
                                }
                                price_cache[cache_key] = stock_data[symbol]
                                logger.info(f"Used DB price for {symbol}: ${db_quote['c']:.2f}")
                            else:
                                logger.error(f"No DB price for {symbol}, using default 0.0")
                                stock_data[symbol] = {
                                    "current_price": 0.0,
                                    "high_price": 0.0,
                                    "low_price": 0.0,
                                    "previous_close": 0.0
                                }
                                price_cache[cache_key] = stock_data[symbol]
                            break
                    else:
                        logger.error(f"Failed to fetch Finnhub price for {symbol}: {str(e)}")
                        stock_data[symbol] = {
                            "current_price": 0.0,
                            "high_price": 0.0,
                            "low_price": 0.0,
                            "previous_close": 0.0
                        }
                        price_cache[cache_key] = stock_data[symbol]
                        break
        except Exception as e:
            logger.error(f"Unexpected error processing {symbol}: {str(e)}")
            stock_data[symbol] = {
                "current_price": 0.0,
                "high_price": 0.0,
                "low_price": 0.0,
                "previous_close": 0.0
            }
            price_cache[cache_key] = stock_data[symbol]

    return stock_data

def main():
    """Main function to fetch and store stock prices."""
    logger.info("Starting stock price fetch")
    try:
        stock_data = fetch_stock_prices()
        if not stock_data:
            print("No stock prices fetched. Check logs for details.")
            logger.error("No stock prices fetched")
            return
        logger.info("Stock price fetch completed")
        print("Fetched stock prices:")
        for symbol, data in stock_data.items():
            print(f"{symbol}: ${data['current_price']:.2f}")
    except Exception as e:
        logger.error(f"Stock price fetch failed: {str(e)}")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()