import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "smarthealthplus.db")

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # So we can access columns by name
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        print("SQLite connection error:", e)
        return None
