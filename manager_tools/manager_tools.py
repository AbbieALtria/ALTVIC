#!/usr/bin/env python3
# =============================================================================
# File:         manager_tools/manager_tools.py
# Version:      4.1.0
# Date:         2026-04-03
# Description:  Enterprise Manager Tools - Complete Campaign & DID Management
# Author:       Altria Ops Team
# =============================================================================

from core.database import db
from utils.colors import Colors, print_header, print_success, print_error, print_warning, print_color, print_info
from datetime import datetime, timedelta
from decimal import Decimal
import re

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def safe_str(value, default="-"):
    return str(value) if value is not None else default

def format_number(value):
    if value is None:
        return "0"
    try:
        if isinstance(value, Decimal):
            value = int(value)
        return f"{int(value):,}"
    except:
        return str(value)

def format_timedelta(td):
    """Convert timedelta to HH:MM:SS string format"""
    if td is None:
        return "0:00:00"
    if isinstance(td, timedelta):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    return str(td)

def to_int(value):
    """Convert Decimal or other types to int safely"""
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(value)
    except:
        return 0

def to_float(value):
    """Convert Decimal or other types to float safely"""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except:
        return 0.0

# =============================================================================
# DATABASE QUERY FUNCTIONS
# =============================================================================

def get_did_column_name():
    """Auto-detect the correct DID column name in vicidial_closer_log"""
    possible_columns = ['did_id', 'did_pattern', 'did', 'extension', 'phone_number', 'called_number']
    
    try:
        check_query = "SHOW COLUMNS FROM vicidial_closer_log"
        columns = db.execute_query(check_query) or []
        existing_columns = [col['Field'].lower() for col in columns]
        
        for col in possible_columns:
            if col in existing_columns:
                return col
    except:
        pass
    
    return 'did_id'

def discover_dids_from_calls(campaign_pattern=None, days_back=365):
    """Discover DIDs from call logs using auto-detected column name"""
    did_column = get_did_column_name()
    
    if campaign_pattern:
        query = f"""
            SELECT DISTINCT 
                {did_column} AS did_number,
                COUNT(*) AS call_count,
                MIN(DATE(call_date)) AS first_seen,
                MAX(DATE(call_date)) AS last_seen,
                GROUP_CONCAT(DISTINCT campaign_id) AS campaigns
            FROM vicidial_closer_log
            WHERE campaign_id LIKE %s
              AND call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
              AND {did_column} IS NOT NULL
              AND {did_column} != ''
              AND {did_column} != '0'
            GROUP BY {did_column}
            ORDER BY call_count DESC
            LIMIT 50;
        """
        results = db.execute_query(query, (campaign_pattern, days_back)) or []
    else:
        query = f"""
            SELECT DISTINCT 
                {did_column} AS did_number,
                COUNT(*) AS call_count,
                MIN(DATE(call_date)) AS first_seen,
                MAX(DATE(call_date)) AS last_seen,
                GROUP_CONCAT(DISTINCT campaign_id) AS campaigns
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
              AND {did_column} IS NOT NULL
              AND {did_column} != ''
              AND {did_column} != '0'
            GROUP BY {did_column}
            ORDER BY call_count DESC
            LIMIT 50;
        """
        results = db.execute_query(query, (days_back,)) or []
    
    return results

def get_all_campaigns_with_lifecycle():
    """Get all campaigns with their lifecycle information"""
    query = """
        SELECT 
            campaign_id,
            MIN(DATE(call_date)) AS first_call,
            MAX(DATE(call_date)) AS last_call,
            COUNT(*) AS total_calls
        FROM vicidial_closer_log
        WHERE campaign_id IS NOT NULL AND campaign_id != ''
        GROUP BY campaign_id
        ORDER BY campaign_id;
    """
    return db.execute_query(query) or []

def get_campaign_lifecycle(campaign_id):
    """Get campaign lifecycle info: first call, last call"""
    query_calls = """
        SELECT 
            MIN(DATE(call_date)) AS first_call,
            MAX(DATE(call_date)) AS last_call,
            COUNT(*) AS total_calls,
            DATEDIFF(MAX(call_date), MIN(call_date)) AS active_days
        FROM vicidial_closer_log
        WHERE campaign_id = %s
    """
    call_info = db.execute_query(query_calls, (campaign_id,))
    
    return {
        'first_call': call_info[0]['first_call'] if call_info and call_info[0]['first_call'] else None,
        'last_call': call_info[0]['last_call'] if call_info and call_info[0]['last_call'] else None,
        'total_calls': to_int(call_info[0]['total_calls']) if call_info else 0,
        'active_days': to_int(call_info[0]['active_days']) if call_info else 0,
    }

# =============================================================================
# CAMPAIGN SEARCH & SELECTION
# =============================================================================

def search_and_select_campaign(search_term):
    """Search for campaigns matching a term and let user select"""
    campaigns = get_all_campaigns_with_lifecycle()
    
    if not campaigns:
        print_warning("No campaigns found in database.")
        return None
    
    # Search for matches (case-insensitive)
    matches = []
    search_lower = search_term.lower()
    
    for camp in campaigns:
        if search_lower in camp['campaign_id'].lower():
            matches.append(camp)
    
    if not matches:
        print_warning(f"No campaigns found matching '{search_term}'")
        print(f"\n{Colors.CYAN}📋 Available campaigns (first 20):{Colors.RESET}")
        print("  " + "─" * 60)
        for i, camp in enumerate(campaigns[:20], 1):
            first_call = camp['first_call'] or 'Never'
            total_calls = format_number(to_int(camp['total_calls']))
            print(f"   {i:2d}. {camp['campaign_id'][:35]:<35} | First: {first_call} | Calls: {total_calls}")
        if len(campaigns) > 20:
            print(f"   ... and {len(campaigns) - 20} more campaigns")
        print("  " + "─" * 60)
        return None
    
    if len(matches) == 1:
        # Single match, return it directly
        return matches[0]['campaign_id']
    
    # Multiple matches, let user choose
    print(f"\n{Colors.YELLOW}📋 Found {len(matches)} campaigns matching '{search_term}':{Colors.RESET}")
    print("  " + "─" * 80)
    print(f"  {'#':<4} {'Campaign Name':<35} {'First Call':<12} {'Last Call':<12} {'Total Calls'}")
    print("  " + "─" * 80)
    
    for i, camp in enumerate(matches, 1):
        first_call = str(camp['first_call'] or 'Never')[:10]
        last_call = str(camp['last_call'] or 'Never')[:10]
        total_calls = format_number(to_int(camp['total_calls']))
        
        # Status indicator
        if camp['last_call']:
            days_since = (datetime.now().date() - camp['last_call']).days
            if days_since <= 7:
                status = "🟢"
            elif days_since <= 30:
                status = "🟡"
            else:
                status = "🔴"
        else:
            status = "⚫"
        
        print(f"  {i:<4} {status} {camp['campaign_id'][:33]:<33} {first_call:<12} {last_call:<12} {total_calls}")
    
    print("  " + "─" * 80)
    
    choice = input(f"\n{Colors.CYAN}Select campaign number (or 0 to cancel): {Colors.RESET}").strip()
    
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(matches):
            return matches[idx]['campaign_id']
    
    return None

