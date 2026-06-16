#!/usr/bin/env python3
# =============================================================================
# Script:       get_groups.py
# Version:      1.0.0
# Date:         2026-02-26
# Description:  Query ViciDial database to list all inbound groups
# Author:       Altria Ops Team
# =============================================================================

import mysql.connector
import getpass
import os
from tabulate import tabulate

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    clear_screen()
    
    print("=" * 80)
    print("                 VICIDIAL INBOUND GROUPS REPORT")
    print("=" * 80)
    print()
    
    # Database connection details
    host = "localhost"
    database = "asterisk"
    user = "cron"
    
    try:
        # Get password securely
        password = getpass.getpass(f"Enter MySQL password for user '{user}': ")
        
        # Connect to database
        print("\n📡 Connecting to database...", end="", flush=True)
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        print(" ✅")
        
        cursor = conn.cursor(dictionary=True)
        
        # Get total count
        cursor.execute("SELECT COUNT(*) as total FROM vicidial_inbound_groups")
        total = cursor.fetchone()['total']
        print(f"\n📊 Total inbound groups: {total}")
        
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
            print("\n" + "=" * 80)
            print("INBOUND GROUPS LIST")
            print("=" * 80)
            
            # Prepare data for tabulate
            table_data = []
            for i, group in enumerate(groups, 1):
                active_status = "✅ Active" if group['active'] == 'Y' else "❌ Inactive"
                description = group['description'] or ""
                if len(description) > 40:
                    description = description[:37] + "..."
                
                table_data.append([
                    i,
                    group['group_id'],
                    group['group_name'] or "",
                    active_status,
                    description
                ])
            
            # Print table
            headers = ["#", "Group ID", "Group Name", "Status", "Description"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            print(f"\n✅ Total: {len(groups)} groups displayed")
            
            # Option to see campaign assignments
            print("\n" + "=" * 80)
            show_campaigns = input("🔍 Show campaign assignments? (y/n): ").strip().lower()
            
            if show_campaigns == 'y':
                print("\n" + "=" * 80)
                print("CAMPAIGN ASSIGNMENTS BY GROUP")
                print("=" * 80)
                
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
                            print(f"\n📌 {group_id} - {group['group_name'] or 'No name'}")
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
        print("\n" + "=" * 80)
        print("✅ Script completed successfully!")
        
    except mysql.connector.Error as err:
        print(f"\n❌ MySQL Error: {err}")
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("=" * 80)

if __name__ == "__main__":
    main()