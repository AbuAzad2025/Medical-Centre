
import sys
import os
from sqlalchemy import create_engine, text

def check_db_connection():
    try:
        from config import config
        env = os.getenv('APP_ENV', 'development')
        db_url = os.getenv('DATABASE_URL')
        print(f"Testing connection to: {db_url.split('@')[1] if '@' in str(db_url) else 'HIDDEN'}")
        
        engine = create_engine(db_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("Database connection successful!")
            print(f"Result: {result.fetchone()}")
            
    except Exception as e:
        print(f"Database connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_db_connection()