# =============================================================================
# CAMPAIGN & DID TABLE DISPLAY FUNCTIONS
# =============================================================================

def show_campaigns_with_dids_table():
    """Display a formatted table of all campaigns with their associated DIDs"""
    print_header("📋 CAMPAIGNS & ASSOCIATED DIDs TABLE", Colors.CYAN)
    
    campaigns = get_all_campaigns_with_lifecycle()
    
    if not campaigns:
        print_warning("No campaigns found")
        return
    
    print("\n" + "═" * 130)
    print(f"{'#':<4} {'Campaign Name':<30} {'First Call':<12} {'Last Call':<12} {'Total Calls':<12} {'DID Count':<10} {'Sample DIDs'}")
    print("═" * 130)
    
    for i, camp in enumerate(campaigns, 1):
        camp_name = camp['campaign_id']
        first_call = str(camp['first_call'] or 'Never')[:10]
        last_call = str(camp['last_call'] or 'Never')[:10]
        total_calls = format_number(to_int(camp['total_calls']))
        
        dids = discover_dids_from_calls(f'%{camp_name}%', 365)
        did_count = len(dids)
        
        if camp['last_call']:
            days_since = (datetime.now().date() - camp['last_call']).days
            if days_since <= 7:
                status = Colors.GREEN
                status_indicator = "🟢"
            elif days_since <= 30:
                status = Colors.YELLOW
                status_indicator = "🟡"
            else:
                status = Colors.RED
                status_indicator = "🔴"
        else:
            status = Colors.RED
            status_indicator = "⚫"
        
        # Get first 2 DIDs as sample
        did_numbers = []
        for did in dids[:2]:
            did_num = did['did_number']
            if did_num and did_num != '0':
                did_numbers.append(str(did_num)[:12])
        
        did_display = ', '.join(did_numbers) if did_numbers else '-'
        if len(dids) > 2:
            did_display += f" (+{len(dids)-2})"
        
        print(f"{status_indicator} {i:<3} {status}{camp_name[:28]:<30}{Colors.RESET} "
              f"{first_call:<12} {last_call:<12} {total_calls:<12} "
              f"{status}{did_count:<10}{Colors.RESET} {did_display[:40]}")
    
    print("═" * 130)
    
    print(f"\n{Colors.YELLOW}📊 LEGEND:{Colors.RESET}")
    print(f"   🟢 {Colors.GREEN}Active (call within 7 days){Colors.RESET}")
    print(f"   🟡 {Colors.YELLOW}Dormant (call within 30 days){Colors.RESET}")
    print(f"   🔴 {Colors.RED}Inactive (no call in 30+ days){Colors.RESET}")
    print(f"   ⚫ {Colors.RED}Never had calls{Colors.RESET}")
    
    active = sum(1 for c in campaigns if c['last_call'] and (datetime.now().date() - c['last_call']).days <= 7)
    dormant = sum(1 for c in campaigns if c['last_call'] and 7 < (datetime.now().date() - c['last_call']).days <= 30)
    inactive = sum(1 for c in campaigns if c['last_call'] and (datetime.now().date() - c['last_call']).days > 30)
    never = sum(1 for c in campaigns if not c['last_call'])
    
    total_dids = 0
    for c in campaigns:
        dids = discover_dids_from_calls(f'%{c["campaign_id"]}%', 365)
        total_dids += len(dids)
    
    print(f"\n{Colors.CYAN}📈 SUMMARY:{Colors.RESET}")
    print(f"   Total Campaigns: {len(campaigns)}")
    print(f"   🟢 Active Campaigns: {active}")
    print(f"   🟡 Dormant Campaigns: {dormant}")
    print(f"   🔴 Inactive Campaigns: {inactive}")
    print(f"   ⚫ Never Active: {never}")
    print(f"   📞 Total DIDs Discovered: {total_dids}")

def show_campaign_detail_with_dids(campaign_name):
    """Show detailed information for a specific campaign including all its DIDs"""
    # First, verify this is an exact campaign match
    campaigns = get_all_campaigns_with_lifecycle()
    exact_match = None
    
    for camp in campaigns:
        if camp['campaign_id'].lower() == campaign_name.lower():
            exact_match = camp
            break
    
    if not exact_match:
        # Not an exact match, try to search
        print_warning(f"Campaign '{campaign_name}' not found. Searching for matches...")
        selected = search_and_select_campaign(campaign_name)
        if selected:
            campaign_name = selected
        else:
            return None
    
    print_header(f"📋 CAMPAIGN DETAILS: {campaign_name.upper()}", Colors.CYAN)
    
    lifecycle = get_campaign_lifecycle(campaign_name)
    
    print(f"\n{Colors.YELLOW}📅 CAMPAIGN LIFECYCLE:{Colors.RESET}")
    print(f"   Campaign Name:    {Colors.CYAN}{campaign_name}{Colors.RESET}")
    print(f"   First Call Date:  {lifecycle['first_call'] or f'{Colors.RED}Never{Colors.RESET}'}")
    print(f"   Last Call Date:   {lifecycle['last_call'] or f'{Colors.RED}Never{Colors.RESET}'}")
    print(f"   Total Calls:      {format_number(lifecycle['total_calls'])}")
    print(f"   Active Days:      {lifecycle['active_days']} days")
    
    if lifecycle['first_call']:
        days_since_start = (datetime.now().date() - lifecycle['first_call']).days
        print(f"   Days Since Start: {days_since_start} days")
    
    if lifecycle['last_call']:
        days_since_last = (datetime.now().date() - lifecycle['last_call']).days
        if days_since_last <= 7:
            status = f"{Colors.GREEN}🟢 Active (within 7 days){Colors.RESET}"
        elif days_since_last <= 30:
            status = f"{Colors.YELLOW}🟡 Dormant (within 30 days){Colors.RESET}"
        else:
            status = f"{Colors.RED}🔴 Inactive ({days_since_last} days ago){Colors.RESET}"
        print(f"   Status:           {status}")
    
    print(f"\n{Colors.YELLOW}📞 ASSOCIATED DIDs (from call logs):{Colors.RESET}")
    dids = discover_dids_from_calls(f'%{campaign_name}%', 365)
    
    if dids:
        print("  " + "─" * 110)
        print(f"  {'DID Number':<20} {'Call Count':<12} {'First Seen':<12} {'Last Seen':<12} {'Days Active'}")
        print("  " + "─" * 110)
        
        for did in dids[:50]:
            did_number = did['did_number']
            call_count = format_number(to_int(did['call_count']))
            first_seen = did['first_seen']
            last_seen = did['last_seen']
            
            if first_seen and last_seen and isinstance(first_seen, datetime) and isinstance(last_seen, datetime):
                days_active = (last_seen.date() - first_seen.date()).days
                days_active_str = f"{days_active} days"
            else:
                days_active_str = "-"
            
            if last_seen and isinstance(last_seen, datetime):
                days_since = (datetime.now().date() - last_seen.date()).days
                if days_since <= 7:
                    did_status = f"{Colors.GREEN}🟢{Colors.RESET}"
                elif days_since <= 30:
                    did_status = f"{Colors.YELLOW}🟡{Colors.RESET}"
                else:
                    did_status = f"{Colors.RED}🔴{Colors.RESET}"
            else:
                did_status = "⚫"
            
            print(f"  {did_status} {str(did_number)[:18]:<18} {call_count:<12} {str(first_seen)[:10]:<12} {str(last_seen)[:10]:<12} {days_active_str}")
        
        if len(dids) > 50:
            print(f"  ... and {len(dids) - 50} more DIDs")
        
        print("  " + "─" * 110)
        
        total_calls = sum(to_int(d['call_count']) for d in dids)
        active_dids = 0
        for d in dids:
            if d['last_seen'] and isinstance(d['last_seen'], datetime):
                if (datetime.now().date() - d['last_seen'].date()).days <= 7:
                    active_dids += 1
        
        print(f"\n  {Colors.CYAN}DID Summary:{Colors.RESET}")
        print(f"     Total DIDs: {len(dids)}")
        print(f"     Active DIDs (last 7 days): {active_dids}")
        print(f"     Total calls across all DIDs: {format_number(total_calls)}")
        
    else:
        print(f"  {Colors.YELLOW}No DIDs discovered from call logs for this campaign{Colors.RESET}")
        print("  Possible reasons:")
        print("    1. Campaign uses outbound dialing only (no inbound DIDs)")
        print("    2. No calls recorded for this campaign")
        print("    3. DID information isn't being logged")
    
    return lifecycle

