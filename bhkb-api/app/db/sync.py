"""Synchronous PostgreSQL helpers used in ingestion scripts"""
import os

import psycopg

DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    raise RuntimeError("DATABASE_URL is not set. Check your .env / docker-compose.yml.")


def get_conn():
    if not DB_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(DB_URL, autocommit=True)
