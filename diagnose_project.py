import os
import sys
from pathlib import Path
import mysql.connector
from data.mysql_db import get_db_connection
from langchain_groq import ChatGroq
from utils.config import GROQ_API_KEY
from utils.logger import logger

def diagnose_project():
    print("=== Project Diagnosis ===")
    cwd = os.getcwd()
    print(f"Current working directory: {cwd}")
    
    print("\nsys.path:")
    for path in sys.path:
        print(f"  {path}")
    
    project_root = str(Path(__file__).parent)
    print(f"\nProject root: {project_root}")
    if project_root not in sys.path:
        print("  Adding project root to sys.path")
        sys.path.insert(0, project_root)
    
    agents_dir = os.path.join(project_root, "agents")
    print(f"\nAgents directory: {agents_dir}")
    if os.path.exists(agents_dir):
        print("  Agents directory exists")
        files = os.listdir(agents_dir)
        print("  Files in agents/:")
        for f in files:
            print(f"    {f}")
    else:
        print("  ERROR: Agents directory does not exist")
    
    files_to_check = [
        "agents/__init__.py",
        "agents/workflow.py",
        "agents/preference_parser.py",
        "agents/market_analyst.py",
        "agents/strategist.py",
        "agents/executor.py",
        "app.py",
        "data/mysql_db.py",
        "utils/config.py",
        "utils/logger.py",
        "schema.sql"
    ]
    print("\nChecking critical files:")
    for f in files_to_check:
        path = os.path.join(project_root, f)
        print(f"  {f}: {'Exists' if os.path.exists(path) else 'Missing'}")
    
    print("\nTesting imports and methods:")
    try:
        from agents import run_workflow
        print("  Imported run_workflow successfully")
    except ImportError as e:
        print(f"  ERROR: Failed to import run_workflow: {str(e)}")
    
    try:
        from agents.market_analyst import MarketAnalystAgent
        market_analyst = MarketAnalystAgent()
        if hasattr(market_analyst, "analyze_stock"):
            print("  MarketAnalystAgent.analyze_stock exists")
        else:
            print("  ERROR: MarketAnalystAgent missing analyze_stock method")
        if hasattr(market_analyst, "fetch_financials"):
            print("  MarketAnalystAgent.fetch_financials exists")
        else:
            print("  ERROR: MarketAnalystAgent missing fetch_financials method")
    except ImportError as e:
        print(f"  ERROR: Failed to import MarketAnalystAgent: {str(e)}")
    
    try:
        from agents.strategist import StrategistAgent
        strategist = StrategistAgent()
        if hasattr(strategist, "generate_recommendations"):
            print("  StrategistAgent.generate_recommendations exists")
        else:
            print("  ERROR: StrategistAgent missing generate_recommendations method")
    except ImportError as e:
        print(f"  ERROR: Failed to import StrategistAgent: {str(e)}")
    
    print("\nTesting database connectivity:")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE 'stocks'")
        if cursor.fetchone():
            print("  Stocks table exists")
        else:
            print("  ERROR: Stocks table missing")
        cursor.execute("SHOW TABLES LIKE 'income_statements'")
        if cursor.fetchone():
            print("  Income_statements table exists")
        else:
            print("  ERROR: Income_statements table missing")
        cursor.execute("SELECT COUNT(*) AS count FROM stocks")
        stock_count = cursor.fetchone()[0]
        print(f"  Stocks table contains {stock_count} records")
        cursor.close()
        conn.close()
        print("  Database connection successful")
    except mysql.connector.Error as e:
        print(f"  ERROR: Database connection failed: {str(e)}")
    
    print("\nTesting Groq API connectivity:")
    try:
        llm = ChatGroq(model_name="llama-3.1-8b-instant", api_key=GROQ_API_KEY)
        response = llm.invoke("Test API connectivity")
        print("  Groq API test successful")
        logger.info(f"Groq API test response: {response.content[:100]}...")
    except Exception as e:
        print(f"  ERROR: Groq API test failed: {str(e)}")
    
    print("\n=== Diagnosis Complete ===")

if __name__ == "__main__":
    diagnose_project()