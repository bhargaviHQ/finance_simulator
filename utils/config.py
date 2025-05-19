from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")


AZURE_DATABASE=os.getenv("AZURE_DATABASE")
AZURE_HOSTNAME=os.getenv("AZURE_HOSTNAME")
AZURE_PASSWORD=os.getenv("AZURE_PASSWORD")
AZURE_USER=os.getenv("AZURE_USER")
AZURE_PORT=os.getenv("AZURE_PORT")
AZURE_SSL_CA=os.getenv("AZURE_SSL_CA")