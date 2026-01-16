import os
import psycopg2

def get_db_connection():
    try:
        DATABASE_URL = os.getenv("DATABASE_URL")

        if not DATABASE_URL:
            raise Exception("DATABASE_URL not set")

        conn = psycopg2.connect(
            DATABASE_URL,
            sslmode="require"
        )
        return conn

    except Exception as e:
        print("❌ PostgreSQL connection error:", e)
        return None
