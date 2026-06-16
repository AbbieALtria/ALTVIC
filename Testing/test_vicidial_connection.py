# test_vicidial_connection.py - Test connection to Vicidial MySQL server

import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    print("=" * 60)
    print("TESTING CONNECTION TO VICIDIAL SERVER")
    print("=" * 60)
    
    host = os.getenv('DB_HOST', '')
    user = os.getenv('DB_USER', '')
    password = os.getenv('DB_PASSWORD', '')
    database = os.getenv('DB_NAME', '')
    port = int(os.getenv('DB_PORT', 3306))
    
    print(f"\n📋 Connection Details:")
    print(f"  • Host: {host}")
    print(f"  • Port: {port}")
    print(f"  • User: {user}")
    print(f"  • Database: {database}")
    
    if not host or not user:
        print("\n❌ Missing database credentials in .env file!")
        return False
    
    try:
        print("\n🔄 Attempting to connect to Vicidial server...")
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        print("✅ Connected successfully!")
        
        # Test a simple query
        with conn.cursor() as cursor:
            cursor.execute("SELECT NOW() as server_time")
            result = cursor.fetchone()
            print(f"📅 Server time: {result['server_time']}")
            
            # Check if Vicidial tables exist
            cursor.execute("SHOW TABLES LIKE 'vicidial_%' LIMIT 5")
            tables = cursor.fetchall()
            if tables:
                print("\n📊 Vicidial tables found:")
                for table in tables:
                    print(f"  • {list(table.values())[0]}")
            else:
                print("\n⚠️ No vicidial tables found in this database")
        
        conn.close()
        return True
        
    except pymysql.Error as e:
        print(f"\n❌ Connection failed: {e}")
        
        if "Access denied" in str(e):
            print("\n🔧 FIX: Wrong username or password")
        elif "Can't connect" in str(e):
            print("\n🔧 FIX: Cannot reach the server")
            print(f"   • Check if {host} is correct")
            print("   • Check if MySQL port 3306 is open on the server")
            print("   • Check firewall settings")
        elif "Unknown database" in str(e):
            print("\n🔧 FIX: Database doesn't exist")
            print(f"   • Database '{database}' not found")
        
        return False

if __name__ == "__main__":
    test_connection()
    input("\nPress Enter to exit...")