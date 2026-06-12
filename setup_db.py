"""
إنشاء قاعدة بيانات PostgreSQL
يتطلب تعيين متغيرات البيئة:
  PG_USER, PG_PASSWORD, PG_HOST, PG_PORT, PG_DB_NAME
"""
import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.sql import Identifier, Literal, SQL

def create_database():
    db_name = os.environ.get('PG_DB_NAME') or os.environ.get('DATABASE_NAME') or 'medical_system'
    user = os.environ.get('PG_USER') or os.environ.get('DATABASE_USER') or 'postgres'
    host = os.environ.get('PG_HOST') or os.environ.get('DATABASE_HOST') or 'localhost'
    port = os.environ.get('PG_PORT') or os.environ.get('DATABASE_PORT') or '5432'
    password = os.environ.get('PG_PASSWORD') or os.environ.get('DATABASE_PASSWORD')

    if not password:
        print("ERROR: PG_PASSWORD or DATABASE_PASSWORD environment variable is required.", flush=True)
        return False

    print(f"Attempting to connect to PostgreSQL at {host}:{port} as {user}...", flush=True)

    try:
        con = psycopg2.connect(dbname='postgres', user=user, host=host, password=password, port=port)
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        print("Connection successful.", flush=True)
    except psycopg2.OperationalError as e:
        print(f"Connection failed: {e}", flush=True)
        return False

    try:
        cur = con.cursor()

        # Check if exists (parameterized)
        cur.execute(
            SQL("SELECT 1 FROM pg_catalog.pg_database WHERE datname = {}").format(Literal(db_name))
        )
        exists = cur.fetchone()

        if not exists:
            print(f"Creating database {db_name}...", flush=True)
            cur.execute(SQL("CREATE DATABASE {}").format(Identifier(db_name)))
            print("Database created successfully.", flush=True)
        else:
            print(f"Database {db_name} already exists.", flush=True)

        cur.close()
        con.close()
        return True
    except Exception as e:
        print(f"An error occurred during DB creation: {e}", flush=True)
        return False

if __name__ == "__main__":
    success = create_database()
    if not success:
        sys.exit(1)
