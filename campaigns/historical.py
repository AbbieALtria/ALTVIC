#!/usr/bin/env python3
# =============================================================================
# File:         historical.py
# Version:      1.2.0
# Date:         2024-01-15
# Description:  Historical campaign comparisons and trend analysis
# Update:       - Changed campaign list source to last 30 days (calls-based standard)
#               - Increased campaign display from 10 to 20
#               - Fixed numeric validation to accept 1-20
# Author:       Altria Ops Team
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms, time_ago

def display_all_campaigns(campaigns, title="AVAILABLE CAMPAIGNS"):
    """Display ALL campaigns without truncation"""
    print(f"\n{title} (Total: {len(campaigns)})")
    print("-" * 80)
    
    # Display in 4 columns
    col_width = 22
    cols = 4
    
    for i, camp in enumerate(campaigns, 1):
        display = f"{i:3}. {camp}"
        if len(display) < col_width:
            display = display.ljust(col_width)
        print(display, end="")
        if i % cols == 0:
            print()
    
    if len(campaigns) % cols != 0:
        print()
    print("-" * 80)
    print(f"Total: {len(campaigns)} campaigns")

def get_campaign_list():
    """
    Returns campaigns that have call activity in the last 30 days (calls-based standard).
    Source of truth: vicidial_closer_log
    """
    query = """
        SELECT DISTINCT campaign_id
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        ORDER BY campaign_id
    """
    results = db.execute_query(query)
    return [r['campaign_id'] for r in results] if results else []

def get_date_range(period):
    """Get date range based on period selection"""
    today = datetime.now().date()
    
    ranges = {
        'today': (today, today),
        'yesterday': (today - timedelta(days=1), today - timedelta(days=1)),
        'this_week': (today - timedelta(days=today.weekday()), today),
        'last_week': (today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 1)),
        'this_month': (today.replace(day=1), today),
        'last_month': ((today.replace(day=1) - timedelta(days=1)).replace(day=1), 
                      today.replace(day=1) - timedelta(days=1)),
        'last_30_days': (today - timedelta(days=30), today),
        'last_90_days': (today - timedelta(days=90), today)
    }
    return ranges.get(period, (today - timedelta(days=7), today))

def compare_periods(campaign=None):
    """Compare two time periods"""
    print_header("📊 COMPARE TIME PERIODS", Colors.MAGENTA)
    
    print("\nSelect first period:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. This Week")
    print("  4. Last Week")
    print("  5. This Month")
    print("  6. Last Month")
    print("  7. Last 30 Days")
    print("  8. Custom Range")
    
    choice1 = input("\nChoice (1-8): ").strip()
    period_map = {
        '1': 'today', '2': 'yesterday', '3': 'this_week', '4': 'last_week',
        '5': 'this_month', '6': 'last_month', '7': 'last_30_days'
    }
    
    if choice1 == '8':
        print("\n📅 Custom Range 1:")
        start1 = input("Start date (YYYY-MM-DD): ").strip()
        end1 = input("End date (YYYY-MM-DD): ").strip()
        try:
            start1 = datetime.strptime(start1, '%Y-%m-%d').date()
            end1 = datetime.strptime(end1, '%Y-%m-%d').date()
        except:
            print_error("Invalid date format")
            return
    elif choice1 in period_map:
        start1, end1 = get_date_range(period_map[choice1])
    else:
        print_error("Invalid choice")
        return
    
    print("\nSelect second period:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. This Week")
    print("  4. Last Week")
    print("  5. This Month")
    print("  6. Last Month")
    print("  7. Last 30 Days")
    print("  8. Custom Range")
    
    choice2 = input("\nChoice (1-8): ").strip()
    
    if choice2 == '8':
        print("\n📅 Custom Range 2:")
        start2 = input("Start date (YYYY-MM-DD): ").strip()
        end2 = input("End date (YYYY-MM-DD): ").strip()
        try:
            start2 = datetime.strptime(start2, '%Y-%m-%d').date()
            end2 = datetime.strptime(end2, '%Y-%m-%d').date()
        except:
            print_error("Invalid date format")
            return
    elif choice2 in period_map:
        start2, end2 = get_date_range(period_map[choice2])
    else:
        print_error("Invalid choice")
        return
    
    # Get comparison data
    _compare_campaigns_data(campaign, start1, end1, start2, end2)

