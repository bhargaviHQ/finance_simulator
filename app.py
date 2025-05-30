import streamlit as st
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import finnhub
import pytz
from decimal import Decimal
from cachetools import TTLCache
import time
import mysql.connector
from scripts.fetch_stock_prices import fetch_stock_prices
# from utils.config import FINNHUB_API_KEY, GNEWS_API_KEY
from utils.logger import logger
from agents import EducatorAgent, StrategistAgent, MarketAnalystAgent, ExecutorAgent, MonitorGuardrailAgent, run_workflow
from auth.auth import sign_up, sign_in, get_user
from gamification.leaderboard import update_leaderboard, get_leaderboard
from gamification.virtual_currency import get_balance, add_trade, get_portfolio
from data.mysql_db import get_db_connection
import requests
import json
import decimal
# Project setup
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Page configuration
st.set_page_config(page_title="💡 ThinkInvest", layout="wide", initial_sidebar_state="expanded")

# Fetching API Keys
NEWSAPI_KEY = st.secrets["NEWSAPI_KEY"]
FINNHUB_API_KEY = st.secrets["FINNHUB_API_KEY"]
GNEWS_API_KEY = st.secrets["GNEWS_API_KEY"]

# Custom CSS for dark theme
st.markdown("""
    <style>
    .main {
        background-color: #1a1a1a;
        padding: 20px;
        color: #ffffff;
    }
    .stSidebar {
        background: linear-gradient(180deg, #1c2526 0%, #2a3d45 100%);
        color: #ffffff;
        padding: 20px;
    }
    .stSidebar .sidebar-content {
        font-family: 'Arial', sans-serif;
    }
    .nav-item {
        padding: 10px 15px;
        margin: 5px 0;
        border-radius: 8px;
        font-size: 16px;
        color: #ffffff;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    .nav-item:hover {
        background-color: #374151;
        transform: translateX(5px);
    }
    .nav-item.active {
        background-color: #4b5563;
        color: #ffffff;
        font-weight: bold;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .stButton>button {
        background-color: #4b5563;
        color: #ffffff;
        border-radius: 8px;
        padding: 10px 20px;
        transition: all 0.3s ease;
        border: none;
        width: 100%;
        font-size: 16px;
    }
    .stButton>button:hover {
        background-color: #6b7280;
        transform: translateY(-2px);
    }
    .stTextInput>input, .stNumberInput>input {
        background-color: #374151;
        color: #ffffff;
        border-radius: 8px;
        border: 1px solid #4b5563;
        padding: 8px;
        font-size: 16px;
        width: 100%;
    }
    .stSelectbox [data-baseweb="select"] {
        background-color: #374151;
        color: #ffffff;
        border-radius: 8px;
        border: 1px solid #4b5563;
    }
    .stSelectbox [data-baseweb="select"] span {
        color: #ffffff;
    }
    .stTable {
        background-color: #2d2d2d;
        color: #ffffff;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        padding: 10px;
    }
    .stExpander {
        background-color: #2d2d2d;
        color: #ffffff;
        border-radius: 8px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    .stExpander div[data-testid="stExpanderToggle"] {
        color: #ffffff;
    }
    .header {
        font-size: 2.5em;
        color: #ffffff;
        margin-bottom: 20px;
        text-align: center;
    }
    .subheader {
        font-size: 1.5em;
        color: #d1d5db;
        margin-top: 20px;
        margin-bottom: 10px;
    }
    .balance {
        font-size: 1.2em;
        color: #ffffff;
        background-color: #4b5563;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        margin-top: 20px;
    }
    .stMarkdown, .stMarkdown p, .stMarkdown div {
        color: #ffffff;
    }
    .stTabs {
        width: 400px;
        margin: 0 auto;
    }
    .stTabs [data-baseweb="tab"] {
        color: #d1d5db;
        background-color: #2d2d2d;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        margin-right: 5px;
        width: 50%;
        text-align: center;
        font-size: 16px;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #ffffff;
        background-color: #4b5563;
        font-weight: bold;
    }
    .stock-card {
        background-color: #2d2d2d;
        padding: 10px;
        border-radius: 8px;
        margin: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    .stock-card a:hover {
        color: #22c55e;
    }
    .stock-price {
        font-size: 2em;
        font-weight: bold;
        color: #ffffff;
    }
    .stock-details {
        font-size: 1em;
        color: #d1d5db;
    }
    .profit {
        color: #22c55e;
        font-weight: bold;
    }
    .loss {
        color: #ef4444;
        font-weight: bold;
    }
    .top-user {
        font-size: 1.5em;
        color: #ffffff;
        background-color: #1e40af;
        padding: 10px;
        border-radius: 8px;
        margin-bottom: 20px;
        text-align: center;
    }
    .auth-container {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        padding: 20px 0;
    }
    .auth-card {
        background-color: #2d2d2d;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        width: 400px;
        text-align: center;
    }
    .auth-title {
        font-size: 2.2em;
        color: #ffffff;
        margin-bottom: 10px;
    }
    .auth-input-label {
        text-align: left;
        color: #d1d5db;
        font-size: 14px;
        margin-bottom: 5px;
        margin-top: 10px;
    }
    .auth-button {
        background-color: #1e40af;
        color: #ffffff;
        font-weight: bold;
        transition: all 0.3s ease;
        margin-top: 20px;
        padding: 10px;
        border-radius: 8px;
    }
    .auth-button:hover {
        background-color: #2563eb;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    *:focus {
        outline: none !important;
        box-shadow: 0 0 0 2px #ffffff !important;
    }
    input:invalid, select:invalid, textarea:invalid {
        border-color: #ef4444 !important;
    }
    .stButton>button {
        background-color: #4b5563;
        color: #ffffff;
        border-radius: 8px;
        padding: 10px 20px;
        transition: all 0.3s ease;
        border: none;
        width: 100%;
        font-size: 16px;
    }
    .nav-item:hover {
        background-color: #374151;
        color: #cbd5e1;
        transform: translateX(5px);
    }
    ::selection {
        background: #4b5563;
        color: #ffffff;
    }
    </style>
""", unsafe_allow_html=True)

