from langchain_groq import ChatGroq
from utils.config import GROQ_API_KEY, NEWSAPI_KEY, FINNHUB_API_KEY
from utils.logger import logger
import finnhub
import mysql.connector
from data.mysql_db import get_db_connection
from newsapi import NewsApiClient
import time
from datetime import datetime, timedelta
from cachetools import TTLCache
from typing import Dict, List
import json


class MarketAnalystAgent:
    def __init__(self):
        self.llm = ChatGroq(model_name="llama-3.1-8b-instant", api_key=GROQ_API_KEY)
        self.finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
        self.newsapi_client = NewsApiClient(api_key=NEWSAPI_KEY)
        self.cache = TTLCache(maxsize=100, ttl=3600)

    def fetch_financials(self, cik: str) -> dict:
        cache_key = f"financials_{cik}"
        if cache_key in self.cache:
            logger.info(f"Returning cached financials for CIK {cik}")
            return self.cache[cache_key]

        try:
            logger.info(f"Fetching MySQL financials for CIK {cik}")
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            five_years_ago = datetime.now() - timedelta(days=5*365)

            cursor.execute("""
                SELECT revenue, net_income, fiscal_date_ending
                FROM income_statements
                WHERE cik = %s AND fiscal_date_ending >= %s
                ORDER BY fiscal_date_ending DESC
            """, (cik, five_years_ago))
            income = cursor.fetchall() or []
            logger.info(f"Income statements for CIK {cik}: {len(income)} records")

            cursor.execute("""
                SELECT total_assets, total_liabilities, total_equity
                FROM balance_sheets
                WHERE cik = %s AND fiscal_date_ending >= %s
                ORDER BY fiscal_date_ending DESC
            """, (cik, five_years_ago))
            balance = cursor.fetchall() or []
            logger.info(f"Balance sheets for CIK {cik}: {len(balance)} records")

            cursor.execute("""
                SELECT operating_cash_flow, capital_expenditure
                FROM cash_flows
                WHERE cik = %s AND fiscal_date_ending >= %s
                ORDER BY fiscal_date_ending DESC
            """, (cik, five_years_ago))
            cash_flow = cursor.fetchall() or []
            logger.info(f"Cash flows for CIK {cik}: {len(cash_flow)} records")

            cursor.close()
            conn.close()

            financials = {
                "income": income,
                "balance": balance,
                "cash_flow": cash_flow
            }
            self.cache[cache_key] = financials
            return financials

        except Exception as e:
            logger.error(f"Failed to fetch financials for CIK {cik}: {str(e)}")
            return {}

    def fetch_news_sentiment(self, symbols: List[str]) -> Dict[str, str]:
        sentiments = {}
        to_date = datetime.now()
        from_date = to_date - timedelta(days=7)

        for symbol in symbols:
            cache_key = f"news_{symbol}"
            if cache_key in self.cache:
                logger.info(f"Returning cached news sentiment for {symbol}")
                sentiments[symbol] = self.cache[cache_key]
                continue

            try:
                logger.info(f"Fetching news for {symbol}")
                response = self.newsapi_client.get_everything(
                    q=symbol,
                    from_param=from_date.strftime('%Y-%m-%d'),
                    to=to_date.strftime('%Y-%m-%d'),
                    language='en',
                    sort_by='relevancy'
                )
                articles = response.get('articles', [])
                if not articles:
                    logger.info(f"No news articles found for {symbol}")
                    sentiments[symbol] = "Neutral"
                    self.cache[cache_key] = "Neutral"
                    continue

                headlines = [article['title'] for article in articles[:5]]
                prompt = f"""
Analyze the sentiment of these news headlines for {symbol}:
{headlines}
Score sentiment from -1 (negative) to 1 (positive). Return a JSON object:
```json
{{
    "sentiment": "Positive",
    "score": 0.8
}}
Where sentiment is 'Positive' (>=0.3), 'Negative' (<= -0.3), or 'Neutral' (else).
"""
                response = self.llm.invoke(prompt)
                result = json.loads(response.content.strip())
                sentiment = result.get("sentiment", "Neutral")

                if sentiment not in ["Positive", "Negative", "Neutral"]:
                    logger.warning(f"Invalid sentiment for {symbol}: {sentiment}")
                    sentiment = "Neutral"

                logger.info(f"News sentiment for {symbol}: {sentiment}")
                sentiments[symbol] = sentiment
                self.cache[cache_key] = sentiment

            except Exception as e:
                logger.error(f"Failed to fetch news for {symbol}: {str(e)}")
                if "429" in str(e):
                    time.sleep(10)
                sentiments[symbol] = "Neutral"
                self.cache[cache_key] = "Neutral"

        return sentiments

    def calculate_ratios(self, financials: dict, current_price: float, shares_outstanding: float) -> dict:
        try:
            latest_income = financials.get("income", [{}])[0]
            latest_balance = financials.get("balance", [{}])[0]

            eps = latest_income.get("net_income", 0) / shares_outstanding if shares_outstanding else 0
            pe_ratio = current_price / eps if eps != 0 else None
            debt_to_equity = (
                latest_balance.get("total_liabilities", 0) /
                latest_balance.get("total_equity", 1)
                if latest_balance.get("total_equity", 0) != 0 else None
            )

            return {
                "pe_ratio": round(pe_ratio, 2) if pe_ratio else None,
                "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity else None
            }
        except Exception as e:
            logger.error(f"Failed to calculate ratios: {str(e)}")
            return {"pe_ratio": None, "debt_to_equity": None}

    def analyze_stock(self, symbol: str) -> dict:
        cache_key = f"analysis_{symbol}"
        if cache_key in self.cache:
            logger.info(f"Returning cached analysis for {symbol}")
            return self.cache[cache_key]

        try:
            logger.info(f"Analyzing stock {symbol}")
            for attempt in range(2):
                try:
                    quote = self.finnhub_client.quote(symbol)
                    company = self.finnhub_client.company_profile2(symbol=symbol)
                    logger.info(f"Finnhub data for {symbol}: {quote}, {company}")
                    break
                except Exception as e:
                    if "429" in str(e):
                        logger.warning(f"Rate limit for {symbol}, retrying after 10s")
                        time.sleep(10)
                    if attempt == 1:
                        raise

            cik = company.get("cik", "")
            shares_outstanding = company.get("shareOutstanding", 1) * 1e6

            financials = self.fetch_financials(cik) if cik else {}
            news_sentiment = self.fetch_news_sentiment([symbol]).get(symbol, "Neutral")
            ratios = self.calculate_ratios(financials, quote.get("c", 0.0), shares_outstanding)

            stock_data = {
                "symbol": symbol,
                "current_price": quote.get("c", 0.0),
                "high": quote.get("h", 0.0),
                "low": quote.get("l", 0.0),
                "company": company.get("name", symbol),
                "cik": cik,
                "financials": financials,
                "pe_ratio": ratios["pe_ratio"],
                "debt_to_equity": ratios["debt_to_equity"]
            }

            logger.info(f"Preparing LLM analysis for {symbol}")
            prompt = f"""
Analyze the stock {symbol} based on:

Current Price: ${stock_data['current_price']:.2f}
High: ${stock_data['high']:.2f}
Low: ${stock_data['low']:.2f}
P/E Ratio: {stock_data['pe_ratio'] or 'N/A'}
Debt-to-Equity: {stock_data['debt_to_equity'] or 'N/A'}
Company: {stock_data['company']}
Financials (5 years): {stock_data['financials']}
News Sentiment: {news_sentiment}
Provide a brief analysis (3-4 sentences) covering market trends, financial health, and risks.
Return the analysis as a string.
"""
            try:
                response = self.llm.invoke(prompt)
                analysis = response.content.strip()
                logger.info(f"LLM analysis for {symbol}: {analysis}")
            except Exception as e:
                if "429" in str(e):
                    logger.error(f"Rate limit for LLM analysis of {symbol}")
                    analysis = "Error: Rate limit exceeded"
                    time.sleep(10)
                else:
                    logger.error(f"LLM analysis failed for {symbol}: {str(e)}")
                    analysis = f"Error: Unable to analyze {symbol}"

            result = {
                "analysis": analysis,
                "financials": financials,
                "price": stock_data["current_price"],
                "company": stock_data["company"],
                "cik": cik,
                "news_sentiment": news_sentiment,
                "pe_ratio": stock_data["pe_ratio"],
                "debt_to_equity": stock_data["debt_to_equity"],
                "symbol": symbol
            }

            required_keys = ["symbol", "price", "company", "analysis", "news_sentiment"]
            missing_keys = [key for key in required_keys if key not in result]
            if missing_keys:
                logger.error(f"Result missing required keys for {symbol}: {missing_keys}")
                raise ValueError(f"Invalid result format, missing: {missing_keys}")

            logger.debug(f"Returning analysis result for {symbol}: {result}")
            self.cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Failed to analyze stock {symbol}: {str(e)}")
            return {
                "symbol": symbol,
                "analysis": f"Error: {str(e)}",
                "financials": {},
                "price": 0.0,
                "company": symbol,
                "cik": "",
                "news_sentiment": "Neutral",
                "pe_ratio": None,
                "debt_to_equity": None
            }