def show_campaigns_most_dids():
    """Show campaigns with the most associated DIDs"""
    print_header("🏆 CAMPAIGNS WITH MOST DIDs", Colors.CYAN)
    
    campaigns = get_all_campaigns_with_lifecycle()
    campaign_did_counts = []
    
    print("\n" + "🔄 Analyzing campaigns...")
    
    for i, camp in enumerate(campaigns):
        dids = discover_dids_from_calls(f'%{camp["campaign_id"]}%', 365)
        campaign_did_counts.append({
            'name': camp['campaign_id'],
            'did_count': len(dids),
            'total_calls': to_int(camp['total_calls']),
            'last_call': camp['last_call']
        })
        if (i + 1) % 10 == 0:
            print(f"   Processed {i + 1}/{len(campaigns)} campaigns...")
    
    campaign_did_counts.sort(key=lambda x: x['did_count'], reverse=True)
    
    print("\n" + "═" * 90)
    print(f"{'Rank':<6} {'Campaign Name':<35} {'DID Count':<12} {'Total Calls':<12} {'Last Call'}")
    print("═" * 90)
    
    shown = 0
    for i, camp in enumerate(campaign_did_counts, 1):
        if camp['did_count'] > 0:
            if camp['did_count'] >= 20:
                color = Colors.GREEN
            elif camp['did_count'] >= 10:
                color = Colors.YELLOW
            else:
                color = Colors.CYAN
            
            last_call = str(camp['last_call'] or 'Never')[:10]
            print(f"{i:<6} {color}{camp['name'][:33]:<35}{Colors.RESET} "
                  f"{camp['did_count']:<12} {format_number(camp['total_calls']):<12} {last_call}")
            shown += 1
            if shown >= 20:
                break
    
    print("═" * 90)
    
    if shown == 0:
        print(f"\n{Colors.YELLOW}No campaigns with DIDs found{Colors.RESET}")

def show_dids_by_pattern():
    """Search and display DIDs by pattern"""
    print_header("📞 Search DIDs by Pattern", Colors.CYAN)
    
    pattern = input(f"{Colors.CYAN}Enter DID pattern (e.g., '800', '212', or Enter for all): {Colors.RESET}").strip()
    did_column = get_did_column_name()
    
    if pattern:
        query = f"""
            SELECT DISTINCT 
                {did_column} AS did_number,
                COUNT(*) AS call_count,
                MIN(DATE(call_date)) AS first_seen,
                MAX(DATE(call_date)) AS last_seen,
                GROUP_CONCAT(DISTINCT campaign_id) AS campaigns
            FROM vicidial_closer_log
            WHERE {did_column} LIKE %s
              AND call_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
              AND {did_column} IS NOT NULL
              AND {did_column} != ''
            GROUP BY did_number
            ORDER BY call_count DESC
            LIMIT 30;
        """
        results = db.execute_query(query, (f'%{pattern}%',)) or []
    else:
        results = discover_dids_from_calls(None, 365)[:30]
    
    if not results:
        print_warning(f"No DIDs found matching pattern: {pattern}")
        return
    
    print_header(f"📞 DIDs MATCHING: {pattern or 'ALL TOP DIDs'}", Colors.GREEN)
    print("─" * 120)
    print(f"{'DID Number':<20} {'Call Count':<12} {'First Seen':<12} {'Last Seen':<12} {'Campaigns'}")
    print("─" * 120)
    
    for did in results:
        did_number = did.get('did_number', 'Unknown')
        call_count = format_number(to_int(did.get('call_count', 0)))
        first_seen = str(did.get('first_seen', 'Unknown'))[:10]
        last_seen = str(did.get('last_seen', 'Unknown'))[:10]
        campaigns = did.get('campaigns', 'Unknown')[:45]
        
        print(f"{str(did_number)[:18]:<18} {call_count:<12} {first_seen:<12} {last_seen:<12} {campaigns}")
    
    print("─" * 120)

# =============================================================================
# CAMPAIGN SELECTION & PERIOD CONFIGURATION
# =============================================================================

def select_campaign(prompt="Select campaign"):
    """Interactive campaign selection with grouping"""
    campaigns = get_all_campaigns_with_lifecycle()
    
    if not campaigns:
        print_warning("No campaigns found in database.")
        return None
    
    print(f"\n{Colors.CYAN}Available Campaigns (with lifecycle info):{Colors.RESET}")
    print("  " + "─" * 85)
    print(f"  {'#':<4} {'Campaign':<30} {'First Call':<12} {'Last Call':<12} {'Total Calls':<12}")
    print("  " + "─" * 85)
    
    for i, row in enumerate(campaigns, 1):
        first_call = row['first_call'] or 'Never'
        last_call = row['last_call'] or 'Never'
        total_calls = format_number(to_int(row['total_calls']))
        
        if row['last_call']:
            days_since = (datetime.now().date() - row['last_call']).days
            if days_since <= 7:
                status = Colors.GREEN
            elif days_since <= 30:
                status = Colors.YELLOW
            else:
                status = Colors.RED
        else:
            status = Colors.RED
        
        print(f"  {i:<4} {row['campaign_id'][:28]:<30} {status}{first_call}{Colors.RESET:<12} "
              f"{status}{last_call}{Colors.RESET:<12} {total_calls:<12}")
    
    print("  " + "─" * 85)
    
    print(f"\n{Colors.YELLOW}💡 TIPS:{Colors.RESET}")
    print(f"   • Enter a number to select campaign")
    print(f"   • Enter a name directly (exact match)")
    print(f"   • Enter a partial name to search (e.g., 'xsh')")
    print(f"   • Type 'table' to see all campaigns with their DIDs")
    print(f"   • Type 'all' for all campaigns")
    
    sel = input(f"\n{Colors.CYAN}{prompt}: {Colors.RESET}").strip()
    
    if sel.lower() == 'all':
        return 'ALL'
    elif sel.lower() == 'table':
        show_campaigns_with_dids_table()
        return select_campaign(prompt)
    elif sel.isdigit() and 1 <= int(sel) <= len(campaigns):
        return campaigns[int(sel)-1]['campaign_id']
    else:
        # Check if exact match exists
        exact_match = None
        for camp in campaigns:
            if camp['campaign_id'].lower() == sel.lower():
                exact_match = camp['campaign_id']
                break
        
        if exact_match:
            return exact_match
        else:
            # Search for partial matches
            result = search_and_select_campaign(sel)
            if result:
                return result
            else:
                return None