STOCK_LIST = ["UNH", "TSLA", "QCOM", "ORCL", "NVDA", "NFLX", "MSFT", "META", "LLY", "JNJ", 
              "INTC", "IBM", "GOOGL", "GM", "F", "CSCO", "AMZN", "AMD", "ADBE", "AAPL"]

# Initialize Finnhub client
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

        if result:
            last_updated = result["last_updated"]
            if last_updated:
                # If last_updated is naive, assume it's in UTC and make it offset-aware
                if last_updated.tzinfo is None:
                    last_updated = pytz.timezone("UTC").localize(last_updated)
                # Compare with current UTC time minus 1 hour
                if last_updated >= datetime.now(timezone.utc) - timedelta(hours=1):
                    logger.info(f"Fetched recent price for {symbol} from DB")
                    return {
                        "o": result["open_price"],
                        "c": result["current_price"],
                        "h": result["high_price"],
                        "l": result["low_price"],
                        "pc": result["close_price"]
                    }
            logger.info(f"No recent or valid price for {symbol} in DB")
        else:
            logger.info(f"No price data found for {symbol} in DB")
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

# News fetching function for server-side API
def fetch_news(symbol: str):
    try:
        url = f"https://gnews.io/api/v4/search?q={symbol}&lang=en&max=5&apikey={GNEWS_API_KEY}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        articles = response.json().get("articles", [])
        news_data = [
            {
                "title": article["title"],
                "summary": article["description"] or "No summary available",
                "url": article["url"]
            }
            for article in articles if article.get("title") and article.get("url")
        ][:5]  # Ensure only top 5
        logger.info(f"Fetched {len(news_data)} news articles for {symbol}")
        return news_data
    except Exception as e:
        logger.error(f"Failed to fetch news for {symbol}: {str(e)}")
        return []

# Streamlit endpoint for news fetching
def news_endpoint():
    symbol = st.query_params.get("symbol", None)
    if not symbol:
        st.error("No symbol provided")
        return
    news_data = fetch_news(symbol)
    st.json(news_data)

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.balance = 100000.0
    st.session_state.last_portfolio_refresh = 0.0
    st.session_state.preferences = None

# Authentication UI
if not st.session_state.authenticated:
    st.markdown("<h1 class='header'>💡 ThinkInvest </h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🔐 Sign In", "✨ Sign Up"])
    
    with tab1:
        with st.container():
            st.markdown("<div class='auth-title'>Sign In</div>", unsafe_allow_html=True)
            with st.form(key="signin_form"):
                email = st.text_input("Email", placeholder="Enter your email", key="signin_email", label_visibility="visible")
                password = st.text_input("Password", type="password", placeholder="Enter your password", key="signin_password", label_visibility="visible")
                if st.form_submit_button("Sign In"):
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
            st.markdown("</div>", unsafe_allow_html=True)
    
    with tab2:
        with st.container():
            st.markdown("<div class='auth-title'>Sign Up</div>", unsafe_allow_html=True)
            with st.form(key="signup_form"):
                signup_email = st.text_input("Email", placeholder="Enter your email", key="signup_email", label_visibility="visible")
                signup_password = st.text_input("Password", type="password", placeholder="Enter your password", key="signup_password", label_visibility="visible")
                username = st.text_input("Username", placeholder="Choose a username", key="signup_username", label_visibility="visible")
                if st.form_submit_button("Sign Up"):
                    try:
                        if sign_up(signup_email, signup_password, username):
                            st.success("Account created! Please sign in.")
                        else:
                            st.error("Email already exists or invalid input")
                    except Exception as e:
                        st.error(f"Sign-up failed: {str(e)}")
            st.markdown("</div>", unsafe_allow_html=True)