def _compare_campaigns_data(campaign=None, start1=None, end1=None, start2=None, end2=None):
    """Compare campaign performance between two periods"""
    
    # If dates not provided, use defaults
    if not start1 or not end1:
        end1 = datetime.now().date()
        start1 = end1 - timedelta(days=7)
    
    if not start2 or not end2:
        end2 = start1 - timedelta(days=1)
        start2 = end2 - timedelta(days=7)
    
    try:
        # Build WHERE clause
        where_clause = ""
        params = []
        
        if campaign:
            where_clause = "AND campaign_id = %s"
            params.append(campaign)
        
        # Query for first period
        query1 = f"""
        SELECT 
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
            SUM(length_in_sec) as total_talk,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
            AVG(queue_seconds) as avg_queue,
            COUNT(DISTINCT DATE(call_date)) as days_active
        FROM vicidial_closer_log
        WHERE DATE(call_date) BETWEEN %s AND %s
        {where_clause}
        """
        
        period1 = db.execute_query(query1, [start1, end1] + params)
        
        # Query for second period
        query2 = f"""
        SELECT 
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
            SUM(length_in_sec) as total_talk,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
            AVG(queue_seconds) as avg_queue,
            COUNT(DISTINCT DATE(call_date)) as days_active
        FROM vicidial_closer_log
        WHERE DATE(call_date) BETWEEN %s AND %s
        {where_clause}
        """
        
        period2 = db.execute_query(query2, [start2, end2] + params)
        
        if not period1 or not period2:
            print_error("No data available for selected periods")
            return
        
        p1 = period1[0]
        p2 = period2[0]
        
        # Calculate metrics
        p1_answer_rate = (p1['answered'] / p1['total_calls'] * 100) if p1['total_calls'] > 0 else 0
        p2_answer_rate = (p2['answered'] / p2['total_calls'] * 100) if p2['total_calls'] > 0 else 0
        
        p1_abandon_rate = (p1['abandoned'] / p1['total_calls'] * 100) if p1['total_calls'] > 0 else 0
        p2_abandon_rate = (p2['abandoned'] / p2['total_calls'] * 100) if p2['total_calls'] > 0 else 0
        
        p1_daily_avg = p1['total_calls'] / p1['days_active'] if p1['days_active'] > 0 else 0
        p2_daily_avg = p2['total_calls'] / p2['days_active'] if p2['days_active'] > 0 else 0
        
        # Display header
        title = " CAMPAIGN COMPARISON "
        if campaign:
            title = f" CAMPAIGN: {campaign} "
        
        print_header(title, Colors.MAGENTA)
        
        print(f"\n{'='*90}")
        print(f"📅 Period 1: {start1} to {end1} ({p1['days_active']} days)")
        print(f"📅 Period 2: {start2} to {end2} ({p2['days_active']} days)")
        print(f"{'='*90}")
        
        # Comparison table
        print(f"\n{'Metric':<25} {'Period 1':<20} {'Period 2':<20} {'Change':<15}")
        print(f"{'-'*80}")
        
        # Total Calls
        calls_change = p1['total_calls'] - p2['total_calls']
        calls_pct = (calls_change / p2['total_calls'] * 100) if p2['total_calls'] > 0 else 0
        print(f"{'Total Calls':<25} {p1['total_calls']:<20} {p2['total_calls']:<20} ", end='')
        _print_change(calls_change, calls_pct)
        
        # Daily Average
        daily_change = p1_daily_avg - p2_daily_avg
        daily_pct = (daily_change / p2_daily_avg * 100) if p2_daily_avg > 0 else 0
        print(f"{'Daily Avg Calls':<25} {p1_daily_avg:.1f}{' ':<16} {p2_daily_avg:.1f}{' ':<16} ", end='')
        _print_change(daily_change, daily_pct)
        
        # Answered Calls
        ans_change = p1['answered'] - p2['answered']
        ans_pct = (ans_change / p2['answered'] * 100) if p2['answered'] > 0 else 0
        print(f"{'Answered Calls':<25} {p1['answered']:<20} {p2['answered']:<20} ", end='')
        _print_change(ans_change, ans_pct)
        
        # Answer Rate
        rate_change = p1_answer_rate - p2_answer_rate
        print(f"{'Answer Rate':<25} {p1_answer_rate:.1f}%{' ':<16} {p2_answer_rate:.1f}%{' ':<16} ", end='')
        _print_change(rate_change, rate_change, is_percent=True)
        
        # Abandoned Calls
        abd_change = p1['abandoned'] - p2['abandoned']
        abd_pct = (abd_change / p2['abandoned'] * 100) if p2['abandoned'] > 0 else 0
        print(f"{'Abandoned Calls':<25} {p1['abandoned']:<20} {p2['abandoned']:<20} ", end='')
        _print_change(abd_change, abd_pct)
        
        # Abandon Rate
        abd_rate_change = p1_abandon_rate - p2_abandon_rate
        print(f"{'Abandon Rate':<25} {p1_abandon_rate:.1f}%{' ':<16} {p2_abandon_rate:.1f}%{' ':<16} ", end='')
        _print_change(abd_rate_change, abd_rate_change, is_percent=True)
        
        # Total Talk Time
        talk_change = (p1['total_talk'] or 0) - (p2['total_talk'] or 0)
        talk_pct = (talk_change / p2['total_talk'] * 100) if p2['total_talk'] and p2['total_talk'] > 0 else 0
        print(f"{'Total Talk Time':<25} {sec_to_hms(p1['total_talk']):<20} {sec_to_hms(p2['total_talk']):<20} ", end='')
        _print_change(talk_change, talk_pct)
        
        # Average Talk Time
        avg_talk_change = (p1['avg_talk'] or 0) - (p2['avg_talk'] or 0)
        avg_talk_pct = (avg_talk_change / p2['avg_talk'] * 100) if p2['avg_talk'] and p2['avg_talk'] > 0 else 0
        print(f"{'Avg Talk Time':<25} {sec_to_hms(p1['avg_talk']):<20} {sec_to_hms(p2['avg_talk']):<20} ", end='')
        _print_change(avg_talk_change, avg_talk_pct)
        
        # Average Queue Time
        avg_queue_change = (p1['avg_queue'] or 0) - (p2['avg_queue'] or 0)
        avg_queue_pct = (avg_queue_change / p2['avg_queue'] * 100) if p2['avg_queue'] and p2['avg_queue'] > 0 else 0
        print(f"{'Avg Queue Time':<25} {sec_to_hms(p1['avg_queue']):<20} {sec_to_hms(p2['avg_queue']):<20} ", end='')
        _print_change(avg_queue_change, avg_queue_pct)
        
        print(f"{'-'*80}")
        
        # Summary
        print(f"\n📊 SUMMARY:")
        if p1['total_calls'] > p2['total_calls']:
            print(f"  • Period 1 had {calls_change} more calls ({calls_pct:.1f}% increase)")
        elif p1['total_calls'] < p2['total_calls']:
            print(f"  • Period 2 had {abs(calls_change)} more calls ({abs(calls_pct):.1f}% higher)")
        else:
            print(f"  • Both periods had the same number of calls")
        
        if p1_answer_rate > p2_answer_rate:
            print(f"  • Answer rate improved by {rate_change:.1f}%")
        elif p1_answer_rate < p2_answer_rate:
            print(f"  • Answer rate decreased by {abs(rate_change):.1f}%")
        
    except Exception as e:
        print_error(f"Error comparing campaigns: {e}")

