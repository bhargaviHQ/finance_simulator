import yfinance as yf

def get_stock_data(symbol):
    stock = yf.Ticker(symbol)
    return stock.info