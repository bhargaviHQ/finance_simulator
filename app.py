import streamlit as st
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import finnhub
from decimal import Decimal
from cachetools import TTLCache
import time
import mysql.connector
from scripts.fetch_stock_prices import fetch_stock_prices
from utils.config import FINNHUB_API_KEY
from utils.logger import logger
from agents import EducatorAgent, StrategistAgent, MarketAnalystAgent, ExecutorAgent, MonitorGuardrailAgent, run_workflow
from auth.auth import sign_up, sign_in, get_user
from gamification.leaderboard import update_leaderboard, get_leaderboard
from gamification.virtual_currency import get_balance, add_trade, get_portfolio
from data.mysql_db import get_db_connection

project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

st.set_page_config(page_title="Finance Simulator", layout="wide")

STOCK_LIST = ["UNH", "TSLA", "QCOM", "ORCL", "NVDA", "NFLX", "MSFT", "META", "LLY", "JNJ", 
              "INTC", "IBM", "GOOGL", "GM", "F", "CSCO", "AMZN", "AMD", "ADBE", "AAPL"]

try:
    finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Finnhub client: {str(e)}")
    st.error(f"Finnhub initialization failed: {str(e)}")
    raise

# Cache for stock prices (1-hour TTL)
price_cache = TTLCache(maxsize=100, ttl=3600)

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
        if result and result["last_updated"] >= datetime.now(timezone.utc) - timedelta(hours=1):
            logger.info(f"Fetched recent price for {symbol} from DB")
            return {
                "o": result["open_price"],
                "c": result["current_price"],
                "h": result["high_price"],
                "l": result["low_price"],
                "pc": result["close_price"]
            }
        logger.info(f"No recent price for {symbol} in DB")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch price from DB for {symbol}: {str(e)}")
        return None

def update_stock_price_in_db(symbol: str, quote: dict):
    try:
        conn = get_db_connection()
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
        cursor.close()
        conn.close()
        logger.info(f"Updated price for {symbol} in DB")
    except Exception as e:
        logger.error(f"Failed to update price in DB for {symbol}: {str(e)}")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.balance = 100000.0
    st.session_state.last_portfolio_refresh = 0.0
    st.session_state.preferences = None