def _print_change(change, pct, is_percent=False):
    """Print formatted change with color"""
    if change > 0:
        if is_percent:
            print_color(f"▲ +{change:.1f}%", Colors.GREEN)
        else:
            print_color(f"▲ +{int(change)} (+{pct:.1f}%)", Colors.GREEN)
    elif change < 0:
        if is_percent:
            print_color(f"▼ {change:.1f}%", Colors.RED)
        else:
            print_color(f"▼ {int(change)} ({pct:.1f}%)", Colors.RED)
    else:
        print_color(f"→ 0 (0%)", Colors.YELLOW)

def compare_campaigns_side_by_side():
    """Compare multiple campaigns side by side"""
    print_header("📊 CAMPAIGN COMPARISON", Colors.CYAN)
    
    # Get campaign list
    campaigns = get_campaign_list()
    
    if not campaigns:
        print_warning("No campaigns found")
        return
    
    # Display campaigns
    print("\n📋 Available Campaigns:")
    col_width = 20
    cols = 3
    
    for i, camp in enumerate(campaigns, 1):
        print(f"{i:3}. {camp:<{col_width-4}}", end="")
        if i % cols == 0:
            print()
    
    if len(campaigns) % cols != 0:
        print()
    
    # Select campaigns to compare
    print("\n" + "-" * 60)
    print("Enter campaign numbers to compare (comma-separated, e.g., 1,3,5):")
    choice = input("Choice: ").strip()
    
    selected = []
    for part in choice.split(','):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(campaigns):
                selected.append(campaigns[idx])
    
    if len(selected) < 2:
        print_error("Please select at least 2 campaigns")
        return
    
    # Select date range
    print("\nSelect date range:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. This Week")
    print("  4. Last Week")
    print("  5. This Month")
    print("  6. Last Month")
    print("  7. Last 30 Days")
    print("  8. Custom Range")
    
    range_choice = input("\nChoice (1-8): ").strip()
    
    if range_choice == '8':
        start = input("Start date (YYYY-MM-DD): ").strip()
        end = input("End date (YYYY-MM-DD): ").strip()
        try:
            start = datetime.strptime(start, '%Y-%m-%d').date()
            end = datetime.strptime(end, '%Y-%m-%d').date()
        except:
            print_error("Invalid date format")
            return
    else:
        period_map = {
            '1': 'today', '2': 'yesterday', '3': 'this_week', '4': 'last_week',
            '5': 'this_month', '6': 'last_month', '7': 'last_30_days'
        }
        if range_choice in period_map:
            start, end = get_date_range(period_map[range_choice])
        else:
            print_error("Invalid choice")
            return
    
    # Get data for each campaign
    campaign_data = []
    
    for camp in selected:
        query = """
        SELECT 
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
            SUM(length_in_sec) as total_talk,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        WHERE DATE(call_date) BETWEEN %s AND %s
          AND campaign_id = %s
        """
        
        data = db.execute_query(query, (start, end, camp))
        if data and data[0]['total_calls'] > 0:
            campaign_data.append((camp, data[0]))
    
    if not campaign_data:
        print_error("No data available for selected campaigns")
        return
    
    # Display comparison table
    print_header(f"📊 CAMPAIGN COMPARISON: {start} to {end}", Colors.MAGENTA)
    
    # Create table header
    print(f"\n{'Metric':<20}", end='')
    for camp, _ in campaign_data:
        print(f"{camp:<15}", end='')
    print()
    print('-' * (20 + 15 * len(campaign_data)))
    
    # Total Calls
    print(f"{'Total Calls':<20}", end='')
    for _, data in campaign_data:
        print(f"{data['total_calls']:<15}", end='')
    print()
    
    # Answered Calls
    print(f"{'Answered':<20}", end='')
    for _, data in campaign_data:
        ans_pct = (data['answered']/data['total_calls']*100) if data['total_calls'] > 0 else 0
        print(f"{data['answered']} ({ans_pct:.0f}%){' ':<6}", end='')
    print()
    
    # Abandoned Calls
    print(f"{'Abandoned':<20}", end='')
    for _, data in campaign_data:
        abd_pct = (data['abandoned']/data['total_calls']*100) if data['total_calls'] > 0 else 0
        print(f"{data['abandoned']} ({abd_pct:.0f}%){' ':<6}", end='')
    print()
    
    # Total Talk Time
    print(f"{'Total Talk':<20}", end='')
    for _, data in campaign_data:
        talk_time = sec_to_hms(data['total_talk'] or 0)
        print(f"{talk_time:<15}", end='')
    print()
    
    # Average Talk Time
    print(f"{'Avg Talk':<20}", end='')
    for _, data in campaign_data:
        avg_talk = sec_to_hms(data['avg_talk'] or 0)
        print(f"{avg_talk:<15}", end='')
    print()
    
    # Average Queue Time
    print(f"{'Avg Queue':<20}", end='')
    for _, data in campaign_data:
        avg_queue = f"{data['avg_queue']:.0f}s" if data['avg_queue'] else 'N/A'
        print(f"{avg_queue:<15}", end='')
    print()