def get_period_config():
    """Get period configuration from user"""
    print("\n" + "─" * 50)
    print(f"{Colors.CYAN}Period Options:{Colors.RESET}")
    print("   1. Today")
    print("   2. Yesterday")
    print("   3. Last 7 Days")
    print("   4. Last 30 Days")
    print("   5. This Month")
    print("   6. Last Month")
    print("   7. Last 90 Days")
    print("   8. Year to Date")
    print("   9. Custom Date Range")
    print("  10. Week by Week (Last 12 weeks)")
    print("  11. Month by Month (Last 12 months)")
    print("  12. 🔍 Since Campaign Start")
    print("  13. 🔍 All Time (Complete History)")
    print("─" * 50)
    
    choice = input(f"\n{Colors.CYAN}Choose period: {Colors.RESET}").strip()
    
    if choice == '1':
        return ("call_date >= CURDATE()", "Today", "DATE(call_date)", None)
    elif choice == '2':
        return ("call_date >= DATE_SUB(CURDATE(), INTERVAL 1 DAY) AND call_date < CURDATE()", "Yesterday", "DATE(call_date)", None)
    elif choice == '3':
        return ("call_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)", "Last 7 Days", "DATE(call_date)", None)
    elif choice == '4':
        return ("call_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)", "Last 30 Days", "DATE(call_date)", None)
    elif choice == '5':
        return ("YEAR(call_date) = YEAR(CURDATE()) AND MONTH(call_date) = MONTH(CURDATE())", "This Month", "DATE(call_date)", None)
    elif choice == '6':
        return ("YEAR(call_date) = YEAR(CURDATE() - INTERVAL 1 MONTH) AND MONTH(call_date) = MONTH(CURDATE() - INTERVAL 1 MONTH)", "Last Month", "DATE(call_date)", None)
    elif choice == '7':
        return ("call_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)", "Last 90 Days", "DATE(call_date)", None)
    elif choice == '8':
        return ("YEAR(call_date) = YEAR(CURDATE())", "Year to Date", "DATE(call_date)", None)
    elif choice == '9':
        print("\n" + "─" * 40)
        start_date = input(f"{Colors.CYAN}Start Date (YYYY-MM-DD): {Colors.RESET}").strip()
        end_date = input(f"{Colors.CYAN}End Date (YYYY-MM-DD): {Colors.RESET}").strip()
        return (f"call_date >= '{start_date}' AND call_date <= '{end_date}'", f"{start_date} to {end_date}", "DATE(call_date)", None)
    elif choice == '10':
        return ("call_date >= DATE_SUB(CURDATE(), INTERVAL 84 DAY)", "Last 12 Weeks", "YEARWEEK(call_date, 1)", None)
    elif choice == '11':
        return ("call_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)", "Last 12 Months", "DATE_FORMAT(call_date, '%%Y-%%m')", None)
    elif choice == '12':
        return (None, "Since Campaign Start", "DATE(call_date)", "since_start")
    elif choice == '13':
        return (None, "All Time (Complete History)", "DATE(call_date)", "all_time")
    else:
        return ("call_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)", "Last 30 Days", "DATE(call_date)", None)

# =============================================================================
# MAIN MENU & REPORT FUNCTIONS
# =============================================================================

def manager_tools_menu():
    while True:
        print_header("📊 ENTERPRISE MANAGER TOOLS", Colors.MAGENTA)
        print("  " + "─" * 75)
        print("   1. 📈 Campaign Volume Report")
        print("   2. 📊 Campaign Performance Comparison")
        print("   3. 🔥 Weekly Volume Report")
        print("   4. 📅 Multi-Period Trend Analysis")
        print("   5. 🏆 Top/Bottom Campaigns by Volume")
        print("   6. 📋 Campaign Health Dashboard")
        print("   7. 🔍 Campaign Lifecycle & DID Discovery")
        print("   8. 🔗 Campaign Group Analysis (Xshield, Keto, etc.)")
        print("   9. 📋 Show All Campaigns Table (with DIDs)")
        print("  10. 🏆 Campaigns with Most DIDs")
        print("  11. 📞 Search DIDs by Pattern")
        print("   0. 🔙 Back to Main Menu")
        print("  " + "─" * 75)

        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

        if choice == '1':
            campaign_volume_report()
        elif choice == '2':
            compare_campaigns()
        elif choice == '3':
            weekly_volume_report()
        elif choice == '4':
            multi_period_trend()
        elif choice == '5':
            top_bottom_campaigns()
        elif choice == '6':
            campaign_health_dashboard()
        elif choice == '7':
            campaign_lifecycle_inspector()
        elif choice == '8':
            campaign_group_analysis()
        elif choice == '9':
            show_campaigns_with_dids_table()
        elif choice == '10':
            show_campaigns_most_dids()
        elif choice == '11':
            show_dids_by_pattern()
        elif choice == '0':
            break
        else:
            print_error("Invalid option")

        input("\nPress Enter to continue...")

def campaign_lifecycle_inspector():
    """Inspect campaign lifecycle and discovered DIDs"""
    print_header("🔍 Campaign Lifecycle & DID Discovery", Colors.CYAN)
    
    print(f"\n{Colors.YELLOW}💡 TIPS:{Colors.RESET}")
    print("   • Enter a FULL campaign name for details (e.g., 'Xshield')")
    print("   • Enter a PARTIAL name to search (e.g., 'xsh' will show all campaigns with 'xsh')")
    print("   • Type 'table' to see all campaigns with their DIDs")
    print("   • Type 'topdids' to see campaigns with most DIDs")
    
    campaign_input = input(f"\n{Colors.CYAN}Campaign name or partial search: {Colors.RESET}").strip()
    
    if not campaign_input:
        print_warning("No input provided")
        return
    
    if campaign_input.lower() == 'table':
        show_campaigns_with_dids_table()
        return
    elif campaign_input.lower() == 'topdids':
        show_campaigns_most_dids()
        return
    else:
        show_campaign_detail_with_dids(campaign_input)

