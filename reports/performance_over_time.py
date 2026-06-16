#!/usr/bin/env python3
# =============================================================================
# File:         performance_over_time.py
# Version:      2.0.0
# Date:         2026-03-02
# Description:  Performance metrics over time with EST timezone and campaign breakdown
# Location:     D:/Altria_Ops/reports/performance_over_time.py
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import sec_to_hms
import pytz

# =============================================================================
# Timezone Helper
# =============================================================================

def get_est_now():
    """Get current time in EST"""
    utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    est_tz = pytz.timezone('America/New_York')
    return utc_now.astimezone(est_tz)

def get_est_date_range(period_choice):
    """Get date range based on EST timezone"""
    est_now = get_est_now()
    est_today = est_now.date()
    
    if period_choice == '1':  # Today
        start_dt = datetime.combine(est_today, datetime.min.time())
        end_dt = datetime.combine(est_today, datetime.max.time())
        title = "TODAY"
        
    elif period_choice == '2':  # Yesterday
        est_yesterday = est_today - timedelta(days=1)
        start_dt = datetime.combine(est_yesterday, datetime.min.time())
        end_dt = datetime.combine(est_yesterday, datetime.max.time())
        title = "YESTERDAY"
        
    elif period_choice == '3':  # Last 7 days
        start_dt = datetime.combine(est_today - timedelta(days=6), datetime.min.time())
        end_dt = datetime.combine(est_today, datetime.max.time())
        title = "LAST 7 DAYS"
        
    elif period_choice == '4':  # Last 30 days
        start_dt = datetime.combine(est_today - timedelta(days=29), datetime.min.time())
        end_dt = datetime.combine(est_today, datetime.max.time())
        title = "LAST 30 DAYS"
        
    elif period_choice == '5':  # Last 12 weeks
        start_dt = datetime.combine(est_today - timedelta(weeks=12), datetime.min.time())
        end_dt = datetime.combine(est_today, datetime.max.time())
        title = "LAST 12 WEEKS"
        
    elif period_choice == '6':  # Last 12 months
        start_dt = datetime.combine(est_today - timedelta(days=365), datetime.min.time())
        end_dt = datetime.combine(est_today, datetime.max.time())
        title = "LAST 12 MONTHS"
        
    elif period_choice == '7':  # Custom range
        print("\n📅 Enter custom range (EST):")
        start_str = input("Start date (YYYY-MM-DD): ").strip()
        end_str = input("End date (YYYY-MM-DD): ").strip()
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
            title = f"{start_str} to {end_str}"
        except:
            print_error("Invalid date format")
            return None, None, None
            
    else:
        start_dt = datetime.combine(est_today - timedelta(days=6), datetime.min.time())
        end_dt = datetime.combine(est_today, datetime.max.time())
        title = "LAST 7 DAYS"
    
    return start_dt, end_dt, title

# =============================================================================
# Campaign Selection
# =============================================================================

def get_campaign_filter():
    """Get campaign filter from user"""
    try:
        query = """
        SELECT DISTINCT campaign_id
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        ORDER BY campaign_id
        """
        campaigns = db.execute_query(query)
        campaign_list = [c['campaign_id'] for c in campaigns] if campaigns else []
        
        if not campaign_list:
            return None, None, []
        
        print("\n📋 Available Campaigns:")
        print("-" * 60)
        
        # Display in columns
        for i, camp in enumerate(campaign_list, 1):
            print(f"{i:3}. {camp}", end="")
            if i % 5 == 0:
                print()
            else:
                print("  ", end="")
        print("\n" + "-" * 60)
        
        print("Enter campaign numbers (comma-separated) or 'all':")
        choice = input("> ").strip().lower()
        
        if choice == 'all' or choice == '':
            return None, None, campaign_list
        else:
            selected = []
            for part in choice.split(','):
                part = part.strip()
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(campaign_list):
                        selected.append(campaign_list[idx])
            if selected:
                placeholders = ','.join(['%s'] * len(selected))
                return f" AND campaign_id IN ({placeholders})", selected, selected
            else:
                return None, None, campaign_list
            
    except Exception as e:
        print_error(f"Error loading campaigns: {e}")
        return None, None, []

