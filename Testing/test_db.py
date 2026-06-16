# test_db.py - Test database connection

from core.database import db
from utils.colors import Colors, print_color

def test_connection():
    print_color("\n🔍 Testing Database Connection...", Colors.CYAN)
    
    # Try to connect and run a simple query
    result = db.execute_query("SELECT NOW() as now")
    
    if result:
        print_color(f"✅ Connected successfully!", Colors.GREEN)
        print_color(f"   Server time: {result[0]['now']}", Colors.YELLOW)
        return True
    else:
        print_color(f"❌ Connection failed!", Colors.RED)
        return False

if __name__ == "__main__":
    test_connection()