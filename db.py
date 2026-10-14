import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
VECTOR_STORE = os.getenv("VECTOR_STORE", "postgres").strip().lower()
MONGODB_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI", "")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "ai_ml_vectordb")
MONGODB_SERVER_SELECTION_TIMEOUT_MS = int(
    os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "30000")
)
MONGODB_CONNECT_TIMEOUT_MS = int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "10000"))


def check_database_connection() -> tuple[bool, str]:
    """Return whether the selected database is configured and reachable."""
    if VECTOR_STORE in {"mongo", "mongodb", "mongodb-atlas"}:
        if not MONGODB_URI:
            return False, "MONGODB_URI is not configured."
        try:
            from pymongo import MongoClient

            client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=MONGODB_SERVER_SELECTION_TIMEOUT_MS,
                connectTimeoutMS=MONGODB_CONNECT_TIMEOUT_MS,
            )
            client.admin.command("ping")
            client.close()
            return True, f"Connected to MongoDB ({MONGODB_DATABASE})."
        except Exception as error:
            return False, f"MongoDB is not reachable: {error}"

    missing = [
        name
        for name, value in {
            "DB_HOST": DB_HOST,
            "DB_PORT": DB_PORT,
            "DB_NAME": DB_NAME,
            "DB_USER": DB_USER,
            "DB_PASSWORD": DB_PASSWORD,
        }.items()
        if not value
    ]
    if missing:
        return False, f"Missing database settings: {', '.join(missing)}."

    try:
        with get_connection() as connection:
            connection.execute("SELECT 1")
        return True, f"Connected to PostgreSQL ({DB_NAME})."
    except Exception as error:
        return False, f"PostgreSQL is not reachable: {error}"


def get_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


if __name__ == "__main__":
    try:
        conn = get_connection()

        print("PostgreSQL connected successfully")

        conn.close()

    except Exception as e:
        print("Database connection failed")
        print(e)