# =============================================================================
# Performance Metrics Functions
# =============================================================================

def show_call_volume():
    """Show call volume over time with simple campaign breakdown"""
    print_header("📞 CALL VOLUME OVER TIME", Colors.CYAN)
    
    print("\nSelect period:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. Last 7 Days (Daily)")
    print("  4. Last 30 Days (Daily)")
    print("  5. Last 12 Weeks (Weekly)")
    print("  6. Last 12 Months (Monthly)")
    print("  7. Custom Range")
    
    period_choice = input("\nChoice (1-7): ").strip()
    
    start_dt, end_dt, title = get_est_date_range(period_choice)
    if not start_dt:
        return
    
    campaign_filter, campaign_params, selected_campaigns = get_campaign_filter()
    
    print(f"\n📊 Analyzing {title}...")
    print(f"  Period: {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')} (EST)")
    
    # First get daily totals
    if campaign_filter:
        daily_query = f"""
        SELECT 
            DATE(call_date) as date,
            COUNT(*) as calls
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        {campaign_filter}
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt] + campaign_params
    else:
        daily_query = """
        SELECT 
            DATE(call_date) as date,
            COUNT(*) as calls
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt]
    
    daily_results = db.execute_query(daily_query, params)
    
    if not daily_results:
        # Check if there's any data at all
        check_query = "SELECT COUNT(*) as count FROM vicidial_closer_log"
        check = db.execute_query(check_query)
        if check and check[0]['count'] > 0:
            print_warning(f"No data for selected period, but database has {check[0]['count']} total records")
            print("Try selecting 'Yesterday' or 'Last 7 Days'")
        else:
            print_warning("No data found in database")
        return
    
    # Show daily totals
    print(f"\n📅 DAILY TOTALS:")
    print("-" * 40)
    print(f"{'Date':<12} {'Calls':<8} {'Bar'}")
    print("-" * 40)
    
    max_calls = max(r['calls'] for r in daily_results)
    total_calls = 0
    
    for r in daily_results:
        date_str = r['date'].strftime('%m/%d')
        calls = r['calls']
        total_calls += calls
        
        # Bar chart
        bar_length = int((calls / max_calls) * 30) if max_calls > 0 else 0
        bar = "█" * bar_length
        
        # Color code
        if calls > max_calls * 0.7:
            color = Colors.RED
        elif calls > max_calls * 0.4:
            color = Colors.YELLOW
        else:
            color = Colors.GREEN
        
        print_color(f"{date_str:<12} {calls:<8} {bar}", color)
    
    print("-" * 40)
    print(f"TOTAL: {total_calls} calls")
    print(f"AVG: {total_calls/len(daily_results):.0f} calls/day")
    
    # Now get campaign breakdown for the same period
    if campaign_filter:
        campaign_query = f"""
        SELECT 
            campaign_id,
            COUNT(*) as calls
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        {campaign_filter}
        GROUP BY campaign_id
        ORDER BY calls DESC
        """
        params = [start_dt, end_dt] + campaign_params
    else:
        campaign_query = """
        SELECT 
            campaign_id,
            COUNT(*) as calls
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        GROUP BY campaign_id
        ORDER BY calls DESC
        """
        params = [start_dt, end_dt]
    
    campaign_results = db.execute_query(campaign_query, params)
    
    if campaign_results:
        print(f"\n📋 CAMPAIGN BREAKDOWN:")
        print("-" * 50)
        print(f"{'Campaign':<20} {'Calls':<8} {'% of Total':<10}")
        print("-" * 50)
        
        for camp in campaign_results:
            camp_calls = camp['calls']
            pct = (camp_calls / total_calls * 100) if total_calls > 0 else 0
            
            # Color code by volume
            if pct > 30:
                color = Colors.RED
            elif pct > 15:
                color = Colors.YELLOW
            else:
                color = Colors.GREEN
            
            print_color(f"{camp['campaign_id']:<20} {camp_calls:<8} {pct:.1f}%", color)
        
        print("-" * 50)

