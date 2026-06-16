#!/usr/bin/env python3
# =============================================================================
# File:         inbound_groups.py
# Version:      2.5.0
# Date:         2026-02-28
# Description:  Final stable Inbound Groups Manager
# Author:       Altria Ops Team
# =============================================================================

from core.database import db
from utils.colors import Colors, print_header, print_error, print_warning, print_info, print_color
from utils.formatter import format_datetime
from utils.unified_search import (
    get_all_ingroups,
    search_ingroups,
    print_ingroup_results,
    show_paginated_results
)


def show_all_inbound_groups():
    print_header("ALL INBOUND GROUPS", Colors.CYAN)

    groups = get_all_ingroups(active_filter="ALL", limit=1000)

    if not groups:
        print_warning("No inbound groups found.")
        input("\nPress Enter to continue...")
        return

    print(f"\nTotal Inbound Groups: {len(groups)}")
    print("=" * 80)

    selected = show_paginated_results(groups, item_type="inbound groups", page=1, page_size=25)

    if selected:
        show_group_details(selected['group_id'])

    return groups


def search_inbound_group():
    print_header("SEARCH INBOUND GROUP", Colors.CYAN)
    term = input("\nEnter group ID or name (or press Enter for all): ").strip()

    results = search_ingroups(term, active_filter="ALL", limit=100)

    if results:
        print_ingroup_results(results)
    else:
        print_warning("No matching inbound groups found.")

    input("\nPress Enter to continue...")


def view_group_agents():
    print_header("VIEW GROUP AGENTS", Colors.CYAN)

    groups = get_all_ingroups(limit=500)
    if not groups:
        print_warning("No groups found.")
        input("\nPress Enter to continue...")
        return

    print("\nAvailable Groups:")
    print("-" * 60)
    for i, g in enumerate(groups[:40], 1):
        print(f"  {i:3}. {g['group_id']}")
    if len(groups) > 40:
        print(f"  ... and {len(groups)-40} more")
    print("-" * 60)

    choice = input("\nEnter number or group name (e.g. Aiven): ").strip()

    selected_group = None
    if choice.isdigit() and 1 <= int(choice) <= len(groups):
        selected_group = groups[int(choice)-1]['group_id']
    else:
        for g in groups:
            if g['group_id'].lower() == choice.lower():
                selected_group = g['group_id']
                break

    if not selected_group:
        print_error(f"Group '{choice}' not found.")
        input("\nPress Enter to continue...")
        return

    print("\nSelect view mode:")
    print("  1. Live agents (currently logged in)")
    print("  2. Agents allowed via user groups")
    print("  3. Agents who recently handled calls (last 30 days)")
    mode = input(f"\nChoice (1-3): ").strip()

    print_header(f"AGENTS FOR: {selected_group}", Colors.GREEN)

    try:
        if mode == '1':
            query = """
                SELECT vla.user, vu.full_name, vla.status,
                       TIMESTAMPDIFF(MINUTE, vla.last_state_change, NOW()) AS minutes_in_status
                FROM vicidial_live_agents vla
                LEFT JOIN vicidial_users vu ON vla.user = vu.user
                WHERE vla.campaign_id = %s
                ORDER BY vla.status, vla.user
            """
            agents = db.execute_query(query, (selected_group,)) or []
            if not agents:
                print_warning("No agents currently logged in.")
            else:
                print(f"\n{'#':<3} {'User':<15} {'Name':<25} {'Status':<12} {'Time'}")
                print("-" * 80)
                for i, a in enumerate(agents, 1):
                    print(f"{i:<3} {a['user']:<15} {a.get('full_name','Unknown'):<25} "
                          f"{a['status']:<12} {a.get('minutes_in_status',0)} min")

        elif mode == '2':
            ug = db.execute_query(
                "SELECT allowed_user_groups FROM vicidial_campaigns WHERE campaign_id = %s",
                (selected_group,)
            )
            if not ug or not ug[0].get('allowed_user_groups'):
                print_warning("No allowed user groups configured.")
                input("\nPress Enter...")
                return

            allowed = [x.strip() for x in ug[0]['allowed_user_groups'].split('-') if x.strip()]
            placeholders = ','.join(['%s'] * len(allowed))
            query = f"SELECT user, full_name, user_group, active FROM vicidial_users WHERE user_group IN ({placeholders}) ORDER BY user"
            users = db.execute_query(query, tuple(allowed)) or []
            if not users:
                print_warning("No users found.")
            else:
                print(f"\n{'#':<3} {'User':<15} {'Name':<25} {'User Group':<20} {'Active'}")
                print("-" * 85)
                for i, u in enumerate(users, 1):
                    print(f"{i:<3} {u['user']:<15} {u.get('full_name','?'):<25} "
                          f"{u['user_group']:<20} {'Y' if u.get('active')=='Y' else 'N'}")

        elif mode == '3':
            query = """
                SELECT a.user, u.full_name, COUNT(*) as calls_30d, MAX(a.event_time) as last_call
                FROM vicidial_agent_log a
                JOIN vicidial_users u ON a.user = u.user
                JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
                WHERE c.campaign_id = %s AND a.event_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY a.user
                ORDER BY calls_30d DESC
            """
            agents = db.execute_query(query, (selected_group,)) or []
            if not agents:
                print_warning(f"No recent activity for '{selected_group}'.")
            else:
                print(f"\n{'#':<3} {'User':<15} {'Name':<25} {'Calls (30d)':<12} {'Last Call'}")
                print("-" * 85)
                for i, a in enumerate(agents, 1):
                    last = format_datetime(a['last_call']) if a['last_call'] else '—'
                    print(f"{i:<3} {a['user']:<15} {a.get('full_name','?'):<25} "
                          f"{a['calls_30d']:<12} {last}")

        else:
            print_error("Invalid choice.")

    except Exception as e:
        print_error(f"Error: {str(e)}")

    input("\nPress Enter to continue...")