def trend_analysis():
    """Trend analysis over time"""
    print_header("📈 TREND ANALYSIS", Colors.CYAN)
    
    try:
        # Get date range options
        print("\nSelect analysis period:")
        print("  1. Last 7 Days (Daily)")
        print("  2. Last 30 Days (Daily)")
        print("  3. Last 12 Weeks (Weekly)")
        print("  4. Last 12 Months (Monthly)")
        print("  5. Custom Range")
        
        period_choice = input("\nChoice (1-5): ").strip()
        
        if period_choice == '1':
            start_date = datetime.now().date() - timedelta(days=7)
            end_date = datetime.now().date()
            interval = 'day'
        elif period_choice == '2':
            start_date = datetime.now().date() - timedelta(days=30)
            end_date = datetime.now().date()
            interval = 'day'
        elif period_choice == '3':
            start_date = datetime.now().date() - timedelta(weeks=12)
            end_date = datetime.now().date()
            interval = 'week'
        elif period_choice == '4':
            start_date = datetime.now().date() - timedelta(days=365)
            end_date = datetime.now().date()
            interval = 'month'
        elif period_choice == '5':
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                interval = input("Interval (day/week/month): ").strip().lower()
            except:
                print_error("Invalid date format")
                return
        else:
            print_error("Invalid choice")
            return
        
        # Get campaign selection
        campaigns = get_campaign_list()
        if not campaigns:
            print_warning("No campaigns found")
            return
        
        print("\n📋 Select campaign (or press Enter for all):")
        print(f"   (Total: {len(campaigns)} — showing first {min(20, len(campaigns))})")
        
        for i, camp in enumerate(campaigns[:20], 1):
            print(f"  {i}. {camp}")
        
        camp_choice = input("\nCampaign name or number: ").strip()
        
        selected_campaign = None
        if camp_choice:
            # Check if it's a valid number within range
            if camp_choice.isdigit() and 1 <= int(camp_choice) <= min(20, len(campaigns)):
                selected_campaign = campaigns[int(camp_choice)-1]
            elif camp_choice in campaigns:
                selected_campaign = camp_choice
            elif camp_choice.isdigit():
                print_warning(f"Number must be between 1 and {min(20, len(campaigns))}")
                return
            else:
                # Try partial match
                partial = [c for c in campaigns if camp_choice.lower() in c.lower()]
                if len(partial) == 1:
                    selected_campaign = partial[0]
                elif len(partial) > 1:
                    print(f"\n🔍 Multiple matches found ({len(partial)}):")
                    for p in partial[:5]:
                        print(f"   • {p}")
                    if len(partial) > 5:
                        print(f"   ... and {len(partial)-5} more")
                    print("\nPlease enter the exact campaign name.")
                    return
                else:
                    print_error(f"Campaign '{camp_choice}' not found")
                    return
        
        # Build query based on interval
        if interval == 'day':
            group_by = "DATE(call_date)"
            date_format = "%Y-%m-%d"
            limit = (end_date - start_date).days
        elif interval == 'week':
            group_by = "YEARWEEK(call_date)"
            date_format = "%Y-W%V"
            limit = 12
        elif interval == 'month':
            group_by = "DATE_FORMAT(call_date, '%Y-%m')"
            date_format = "%Y-%m"
            limit = 12
        else:
            group_by = "DATE(call_date)"
            date_format = "%Y-%m-%d"
            limit = 30
        
        # Build WHERE clause
        where_clause = "WHERE DATE(call_date) BETWEEN %s AND %s"
        params = [start_date, end_date]
        
        if selected_campaign:
            where_clause += " AND campaign_id = %s"
            params.append(selected_campaign)
        
        # Get trend data
        query = f"""
        SELECT 
            {group_by} as period,
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
            SUM(length_in_sec) as total_talk,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        {where_clause}
        GROUP BY {group_by}
        ORDER BY period
        LIMIT {limit}
        """
        
        results = db.execute_query(query, params)
        
        if not results:
            print_error("No data available for selected period")
            return
        
        # Display header
        title = "📈 TREND ANALYSIS"
        if selected_campaign:
            title += f" - {selected_campaign}"
        print_header(title, Colors.MAGENTA)
        print(f"Period: {start_date} to {end_date}")
        
        # Calculate statistics
        total_calls = sum(r['total_calls'] for r in results)
        avg_calls = total_calls / len(results)
        
        # Find trends
        calls_list = [r['total_calls'] for r in results]
        first_avg = sum(calls_list[:3]) / 3 if len(calls_list) >= 3 else calls_list[0]
        last_avg = sum(calls_list[-3:]) / 3 if len(calls_list) >= 3 else calls_list[-1]
        trend_pct = ((last_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
        
        # Display trend chart
        print(f"\n📊 CALL VOLUME TREND:")
        print("-" * 70)
        
        max_calls = max(calls_list)
        for i, r in enumerate(results):
            period = str(r['period'])
            if len(period) > 10:
                period = period[-5:]  # Shorten for display
            calls = r['total_calls']
            bar_length = int((calls / max_calls) * 30) if max_calls > 0 else 0
            bar = "█" * bar_length
            
            # Color based on volume
            if calls > avg_calls * 1.2:
                color = Colors.GREEN
            elif calls < avg_calls * 0.8:
                color = Colors.RED
            else:
                color = Colors.YELLOW
            
            print_color(f"{period:<12} {calls:>5} {bar}", color)
        
        # Display statistics
        print(f"\n📈 TREND STATISTICS:")
        print("-" * 50)
        print(f"  • Total Calls: {total_calls}")
        print(f"  • Average Calls: {avg_calls:.1f}")
        print(f"  • Peak Calls: {max(calls_list)}")
        print(f"  • Lowest Calls: {min(calls_list)}")
        print(f"  • Trend: ", end='')
        if trend_pct > 10:
            print_color(f"▲ Strong Upward (+{trend_pct:.1f}%)", Colors.GREEN)
        elif trend_pct > 0:
            print_color(f"▲ Slight Upward (+{trend_pct:.1f}%)", Colors.GREEN)
        elif trend_pct < -10:
            print_color(f"▼ Strong Downward ({trend_pct:.1f}%)", Colors.RED)
        elif trend_pct < 0:
            print_color(f"▼ Slight Downward ({trend_pct:.1f}%)", Colors.RED)
        else:
            print_color(f"→ Stable (0%)", Colors.YELLOW)
        
        # Answer rate trend
        ans_rates = [(r['answered']/r['total_calls']*100) if r['total_calls'] > 0 else 0 for r in results]
        first_ans_rate = sum(ans_rates[:3]) / 3 if len(ans_rates) >= 3 else ans_rates[0]
        last_ans_rate = sum(ans_rates[-3:]) / 3 if len(ans_rates) >= 3 else ans_rates[-1]
        ans_trend = last_ans_rate - first_ans_rate
        
        print(f"  • Answer Rate Trend: ", end='')
        if ans_trend > 5:
            print_color(f"▲ Improving (+{ans_trend:.1f}%)", Colors.GREEN)
        elif ans_trend > 0:
            print_color(f"▲ Slight Improvement (+{ans_trend:.1f}%)", Colors.GREEN)
        elif ans_trend < -5:
            print_color(f"▼ Declining ({ans_trend:.1f}%)", Colors.RED)
        elif ans_trend < 0:
            print_color(f"▼ Slight Decline ({ans_trend:.1f}%)", Colors.RED)
        else:
            print_color(f"→ Stable", Colors.YELLOW)
        
    except Exception as e:
        print_error(f"Error in trend analysis: {e}")

def performance_over_time():
    """Performance metrics over time"""
    print_header("📉 PERFORMANCE OVER TIME", Colors.MAGENTA)
    
    try:
        # Get metric selection
        print("\nSelect metric to analyze:")
        print("  1. Call Volume")
        print("  2. Answer Rate")
        print("  3. Abandon Rate")
        print("  4. Average Talk Time")
        print("  5. Average Queue Time")
        print("  6. All Metrics")
        
        metric_choice = input("\nChoice (1-6): ").strip()
        
        metric_map = {
            '1': ('total_calls', 'Call Volume'),
            '2': ('answer_rate', 'Answer Rate'),
            '3': ('abandon_rate', 'Abandon Rate'),
            '4': ('avg_talk', 'Avg Talk Time'),
            '5': ('avg_queue', 'Avg Queue Time'),
            '6': ('all', 'All Metrics')
        }
        
        if metric_choice not in metric_map:
            print_error("Invalid choice")
            return
        
        metric_field, metric_name = metric_map[metric_choice]
        
        # Get period selection
        print("\nSelect period:")
        print("  1. Last 7 Days (Daily)")
        print("  2. Last 30 Days (Daily)")
        print("  3. Last 12 Weeks (Weekly)")
        print("  4. Last 12 Months (Monthly)")
        print("  5. Custom Range")
        
        period_choice = input("\nChoice (1-5): ").strip()
        
        if period_choice == '1':
            start_date = datetime.now().date() - timedelta(days=7)
            end_date = datetime.now().date()
            interval = 'day'
        elif period_choice == '2':
            start_date = datetime.now().date() - timedelta(days=30)
            end_date = datetime.now().date()
            interval = 'day'
        elif period_choice == '3':
            start_date = datetime.now().date() - timedelta(weeks=12)
            end_date = datetime.now().date()
            interval = 'week'
        elif period_choice == '4':
            start_date = datetime.now().date() - timedelta(days=365)
            end_date = datetime.now().date()
            interval = 'month'
        elif period_choice == '5':
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                interval = input("Interval (day/week/month): ").strip().lower()
            except:
                print_error("Invalid date format")
                return
        else:
            print_error("Invalid choice")
            return
        
        # Get campaign selection
        campaigns = get_campaign_list()
        if not campaigns:
            print_warning("No campaigns found")
            return
        
        print("\n📋 Select campaign (or press Enter for all):")
        print(f"   (Total: {len(campaigns)} — showing first {min(20, len(campaigns))})")
        
        for i, camp in enumerate(campaigns[:20], 1):
            print(f"  {i}. {camp}")
        
        camp_choice = input("\nCampaign name or number: ").strip()
        
        selected_campaign = None
        if camp_choice:
            # Check if it's a valid number within range
            if camp_choice.isdigit() and 1 <= int(camp_choice) <= min(20, len(campaigns)):
                selected_campaign = campaigns[int(camp_choice)-1]
            elif camp_choice in campaigns:
                selected_campaign = camp_choice
            elif camp_choice.isdigit():
                print_warning(f"Number must be between 1 and {min(20, len(campaigns))}")
                return
            else:
                # Try partial match
                partial = [c for c in campaigns if camp_choice.lower() in c.lower()]
                if len(partial) == 1:
                    selected_campaign = partial[0]
                elif len(partial) > 1:
                    print(f"\n🔍 Multiple matches found ({len(partial)}):")
                    for p in partial[:5]:
                        print(f"   • {p}")
                    if len(partial) > 5:
                        print(f"   ... and {len(partial)-5} more")
                    print("\nPlease enter the exact campaign name.")
                    return
                else:
                    print_error(f"Campaign '{camp_choice}' not found")
                    return
        
        # Build query based on interval
        if interval == 'day':
            group_by = "DATE(call_date)"
            date_format = "%Y-%m-%d"
        elif interval == 'week':
            group_by = "YEARWEEK(call_date)"
            date_format = "%Y-W%V"
        elif interval == 'month':
            group_by = "DATE_FORMAT(call_date, '%Y-%m')"
            date_format = "%Y-%m"
        else:
            group_by = "DATE(call_date)"
            date_format = "%Y-%m-%d"
        
        # Build WHERE clause
        where_clause = "WHERE DATE(call_date) BETWEEN %s AND %s"
        params = [start_date, end_date]
        
        if selected_campaign:
            where_clause += " AND campaign_id = %s"
            params.append(selected_campaign)
        
        # Get performance data
        query = f"""
        SELECT 
            {group_by} as period,
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        {where_clause}
        GROUP BY {group_by}
        ORDER BY period
        """
        
        results = db.execute_query(query, params)
        
        if not results:
            print_error("No data available for selected period")
            return
        
        # Display header
        title = f"📉 PERFORMANCE OVER TIME - {metric_name}"
        if selected_campaign:
            title += f" - {selected_campaign}"
        print_header(title, Colors.MAGENTA)
        print(f"Period: {start_date} to {end_date}")
        
        if metric_field == 'all':
            # Display all metrics table
            print(f"\n{'Period':<12} {'Calls':<8} {'Ans%':<7} {'Abd%':<7} {'Avg Talk':<10} {'Avg Queue':<10}")
            print("-" * 60)
            
            for r in results:
                period = str(r['period'])
                if len(period) > 10:
                    period = period[-5:]
                
                total = r['total_calls']
                ans_pct = (r['answered']/total*100) if total > 0 else 0
                abd_pct = (r['abandoned']/total*100) if total > 0 else 0
                avg_talk = sec_to_hms(r['avg_talk'] or 0)
                avg_queue = sec_to_hms(r['avg_queue'] or 0)
                
                print(f"{period:<12} {total:<8} {ans_pct:.1f}%{' ':<3} {abd_pct:.1f}%{' ':<3} {avg_talk:<10} {avg_queue:<10}")
        
        else:
            # Display single metric chart
            print(f"\n📊 {metric_name} TREND:")
            print("-" * 60)
            
            values = []
            for r in results:
                if metric_field == 'total_calls':
                    val = r['total_calls']
                elif metric_field == 'answer_rate':
                    val = (r['answered']/r['total_calls']*100) if r['total_calls'] > 0 else 0
                elif metric_field == 'abandon_rate':
                    val = (r['abandoned']/r['total_calls']*100) if r['total_calls'] > 0 else 0
                elif metric_field == 'avg_talk':
                    val = r['avg_talk'] or 0
                elif metric_field == 'avg_queue':
                    val = r['avg_queue'] or 0
                else:
                    val = r['total_calls']
                values.append(val)
            
            max_val = max(values) if values else 1
            
            for i, r in enumerate(results):
                period = str(r['period'])
                if len(period) > 10:
                    period = period[-5:]
                
                val = values[i]
                
                # Format value for display
                if metric_field in ['avg_talk', 'avg_queue']:
                    val_display = sec_to_hms(val)
                    bar_length = int((val / max_val) * 30) if max_val > 0 else 0
                elif metric_field in ['answer_rate', 'abandon_rate']:
                    val_display = f"{val:.1f}%"
                    bar_length = int(val / 3)  # Scale percentage to 30 chars max
                else:
                    val_display = str(val)
                    bar_length = int((val / max_val) * 30) if max_val > 0 else 0
                
                bar = "█" * bar_length
                
                print(f"{period:<12} {val_display:>8} {bar}")
            
            # Calculate statistics
            avg_val = sum(values) / len(values)
            print(f"\n📊 Statistics:")
            print(f"  • Average: {avg_val:.1f}")
            print(f"  • Peak: {max(values):.1f}")
            print(f"  • Lowest: {min(values):.1f}")
        
    except Exception as e:
        print_error(f"Error in performance over time: {e}")

def historical_menu():
    """Main historical comparisons menu"""
    while True:
        print_header("📊 HISTORICAL COMPARISONS", Colors.MAGENTA)
        print("  1. 📅 Compare Time Periods")
        print("  2. 📊 Compare Campaigns Side-by-Side")
        print("  3. 📈 Trend Analysis")
        print("  4. 📉 Performance Over Time")
        print("  0. 🔙 Back")
        print("-" * 40)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            compare_periods()
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            compare_campaigns_side_by_side()
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            trend_analysis()
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            performance_over_time()
            input("\nPress Enter to continue...")
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    historical_menu()