def show_answer_rate():
    """Show answer rate over time"""
    print_header("🎯 ANSWER RATE OVER TIME", Colors.GREEN)
    
    print("\nSelect period:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. Last 7 Days (Daily)")
    print("  4. Last 30 Days (Daily)")
    print("  5. Last 12 Weeks (Weekly)")
    print("  6. Last 12 Months (Monthly)")
    print("  7. Custom Range")
    
    period_choice = input("\nChoice (1-7): ").strip()
    
    start_dt, end_dt, title = get_est_date_range(period_choice)
    if not start_dt:
        return
    
    campaign_filter, campaign_params, selected_campaigns = get_campaign_filter()
    
    print(f"\n📊 Analyzing {title}...")
    
    if campaign_filter:
        query = f"""
        SELECT 
            DATE(call_date) as date,
            COUNT(*) as total,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        {campaign_filter}
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt] + campaign_params
    else:
        query = """
        SELECT 
            DATE(call_date) as date,
            COUNT(*) as total,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt]
    
    results = db.execute_query(query, params)
    
    if not results:
        print_warning("No data found")
        return
    
    print(f"\n{'Date':<12} {'Total':<8} {'Answered':<10} {'Rate':<8} {'Bar'}")
    print("-" * 60)
    
    max_rate = 100
    total_calls = 0
    total_answered = 0
    
    for r in results:
        date_str = r['date'].strftime('%m/%d')
        total = r['total']
        answered = r['answered'] or 0
        rate = (answered / total * 100) if total > 0 else 0
        
        total_calls += total
        total_answered += answered
        
        # Bar chart
        bar_length = int((rate / max_rate) * 30)
        bar = "█" * bar_length
        
        # Color code
        if rate >= 80:
            color = Colors.GREEN
        elif rate >= 60:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        
        print_color(f"{date_str:<12} {total:<8} {answered:<10} {rate:.0f}%{' ':<2} {bar}", color)
    
    print("-" * 60)
    avg_rate = (total_answered / total_calls * 100) if total_calls > 0 else 0
    print(f"OVERALL: {avg_rate:.1f}% answer rate")

def show_abandon_rate():
    """Show abandon rate over time"""
    print_header("⚠️ ABANDON RATE OVER TIME", Colors.RED)
    
    print("\nSelect period:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. Last 7 Days (Daily)")
    print("  4. Last 30 Days (Daily)")
    print("  5. Last 12 Weeks (Weekly)")
    print("  6. Last 12 Months (Monthly)")
    print("  7. Custom Range")
    
    period_choice = input("\nChoice (1-7): ").strip()
    
    start_dt, end_dt, title = get_est_date_range(period_choice)
    if not start_dt:
        return
    
    campaign_filter, campaign_params, selected_campaigns = get_campaign_filter()
    
    print(f"\n📊 Analyzing {title}...")
    
    if campaign_filter:
        query = f"""
        SELECT 
            DATE(call_date) as date,
            COUNT(*) as total,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        {campaign_filter}
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt] + campaign_params
    else:
        query = """
        SELECT 
            DATE(call_date) as date,
            COUNT(*) as total,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt]
    
    results = db.execute_query(query, params)
    
    if not results:
        print_warning("No data found")
        return
    
    print(f"\n{'Date':<12} {'Total':<8} {'Abandoned':<10} {'Rate':<8} {'Bar'}")
    print("-" * 60)
    
    max_rate = 30
    total_calls = 0
    total_abandoned = 0
    
    for r in results:
        date_str = r['date'].strftime('%m/%d')
        total = r['total']
        abandoned = r['abandoned'] or 0
        rate = (abandoned / total * 100) if total > 0 else 0
        
        total_calls += total
        total_abandoned += abandoned
        
        # Bar chart
        bar_length = int((rate / max_rate) * 30)
        bar = "█" * bar_length
        
        # Color code (lower is better)
        if rate <= 5:
            color = Colors.GREEN
        elif rate <= 10:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        
        print_color(f"{date_str:<12} {total:<8} {abandoned:<10} {rate:.0f}%{' ':<2} {bar}", color)
    
    print("-" * 60)
    avg_rate = (total_abandoned / total_calls * 100) if total_calls > 0 else 0
    print(f"OVERALL: {avg_rate:.1f}% abandon rate")