def campaign_group_analysis():
    """Analyze campaign groups (all Xshield, all Keto, etc.)"""
    print_header("🔗 Campaign Group Analysis", Colors.CYAN)
    
    print(f"\n{Colors.YELLOW}📊 Available Campaign Groups:{Colors.RESET}")
    print("  " + "─" * 50)
    print("   1. XSHIELD Group (xshield%, Xshield)")
    print("   2. KETO Group (keto%, Keto%)")
    print("   3. SPIRE Group (spire%, Spire%)")
    print("   4. NYX Group (nyx%, Nyx%)")
    print("   5. BANK Group (%bank%)")
    print("   6. Custom Pattern (enter your own LIKE pattern)")
    print("  " + "─" * 50)
    
    choice = input(f"\n{Colors.CYAN}Choose group: {Colors.RESET}").strip()
    
    if choice == '1':
        pattern = 'xshield%'
        group_name = "XSHIELD GROUP"
    elif choice == '2':
        pattern = 'keto%'
        group_name = "KETO GROUP"
    elif choice == '3':
        pattern = 'spire%'
        group_name = "SPIRE GROUP"
    elif choice == '4':
        pattern = 'nyx%'
        group_name = "NYX GROUP"
    elif choice == '5':
        pattern = '%bank%'
        group_name = "BANK GROUP"
    elif choice == '6':
        pattern = input(f"{Colors.CYAN}Enter pattern (e.g., '%bank%'): {Colors.RESET}").strip()
        group_name = f"PATTERN: {pattern}"
    else:
        print_error("Invalid choice")
        return
    
    query = f"""
        SELECT 
            campaign_id,
            MIN(DATE(call_date)) AS first_call,
            MAX(DATE(call_date)) AS last_call,
            COUNT(*) AS total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered
        FROM vicidial_closer_log
        WHERE campaign_id LIKE %s
        GROUP BY campaign_id
        ORDER BY total_calls DESC;
    """
    
    results = db.execute_query(query, (pattern,)) or []
    
    if not results:
        print_warning(f"No campaigns found matching pattern: {pattern}")
        return
    
    print_header(f"📊 {group_name} - CAMPAIGN ANALYSIS", Colors.GREEN)
    print("─" * 100)
    print(f"{'Campaign':<30} {'First Call':<12} {'Last Call':<12} {'Total Calls':<12} {'Answer Rate'}")
    print("─" * 100)
    
    total_calls_all = 0
    total_answered_all = 0
    
    for row in results:
        first_call = row['first_call'] or 'Never'
        last_call = row['last_call'] or 'Never'
        total_calls = to_int(row['total_calls'])
        answered = to_int(row['answered'])
        rate = round(100.0 * answered / total_calls, 2) if total_calls > 0 else 0
        
        total_calls_all += total_calls
        total_answered_all += answered
        
        rate_color = Colors.GREEN if rate >= 80 else (Colors.YELLOW if rate >= 60 else Colors.RED)
        
        if row['last_call']:
            days_since = (datetime.now().date() - row['last_call']).days
            if days_since <= 7:
                status = Colors.GREEN
            elif days_since <= 30:
                status = Colors.YELLOW
            else:
                status = Colors.RED
        else:
            status = Colors.RED
        
        print(f"{status}{row['campaign_id'][:28]:<30}{Colors.RESET} "
              f"{first_call:<12} {last_call:<12} "
              f"{format_number(total_calls):<12} {rate_color}{rate}%{Colors.RESET}")
    
    print("─" * 100)
    
    overall_rate = round(100.0 * total_answered_all / total_calls_all, 2) if total_calls_all > 0 else 0
    print(f"\n{Colors.YELLOW}📊 GROUP TOTALS:{Colors.RESET}")
    print(f"   Campaigns in Group: {len(results)}")
    print(f"   Total Calls: {format_number(total_calls_all)}")
    print(f"   Total Answered: {format_number(total_answered_all)}")
    print(f"   Overall Answer Rate: {overall_rate}%")
    
    print(f"\n{Colors.YELLOW}📞 DISCOVERED DIDs FOR THIS GROUP:{Colors.RESET}")
    discovered_dids = discover_dids_from_calls(pattern, 365)
    
    if discovered_dids:
        print("  " + "─" * 110)
        print(f"  {'DID Number':<20} {'Call Count':<12} {'First Seen':<12} {'Last Seen':<12} {'Campaigns'}")
        print("  " + "─" * 110)
        for did in discovered_dids[:15]:
            print(f"  {str(did['did_number'])[:18]:<18} "
                  f"{format_number(to_int(did['call_count'])):<12} "
                  f"{str(did['first_seen'])[:10]:<12} "
                  f"{str(did['last_seen'])[:10]:<12} "
                  f"{did['campaigns'][:35]:<35}")
        print("  " + "─" * 110)
    else:
        print(f"  {Colors.YELLOW}No DIDs discovered from call logs{Colors.RESET}")

