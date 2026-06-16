#!/usr/bin/env python3
# =============================================================================
# Script:       get_groups.py
# Location:     D:\Altria_Ops\get_groups.py
# Version:      1.0.0
# Date:         2026-02-26
# Description:  List ViciDial inbound groups from remote server
# Author:       Altria Ops Team
# =============================================================================

import mysql.connector
from mysql.connector import Error
import getpass
import os

# =============================================================================
# Database Configuration - CHANGE THESE VALUES
# =============================================================================
DB_CONFIG = {
    'host': '216.219.88.67',      # Your remote server IP
    'port': 3306,                  # MySQL port
    'database': 'asterisk',        # Database name
    'user': 'cron',                 # Database user
    'password': '1234'              # Database password
}

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_line(char="=", length=80):
    """Print a line of characters"""
    print(char * length)

def test_connection():
    """Test database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.close()
        return True, "Connection successful"
    except Error as e:
        return False, str(e)

def main():
    clear_screen()
    
    print_line("=")
    print("                 VICIDIAL INBOUND GROUPS REPORT".center(80))
    print_line("=")
    print()
    
    # Show connection details
    print(f"📡 Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"📡 Database: {DB_CONFIG['database']}")
    print(f"📡 User: {DB_CONFIG['user']}")
    print()
    
    # Test connection
    print("Testing connection...")
    success, message = test_connection()
    
    if not success:
        print(f"❌ Connection failed: {message}")
        print_line("-")
        print("\n💡 Troubleshooting tips:")
        print("  1. Check if the server IP is correct: 216.219.88.67")
        print("  2. Verify MySQL is running on the remote server")
        print("  3. Check firewall settings (port 3306 should be open)")
        print("  4. Verify MySQL allows remote connections")
        print("  5. Check if user 'cron' has remote access permissions")
        print("  6. Try telnet 216.219.88.67 3306 to test connectivity")
        return
    
    print("✅ Connection successful!")
    
    try:
        # Connect to database
        print("\n📡 Connecting to database...", end="", flush=True)
        conn = mysql.connector.connect(**DB_CONFIG)
        print(" ✅")
        
        cursor = conn.cursor(dictionary=True)
        
        # Get MySQL version
        cursor.execute("SELECT VERSION() as version")
        version = cursor.fetchone()['version']
        print(f"📊 MySQL Version: {version}")
        
        # Get total count of inbound groups
        cursor.execute("SELECT COUNT(*) as total FROM vicidial_inbound_groups")
        result = cursor.fetchone()
        total = result['total'] if result else 0
        print(f"\n📊 Total inbound groups: {total}")
        
        if total == 0:
            print("\n❌ No inbound groups found in database")
            return
        
        # Get all groups with details
        cursor.execute("""
            SELECT 
                group_id,
                group_name,
                active,
                description
            FROM vicidial_inbound_groups
            ORDER BY active DESC, group_id
        """)
        
        groups = cursor.fetchall()
        
        if groups:
            print("\n" + "-" * 80)
            print("INBOUND GROUPS LIST")
            print("-" * 80)
            print(f"{'#':<4} {'Group ID':<20} {'Group Name':<30} {'Status':<10} {'Description'}")
            print("-" * 80)
            
            for i, group in enumerate(groups, 1):
                group_id = group['group_id']
                group_name = group['group_name'] or ""
                if len(group_name) > 28:
                    group_name = group_name[:25] + "..."
                    
                active_status = "✅" if group['active'] == 'Y' else "❌"
                
                description = group['description'] or ""
                if len(description) > 20:
                    description = description[:17] + "..."
                
                print(f"{i:<4} {group_id:<20} {group_name:<30} {active_status:<10} {description}")
            
            print("-" * 80)
            print(f"✅ Total: {len(groups)} groups displayed")
            
            # Option to see campaign assignments
            print("\n" + "-" * 80)
            show_campaigns = input("🔍 Show campaign assignments? (y/n): ").strip().lower()
            
            if show_campaigns == 'y':
                print("\n" + "-" * 80)
                print("CAMPAIGN ASSIGNMENTS BY GROUP")
                print("-" * 80)
                
                # Find the allowed groups column
                cursor.execute("SHOW COLUMNS FROM vicidial_campaigns")
                columns = [col['Field'] for col in cursor.fetchall()]
                
                # Check for common column names
                candidates = [
                    "allowed_ingroups", "allowed_inbound_groups", 
                    "allowed_in_groups", "allow_ingroups", 
                    "inbound_groups", "allowed_groups", "closer_campaigns"
                ]
                
                allowed_col = None
                for col in candidates:
                    if col in columns:
                        allowed_col = col
                        break
                
                if allowed_col:
                    print(f"\n📌 Using column: {allowed_col}")
                    print()
                    
                    for group in groups:
                        group_id = group['group_id']
                        cursor.execute(f"""
                            SELECT campaign_id, campaign_name, active
                            FROM vicidial_campaigns
                            WHERE {allowed_col} LIKE %s
                               OR {allowed_col} LIKE %s
                               OR {allowed_col} LIKE %s
                            ORDER BY campaign_id
                        """, (f"%{group_id}%", f"% {group_id} %", f"{group_id}%"))
                        
                        campaigns = cursor.fetchall()
                        
                        if campaigns:
                            group_name_display = group['group_name'] or "No name"
                            print(f"\n📌 {group_id} - {group_name_display}")
                            for camp in campaigns:
                                status = "✅" if camp['active'] == 'Y' else "❌"
                                print(f"  • {camp['campaign_id']} - {camp['campaign_name']} {status}")
                else:
                    print("\n❌ Could not find allowed groups column")
                    print(f"Available columns: {', '.join(columns[:10])}")
                    if len(columns) > 10:
                        print(f"... and {len(columns)-10} more")
        
        else:
            print("\n❌ No inbound groups found in database")
        
        # Close connection
        cursor.close()
        conn.close()
        print("\n" + "-" * 80)
        print("✅ Script completed successfully!")
        
    except mysql.connector.Error as err:
        print(f"\n❌ MySQL Error: {err}")
        print("\n💡 Troubleshooting tips:")
        print("  1. Check if the server is accessible")
        print("  2. Verify username and password")
        print("  3. Check if database 'asterisk' exists")
        print("  4. Verify table 'vicidial_inbound_groups' exists")
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("-" * 80)

if __name__ == "__main__":
    main()