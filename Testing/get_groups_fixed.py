#!/usr/bin/env python3
# =============================================================================
# Script:       get_groups_fixed.py
# Location:     D:\Altria_Ops\get_groups_fixed.py
# Version:      1.0.0
# Date:         2026-02-26
# Description:  List ViciDial inbound groups (fixed for your table structure)
# Author:       Altria Ops Team
# =============================================================================

import mysql.connector
from mysql.connector import Error
import os

# =============================================================================
# Database Configuration
# =============================================================================
DB_CONFIG = {
    'host': '216.219.88.67',
    'port': 3306,
    'database': 'asterisk',
    'user': 'cron',
    'password': '1234'
}

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_line(char="=", length=80):
    """Print a line of characters"""
    print(char * length)

def main():
    clear_screen()
    
    print_line("=")
    print("VICIDIAL INBOUND GROUPS REPORT".center(80))
    print_line("=")
    print()
    
    try:
        # Connect to database
        print(f"📡 Connecting to {DB_CONFIG['host']}...", end="", flush=True)
        conn = mysql.connector.connect(**DB_CONFIG)
        print(" ✅")
        
        cursor = conn.cursor(dictionary=True)
        
        # First, let's see what columns actually exist in the table
        cursor.execute("SHOW COLUMNS FROM vicidial_inbound_groups")
        columns = cursor.fetchall()
        
        print("\n📋 Table Structure:")
        print("-" * 50)
        for col in columns:
            print(f"  • {col['Field']} ({col['Type']})")
        print("-" * 50)
        
        # Build query based on available columns
        select_cols = ["group_id", "group_name", "active"]
        
        # Add description only if it exists
        has_description = any(col['Field'] == 'description' for col in columns)
        
        query = f"""
            SELECT {', '.join(select_cols)}
            FROM vicidial_inbound_groups
            ORDER BY active DESC, group_id
        """
        
        cursor.execute(query)
        groups = cursor.fetchall()
        
        print(f"\n📊 Total inbound groups: {len(groups)}")
        
        if groups:
            print("\n" + "-" * 80)
            print("INBOUND GROUPS LIST")
            print("-" * 80)
            print(f"{'#':<4} {'Group ID':<20} {'Group Name':<40} {'Status':<8}")
            print("-" * 80)
            
            for i, group in enumerate(groups, 1):
                group_id = group['group_id']
                group_name = group['group_name'] or ""
                if len(group_name) > 38:
                    group_name = group_name[:35] + "..."
                    
                active_status = "✅" if group['active'] == 'Y' else "❌"
                
                print(f"{i:<4} {group_id:<20} {group_name:<40} {active_status:<8}")
            
            print("-" * 80)
            print(f"✅ Total: {len(groups)} groups displayed")
            
            # Option to see campaign assignments
            print("\n" + "-" * 80)
            show_campaigns = input("🔍 Show campaign assignments? (y/n): ").strip().lower()
            
            if show_campaigns == 'y':
                print("\n" + "-" * 80)
                print("CAMPAIGN ASSIGNMENTS BY GROUP")
                print("-" * 80)
                
                # Find the allowed groups column in campaigns table
                cursor.execute("SHOW COLUMNS FROM vicidial_campaigns")
                campaign_columns = [col['Field'] for col in cursor.fetchall()]
                
                # Check for common column names
                candidates = [
                    "allowed_ingroups", "allowed_inbound_groups", 
                    "allowed_in_groups", "allow_ingroups", 
                    "inbound_groups", "allowed_groups", "closer_campaigns"
                ]
                
                allowed_col = None
                for col in candidates:
                    if col in campaign_columns:
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
                    print(f"Available columns: {', '.join(campaign_columns[:10])}")
                    if len(campaign_columns) > 10:
                        print(f"... and {len(campaign_columns)-10} more")
        
        # Close connection
        cursor.close()
        conn.close()
        print("\n" + "-" * 80)
        print("✅ Script completed successfully!")
        
    except mysql.connector.Error as err:
        print(f"\n❌ MySQL Error: {err}")
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("-" * 80)

if __name__ == "__main__":
    main()