import sqlite3
import os

# Use Render persistent disk (or fallback locally)
DB_PATH = "/var/data/smarthealthplus.db"

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        print("SQLite connection error:", e)
        return None
