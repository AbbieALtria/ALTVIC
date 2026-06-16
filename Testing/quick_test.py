# quick_test.py - Quick test with your actual credentials

import pymysql
from pymysql.cursors import DictCursor

def test():
    print("=" * 60)
    print("TESTING CONNECTION TO VICIDIAL SERVER")
    print("=" * 60)
    
    # Your working credentials
    config = {
        'host': '216.219.88.67',
        'user': 'cron',
        'password': '1234',
        'database': 'asterisk',
        'port': 3306,
        'cursorclass': DictCursor
    }
    
    print(f"\n📋 Connecting to:")
    print(f"  • Host: {config['host']}")
    print(f"  • User: {config['user']}")
    print(f"  • Database: {config['database']}")
    
    try:
        conn = pymysql.connect(**config)
        print("✅ Connected successfully!")
        
        with conn.cursor() as cursor:
            # Get server time
            cursor.execute("SELECT NOW() as now")
            result = cursor.fetchone()
            print(f"📅 Server time: {result['now']}")
            
            # Fixed: Correct syntax for SHOW TABLES
            cursor.execute("SHOW TABLES LIKE 'vicidial_%'")
            tables = cursor.fetchall()
            if tables:
                print(f"\n📊 Found {len(tables)} Vicidial tables")
                print("  First 5 tables:")
                for i, table in enumerate(tables[:5]):
                    # Handle different result formats
                    table_name = list(table.values())[0] if table else ''
                    print(f"    {i+1}. {table_name}")
            else:
                print("\n⚠️ No vicidial tables found")
            
            # Test a simple query from your closer_report
            print("\n🔍 Testing vicidial_closer_log access...")
            cursor.execute("SELECT COUNT(*) as count FROM vicidial_closer_log LIMIT 1")
            count = cursor.fetchone()
            print(f"✅ Can access vicidial_closer_log")
        
        conn.close()
        print("\n✅ All tests passed! Your database connection is working.")
        return True
        
    except pymysql.Error as e:
        print(f"\n❌ Connection failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test()
    input("\nPress Enter to exit...")