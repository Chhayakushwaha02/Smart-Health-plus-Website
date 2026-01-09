import os

class Config:
    SECRET_KEY = os.getenv("SMART_HEALTH_PLUS_SECRET_KEY", "smarthealthplus_secret_key")

    # PostgreSQL database URL (Render provides this)
    DATABASE_URL = os.getenv("DATABASE_URL")