def show_avg_talk_time():
    """Show average talk time over time"""
    print_header("⏱️ AVERAGE TALK TIME OVER TIME", Colors.BLUE)
    
    print("\nSelect period:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. Last 7 Days (Daily)")
    print("  4. Last 30 Days (Daily)")
    print("  5. Last 12 Weeks (Weekly)")
    print("  6. Last 12 Months (Monthly)")
    print("  7. Custom Range")
    
    period_choice = input("\nChoice (1-7): ").strip()
    
    start_dt, end_dt, title = get_est_date_range(period_choice)
    if not start_dt:
        return
    
    campaign_filter, campaign_params, selected_campaigns = get_campaign_filter()
    
    print(f"\n📊 Analyzing {title}...")
    
    if campaign_filter:
        query = f"""
        SELECT 
            DATE(call_date) as date,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        {campaign_filter}
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt] + campaign_params
    else:
        query = """
        SELECT 
            DATE(call_date) as date,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt]
    
    results = db.execute_query(query, params)
    
    if not results:
        print_warning("No data found")
        return
    
    print(f"\n{'Date':<12} {'Avg Talk':<12} {'Bar'}")
    print("-" * 40)
    
    max_talk = max(r['avg_talk'] or 0 for r in results)
    
    for r in results:
        date_str = r['date'].strftime('%m/%d')
        avg_talk = r['avg_talk'] or 0
        
        # Bar chart
        bar_length = int((avg_talk / max_talk) * 30) if max_talk > 0 else 0
        bar = "█" * bar_length
        
        # Color code
        if avg_talk > 300:
            color = Colors.RED
        elif avg_talk > 180:
            color = Colors.YELLOW
        else:
            color = Colors.GREEN
        
        print_color(f"{date_str:<12} {sec_to_hms(avg_talk):<12} {bar}", color)

def show_avg_queue_time():
    """Show average queue time over time"""
    print_header("⏳ AVERAGE QUEUE TIME OVER TIME", Colors.MAGENTA)
    
    print("\nSelect period:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. Last 7 Days (Daily)")
    print("  4. Last 30 Days (Daily)")
    print("  5. Last 12 Weeks (Weekly)")
    print("  6. Last 12 Months (Monthly)")
    print("  7. Custom Range")
    
    period_choice = input("\nChoice (1-7): ").strip()
    
    start_dt, end_dt, title = get_est_date_range(period_choice)
    if not start_dt:
        return
    
    campaign_filter, campaign_params, selected_campaigns = get_campaign_filter()
    
    print(f"\n📊 Analyzing {title}...")
    
    if campaign_filter:
        query = f"""
        SELECT 
            DATE(call_date) as date,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        {campaign_filter}
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt] + campaign_params
    else:
        query = """
        SELECT 
            DATE(call_date) as date,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt]
    
    results = db.execute_query(query, params)
    
    if not results:
        print_warning("No data found")
        return
    
    print(f"\n{'Date':<12} {'Avg Queue':<12} {'Bar'}")
    print("-" * 40)
    
    max_queue = max(r['avg_queue'] or 0 for r in results)
    
    for r in results:
        date_str = r['date'].strftime('%m/%d')
        avg_queue = r['avg_queue'] or 0
        
        # Bar chart
        bar_length = int((avg_queue / max_queue) * 30) if max_queue > 0 else 0
        bar = "█" * bar_length
        
        # Color code (lower is better)
        if avg_queue <= 20:
            color = Colors.GREEN
        elif avg_queue <= 60:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        
        print_color(f"{date_str:<12} {avg_queue:.0f}s{' ':<8} {bar}", color)

