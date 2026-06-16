#!/usr/bin/env python3
# core/email_database.py - Pinktools (altriaca_email) database connector

import pymysql
from pymysql.cursors import DictCursor
import os
from dotenv import load_dotenv

load_dotenv()

class EmailDatabase:
    def __init__(self):
        self.host     = os.getenv('EMAIL_DB_HOST',     'localhost')
        self.user     = os.getenv('EMAIL_DB_USER',     'altriaca_root')
        self.password = os.getenv('EMAIL_DB_PASSWORD', '')
        self.database = os.getenv('EMAIL_DB_NAME',     'altriaca_email')
        self.port     = int(os.getenv('EMAIL_DB_PORT', 3306))

    def execute_query(self, query, params=None):
        conn = cursor = None
        try:
            conn = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port,
                cursorclass=DictCursor,
                charset='utf8mb4',
                connect_timeout=5
            )
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            return cursor.fetchall()
        except pymysql.Error as e:
            print(f"[EmailDB] Query error: {e}")
            return []
        finally:
            if cursor: cursor.close()
            if conn:   conn.close()

    def test_connection(self):
        try:
            result = self.execute_query("SELECT 1 AS ok")
            return bool(result)
        except Exception:
            return False

email_db = EmailDatabase()
