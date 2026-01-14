import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Load .env only for local development
load_dotenv()

def get_db_connection():
    """
    Creates and returns a MySQL database connection
    Works for both localhost (.env) and Render (env vars)
    """
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            autocommit=True
        )

        if connection.is_connected():
            return connection

    except Error as e:
        print("❌ MySQL connection error:", e)
        return None
