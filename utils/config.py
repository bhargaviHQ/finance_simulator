import streamlit as st
from dotenv import load_dotenv
import os
import base64
import tempfile
import requests

#API Configs
GROQ_API_KEY = st.secrets["api"]["GROQ_API_KEY"]
NEWSAPI_KEY = st.secrets["api"]["NEWSAPI_KEY"]
FINNHUB_API_KEY = st.secrets["api"]["FINNHUB_API_KEY"]
GNEWS_API_KEY = st.secrets["api"]["GNEWS_API_KEY"]

#Database Configs
AZURE_DATABASE=st.secrets["database"]["AZURE_DATABASE"]
AZURE_HOSTNAME=st.secrets["database"]["AZURE_HOSTNAME"]
AZURE_PASSWORD=st.secrets["database"]["AZURE_PASSWORD"]
AZURE_USER=st.secrets["database"]["AZURE_USER"]
AZURE_PORT=st.secrets["database"]["AZURE_PORT"]
# AZURE_SSL_CA=st.secrets["database"]["AZURE_SSL_CA"]

cert_base64 = st.secrets["database"]["AZURE_CERT"]
AZURE_SSL = base64.b64decode(cert_base64)

with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as tmp_cert_file:
    tmp_cert_file.write(AZURE_SSL)
    AZURE_SSL_CA = tmp_cert_file.name


load_dotenv()
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
# FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
# MYSQL_HOST = os.getenv("MYSQL_HOST")
# MYSQL_USER = os.getenv("MYSQL_USER")
# MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
# MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
# GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")

# AZURE_DATABASE=os.getenv("AZURE_DATABASE")
# AZURE_HOSTNAME=os.getenv("AZURE_HOSTNAME")
# AZURE_PASSWORD=os.getenv("AZURE_PASSWORD")
# AZURE_USER=os.getenv("AZURE_USER")
# AZURE_PORT=os.getenv("AZURE_PORT")
# AZURE_SSL_CA=os.getenv("AZURE_SSL_CA")
# st.write(f"Using DB user: {FINNHUB_API_KEY}")
# st.write(f"Using DB user: {GROQ_API_KEY}")
# st.write(f"Using DB user: {GNEWS_API_KEY}")
# st.write(f"Using DB user: {NEWSAPI_KEY}")