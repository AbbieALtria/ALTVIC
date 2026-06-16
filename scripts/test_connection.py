import mysql.connector
from mysql.connector import Error
from config.settings import get_db_connection_params

def test_connection():
    conn_params = get_db_connection_params()
    print(f"Testing connection to: {conn_params['host']}:{conn_params['port']}")
    print(f"Database: {conn_params['database']}")
    print(f"User: {conn_params['user']}")
    print("-" * 50)
    
    try:
        conn = mysql.connector.connect(**conn_params)
        print("✅ Connection successful!")
        
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"📊 MySQL Version: {version[0]}")
        
        cursor.close()
        conn.close()
        
    except Error as e:
        print(f"❌ Connection failed: {e}")
        print("\n💡 Check:")
        print("1. MySQL server is running on the remote host")
        print("2. Port 3306 is open in firewall")
        print("3. MySQL allows remote connections")
        print("4. User 'cron' has proper permissions")

if __name__ == "__main__":
    test_connection()