def campaign_volume_report():
    """Detailed volume report for selected campaign"""
    print_header("📈 Campaign Volume Report", Colors.CYAN)
    
    campaign_input = select_campaign("Select campaign for volume report")
    if not campaign_input:
        return
    
    date_where, title, group_by, special = get_period_config()
    
    if special == 'since_start':
        if campaign_input == 'ALL':
            query_start = "SELECT MIN(DATE(call_date)) AS first_call FROM vicidial_closer_log"
            start_result = db.execute_query(query_start)
            if start_result and start_result[0]['first_call']:
                date_where = f"call_date >= '{start_result[0]['first_call']}'"
                title = f"Since First Call Ever ({start_result[0]['first_call']})"
        elif '%' in campaign_input:
            query_start = """
                SELECT MIN(DATE(call_date)) AS first_call
                FROM vicidial_closer_log
                WHERE campaign_id LIKE %s
            """
            start_result = db.execute_query(query_start, (campaign_input,))
            if start_result and start_result[0]['first_call']:
                date_where = f"call_date >= '{start_result[0]['first_call']}'"
                title = f"Since Campaign Start ({start_result[0]['first_call']})"
        else:
            lifecycle = get_campaign_lifecycle(campaign_input)
            if lifecycle['first_call']:
                date_where = f"call_date >= '{lifecycle['first_call']}'"
                title = f"Since Campaign Start ({lifecycle['first_call']})"
            else:
                print_warning(f"No call data found for campaign '{campaign_input}'")
                return
    elif special == 'all_time':
        date_where = "1=1"
        title = "All Time (Complete History)"
    
    if campaign_input != 'ALL' and '%' not in campaign_input:
        show_campaign_detail_with_dids(campaign_input)
    
    if campaign_input == 'ALL':
        query = f"""
            SELECT 
                campaign_id AS `Campaign`,
                COUNT(*) AS `Total Calls`,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
                ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Answer Rate`,
                SEC_TO_TIME(ROUND(AVG(length_in_sec), 0)) AS `Avg Talk Time`,
                SEC_TO_TIME(SUM(length_in_sec)) AS `Total Talk Time`
            FROM vicidial_closer_log
            WHERE {date_where}
            GROUP BY campaign_id
            ORDER BY `Total Calls` DESC;
        """
        results = db.execute_query(query) or []
        header_title = f"ALL CAMPAIGNS - {title}"
    elif '%' in campaign_input:
        query = f"""
            SELECT 
                DATE(call_date) AS `Period`,
                COUNT(*) AS `Total Calls`,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
                ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Answer Rate`,
                SEC_TO_TIME(ROUND(AVG(length_in_sec), 0)) AS `Avg Talk Time`,
                SEC_TO_TIME(SUM(length_in_sec)) AS `Total Talk Time`
            FROM vicidial_closer_log
            WHERE campaign_id LIKE %s AND {date_where}
            GROUP BY DATE(call_date)
            ORDER BY DATE(call_date) DESC;
        """
        results = db.execute_query(query, (campaign_input,)) or []
        header_title = f"PATTERN: {campaign_input} - {title}"
    else:
        query = f"""
            SELECT 
                {group_by} AS `Period`,
                COUNT(*) AS `Total Calls`,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
                ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Answer Rate`,
                SEC_TO_TIME(ROUND(AVG(length_in_sec), 0)) AS `Avg Talk Time`,
                SEC_TO_TIME(SUM(length_in_sec)) AS `Total Talk Time`
            FROM vicidial_closer_log
            WHERE campaign_id = %s AND {date_where}
            GROUP BY {group_by}
            ORDER BY MIN(call_date) DESC;
        """
        results = db.execute_query(query, (campaign_input,)) or []
        header_title = f"{campaign_input.upper()} - {title}"
    
    if not results:
        print_warning(f"No data found for period: {title}")
        return
    
    print_header(f"📊 {header_title}", Colors.GREEN)
    print("─" * 130)
    
    if campaign_input == 'ALL' or '%' in campaign_input:
        print(f"{'Date/Period':<15} {'Total Calls':<12} {'Answered':<10} {'Answer Rate':<12} {'Avg Talk Time':<15} {'Total Talk Time'}")
        print("─" * 130)
        for row in results:
            period = row.get('Period', 'N/A')
            total_calls = to_int(row.get('Total Calls', 0))
            answered = to_int(row.get('Answered', 0))
            rate = to_float(row.get('Answer Rate', 0))
            
            rate_color = Colors.GREEN if rate >= 80 else (Colors.YELLOW if rate >= 60 else Colors.RED)
            avg_talk = format_timedelta(row.get('Avg Talk Time'))
            total_talk = format_timedelta(row.get('Total Talk Time'))
            print(f"{str(period)[:14]:<15} {format_number(total_calls):<12} "
                  f"{format_number(answered):<10} {rate_color}{rate}%{Colors.RESET:<9} "
                  f"{avg_talk:<15} {total_talk}")
    else:
        print(f"{'Period':<15} {'Total Calls':<12} {'Answered':<10} {'Answer Rate':<12} {'Avg Talk Time':<15} {'Total Talk Time'}")
        print("─" * 130)
        for row in results:
            period = row.get('Period', 'N/A')
            total_calls = to_int(row.get('Total Calls', 0))
            answered = to_int(row.get('Answered', 0))
            rate = to_float(row.get('Answer Rate', 0))
            
            rate_color = Colors.GREEN if rate >= 80 else (Colors.YELLOW if rate >= 60 else Colors.RED)
            avg_talk = format_timedelta(row.get('Avg Talk Time'))
            total_talk = format_timedelta(row.get('Total Talk Time'))
            print(f"{str(period)[:14]:<15} {format_number(total_calls):<12} "
                  f"{format_number(answered):<10} {rate_color}{rate}%{Colors.RESET:<9} "
                  f"{avg_talk:<15} {total_talk}")
    
    print("─" * 130)
    
    if results:
        total_calls = sum(to_int(r.get('Total Calls', 0)) for r in results)
        total_answered = sum(to_int(r.get('Answered', 0)) for r in results)
        overall_rate = round(100.0 * total_answered / total_calls, 2) if total_calls > 0 else 0
        print(f"\n{Colors.YELLOW}📊 SUMMARY:{Colors.RESET}")
        print(f"   Total Periods: {len(results)}")
        print(f"   Total Calls: {format_number(total_calls)}")
        print(f"   Total Answered: {format_number(total_answered)}")
        print(f"   Overall Answer Rate: {Colors.GREEN if overall_rate >= 80 else Colors.YELLOW}{overall_rate}%{Colors.RESET}")

def weekly_volume_report():
    """Weekly volume report for selected campaign(s)"""
    print_header("🔥 Weekly Volume Report", Colors.CYAN)
    
    campaign_input = select_campaign("Select campaign for weekly report")
    if not campaign_input:
        return
    
    weeks = input(f"\n{Colors.CYAN}Number of weeks to analyze (default 12): {Colors.RESET}").strip()
    weeks = int(weeks) if weeks.isdigit() else 12
    
    if campaign_input != 'ALL' and '%' not in campaign_input and campaign_input.lower() != 'all':
        show_campaign_detail_with_dids(campaign_input)
    
    if campaign_input == 'ALL' or campaign_input.lower() == 'all':
        query = f"""
            SELECT 
                YEARWEEK(call_date, 1) AS `Week`,
                MIN(DATE(call_date)) AS `Week_Start`,
                COUNT(*) AS `Total Calls`,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
                ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Answer Rate`
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL {weeks} WEEK)
            GROUP BY `Week`
            ORDER BY `Week` DESC;
        """
        results = db.execute_query(query) or []
        header_title = f"ALL CAMPAIGNS - Last {weeks} Weeks"
    elif '%' in campaign_input:
        query = f"""
            SELECT 
                YEARWEEK(call_date, 1) AS `Week`,
                MIN(DATE(call_date)) AS `Week_Start`,
                COUNT(*) AS `Total Calls`,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
                ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Answer Rate`
            FROM vicidial_closer_log
            WHERE campaign_id LIKE %s
              AND call_date >= DATE_SUB(CURDATE(), INTERVAL {weeks} WEEK)
            GROUP BY `Week`
            ORDER BY `Week` DESC;
        """
        results = db.execute_query(query, (campaign_input,)) or []
        header_title = f"PATTERN: {campaign_input} - Last {weeks} Weeks"
    else:
        query = f"""
            SELECT 
                YEARWEEK(call_date, 1) AS `Week`,
                MIN(DATE(call_date)) AS `Week_Start`,
                COUNT(*) AS `Total Calls`,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
                ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Answer Rate`
            FROM vicidial_closer_log
            WHERE campaign_id = %s
              AND call_date >= DATE_SUB(CURDATE(), INTERVAL {weeks} WEEK)
            GROUP BY `Week`
            ORDER BY `Week` DESC;
        """
        results = db.execute_query(query, (campaign_input,)) or []
        header_title = f"{campaign_input.upper()} - Last {weeks} Weeks"
    
    if not results:
        print_warning(f"No data found for the last {weeks} weeks.")
        return
    
    print_header(f"📊 {header_title}", Colors.GREEN)
    print("─" * 85)
    print(f"{'Week':<12} {'Start Date':<12} {'Total Calls':<12} {'Answered':<10} {'Answer Rate'}")
    print("─" * 85)
    
    for row in results:
        week_num = to_int(row.get('Week', 0))
        year = str(week_num)[:4] if week_num > 0 else "0000"
        week = str(week_num)[4:] if week_num > 0 else "00"
        week_display = f"W{week} '{year[2:]}'"
        
        total_calls = to_int(row.get('Total Calls', 0))
        answered = to_int(row.get('Answered', 0))
        rate = to_float(row.get('Answer Rate', 0))
        rate_color = Colors.GREEN if rate >= 80 else (Colors.YELLOW if rate >= 60 else Colors.RED)
        
        print(f"{week_display:<12} {row['Week_Start']:<12} "
              f"{format_number(total_calls):<12} "
              f"{format_number(answered):<10} "
              f"{rate_color}{rate}%{Colors.RESET}")
    
    print("─" * 85)
    
    if len(results) >= 2:
        current_week = to_int(results[0].get('Total Calls', 0))
        prev_week = to_int(results[1].get('Total Calls', 0))
        change = ((current_week - prev_week) / prev_week * 100) if prev_week > 0 else 0
        trend = "↑" if change > 0 else "↓" if change < 0 else "→"
        trend_color = Colors.GREEN if change > 0 else Colors.RED if change < 0 else Colors.YELLOW
        
        print(f"\n{Colors.YELLOW}📈 TREND:{Colors.RESET}")
        print(f"   Week-over-Week Change: {trend_color}{trend} {abs(change):.1f}%{Colors.RESET}")

