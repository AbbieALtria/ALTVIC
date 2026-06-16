# core/database.py - Database connection handler for Altria_Ops
# Using the exact same settings as your working vicidial-monitor

import pymysql
from pymysql.cursors import DictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Database:
    def __init__(self):
        # Use the credentials from your working config
        self.host = os.getenv('DB_HOST', '167.17.68.94')
        self.user = os.getenv('DB_USER', 'altriadb')
        self.password = os.getenv('DB_PASSWORD', 'altria123db')
        self.database = os.getenv('DB_NAME', 'asterisk')
        self.port = int(os.getenv('DB_PORT', 3306))
        
    def execute_query(self, query, params=None):
        """Execute query and return results - matching your working pattern exactly"""
        conn = None
        cursor = None
        try:
            # Create connection with your working credentials
            conn = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port,
                cursorclass=DictCursor,
                charset='utf8mb4'
            )
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            return cursor.fetchall()
        except pymysql.Error as e:
            print(f"❌ Query error: {e}")
            print(f"   Query: {query[:100]}...")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

# Create global database instance
db = Database()