else:
    # Check for news endpoint request
    if st.query_params.get("endpoint", None) == "news":
        news_endpoint()
    else:
        # Main application UI
        st.markdown(f"<h1 class='header'>Welcome, {st.session_state.username}! 👋</h1>", unsafe_allow_html=True)
        
        # Custom navigation sidebar
        st.sidebar.markdown("<h2 style='color: #ffffff;'>Navigation</h2>", unsafe_allow_html=True)
        nav_items = ["Home", "Get Recommendations", "Trade", "Portfolio", "Leaderboard"]
        selected_page = st.session_state.get("page", "Home")
    
        for item in nav_items:
            if st.sidebar.button(item, key=f"nav_{item}", use_container_width=True):
                st.session_state.page = item
                st.rerun()
    
        # Apply active class to selected navigation item
        st.markdown(f"""
            <script>
            document.querySelectorAll('.stButton').forEach(button => {{
                if (button.textContent === "{selected_page}") {{
                    button.classList.add('active');
                }} else {{
                    button.classList.remove('active');
                }}
            }});
            </script>
        """, unsafe_allow_html=True)

        page = st.session_state.get("page", "Home")

        # Sign out button and balance
        with st.sidebar:
            if st.button("🚪 Sign Out", use_container_width=True):
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

            try:
                st.markdown(f"<div class='balance'>Virtual Balance: ${st.session_state.balance:.2f}</div>", unsafe_allow_html=True)
            except Exception as e:
                logger.error(f"Failed to display balance: {str(e)}")
                st.error(f"Failed to display balance: {str(e)}")

        # Page content
        if page == "Home":
            st.markdown("<h2 class='subheader'>📈 Stock Market Overview</h2>", unsafe_allow_html=True)
            try:
                logger.info("Fetching stock prices for Home page")
                with st.spinner("Loading stock prices..."):
                    stock_data = fetch_stock_prices()
                    if not stock_data:
                        st.error("Failed to load stock prices.")
                    else:
                        # Initialize session state for news toggle
                        if "show_news" not in st.session_state:
                            st.session_state.show_news = {}
                            
                        cols = st.columns(2)  # Create two columns
                        for i, symbol in enumerate(STOCK_LIST):
                            with cols[i % 2]:  # Alternate between columns
                                data = stock_data.get(symbol, {"current_price": 0.0, "high_price": 0.0, "low_price": 0.0, "previous_close": 0.0})
                                current_price = data["current_price"]
                                high_price = data["high_price"]
                                low_price = data["low_price"]
                                previous_close = data["previous_close"]
                                status = "profit" if current_price > previous_close else "loss" if current_price < previous_close else ""
                                status_icon = "↑" if status == "profit" else "↓" if status == "loss" else ""

                                # Create a unique key for the news toggle button
                                news_key = f"news_{symbol}"
                                # Toggle news display when icon is clicked
                                if st.button("📰", key=news_key, help=f"Show/hide news for {symbol}"):
                                    st.session_state.show_news[symbol] = not st.session_state.show_news.get(symbol, False)
                                    st.rerun()

                                # Build the stock card HTML (without news)
                                card_html = f"""
                                    <div class='stock-card' style='width: 95%; margin: 5px; position: relative; padding: 15px; border-radius: 8px; background: #2d2d2d;'>
                                        <h3 style='color: #ffffff; margin: 0 0 10px 0; font-size: 18px;'>{symbol}</h3>
                                        <div class='stock-price' style='font-size: 24px; font-weight: bold; color: #ffffff;'>${current_price:.2f} <span class='{status}'>{status_icon}</span></div>
                                        <div class='stock-details' style='font-size: 14px; color: #d1d5db; margin-top: 5px;'>High: ${high_price:.2f} | Low: ${low_price:.2f}</div>
                                    </div>
                                """
                                st.markdown(card_html, unsafe_allow_html=True)

                                # If news is toggled on, fetch and display the top news article separately
                                if st.session_state.show_news.get(symbol, False):
                                    logger.info(f"Rendering news for {symbol}")
                                    news_data = fetch_news(symbol)
                                    news_html = ""
                                    if news_data and len(news_data) > 0:
                                        top_article = news_data[0]  # Take the first article
                                        summary = top_article["summary"][:100] + "..." if len(top_article["summary"]) > 100 else top_article["summary"]
                                        news_html = f"""
                                            <div style='width: 95%; margin: 5px; padding: 15px; border-radius: 8px; background: #2d2d2d; margin-top: 2px; border-top: 1px solid #4b5563;'>
                                                <a href='{top_article["url"]}' target='_blank' style='color: #22c55e; font-size: 16px; font-weight: bold; text-decoration: none; display: block; margin-bottom: 8px;'>{top_article["title"]}</a>
                                                <p style='color: #d1d5db; font-size: 14px; line-height: 1.5; margin: 0;'>{summary}</p>
                                            </div>
                                        """
                                        logger.debug(f"News HTML for {symbol}: {news_html}")
                                    else:
                                        news_html = """
                                            <div style='width: 95%; margin: 5px; padding: 15px; border-radius: 8px; background: #2d2d2d; margin-top: 2px; border-top: 1px solid #4b5563;'>
                                                <p style='color: #d1d5db; font-size: 14px; margin: 0;'>No news available.</p>
                                            </div>
                                        """
                                        logger.debug(f"No news available for {symbol}")
                                    # Use st.write instead of st.markdown for HTML content
                                    st.write(news_html, unsafe_allow_html=True)
            except Exception as e:
                logger.error(f"Failed to load stock prices for Home page: {str(e)}")
                st.error(f"Failed to load stock prices: {str(e)}")

            # Add CSS for hover effect and improved styling
            st.markdown("""
                <style>
                .stock-card a:hover, .news-section a:hover {
                    color: #4ade80 !important;
                }
                .stock-card, .news-section {
                    box-shadow: 0 2  #2px 4px rgba(0,0,0,0.3);
                }
                </style>
            """, unsafe_allow_html=True)
        
        elif page == "Get Recommendations":
            st.markdown("<h2 class='subheader'>📊 Get Personalized Stock Recommendations</h2>", unsafe_allow_html=True)
            with st.form(key="preferences_form"):
                col1, col2 = st.columns(2)
                with col1:
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
                with col2:
                    time_horizon = st.selectbox(
                        "Time Horizon",
                        ["short", "medium", "long"],
                        help="Select 'short' for 1-3 years, 'medium' for 3-7 years, 'long' for 7+ years."
                    )
                    investment_style = st.selectbox(
                        "Investment Style",
                        ["value", "growth", "index"],
                        help="Select 'index' for passive investing, or choose 'value' or 'growth'."
                    )
                investment_amount = st.number_input(
                    "Investment Amount ($)",
                    min_value=0.0,
                    value=500.0,
                    step=100.0,
                    help="Enter the amount you wish to invest (e.g., 500.0)."
                )
                
                # Add text input for additional details
                additional_details = st.text_area(
                    "Additional Details",
                    placeholder="Enter any additional details about your investment preferences, goals, or constraints...",
                    help="Provide more context about your investment strategy, specific sectors you're interested in, or any other relevant information."
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
                        "investment_style": investment_style,
                        "additional_details": additional_details
                    }
                    st.session_state.preferences = preferences
                    logger.info(f"Submitted preferences: {preferences}")
                    
                    st.markdown("<h3 style='color: #ffffff;'>Your Investment Preferences</h3>", unsafe_allow_html=True)
                    prefs_display = {
                        "Risk Appetite": preferences["risk_appetite"],
                        "Investment Goals": preferences["investment_goals"],
                        "Time Horizon": preferences["time_horizon"],
                        "Investment Amount": f"${preferences['investment_amount']:.2f}",
                        "Investment Style": preferences["investment_style"]
                    }
                    if additional_details:
                        prefs_display["Additional Details"] = additional_details
                    st.table(pd.DataFrame([prefs_display]))
                    
                    st.info("Starting investment analysis...")
                    logger.info("Starting recommendation workflow")
                    
                    with st.spinner("Analyzing investment scenario..."):
                        result = run_workflow(preferences, st.session_state.user_id)
                    
                    if result["recommendations"]:
                        st.success("Analysis complete!")
                        
                        # Display the agent's thinking process first
                        with st.expander("🧠 Agent's Thought Process", expanded=True):
                            st.markdown("<h4 style='color: #ffffff;'>Inner Monologue</h4>", unsafe_allow_html=True)
                            for thought in result.get("thinking_process", []):
                                st.markdown(f"<div class='thought-bubble'>{thought}</div>", unsafe_allow_html=True)
                        
                        # Display market insights and analysis process in a collapsible section
                        with st.expander("🔍 Analysis Process", expanded=True):
                            st.markdown("<h4 style='color: #ffffff;'>Market Analysis & Insights</h4>", unsafe_allow_html=True)
                            insights_text = result["market_insights"].replace("\n", "<br>")
                            st.markdown(f"<div class='analysis-box'>{insights_text}</div>", unsafe_allow_html=True)
                        
                        # Display analysis steps in a separate collapsible section
                        with st.expander("📊 Analysis Steps", expanded=True):
                            st.markdown("<h4 style='color: #ffffff;'>Step-by-Step Analysis</h4>", unsafe_allow_html=True)
                            for step in result.get("reasoning_steps", []):
                                if isinstance(step, str):
                                    if step.startswith("🧩"):  # This is a recommendation detail
                                        formatted_step = step.replace("\n", "<br>")
                                        st.markdown(f"<div class='recommendation-box'>{formatted_step}</div>", unsafe_allow_html=True)
                                    else:
                                        formatted_step = step.replace("\n", "<br>")
                                        st.markdown(f"<div class='step-box'>{formatted_step}</div>", unsafe_allow_html=True)
                        
                        # Select the best recommendation
                        recommendation = result["recommendations"][0]  # Take the highest scored recommendation
                        
                        # Display selected recommendation
                        st.markdown("<h3 style='color: #ffffff;'>Agent's Trade Analysis</h3>", unsafe_allow_html=True)
                        with st.expander("Trade Details", expanded=True):
                            st.markdown(f"""
                            **{recommendation['Symbol']} - {recommendation['Company']}**
                            - Action: {recommendation['Action']}
                            - Quantity: {recommendation['Quantity']:.2f} shares
                            - Current Price: ${recommendation['CurrentPrice']:.2f}
                            - Total Cost: ${recommendation['TotalCost']:.2f}
                            - Investment Amount Available: ${preferences['investment_amount']:.2f}
                            - Reason: {recommendation['Reason']}
                            - Caution: {recommendation['Caution']}
                            - News Sentiment: {recommendation['NewsSentiment']}
                            - Score: {recommendation['Score']}
                            
                            **Investment Analysis:**
                            - Utilization: {(recommendation['TotalCost'] / preferences['investment_amount'] * 100):.1f}% of available investment amount
                            - Remaining Budget: ${preferences['investment_amount'] - recommendation['TotalCost']:.2f}
                            """)
                        
                        # Automatically execute the trade
                        try:
                            logger.info(f"Starting automated trade execution for {recommendation['Symbol']}")
                            
                            # Get current price
                            quote = finnhub_client.quote(recommendation["Symbol"])
                            price = float(quote["c"])
                            quantity = float(recommendation["Quantity"])
                            amount = price * quantity
                            
                            logger.info(f"Trade details - Symbol: {recommendation['Symbol']}, Price: {price}, Quantity: {quantity}, Amount: {amount}")
                            
                            if amount <= st.session_state.balance or recommendation["Action"].lower() == "sell":
                                # Create trade record
                                trade_id = f"trade_{st.session_state.user_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
                                trade = {
                                    "id": trade_id,
                                    "symbol": recommendation["Symbol"],
                                    "quantity": quantity,
                                    "price": price,
                                    "trade_type": recommendation["Action"].lower(),
                                    "amount": amount,
                                    "user_id": st.session_state.user_id,
                                    "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                                }
                                
                                logger.info(f"Attempting to add trade to database: {trade}")
                                
                                # Try to execute trade up to 3 times
                                success = False
                                for attempt in range(3):
                                    try:
                                        if add_trade(st.session_state.user_id, trade):
                                            success = True
                                            logger.info(f"Trade successfully added to database: {trade_id}")
                                            
                                            # Update session balance
                                            if trade["trade_type"] == "buy":
                                                st.session_state.balance = float(st.session_state.balance - amount)
                                            else:
                                                st.session_state.balance = float(st.session_state.balance + amount)
                                            
                                            # Update leaderboard
                                            update_leaderboard(st.session_state.user_id, st.session_state.username, st.session_state.balance)
                                            logger.info(f"Updated leaderboard for user {st.session_state.user_id}")
                                            
                                            # Show success message with next steps
                                            total_value = float(trade['quantity']) * float(trade['price'])
                                            st.success(f"""
                                            🎯 **Trade Successfully Executed!**
                                            
                                            **Trade Details:**
                                            - Action: {trade['trade_type'].upper()}
                                            - Stock: {trade['symbol']}
                                            - Shares: {trade['quantity']:.2f}
                                            - Price per Share: ${trade['price']:.2f}
                                            - Total Value: ${total_value:.2f}
                                            - New Balance: ${st.session_state.balance:.2f}
                                            
                                            **Next Steps:**
                                            1. Click on the "Portfolio" tab in the navigation menu to view your updated holdings
                                            2. You can track the performance of this trade in your portfolio
                                            3. The trade has been recorded and will be reflected in your account history
                                            """)
                                            
                                            # Update stock price in DB
                                            update_stock_price_in_db(trade['symbol'], {
                                                "o": quote["o"],
                                                "c": quote["c"],
                                                "h": quote["h"],
                                                "l": quote["l"],
                                                "pc": quote["pc"]
                                            })
                                            logger.info(f"Updated stock price in DB for {trade['symbol']}")
                                            break
                                        else:
                                            logger.warning(f"add_trade returned False on attempt {attempt + 1}")
                                            if attempt == 2:
                                                st.error("Agent was unable to execute the trade after multiple attempts. Please try again or use manual trading.")
                                                logger.error(f"Failed to save trade for {trade['symbol']}: add_trade returned False after 3 attempts")
                                    except mysql.connector.errors.IntegrityError as e:
                                        logger.error(f"IntegrityError in add_trade (attempt {attempt + 1}): {str(e)}")
                                        if attempt == 2:
                                            st.error("Database error occurred while executing the trade. Please try again.")
                                    except mysql.connector.errors.DatabaseError as e:
                                        logger.error(f"DatabaseError in add_trade (attempt {attempt + 1}): {str(e)}")
                                        if attempt == 2:
                                            st.error("Database error occurred while executing the trade. Please try again.")
                                    except Exception as e:
                                        logger.error(f"Unexpected error in add_trade (attempt {attempt + 1}): {str(e)}")
                                        if attempt == 2:
                                            st.error("An unexpected error occurred while executing the trade. Please try again.")
                                        
                                    if not success and attempt < 2:
                                        time.sleep(1)
                                        logger.info(f"Retrying trade execution, attempt {attempt + 2}")
                        except Exception as e:
                            logger.error(f"Failed to execute trade: {str(e)}")
                            st.error(f"""
                            ❌ **Trade Execution Failed**
                            
                            An error occurred while executing the trade: {str(e)}
                            Please try again or use manual trading if the issue persists.
                            """)
                    else:
                        st.warning("No valid trade recommendations generated. Please try again.")
        elif page == "Trade":
            st.markdown("<h2 class='subheader'>💹 Trade Stocks</h2>", unsafe_allow_html=True)
            mode = st.radio("Trading Mode", ["Manual", "Agent-Based"])
            if mode == "Manual":
                with st.form(key="manual_trade_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        symbol = st.selectbox("Select Stock", STOCK_LIST, key="manual_trade_stock")
                    with col2:
                        trade_type = st.radio("Trade Type", ["Buy", "Sell"], key="manual_trade_type")
                    amount = st.number_input("Investment Amount ($)", min_value=0.0, max_value=float(st.session_state.balance), step=100.0)
                    if st.form_submit_button("Trade"):
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
                                stock_data = fetch_stock_prices()
                                price = stock_data.get(symbol, {"current_price": 0.0})["current_price"]
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
                st.markdown("<h3 style='color: #ffffff;'>Agent-Based Trade Simulation</h3>", unsafe_allow_html=True)
                with st.form(key="agent_trade_form"):
                    col1, col2 = st.columns(2)
                    with col1:
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
                    with col2:
                        time_horizon = st.selectbox(
                            "Time Horizon",
                            ["short", "medium", "long"],
                            help="Select 'short' for 1-3 years, 'medium' for 3-7 years, 'long' for 7+ years.",
                            key="agent_horizon"
                        )
                        investment_style = st.selectbox(
                            "Investment Style",
                            ["value", "growth", "index"],
                            help="Select 'index' for passive investing, or choose 'value' or 'growth'.",
                            key="agent_style"
                        )
                    investment_amount = st.number_input(
                        "Investment Amount ($)",
                        min_value=0.0,
                        value=500.0,
                        step=100.0,
                        help="Enter the amount you wish to invest (e.g., 500.0).",
                        key="agent_amount"
                    )
                    additional_preferences = st.text_area(
                        "Additional Preferences",
                        placeholder="Enter any additional preferences or requirements (e.g., 'Only tech stocks', 'Focus on renewable energy', 'Avoid high volatility stocks')",
                        help="Specify any additional trading preferences, sector focus, or specific requirements.",
                        key="agent_additional_prefs"
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
                                "investment_style": investment_style,
                                "additional_preferences": additional_preferences.strip() if additional_preferences else ""
                            }
                            logger.info(f"Agent-based trade preferences: {preferences}")
                            
                            with st.spinner("Analyzing trade scenario..."):
                                result = run_workflow(preferences, st.session_state.user_id, is_trade=True)
                            
                            if result["recommendations"]:
                                st.success("Analysis complete!")
                                
                                # Display the agent's thinking process first
                                with st.expander("🧠 Agent's Thought Process", expanded=True):
                                    st.markdown("<h4 style='color: #ffffff;'>Inner Monologue</h4>", unsafe_allow_html=True)
                                    for thought in result.get("thinking_process", []):
                                        st.markdown(f"<div class='thought-bubble'>{thought}</div>", unsafe_allow_html=True)
                                
                                # Display market insights and analysis process in a collapsible section
                                with st.expander("🔍 Analysis Process", expanded=True):
                                    st.markdown("<h4 style='color: #ffffff;'>Market Analysis & Insights</h4>", unsafe_allow_html=True)
                                    insights_text = result["market_insights"].replace("\n", "<br>")
                                    st.markdown(f"<div class='analysis-box'>{insights_text}</div>", unsafe_allow_html=True)
                                
                                # Display analysis steps in a separate collapsible section
                                with st.expander("📊 Analysis Steps", expanded=True):
                                    st.markdown("<h4 style='color: #ffffff;'>Step-by-Step Analysis</h4>", unsafe_allow_html=True)
                                    for step in result.get("reasoning_steps", []):
                                        if isinstance(step, str):
                                            if step.startswith("🧩"):  # This is a recommendation detail
                                                formatted_step = step.replace("\n", "<br>")
                                                st.markdown(f"<div class='recommendation-box'>{formatted_step}</div>", unsafe_allow_html=True)
                                            else:
                                                formatted_step = step.replace("\n", "<br>")
                                                st.markdown(f"<div class='step-box'>{formatted_step}</div>", unsafe_allow_html=True)
                                
                                # Select the best recommendation
                                recommendation = result["recommendations"][0]  # Take the highest scored recommendation
                                
                                # Display selected recommendation
                                st.markdown("<h3 style='color: #ffffff;'>Agent's Trade Analysis</h3>", unsafe_allow_html=True)
                                with st.expander("Trade Details", expanded=True):
                                    st.markdown(f"""
                                    **{recommendation['Symbol']} - {recommendation['Company']}**
                                    - Action: {recommendation['Action']}
                                    - Quantity: {recommendation['Quantity']:.2f} shares
                                    - Current Price: ${recommendation['CurrentPrice']:.2f}
                                    - Total Cost: ${recommendation['TotalCost']:.2f}
                                    - Investment Amount Available: ${preferences['investment_amount']:.2f}
                                    - Reason: {recommendation['Reason']}
                                    - Caution: {recommendation['Caution']}
                                    - News Sentiment: {recommendation['NewsSentiment']}
                                    - Score: {recommendation['Score']}
                                    
                                    **Investment Analysis:**
                                    - Utilization: {(recommendation['TotalCost'] / preferences['investment_amount'] * 100):.1f}% of available investment amount
                                    - Remaining Budget: ${preferences['investment_amount'] - recommendation['TotalCost']:.2f}
                                    """)
                                
                                # Automatically execute the trade
                                try:
                                    logger.info(f"Starting automated trade execution for {recommendation['Symbol']}")
                                    
                                    # Get current price
                                    quote = finnhub_client.quote(recommendation["Symbol"])
                                    price = float(quote["c"])
                                    quantity = float(recommendation["Quantity"])
                                    amount = price * quantity
                                    
                                    logger.info(f"Trade details - Symbol: {recommendation['Symbol']}, Price: {price}, Quantity: {quantity}, Amount: {amount}")
                                    
                                    if amount <= st.session_state.balance or recommendation["Action"].lower() == "sell":
                                        # Create trade record
                                        trade_id = f"trade_{st.session_state.user_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
                                        trade = {
                                            "id": trade_id,
                                            "symbol": recommendation["Symbol"],
                                            "quantity": quantity,
                                            "price": price,
                                            "trade_type": recommendation["Action"].lower(),
                                            "amount": amount,
                                            "user_id": st.session_state.user_id,
                                            "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                                        }
                                        
                                        logger.info(f"Attempting to add trade to database: {trade}")
                                        
                                        # Try to execute trade up to 3 times
                                        success = False
                                        for attempt in range(3):
                                            try:
                                                if add_trade(st.session_state.user_id, trade):
                                                    success = True
                                                    logger.info(f"Trade successfully added to database: {trade_id}")
                                                    
                                                    # Update session balance
                                                    if trade["trade_type"] == "buy":
                                                        st.session_state.balance = float(st.session_state.balance - amount)
                                                    else:
                                                        st.session_state.balance = float(st.session_state.balance + amount)
                                                    
                                                    # Update leaderboard
                                                    update_leaderboard(st.session_state.user_id, st.session_state.username, st.session_state.balance)
                                                    logger.info(f"Updated leaderboard for user {st.session_state.user_id}")
                                                    
                                                    # Show success message with next steps
                                                    total_value = float(trade['quantity']) * float(trade['price'])
                                                    st.success(f"""
                                                    🎯 **Trade Successfully Executed!**
                                                    
                                                    **Trade Details:**
                                                    - Action: {trade['trade_type'].upper()}
                                                    - Stock: {trade['symbol']}
                                                    - Shares: {trade['quantity']:.2f}
                                                    - Price per Share: ${trade['price']:.2f}
                                                    - Total Value: ${total_value:.2f}
                                                    - New Balance: ${st.session_state.balance:.2f}
                                                    
                                                    **Next Steps:**
                                                    1. Click on the "Portfolio" tab in the navigation menu to view your updated holdings
                                                    2. You can track the performance of this trade in your portfolio
                                                    3. The trade has been recorded and will be reflected in your account history
                                                    """)
                                                    
                                                    # Update stock price in DB
                                                    update_stock_price_in_db(trade['symbol'], {
                                                        "o": quote["o"],
                                                        "c": quote["c"],
                                                        "h": quote["h"],
                                                        "l": quote["l"],
                                                        "pc": quote["pc"]
                                                    })
                                                    logger.info(f"Updated stock price in DB for {trade['symbol']}")
                                                    break
                                                else:
                                                    logger.warning(f"add_trade returned False on attempt {attempt + 1}")
                                                    if attempt == 2:
                                                        st.error("Agent was unable to execute the trade after multiple attempts. Please try again or use manual trading.")
                                                        logger.error(f"Failed to save trade for {trade['symbol']}: add_trade returned False after 3 attempts")
                                            except mysql.connector.errors.IntegrityError as e:
                                                logger.error(f"IntegrityError in add_trade (attempt {attempt + 1}): {str(e)}")
                                                if attempt == 2:
                                                    st.error("Database error occurred while executing the trade. Please try again.")
                                            except mysql.connector.errors.DatabaseError as e:
                                                logger.error(f"DatabaseError in add_trade (attempt {attempt + 1}): {str(e)}")
                                                if attempt == 2:
                                                    st.error("Database error occurred while executing the trade. Please try again.")
                                            except Exception as e:
                                                logger.error(f"Unexpected error in add_trade (attempt {attempt + 1}): {str(e)}")
                                                if attempt == 2:
                                                    st.error("An unexpected error occurred while executing the trade. Please try again.")
                                            
                                            if not success and attempt < 2:
                                                time.sleep(1)
                                                logger.info(f"Retrying trade execution, attempt {attempt + 2}")
                                    else:
                                        st.error(f"""
                                        ❌ **Insufficient Balance**
                                        
                                        Required Amount: ${amount:.2f}
                                        Your Balance: ${st.session_state.balance:.2f}
                                        
                                        Please adjust the trade amount or add funds to your account.
                                        """)
                                        logger.error(f"Insufficient balance: {amount} > {st.session_state.balance}")
                                except Exception as e:
                                    logger.error(f"Failed to execute trade: {str(e)}")
                                    st.error(f"""
                                    ❌ **Trade Execution Failed**
                                    
                                    An error occurred while executing the trade: {str(e)}
                                    Please try again or use manual trading if the issue persists.
                                    """)
                            else:
                                st.warning("No valid trade recommendations generated. Please try again.")
                    except Exception as e:
                        logger.error(f"Agent-based trade failed: {str(e)}")
                        st.error(f"Analysis failed: {str(e)}")

        elif page == "Portfolio":
            st.markdown("<h2 class='subheader'>💼 Your Portfolio</h2>", unsafe_allow_html=True)
            st.markdown("<h3 style='color: #ffffff;'>Current Holdings</h3>", unsafe_allow_html=True)
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

                with st.spinner("Loading portfolio data..."):
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
                            try:
                                # Convert Decimal to float for calculations
                                trade_amount = float(trade["amount"]) if isinstance(trade["amount"], (Decimal, float, int)) else 0.0
                                trade_price = float(trade["price"]) if isinstance(trade["price"], (Decimal, float, int)) else 0.0
                                
                                if trade_amount <= 0 or trade_price <= 0:
                                    logger.warning(f"Skipping invalid trade for {symbol}: amount={trade_amount}, price={trade_price}")
                                    continue
                                
                                quantity = trade_amount / trade_price
                                
                                if symbol not in holdings:
                                    holdings[symbol] = {"quantity": 0.0, "total_cost": 0.0, "buy_trades": 0, "realized_profit": 0.0}
                                    transaction_history[symbol] = []
                                
                                if trade["trade_type"] == "buy":
                                    holdings[symbol]["quantity"] += quantity
                                    holdings[symbol]["total_cost"] += trade_amount
                                    holdings[symbol]["buy_trades"] += 1
                                else:  # sell
                                    if holdings[symbol]["quantity"] >= quantity:
                                        avg_buy_price = holdings[symbol]["total_cost"] / holdings[symbol]["quantity"] if holdings[symbol]["quantity"] > 0 else trade_price
                                        holdings[symbol]["quantity"] -= quantity
                                        holdings[symbol]["total_cost"] -= avg_buy_price * quantity
                                        holdings[symbol]["buy_trades"] = max(0, holdings[symbol]["buy_trades"] - 1)
                                        realized_profit = (trade_price - avg_buy_price) * quantity
                                        holdings[symbol]["realized_profit"] += realized_profit
                                    else:
                                        logger.warning(f"Cannot sell {quantity} shares of {symbol}: only {holdings[symbol]['quantity']} available")
                                        continue
                                
                                transaction_history[symbol].append({
                                    "trade_type": trade["trade_type"].capitalize(),
                                    "Quantity": float(quantity),
                                    "Price ($)": float(trade_price),
                                    "Amount ($)": float(trade_amount),
                                    "Timestamp": trade["timestamp"]
                                })
                            except (TypeError, ValueError, decimal.InvalidOperation) as e:
                                logger.error(f"Error processing trade for {symbol}: {str(e)}")
                                continue

                        stock_data = fetch_stock_prices()
                        portfolio_data = []
                        for symbol, data in holdings.items():
                            if data["quantity"] > 0:
                                try:
                                    cache_key = f"price_{symbol}"
                                    if cache_key in price_cache:
                                        current_price = price_cache[cache_key]["current_price"]
                                    else:
                                        db_quote = get_stock_price_from_db(symbol)
                                        if db_quote:
                                            current_price = db_quote["c"]
                                        else:
                                            for attempt in range(3):
                                                try:
                                                    quote = finnhub_client.quote(symbol)
                                                    current_price = quote.get("c", stock_data.get(symbol, {"current_price": 0.0})["current_price"])
                                                    price_cache[cache_key] = {"current_price": current_price}
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
                                                                current_price = stock_data.get(symbol, {"current_price": 0.0})["current_price"]
                                                            break
                                                    else:
                                                        current_price = stock_data.get(symbol, {"current_price": 0.0})["current_price"]
                                                        break
                                    
                                    avg_buy_price = float(data["total_cost"]) / float(data["quantity"]) if data["quantity"] > 0 else 0
                                    unrealized_profit = (float(current_price) - avg_buy_price) * float(data["quantity"])
                                    portfolio_data.append({
                                        "Symbol": symbol,
                                        "Quantity": float(data["quantity"]),
                                        "Avg Buy Price ($)": float(avg_buy_price),
                                        "Current Price ($)": float(current_price),
                                        "Unrealized Profit ($)": float(unrealized_profit),
                                        "Realized Profit ($)": float(data["realized_profit"])
                                    })
                                except Exception as e:
                                    logger.error(f"Failed to fetch price for {symbol}: {str(e)}")
                                    portfolio_data.append({
                                        "Symbol": symbol,
                                        "Quantity": float(data["quantity"]),
                                        "Avg Buy Price ($)": float(data["total_cost"]) / float(data["quantity"]) if data["quantity"] > 0 else 0,
                                        "Current Price ($)": float(stock_data.get(symbol, {"current_price": 0.0})["current_price"]),
                                        "Unrealized Profit ($)": 0.0,
                                        "Realized Profit ($)": float(data["realized_profit"])
                                    })

                        if portfolio_data:
                            # Format the numeric columns
                            df = pd.DataFrame(portfolio_data)
                            for col in ["Quantity", "Avg Buy Price ($)", "Current Price ($)", "Unrealized Profit ($)", "Realized Profit ($)"]:
                                df[col] = df[col].apply(lambda x: f"{float(x):,.2f}")
                            st.table(df)
                        else:
                            st.info("No active holdings in your portfolio.")

                        st.markdown("<h3 style='color: #ffffff;'>Transaction History</h3>", unsafe_allow_html=True)
                        for symbol, transactions in transaction_history.items():
                            with st.expander(f"Transactions for {symbol}"):
                                st.table(pd.DataFrame(transactions))
            except Exception as e:
                logger.error(f"Failed to load portfolio: {str(e)}")
                st.error(f"Failed to load portfolio: {str(e)}")

        elif page == "Leaderboard":
            st.markdown("<h2 class='subheader'>🏆 Leaderboard</h2>", unsafe_allow_html=True)
            try:
                logger.info("Fetching leaderboard")
                leaderboard = get_leaderboard()
                if leaderboard:
                    top_user = leaderboard[0]
                    st.markdown(f"<div class='top-user'>Top Investor: {top_user['username']} with ${float(top_user['balance']):,.2f}</div>", unsafe_allow_html=True)
                    
                    df = pd.DataFrame(leaderboard, columns=["username", "balance"]).rename(columns={"balance": "Masked Balance","username":"Username"})
                    df.reset_index(drop=True, inplace=True)
                    df["Masked Balance"] = df["Masked Balance"].apply(lambda x: f"${float(x):,.2f}")

                    # Use st.write with .to_html and unsafe_allow_html=True to hide index
                    st.write(df.to_html(index=False, classes='table table-striped', justify='center'), unsafe_allow_html=True)

                    # Optionally, add some CSS to style the table via st.markdown
                    st.markdown("""
                        <style>
                        .table {
                            width: 100%;
                            border-collapse: collapse;
                            text-align: center;
                            font-weight: bold;
                        }
                        </style>
                    """, unsafe_allow_html=True)

                else:
                    st.info("No leaderboard data available.")
            except Exception as e:
                logger.error(f"Failed to load leaderboard: {str(e)}")
                st.error(f"Failed to load leaderboard: {str(e)}")

# Add custom CSS for better formatting
st.markdown("""
<style>
.thought-bubble {
    background-color: #2d2d2d;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    font-size: 16px;
    line-height: 1.6;
    white-space: pre-wrap;
}

.analysis-box {
    background-color: #2d2d2d;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    font-size: 16px;
    line-height: 1.6;
    white-space: pre-wrap;
}

.step-box {
    background-color: #2d2d2d;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    font-size: 16px;
    line-height: 1.6;
    white-space: pre-wrap;
}

.recommendation-box {
    background-color: #1e1e1e;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    font-size: 14px;
    font-family: monospace;
    white-space: pre-wrap;
}

/* Fix bullet point alignment */
.step-box ul, .analysis-box ul {
    margin: 0;
    padding-left: 20px;
}

/* Ensure consistent bullet points */
.step-box li, .analysis-box li {
    list-style-type: none;
    position: relative;
    padding-left: 20px;
}

.step-box li:before, .analysis-box li:before {
    content: "•";
    position: absolute;
    left: 0;
}

/* Fix line breaks */
br {
    display: block;
    margin: 5px 0;
    content: "";
}
</style>
""", unsafe_allow_html=True)