def show_all_metrics():
    """Show all metrics in a combined view"""
    print_header("📊 ALL METRICS OVER TIME", Colors.CYAN)
    
    print("\nSelect period:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. Last 7 Days (Daily)")
    print("  4. Last 30 Days (Daily)")
    
    period_choice = input("\nChoice (1-4): ").strip()
    
    start_dt, end_dt, title = get_est_date_range(period_choice)
    if not start_dt:
        return
    
    campaign_filter, campaign_params, selected_campaigns = get_campaign_filter()
    
    print(f"\n📊 Analyzing {title}...")
    print(f"  Period: {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')} (EST)")
    
    if campaign_filter:
        query = f"""
        SELECT 
            DATE(call_date) as date,
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        {campaign_filter}
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt] + campaign_params
    else:
        query = """
        SELECT 
            DATE(call_date) as date,
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        params = [start_dt, end_dt]
    
    results = db.execute_query(query, params)
    
    if not results:
        print_warning("No data found")
        return
    
    print(f"\n{'Date':<12} {'Calls':<8} {'Ans%':<6} {'Abd%':<6} {'AvgTalk':<8} {'AvgQ':<6}")
    print("-" * 60)
    
    total_calls = 0
    total_answered = 0
    total_abandoned = 0
    
    for r in results:
        date_str = r['date'].strftime('%m/%d')
        calls = r['calls']
        answered = r['answered'] or 0
        abandoned = r['abandoned'] or 0
        ans_pct = (answered / calls * 100) if calls > 0 else 0
        abd_pct = (abandoned / calls * 100) if calls > 0 else 0
        avg_talk = sec_to_hms(r['avg_talk'] or 0)
        avg_queue = f"{r['avg_queue']:.0f}s" if r['avg_queue'] else '0s'
        
        total_calls += calls
        total_answered += answered
        total_abandoned += abandoned
        
        # Color code
        if ans_pct >= 80:
            color = Colors.GREEN
        elif ans_pct >= 60:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        
        print_color(f"{date_str:<12} {calls:<8} {ans_pct:.0f}%{' ':<2} {abd_pct:.0f}%{' ':<2} {avg_talk:<8} {avg_queue:<6}", color)
    
    print("-" * 60)
    avg_ans = (total_answered / total_calls * 100) if total_calls > 0 else 0
    avg_abd = (total_abandoned / total_calls * 100) if total_calls > 0 else 0
    print(f"AVG: {avg_ans:.0f}% ans | {avg_abd:.0f}% abd")

def performance_over_time_menu():
    """Main performance over time menu"""
    while True:
        print_header("📉 PERFORMANCE OVER TIME", Colors.CYAN)
        print("  1. 📞 Call Volume")
        print("  2. 🎯 Answer Rate")
        print("  3. ⚠️ Abandon Rate")
        print("  4. ⏱️ Average Talk Time")
        print("  5. ⏳ Average Queue Time")
        print("  6. 📊 All Metrics")
        print("  0. 🔙 Back")
        print("-" * 50)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_call_volume()
        elif choice == '2':
            show_answer_rate()
        elif choice == '3':
            show_abandon_rate()
        elif choice == '4':
            show_avg_talk_time()
        elif choice == '5':
            show_avg_queue_time()
        elif choice == '6':
            show_all_metrics()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    performance_over_time_menu()