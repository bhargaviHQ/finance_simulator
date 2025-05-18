import yfinance as yf
# GETS A STOCK'S COMPLETE DATA - INCLUDES EXACT CURRENT STOCK PRICE, DIVIDEND YIELD, PE RATIO, EPS, MARKET CAP, ETC.
 
ticker = 'AAPL' # APPLE INC.
yf_ticker = yf.Ticker(ticker).info
yf_ticker
# y = yf_ticker.get("sector")