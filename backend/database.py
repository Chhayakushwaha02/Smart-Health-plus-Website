import os
import sqlite3

# ---------------- SQLite Connection ----------------
DB_PATH = os.path.join(os.path.dirname(__file__), "smarthealthplus.db")

def get_db_connection():
    """Connect to local SQLite DB"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        print("SQLite connection error:", e)
        return None


# ---------------- Flask & SQLAlchemy ----------------
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)

app.secret_key = os.environ.get("SMART_HEALTH_PLUS_SECRET_KEY")

# Use the same absolute path for SQLAlchemy
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
