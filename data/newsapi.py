from newsapi import NewsApiClient
from utils.config import NEWSAPI_KEY

newsapi = NewsApiClient(api_key=NEWSAPI_KEY)

def get_news(symbol):
    articles = newsapi.get_everything(q=symbol, language="en", sort_by="relevancy")
    return articles["articles"][:5]