def group_statistics():
    print_header("GROUP STATISTICS", Colors.MAGENTA)

    groups = get_all_ingroups(limit=1000)
    total = len(groups)
    active = len([g for g in groups if g.get('active') == 'Y'])

    print(f"  Total Groups     : {total}")
    print(f"  Active Groups    : {active}")
    print(f"  Inactive Groups  : {total - active}")

    input("\nPress Enter to continue...")


def show_group_details(group_id: str):
    print_header(f"GROUP DETAILS: {group_id}", Colors.MAGENTA)

    try:
        info = db.execute_query(
            "SELECT group_id, group_name, active FROM vicidial_inbound_groups WHERE group_id = %s",
            (group_id,)
        )
        if info:
            g = info[0]
            print(f"  Group Name : {g.get('group_name','N/A')}")
            print(f"  Active     : {'Yes' if g.get('active')=='Y' else 'No'}")

        stats = db.execute_query("""
            SELECT 
                COUNT(*) as calls_30d,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered_30d
            FROM vicidial_closer_log
            WHERE campaign_id = %s 
              AND call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """, (group_id,))

        if stats and stats[0]['calls_30d'] > 0:
            s = stats[0]
            rate = s['answered_30d'] / s['calls_30d'] * 100 if s['calls_30d'] > 0 else 0
            print(f"\n  30-Day Calls   : {s['calls_30d']:,}")
            print(f"  Answered       : {s['answered_30d']:,} ({rate:.1f}%)")
        else:
            print("\n  No calls in last 30 days.")

    except Exception as e:
        print_warning(f"Could not load details: {str(e)}")

    input("\nPress Enter to continue...")


def inbound_groups_menu():
    while True:
        print_header("INBOUND GROUPS MANAGER", Colors.CYAN)
        print("  1. Show All Inbound Groups")
        print("  2. Search Inbound Group")
        print("  3. View Group Agents (Live / Assigned / Recent)")
        print("  4. Group Statistics")
        print("  0. Back to Campaign Menu")
        print("-" * 50)

        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

        if choice == '1':
            show_all_inbound_groups()
        elif choice == '2':
            search_inbound_group()
        elif choice == '3':
            view_group_agents()
        elif choice == '4':
            group_statistics()
        elif choice == '0':
            break
        else:
            print_error("Invalid option")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    inbound_groups_menu()