if not st.session_state.authenticated:
    st.title("Finance Simulator - Sign In / Sign Up")
    tab1, tab2 = st.tabs(["Sign In", "Sign Up"])
    
    with tab1:
        email = st.text_input("Email", key="signin_email")
        password = st.text_input("Password", type="password", key="signin_password")
        if st.button("Sign In"):
            try:
                user = sign_in(email, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user_id = user["id"]
                    st.session_state.username = user["username"]
                    st.session_state.balance = float(user["balance"])
                    st.session_state.last_portfolio_refresh = 0.0
                    st.session_state.preferences = None
                    st.success("Signed in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid email or password")
            except Exception as e:
                st.error(f"Sign-in failed: {str(e)}")
    
    with tab2:
        signup_email = st.text_input("Email", key="signup_email")
        signup_password = st.text_input("Password", type="password", key="signup_password")
        username = st.text_input("Username", key="signup_username")
        if st.button("Sign Up"):
            try:
                if sign_up(signup_email, signup_password, username):
                    st.success("Account created! Please sign in.")
                else:
                    st.error("Email already exists or invalid input")
            except Exception as e:
                st.error(f"Sign-up failed: {str(e)}")
else:
    st.title(f"Welcome, {st.session_state.username}!")
    if st.button("Sign Out"):
        try:
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.balance = 100000.0
            st.session_state.last_portfolio_refresh = 0.0
            st.session_state.preferences = None
            st.rerun()
        except Exception as e:
            st.error(f"Sign-out failed: {str(e)}")

    st.sidebar.header("Navigation")
    page = st.sidebar.radio("Go to", ["Get Recommendations", "Learn", "Trade", "Portfolio", "Leaderboard"])

    if page == "Get Recommendations":
        st.header("Get Personalized Stock Recommendations")
        with st.form(key="preferences_form"):
            risk_appetite = st.selectbox(
                "Risk Appetite",
                ["low", "medium", "high"],
                help="Select 'low' for safe/secure/cautious, 'high' for aggressive/risky, or 'medium' otherwise."
            )
            investment_goals = st.selectbox(
                "Investment Goals",
                ["retirement", "growth", "income"],
                help="Select 'retirement' for long-term savings, 'growth' for wealth/expansion, 'income' for dividends/passive."
            )
            time_horizon = st.selectbox(
                "Time Horizon",
                ["short", "medium", "long"],
                help="Select 'short' for 1-3 years, 'medium' for 3-7 years, 'long' for 7+ years."
            )
            investment_amount = st.number_input(
                "Investment Amount ($)",
                min_value=0.0,
                value=10000.0,
                step=100.0,
                help="Enter the amount you wish to invest (e.g., 5000.0)."
            )
            investment_style = st.selectbox(
                "Investment Style",
                ["value", "growth", "index"],
                help="Select 'index' for passive investing, or choose 'value' or 'growth'."
            )
            submit_button = st.form_submit_button("Get Recommendations")

        if submit_button:
            if investment_amount <= 0:
                st.error("Investment amount must be greater than zero.")
                logger.error(f"Invalid investment amount: {investment_amount}")
            else:
                preferences = {
                    "risk_appetite": risk_appetite,
                    "investment_goals": investment_goals,
                    "time_horizon": time_horizon,
                    "investment_amount": float(investment_amount),
                    "investment_style": investment_style
                }
                st.session_state.preferences = preferences
                logger.info(f"Submitted preferences: {preferences}")
                
                st.subheader("Your Investment Preferences")
                prefs_display = {
                    "Risk Appetite": preferences["risk_appetite"],
                    "Investment Goals": preferences["investment_goals"],
                    "Time Horizon": preferences["time_horizon"],
                    "Investment Amount": f"${preferences['investment_amount']:.2f}",
                    "Investment Style": preferences["investment_style"]
                }
                st.table(pd.DataFrame([prefs_display]))
                
                st.info("Fetching stock data, financials, and news sentiment...")
                logger.info("Starting recommendation workflow")
                with st.spinner("Generating recommendations..."):
                    result = run_workflow(preferences, st.session_state.user_id)
                if result["recommendations"]:
                    st.success("Generated personalized recommendations!")
                    logger.info(f"Generated recommendations: {result['recommendations']}")
                    st.subheader("Your Stock Recommendations")
                    for rec in result["recommendations"]:
                        with st.expander(f"{rec['Symbol']} - {rec['Company']}"):
                            st.markdown(f"**Action**: {rec['Action']}")
                            st.markdown(f"**Quantity**: {rec['Quantity']} shares")
                            st.markdown(f"**Reason**: {rec['Reason']}")
                            st.markdown(f"**Caution**: {rec['Caution']}")
                            st.markdown(f"**News Sentiment**: {rec['NewsSentiment']}")
                            st.markdown(f"**Score**: {rec['Score']}")
                else:
                    logger.warning("No recommendations generated")
                    st.error("No recommendations generated. Possible issues: invalid data, API errors, or rate limits.")
                    st.info("Check finance_simulator/logs/app.log for details.")

    elif page == "Learn":
        st.header("Learn Investment Strategies")
        try:
            educator = EducatorAgent()
            strategy = st.selectbox("Choose a strategy", ["Value Investing", "Growth Investing", "Dividend Investing"])
            if st.button("Learn"):
                logger.info(f"Fetching education for strategy: {strategy}")
                advice = educator.provide_education(strategy)
                st.write(advice)
        except Exception as e:
            logger.error(f"Failed to load educational content: {str(e)}")
            st.error(f"Failed to load educational content: {str(e)}")

    elif page == "Trade":
        st.header("Trade Stocks")
        mode = st.radio("Trading Mode", ["Manual", "Agent-Based"])
        if mode == "Manual":
            try:
                st.subheader("Stock Prices")
                logger.info("Fetching stock prices for manual trading")
                stock_data = fetch_stock_prices()
                st.table(pd.DataFrame.from_dict(stock_data, orient="index", columns=["Price ($)"]))
            except Exception as e:
                logger.error(f"Failed to load stock prices: {str(e)}")
                st.error(f"Failed to load stock prices: {str(e)}")

            symbol = st.selectbox("Select Stock", STOCK_LIST, key="manual_trade_stock")
            trade_type = st.radio("Trade Type", ["Buy", "Sell"], key="manual_trade_type")
            amount = st.number_input("Investment Amount ($)", min_value=0.0, max_value=float(st.session_state.balance), step=100.0)
            if st.button("Trade"):
                try:
                    logger.info(f"Executing manual trade: {symbol}, ${amount}, {trade_type}")
                    if amount <= 0:
                        st.error("Investment amount must be greater than zero")
                        logger.error(f"Invalid amount: {amount}")
                    elif amount > st.session_state.balance and trade_type == "Buy":
                        st.error("Insufficient balance")
                        logger.error(f"Insufficient balance: {amount} > {st.session_state.balance}")
                    elif symbol not in STOCK_LIST:
                        st.error(f"Invalid stock symbol: {symbol}")
                        logger.error(f"Invalid stock symbol: {symbol}")
                    else:
                        price = stock_data.get(symbol, 0.0)
                        if price <= 0:
                            st.error(f"No valid price available for {symbol}")
                            logger.error(f"No valid price for {symbol}")
                        else:
                            quantity = amount / price
                            trade = {
                                "id": f"trade_{st.session_state.user_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
                                "symbol": symbol,
                                "amount": float(amount),
                                "price": float(price),
                                "trade_type": trade_type.lower(),
                                "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                                "user_id": st.session_state.user_id,
                                "quantity": float(quantity)
                            }
                            logger.debug(f"Trade data: {trade}")
                            for attempt in range(3):
                                try:
                                    if add_trade(st.session_state.user_id, trade):
                                        if trade_type == "Buy":
                                            st.session_state.balance = float(st.session_state.balance - amount)
                                        else:
                                            st.session_state.balance = float(st.session_state.balance + amount)
                                        update_leaderboard(st.session_state.user_id, st.session_state.username, st.session_state.balance)
                                        st.success(f"Trade executed: {trade_type} ${amount:.2f} of {symbol} at ${price:.2f} ({quantity:.2f} shares)")
                                        logger.info(f"Trade saved: {symbol}, ${amount}, {trade_type}")
                                        break
                                    else:
                                        st.error("Failed to save trade")
                                        logger.error(f"Failed to save trade for {symbol}: add_trade returned False")
                                        break
                                except mysql.connector.errors.IntegrityError as e:
                                    logger.error(f"IntegrityError in add_trade (attempt {attempt + 1}): {str(e)} (SQLSTATE: {e.sqlstate}, errno: {e.errno})")
                                    if attempt < 2:
                                        logger.warning(f"Retrying trade save for {symbol}...")
                                        time.sleep(1)
                                        continue
                                    st.error(f"Failed to save trade: Database integrity error (e.g., duplicate trade ID)")
                                    break
                                except mysql.connector.errors.DatabaseError as e:
                                    logger.error(f"DatabaseError in add_trade (attempt {attempt + 1}): {str(e)} (SQLSTATE: {e.sqlstate}, errno: {e.errno})")
                                    if attempt < 2:
                                        logger.warning(f"Retrying trade save for {symbol}...")
                                        time.sleep(1)
                                        continue
                                    st.error(f"Failed to save trade: Database error")
                                    break
                                except Exception as e:
                                    logger.error(f"Unexpected error in add_trade (attempt {attempt + 1}): {str(e)}")
                                    st.error(f"Failed to save trade: Unexpected error")
                                    break
                except Exception as e:
                    logger.error(f"Failed to execute trade: {str(e)}")
                    st.error(f"Failed to execute trade: {str(e)}")
        else:
            st.subheader("Agent-Based Trade Simulation")
            with st.form(key="agent_trade_form"):
                risk_appetite = st.selectbox(
                    "Risk Appetite",
                    ["low", "medium", "high"],
                    help="Select 'low' for safe/secure/cautious, 'high' for aggressive/risky, or 'medium' otherwise.",
                    key="agent_risk"
                )
                investment_goals = st.selectbox(
                    "Investment Goals",
                    ["retirement", "growth", "income"],
                    help="Select 'retirement' for long-term savings, 'growth' for wealth/expansion, 'income' for dividends/passive.",
                    key="agent_goals"
                )
                time_horizon = st.selectbox(
                    "Time Horizon",
                    ["short", "medium", "long"],
                    help="Select 'short' for 1-3 years, 'medium' for 3-7 years, 'long' for 7+ years.",
                    key="agent_horizon"
                )
                investment_amount = st.number_input(
                    "Investment Amount ($)",
                    min_value=0.0,
                    value=10000.0,
                    step=100.0,
                    help="Enter the amount you wish to invest (e.g., 5000.0).",
                    key="agent_amount"
                )
                investment_style = st.selectbox(
                    "Investment Style",
                    ["value", "growth", "index"],
                    help="Select 'index' for passive investing, or choose 'value' or 'growth'.",
                    key="agent_style"
                )
                submit_button = st.form_submit_button("Execute Agent-Based Trade")

            if submit_button:
                try:
                    if investment_amount <= 0:
                        st.error("Investment amount must be greater than zero.")
                        logger.error(f"Invalid investment amount: {investment_amount}")
                    else:
                        preferences = {
                            "risk_appetite": risk_appetite,
                            "investment_goals": investment_goals,
                            "time_horizon": time_horizon,
                            "investment_amount": float(investment_amount),
                            "investment_style": investment_style
                        }
                        logger.info(f"Agent-based trade preferences: {preferences}")
                        st.info("Fetching stock data, financials, and news sentiment...")
                        with st.spinner("Generating trade recommendation..."):
                            result = run_workflow(preferences, st.session_state.user_id)
                        if result["recommendations"]:
                            st.success("Generated trade recommendation!")
                            logger.info(f"Agent-based trade recommendations: {result['recommendations']}")
                            executor = ExecutorAgent()
                            recommendation = result["recommendations"][0]
                            trade = executor.execute_trade(recommendation, st.session_state.user_id)
                            for attempt in range(3):
                                try:
                                    quote = finnhub_client.quote(trade["symbol"])
                                    trade["price"] = float(quote.get("c", 0.0))
                                    update_stock_price_in_db(trade["symbol"], quote)
                                    break
                                except Exception as e:
                                    if "429" in str(e):
                                        logger.warning(f"Rate limit for {trade['symbol']}, retrying in {10 * (2 ** attempt)}s")
                                        time.sleep(10 * (2 ** attempt))
                                        if attempt == 2:
                                            logger.error(f"Rate limit exceeded for {trade['symbol']}, falling back to DB")
                                            db_quote = get_stock_price_from_db(trade["symbol"])
                                            if db_quote:
                                                trade["price"] = db_quote["c"]
                                            else:
                                                raise Exception("No price available")
                                    else:
                                        raise
                            trade["id"] = f"trade_{st.session_state.user_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
                            trade["timestamp"] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                            trade["amount"] = float(trade["price"]) * float(trade["quantity"])
                            if trade["amount"] <= st.session_state.balance or trade["trade_type"] == "sell":
                                for attempt in range(3):
                                    try:
                                        if add_trade(st.session_state.user_id, trade):
                                            if trade["trade_type"] == "buy":
                                                st.session_state.balance = float(st.session_state.balance - trade["amount"])
                                            else:
                                                st.session_state.balance = float(st.session_state.balance + trade["amount"])
                                            update_leaderboard(st.session_state.user_id, st.session_state.username, st.session_state.balance)
                                            st.success(f"Agent executed trade: {trade['trade_type'].capitalize()} {trade['quantity']} shares of {trade['symbol']} at ${trade['price']:.2f} (Total: ${trade['amount']:.2f})")
                                            logger.info(f"Agent trade saved: {trade['symbol']}, ${trade['amount']}, {trade['trade_type']}")
                                            break
                                        else:
                                            st.error("Failed to save trade")
                                            logger.error(f"Failed to save agent-based trade for {trade['symbol']}: add_trade returned False")
                                            break
                                    except mysql.connector.errors.IntegrityError as e:
                                        logger.error(f"IntegrityError in agent-based add_trade (attempt {attempt + 1}): {str(e)} (SQLSTATE: {e.sqlstate}, errno: {e.errno})")
                                        if attempt < 2:
                                            logger.warning(f"Retrying agent-based trade save for {trade['symbol']}...")
                                            time.sleep(1)
                                            continue
                                        st.error(f"Failed to save trade: Database integrity error")
                                        break
                                    except mysql.connector.errors.DatabaseError as e:
                                        logger.error(f"DatabaseError in agent-based add_trade (attempt {attempt + 1}): {str(e)} (SQLSTATE: {e.sqlstate}, errno: {e.errno})")
                                        if attempt < 2:
                                            logger.warning(f"Retrying agent-based trade save for {trade['symbol']}...")
                                            time.sleep(1)
                                            continue
                                        st.error(f"Failed to save trade: Database error")
                                        break
                                    except Exception as e:
                                        logger.error(f"Unexpected error in agent-based add_trade (attempt {attempt + 1}): {str(e)}")
                                        st.error(f"Failed to save trade: Unexpected error")
                                        break
                            else:
                                st.error("Insufficient balance")
                        else:
                            logger.warning("No recommendations available for trading")
                            st.error("No recommendations available for trading. Possible issues: API errors or rate limits.")
                            st.info("Check finance_simulator/logs/app.log for details.")
                except Exception as e:
                    logger.error(f"Agent-based trade failed: {str(e)}")
                    st.error(f"Agent-based trade failed: {str(e)}")
                    if "429" in str(e):
                        st.warning("API rate limit exceeded. Please wait a few minutes and try again.")

    elif page == "Portfolio":
        st.header("Your Portfolio")
        st.subheader("Current Holdings")
        try:
            logger.info(f"Fetching portfolio for user {st.session_state.user_id}")
            if "last_portfolio_refresh" not in st.session_state:
                st.session_state.last_portfolio_refresh = time.time()

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Refresh Portfolio"):
                    st.session_state.last_portfolio_refresh = time.time()
                    st.rerun()
            with col2:
                auto_refresh = st.checkbox("Auto-Refresh (every 60s)", value=False)
            
            if auto_refresh:
                current_time = time.time()
                if current_time - st.session_state.last_portfolio_refresh >= 60:
                    st.session_state.last_portfolio_refresh = current_time
                    st.rerun()

            try:
                trades = get_portfolio(st.session_state.user_id)
            except Exception as e:
                logger.error(f"Failed to fetch portfolio from database: {str(e)}")
                st.error(f"Failed to fetch portfolio: {str(e)}")
                trades = None

            if not trades:
                st.info("No trades in your portfolio yet.")
                logger.info(f"No trades found for user {st.session_state.user_id}")
            else:
                holdings = {}
                transaction_history = {}
                for trade in trades:
                    symbol = trade["symbol"]
                    # quantity = trade.get("quantity", trade["amount"] / trade["price"])
                    if not all(isinstance(trade.get(key), (int, float, Decimal)) and trade.get(key) > 0 for key in ["amount", "price"]):
                        logger.warning(f"Skipping invalid trade for {symbol}: amount={trade['amount']}, price={trade['price']}")
                        continue
                    # Calculate quantity since trades table lacks quantity column
                    quantity = float(trade["amount"]) / float(trade["price"]) if trade["amount"] and trade["price"] else 0.0
                    if symbol not in holdings:
                        holdings[symbol] = {"quantity": 0, "total_cost": 0, "buy_trades": 0, "realized_profit": 0}
                        transaction_history[symbol] = []
                    
                    try:
                        if trade["trade_type"] == "buy":
                            holdings[symbol]["quantity"] += quantity
                            holdings[symbol]["total_cost"] += trade["amount"]
                            holdings[symbol]["buy_trades"] += 1
                        else:
                            if holdings[symbol]["quantity"] >= quantity:
                                avg_buy_price = holdings[symbol]["total_cost"] / holdings[symbol]["quantity"] if holdings[symbol]["quantity"] > 0 else trade["price"]
                                holdings[symbol]["quantity"] -= quantity
                                holdings[symbol]["total_cost"] -= avg_buy_price * quantity
                                holdings[symbol]["buy_trades"] = max(0, holdings[symbol]["buy_trades"] - 1)
                                realized_profit = (trade["price"] - avg_buy_price) * quantity
                                holdings[symbol]["realized_profit"] += realized_profit
                            else:
                                logger.warning(f"Cannot sell {quantity} shares of {symbol}: only {holdings[symbol]['quantity']} available")
                                continue
                    except Exception as e:
                        logger.error(f"Error processing trade for {symbol}: {str(e)}")
                        continue
                    
                    transaction_history[symbol].append({
                        "trade_type": trade["trade_type"].capitalize(),
                        "Quantity": quantity,
                        "Price ($)": trade["price"],
                        "Amount ($)": trade["amount"],
                        "Timestamp": trade["timestamp"]
                    })

                stock_data = fetch_stock_prices()
                portfolio_data = []
                for symbol, data in holdings.items():
                    if data["quantity"] > 0:
                        try:
                            cache_key = f"price_{symbol}"
                            if cache_key in price_cache:
                                current_price = price_cache[cache_key]
                            else:
                                db_quote = get_stock_price_from_db(symbol)
                                if db_quote:
                                    current_price = db_quote["c"]
                                else:
                                    for attempt in range(3):
                                        try:
                                            quote = finnhub_client.quote(symbol)
                                            current_price = quote.get("c", stock_data.get(symbol, 0.0))
                                            price_cache[cache_key] = current_price
                                            update_stock_price_in_db(symbol, quote)
                                            break
                                        except Exception as e:
                                            if "429" in str(e):
                                                logger.warning(f"Rate limit for {symbol}, retrying in {10 * (2 ** attempt)}s")
                                                time.sleep(10 * (2 ** attempt))
                                                if attempt == 2:
                                                    logger.error(f"Rate limit exceeded for {symbol}, falling back to DB")
                                                    db_quote = get_stock_price_from_db(symbol)
                                                    if db_quote:
                                                        current_price = db_quote["c"]
                                                    else:
                                                        current_price = stock_data.get(symbol, 0.0)
                                                    break
                                            else:
                                                current_price = stock_data.get(symbol, 0.0)
                                                break
                            
                            avg_buy_price = data["total_cost"] / data["quantity"] if data["quantity"] > 0 else 0
                            unrealized_profit = (current_price - avg_buy_price) * data["quantity"]
                            portfolio_data.append({
                                "Symbol": symbol,
                                "Quantity": data["quantity"],
                                "Avg Buy Price ($)": avg_buy_price,
                                "Current Price ($)": current_price,
                                "Unrealized Profit ($)": unrealized_profit,
                                "Realized Profit ($)": data["realized_profit"]
                            })
                        except Exception as e:
                            logger.error(f"Failed to fetch price for {symbol}: {str(e)}")
                            portfolio_data.append({
                                "Symbol": symbol,
                                "Quantity": data["quantity"],
                                "Avg Buy Price ($)": data["total_cost"] / data["quantity"] if data["quantity"] > 0 else 0,
                                "Current Price ($)": stock_data.get(symbol, 0.0),
                                "Unrealized Profit ($)": 0.0,
                                "Realized Profit ($)": data["realized_profit"]
                            })

                if portfolio_data:
                    st.table(pd.DataFrame(portfolio_data))
                else:
                    st.info("No active holdings in your portfolio.")

                st.subheader("Transaction History")
                for symbol, transactions in transaction_history.items():
                    with st.expander(f"Transactions for {symbol}"):
                        st.table(pd.DataFrame(transactions))
        except Exception as e:
            logger.error(f"Failed to load portfolio: {str(e)}")
            st.error(f"Failed to load portfolio: {str(e)}")

    elif page == "Leaderboard":
        st.header("Leaderboard")
        try:
            logger.info("Fetching leaderboard")
            leaderboard = get_leaderboard()
            st.table(pd.DataFrame(leaderboard, columns=["Username", "Balance", "Badges"]))
        except Exception as e:
            logger.error(f"Failed to load leaderboard: {str(e)}")
            st.error(f"Failed to load leaderboard: {str(e)}")

    try:
        st.sidebar.write(f"Virtual Balance: ${st.session_state.balance:.2f}")
    except Exception as e:
        logger.error(f"Failed to display balance: {str(e)}")
        st.error(f"Failed to display balance: {str(e)}")