def compare_campaigns():
    """Compare multiple campaigns side by side"""
    print_header("📊 Campaign Performance Comparison", Colors.CYAN)
    
    print("\nSelect campaigns to compare (up to 4 campaigns)")
    campaigns = []
    
    for i in range(4):
        campaign_input = select_campaign(f"Select campaign {i+1} (or 'done' to finish)")
        if not campaign_input or campaign_input.lower() == 'done':
            break
        if campaign_input != 'ALL' and '%' not in campaign_input:
            campaigns.append(campaign_input)
    
    if len(campaigns) < 2:
        print_warning("Need at least 2 campaigns to compare.")
        return
    
    date_where, title, _, _ = get_period_config()
    
    print_header(f"📊 CAMPAIGN COMPARISON - {title}", Colors.GREEN)
    print("─" * 120)
    
    header = f"{'Metric':<25}"
    for camp in campaigns:
        header += f"{camp[:20]:<20}"
    print(header)
    print("─" * 120)
    
    metrics = ['Total Calls', 'Answered', 'Answer Rate', 'Avg Talk Time', 'Total Talk Time']
    
    for metric in metrics:
        row = f"{metric:<25}"
        for campaign in campaigns:
            query = f"""
                SELECT 
                    COUNT(*) AS total_calls,
                    SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered,
                    ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS answer_rate,
                    SEC_TO_TIME(ROUND(AVG(length_in_sec), 0)) AS avg_talk,
                    SEC_TO_TIME(SUM(length_in_sec)) AS total_talk
                FROM vicidial_closer_log
                WHERE campaign_id = %s AND {date_where}
            """
            result = db.execute_query(query, (campaign,))
            if result and len(result) > 0:
                r = result[0]
                if metric == 'Total Calls':
                    val = format_number(to_int(r.get('total_calls', 0)))
                elif metric == 'Answered':
                    val = format_number(to_int(r.get('answered', 0)))
                elif metric == 'Answer Rate':
                    rate = to_float(r.get('answer_rate', 0))
                    color = Colors.GREEN if rate >= 80 else (Colors.YELLOW if rate >= 60 else Colors.RED)
                    val = f"{color}{rate}%{Colors.RESET}"
                elif metric == 'Avg Talk Time':
                    val = format_timedelta(r.get('avg_talk'))
                else:
                    val = format_timedelta(r.get('total_talk'))
            else:
                val = "-"
            row += f"{str(val):<20}"
        print(row)
    
    print("─" * 120)

def multi_period_trend():
    """Trend analysis across multiple time periods"""
    print_header("📅 Multi-Period Trend Analysis", Colors.CYAN)
    
    campaign_input = select_campaign("Select campaign for trend analysis")
    if not campaign_input or campaign_input == 'ALL':
        campaign_input = select_campaign("Please select a specific campaign for trend analysis")
        if not campaign_input:
            return
    
    if '%' not in campaign_input and campaign_input.lower() != 'all':
        show_campaign_detail_with_dids(campaign_input)
    
    print("\n" + "─" * 50)
    print(f"{Colors.CYAN}Analysis Type:{Colors.RESET}")
    print("   1. Daily Trend (Last 30 days)")
    print("   2. Weekly Trend (Last 12 weeks)")
    print("   3. Monthly Trend (Last 12 months)")
    print("   4. Hourly Distribution")
    print("─" * 50)
    
    choice = input(f"\n{Colors.CYAN}Choose analysis type: {Colors.RESET}").strip()
    
    if choice == '1':
        query = f"""
            SELECT 
                DATE(call_date) AS `Date`,
                COUNT(*) AS `Calls`,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
                ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Rate`
            FROM vicidial_closer_log
            WHERE campaign_id = %s
              AND call_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(call_date)
            ORDER BY `Date` DESC;
        """
        title = "Daily Trend (Last 30 Days)"
        period_label = "Date"
    elif choice == '2':
        query = f"""
            SELECT 
                YEARWEEK(call_date, 1) AS `Period`,
                MIN(DATE(call_date)) AS `Start_Date`,
                COUNT(*) AS `Calls`,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
                ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Rate`
            FROM vicidial_closer_log
            WHERE campaign_id = %s
              AND call_date >= DATE_SUB(CURDATE(), INTERVAL 12 WEEK)
            GROUP BY `Period`
            ORDER BY `Period` DESC;
        """
        title = "Weekly Trend (Last 12 Weeks)"
        period_label = "Week"
    elif choice == '3':
        query = f"""
            SELECT 
                DATE_FORMAT(call_date, '%%Y-%%m') AS `Period`,
                COUNT(*) AS `Calls`,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
                ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Rate`
            FROM vicidial_closer_log
            WHERE campaign_id = %s
              AND call_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY `Period`
            ORDER BY `Period` DESC;
        """
        title = "Monthly Trend (Last 12 Months)"
        period_label = "Month"
    elif choice == '4':
        query = f"""
            SELECT 
                HOUR(call_date) AS `Hour`,
                COUNT(*) AS `Calls`,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
                ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Rate`
            FROM vicidial_closer_log
            WHERE campaign_id = %s
              AND call_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY `Hour`
            ORDER BY `Hour` ASC;
        """
        title = "Hourly Distribution (Last 30 Days)"
        period_label = "Hour"
    else:
        print_error("Invalid choice")
        return
    
    results = db.execute_query(query, (campaign_input,)) or []
    
    if not results:
        print_warning(f"No data found for campaign '{campaign_input}'")
        return
    
    print_header(f"📊 {campaign_input.upper()} - {title}", Colors.GREEN)
    print("─" * 80)
    print(f"{period_label:<15} {'Total Calls':<12} {'Answered':<10} {'Answer Rate'}")
    print("─" * 80)
    
    for row in results:
        period = row.get('Period') or row.get('Date') or row.get('Hour', 'N/A')
        if choice == '2' and isinstance(period, int) and period > 0:
            year = str(period)[:4]
            week = str(period)[4:]
            period = f"W{week} '{year[2:]}'"
        
        calls = to_int(row.get('Calls', 0))
        answered = to_int(row.get('Answered', 0))
        rate = to_float(row.get('Rate', 0))
        rate_color = Colors.GREEN if rate >= 80 else (Colors.YELLOW if rate >= 60 else Colors.RED)
        
        print(f"{str(period)[:14]:<15} {format_number(calls):<12} "
              f"{format_number(answered):<10} "
              f"{rate_color}{rate}%{Colors.RESET}")
    
    print("─" * 80)

