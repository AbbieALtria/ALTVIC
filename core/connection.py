# core/connection.py - Database connection manager for Altria Ops

import os
import json
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv()

ENV_FILE = Path(__file__).parent.parent / '.env'


class ConnectionManager:
    def __init__(self):
        self.host = os.getenv('DB_HOST', '')
        self.user = os.getenv('DB_USER', '')
        self.password = os.getenv('DB_PASSWORD', '')
        self.database = os.getenv('DB_NAME', 'asterisk')
        self.port = os.getenv('DB_PORT', '3306')

    def prompt_for_connection(self):
        """Interactively prompt the user for DB connection details and save to .env."""
        print("\n  Enter new database connection details.")
        print("  Press Enter to keep the current value shown in brackets.\n")

        host = input(f"  DB Host [{self.host}]: ").strip() or self.host
        user = input(f"  DB User [{self.user}]: ").strip() or self.user
        password = input(f"  DB Password [{'*' * len(self.password)}]: ").strip() or self.password
        database = input(f"  DB Name [{self.database}]: ").strip() or self.database
        port = input(f"  DB Port [{self.port}]: ").strip() or self.port

        if not all([host, user, password, database]):
            print("\n  Missing required fields. Connection not saved.")
            return False

        try:
            import pymysql
            conn = pymysql.connect(
                host=host,
                user=user,
                password=password,
                database=database,
                port=int(port),
                connect_timeout=5
            )
            conn.close()
            print("\n  Connection test successful.")
        except Exception as e:
            print(f"\n  Warning: Could not connect to database: {e}")
            confirm = input("  Save anyway? (y/n): ").strip().lower()
            if confirm != 'y':
                return False

        # Save to .env
        env_path = str(ENV_FILE)
        if not ENV_FILE.exists():
            ENV_FILE.touch()

        set_key(env_path, 'DB_HOST', host)
        set_key(env_path, 'DB_USER', user)
        set_key(env_path, 'DB_PASSWORD', password)
        set_key(env_path, 'DB_NAME', database)
        set_key(env_path, 'DB_PORT', str(port))

        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = str(port)

        print("  Connection details saved to .env")
        return True

    def get_params(self):
        """Return current connection params as a dict."""
        return {
            'host': self.host,
            'user': self.user,
            'password': self.password,
            'database': self.database,
            'port': int(self.port)
        }