def top_bottom_campaigns():
    """Show top and bottom performing campaigns"""
    print_header("🏆 Top & Bottom Campaigns by Volume", Colors.CYAN)
    
    date_where, title, _, _ = get_period_config()
    
    query_top = f"""
        SELECT 
            campaign_id AS `Campaign`,
            COUNT(*) AS `Total Calls`,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
            ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Answer Rate`
        FROM vicidial_closer_log
        WHERE {date_where}
        GROUP BY campaign_id
        ORDER BY `Total Calls` DESC
        LIMIT 10;
    """
    
    query_bottom = f"""
        SELECT 
            campaign_id AS `Campaign`,
            COUNT(*) AS `Total Calls`,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
            ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Answer Rate`
        FROM vicidial_closer_log
        WHERE {date_where}
        GROUP BY campaign_id
        HAVING `Total Calls` > 0
        ORDER BY `Total Calls` ASC
        LIMIT 10;
    """
    
    top_results = db.execute_query(query_top) or []
    bottom_results = db.execute_query(query_bottom) or []
    
    print_header(f"📊 CAMPAIGN RANKINGS - {title}", Colors.GREEN)
    
    if top_results:
        print(f"\n{Colors.GREEN}🏆 TOP 10 CAMPAIGNS BY VOLUME{Colors.RESET}")
        print("─" * 75)
        print(f"{'Rank':<6} {'Campaign':<30} {'Total Calls':<12} {'Answer Rate'}")
        print("─" * 75)
        
        for i, row in enumerate(top_results, 1):
            total_calls = to_int(row.get('Total Calls', 0))
            rate = to_float(row.get('Answer Rate', 0))
            rate_color = Colors.GREEN if rate >= 80 else (Colors.YELLOW if rate >= 60 else Colors.RED)
            print(f"{i:<6} {row['Campaign'][:28]:<30} {format_number(total_calls):<12} {rate_color}{rate}%{Colors.RESET}")
        
        print("─" * 75)
    
    if bottom_results:
        print(f"\n{Colors.YELLOW}📉 BOTTOM 10 CAMPAIGNS BY VOLUME{Colors.RESET}")
        print("─" * 75)
        print(f"{'Rank':<6} {'Campaign':<30} {'Total Calls':<12} {'Answer Rate'}")
        print("─" * 75)
        
        for i, row in enumerate(bottom_results, 1):
            total_calls = to_int(row.get('Total Calls', 0))
            rate = to_float(row.get('Answer Rate', 0))
            rate_color = Colors.GREEN if rate >= 80 else (Colors.YELLOW if rate >= 60 else Colors.RED)
            print(f"{i:<6} {row['Campaign'][:28]:<30} {format_number(total_calls):<12} {rate_color}{rate}%{Colors.RESET}")
        
        print("─" * 75)

def campaign_health_dashboard():
    """Campaign health dashboard with key metrics"""
    print_header("📋 Campaign Health Dashboard", Colors.CYAN)
    
    date_where, title, _, _ = get_period_config()
    
    query = f"""
        SELECT 
            campaign_id AS `Campaign`,
            COUNT(*) AS `Total Calls`,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS `Answered`,
            ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS `Answer Rate`,
            ROUND(AVG(length_in_sec), 0) AS `Avg Duration`,
            COUNT(DISTINCT DATE(call_date)) AS `Active Days`,
            ROUND(COUNT(*) / NULLIF(COUNT(DISTINCT DATE(call_date)), 0), 0) AS `Daily Avg`
        FROM vicidial_closer_log
        WHERE {date_where}
        GROUP BY campaign_id
        HAVING `Total Calls` > 100
        ORDER BY `Total Calls` DESC;
    """
    
    results = db.execute_query(query) or []
    
    if not results:
        print_warning(f"No campaigns with >100 calls found for period: {title}")
        return
    
    print_header(f"📊 CAMPAIGN HEALTH METRICS - {title}", Colors.GREEN)
    print("─" * 120)
    print(f"{'Campaign':<25} {'Total Calls':<12} {'Answer Rate':<12} {'Avg Duration':<12} {'Active Days':<12} {'Daily Avg'}")
    print("─" * 120)
    
    for row in results:
        total_calls = to_int(row.get('Total Calls', 0))
        rate = to_float(row.get('Answer Rate', 0))
        rate_color = Colors.GREEN if rate >= 80 else (Colors.YELLOW if rate >= 60 else Colors.RED)
        
        health = "✅" if rate >= 80 else "⚠️" if rate >= 60 else "❌"
        
        print(f"{health} {row['Campaign'][:22]:<23} "
              f"{format_number(total_calls):<12} "
              f"{rate_color}{rate}%{Colors.RESET:<9} "
              f"{to_int(row.get('Avg Duration', 0)):<12} "
              f"{to_int(row.get('Active Days', 0)):<12} "
              f"{format_number(to_int(row.get('Daily Avg', 0)))}")
    
    print("─" * 120)
    
    if results:
        total_calls = sum(to_int(r.get('Total Calls', 0)) for r in results)
        avg_rate = sum(to_float(r.get('Answer Rate', 0)) for r in results) / len(results)
        healthy = sum(1 for r in results if to_float(r.get('Answer Rate', 0)) >= 80)
        warning = sum(1 for r in results if 60 <= to_float(r.get('Answer Rate', 0)) < 80)
        critical = sum(1 for r in results if to_float(r.get('Answer Rate', 0)) < 60)
        
        print(f"\n{Colors.YELLOW}📊 HEALTH SUMMARY:{Colors.RESET}")
        print(f"   Total Campaigns Analyzed: {len(results)}")
        print(f"   Total Calls: {format_number(total_calls)}")
        print(f"   Average Answer Rate: {avg_rate:.1f}%")
        print(f"   {Colors.GREEN}Healthy (≥80%): {healthy}{Colors.RESET}")
        print(f"   {Colors.YELLOW}Warning (60-79%): {warning}{Colors.RESET}")
        print(f"   {Colors.RED}Critical (<60%): {critical}{Colors.RESET}")

if __name__ == "__main__":
    manager_tools_menu()