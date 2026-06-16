#!/usr/bin/env python3
# =============================================================================
# File:         call_volume.py
# Version:      1.1.0
# Date:         2026-03-02
# Description:  Call volume analysis and visualization over time
# Location:     D:/Altria_Ops/reports/call_volume.py
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info
from utils.formatter import format_datetime, sec_to_hms, time_ago
import pytz
from decimal import Decimal

# =============================================================================
# Helper Functions
# =============================================================================

def safe_float(value):
    """Safely convert any value to float"""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def safe_int(value):
    """Safely convert any value to int"""
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

def get_est_time():
    """Get current time in EST"""
    utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    est_tz = pytz.timezone('America/New_York')
    return utc_now.astimezone(est_tz)

def format_est_date(date_obj):
    """Format date in EST with proper format"""
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.strptime(date_obj, '%Y-%m-%d %H:%M:%S')
        except:
            return date_obj
    
    if hasattr(date_obj, 'strftime'):
        # Ensure it's timezone aware
        if date_obj.tzinfo is None:
            date_obj = pytz.UTC.localize(date_obj)
        est_date = date_obj.astimezone(pytz.timezone('America/New_York'))
        return est_date.strftime('%Y-%m-%d %H:%M:%S EST')
    return str(date_obj)

def show_hourly_volume(period='yesterday'):
    """Show hourly call volume for selected period"""
    
    current_est = get_est_time()
    
    period_titles = {
        'today': 'TODAY (In Progress)',
        'yesterday': 'YESTERDAY',
        'last7': 'LAST 7 DAYS',
        'last30': 'LAST 30 DAYS'
    }
    
    title = period_titles.get(period, period.upper())
    
    # Create a header with EST time
    print_header(f"📊 HOURLY CALL VOLUME - {title}", Colors.CYAN)
    print_color(f"🕒 Report Generated: {current_est.strftime('%Y-%m-%d %H:%M:%S EST')}", Colors.YELLOW)
    print()
    
    try:
        if period == 'today':
            date_filter = "DATE(call_date) = CURDATE()"
            date_desc = "Today"
            # Show the actual date being queried
            today_date = datetime.now().strftime('%Y-%m-%d')
            print_color(f"📅 Data for: {today_date} (EST)", Colors.GREEN)
        elif period == 'yesterday':
            date_filter = "DATE(call_date) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
            date_desc = "Yesterday"
            # Calculate yesterday's date
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_str = yesterday.strftime('%Y-%m-%d')
            print_color(f"📅 Data for: {yesterday_str} (EST)", Colors.GREEN)
        elif period == 'last7':
            date_filter = "call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
            date_desc = "Last 7 Days"
            start_date = datetime.now() - timedelta(days=7)
            end_date = datetime.now() - timedelta(days=1)
            print_color(f"📅 Data from: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (EST)", Colors.GREEN)
        elif period == 'last30':
            date_filter = "call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
            date_desc = "Last 30 Days"
            start_date = datetime.now() - timedelta(days=30)
            end_date = datetime.now() - timedelta(days=1)
            print_color(f"📅 Data from: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (EST)", Colors.GREEN)
        else:
            date_filter = "DATE(call_date) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
            date_desc = "Yesterday"
        
        print()
        
        # Get hourly breakdown
        if period in ['today', 'yesterday']:
            # Single day view
            query = f"""
            SELECT 
                HOUR(call_date) as hour,
                COUNT(*) as calls,
                SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered
            FROM vicidial_closer_log
            WHERE {date_filter}
            GROUP BY HOUR(call_date)
            ORDER BY hour
            """
            
            results = db.execute_query(query)
            
            if not results:
                if period == 'today':
                    # Check if we have any calls today at all
                    check_query = "SELECT COUNT(*) as count FROM vicidial_closer_log WHERE DATE(call_date) = CURDATE()"
                    check = db.execute_query(check_query)
                    if check and check[0]['count'] > 0:
                        print_warning(f"⚠️  No hourly breakdown available for {date_desc} yet - calls are still coming in")
                        print(f"   Total calls so far today: {check[0]['count']}")
                    else:
                        print_warning(f"⚠️  No data found for {date_desc}")
                else:
                    print_warning(f"⚠️  No data found for {date_desc}")
                return
            
            # Calculate max for scaling
            max_calls = max([safe_int(r['calls']) for r in results]) if results else 1
            
            print(f"{'Hour':<8} {'Calls':<8} {'Bar':<30}")
            print("-" * 50)
            
            total_calls = 0
            peak_hour = 0
            peak_calls = 0
            
            for r in results:
                hour = safe_int(r['hour'])
                calls = safe_int(r['calls'])
                total_calls += calls
                
                if calls > peak_calls:
                    peak_calls = calls
                    peak_hour = hour
                
                # Create bar chart
                bar_length = int((calls / max_calls) * 30) if max_calls > 0 else 0
                bar = "█" * bar_length
                
                # Color code by volume
                if calls > max_calls * 0.7:
                    color = Colors.RED
                elif calls > max_calls * 0.4:
                    color = Colors.YELLOW
                else:
                    color = Colors.GREEN
                
                print_color(f"{hour:02d}:00    {calls:<8} {bar}", color)
            
            print("-" * 50)
            print(f"TOTAL: {total_calls} calls")
            print(f"PEAK HOUR: {peak_hour:02d}:00 ({peak_calls} calls)")
            
        else:
            # Multiple days view - average per hour
            query = f"""
            SELECT 
                HOUR(call_date) as hour,
                COUNT(*) / COUNT(DISTINCT DATE(call_date)) as avg_calls,
                COUNT(*) as total_calls,
                COUNT(DISTINCT DATE(call_date)) as days
            FROM vicidial_closer_log
            WHERE {date_filter}
            GROUP BY HOUR(call_date)
            ORDER BY hour
            """
            
            results = db.execute_query(query)
            
            if not results:
                print_warning(f"⚠️  No data found for {date_desc}")
                return
            
            # Get total days for scaling
            days = safe_int(results[0]['days']) if results else 1
            max_avg = max([safe_float(r['avg_calls']) for r in results]) if results else 1
            
            print(f"\nBased on {days} days of data")
            print(f"{'Hour':<8} {'Avg Calls':<10} {'Total':<8} {'Bar':<30}")
            print("-" * 60)
            
            total_avg = 0
            peak_hour = 0
            peak_avg = 0
            
            for r in results:
                hour = safe_int(r['hour'])
                avg_calls = safe_float(r['avg_calls'])
                total_calls = safe_int(r['total_calls'])
                total_avg += avg_calls
                
                if avg_calls > peak_avg:
                    peak_avg = avg_calls
                    peak_hour = hour
                
                # Create bar chart based on average
                bar_length = int((avg_calls / max_avg) * 30) if max_avg > 0 else 0
                bar = "█" * bar_length
                
                # Color code by volume
                if avg_calls > max_avg * 0.7:
                    color = Colors.RED
                elif avg_calls > max_avg * 0.4:
                    color = Colors.YELLOW
                else:
                    color = Colors.GREEN
                
                print_color(f"{hour:02d}:00    {avg_calls:<10.1f} {total_calls:<8} {bar}", color)
            
            print("-" * 60)
            print(f"DAILY AVG: {total_avg:.0f} calls")
            print(f"PEAK HOUR: {peak_hour:02d}:00 (avg {peak_avg:.1f} calls)")
        
        # Add footer with timezone info
        print()
        print_color(f"🕒 All times are in Eastern Standard Time (EST)", Colors.YELLOW)
        
    except Exception as e:
        print_error(f"Error analyzing call volume: {e}")
        import traceback
        traceback.print_exc()

def show_daily_volume(period='last7'):
    """Show daily call volume for selected period"""
    
    current_est = get_est_time()
    
    period_titles = {
        'last7': 'LAST 7 DAYS',
        'last30': 'LAST 30 DAYS',
        'last90': 'LAST 90 DAYS'
    }
    
    title = period_titles.get(period, period.upper())
    
    print_header(f"📊 DAILY CALL VOLUME - {title}", Colors.CYAN)
    print_color(f"🕒 Report Generated: {current_est.strftime('%Y-%m-%d %H:%M:%S EST')}", Colors.YELLOW)
    print()
    
    try:
        if period == 'last7':
            days = 7
            date_filter = "call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
            start_date = datetime.now() - timedelta(days=7)
            end_date = datetime.now() - timedelta(days=1)
        elif period == 'last30':
            days = 30
            date_filter = "call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
            start_date = datetime.now() - timedelta(days=30)
            end_date = datetime.now() - timedelta(days=1)
        elif period == 'last90':
            days = 90
            date_filter = "call_date >= DATE_SUB(NOW(), INTERVAL 90 DAY)"
            start_date = datetime.now() - timedelta(days=90)
            end_date = datetime.now() - timedelta(days=1)
        else:
            days = 7
            date_filter = "call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
            start_date = datetime.now() - timedelta(days=7)
            end_date = datetime.now() - timedelta(days=1)
        
        print_color(f"📅 Data from: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (EST)", Colors.GREEN)
        print()
        
        query = f"""
        SELECT 
            DATE(call_date) as call_date,
            DAYNAME(call_date) as day_name,
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned
        FROM vicidial_closer_log
        WHERE {date_filter}
        GROUP BY DATE(call_date)
        ORDER BY call_date DESC
        """
        
        results = db.execute_query(query)
        
        if not results:
            print_warning(f"⚠️  No data found for the last {days} days")
            return
        
        # Calculate max for scaling
        max_calls = max([safe_int(r['calls']) for r in results]) if results else 1
        
        print(f"{'Date':<12} {'Day':<10} {'Calls':<8} {'Answered':<10} {'Ans%':<6} {'Bar':<30}")
        print("-" * 80)
        
        total_calls = 0
        total_answered = 0
        
        for r in results:
            date = r['call_date'].strftime('%Y-%m-%d') if hasattr(r['call_date'], 'strftime') else str(r['call_date'])
            day = r['day_name'][:3]
            calls = safe_int(r['calls'])
            answered = safe_int(r['answered'])
            abandoned = safe_int(r['abandoned'])
            ans_pct = (answered / calls * 100) if calls > 0 else 0
            
            total_calls += calls
            total_answered += answered
            
            # Create bar chart
            bar_length = int((calls / max_calls) * 30) if max_calls > 0 else 0
            bar = "█" * bar_length
            
            # Color code by volume
            if calls > max_calls * 0.7:
                color = Colors.RED
            elif calls > max_calls * 0.4:
                color = Colors.YELLOW
            else:
                color = Colors.GREEN
            
            print_color(f"{date:<12} {day:<10} {calls:<8} {answered:<10} {ans_pct:.0f}%{' ':<2} {bar}", color)
        
        print("-" * 80)
        avg_daily = total_calls / len(results)
        avg_ans_rate = (total_answered / total_calls * 100) if total_calls > 0 else 0
        print(f"AVERAGES: {avg_daily:.0f} calls/day | {avg_ans_rate:.1f}% answer rate")
        
        # Calculate trend
        if len(results) >= 2:
            first_half = results[len(results)//2:]
            second_half = results[:len(results)//2]
            
            first_avg = sum(safe_int(r['calls']) for r in first_half) / len(first_half)
            second_avg = sum(safe_int(r['calls']) for r in second_half) / len(second_half)
            
            trend = second_avg - first_avg
            if trend > 0:
                print_color(f"📈 Trend: +{trend:.0f} calls/day increase", Colors.GREEN)
            elif trend < 0:
                print_color(f"📉 Trend: {trend:.0f} calls/day decrease", Colors.RED)
        
        print()
        print_color(f"🕒 All dates are in Eastern Standard Time (EST)", Colors.YELLOW)
        
    except Exception as e:
        print_error(f"Error analyzing daily volume: {e}")
        import traceback
        traceback.print_exc()

def compare_days():
    """Compare two specific days"""
    print_header("🔄 COMPARE DAYS", Colors.MAGENTA)
    
    date1 = input("Enter first date (YYYY-MM-DD): ").strip()
    date2 = input("Enter second date (YYYY-MM-DD): ").strip()
    
    if not date1 or not date2:
        return
    
    current_est = get_est_time()
    print_color(f"\n🕒 Report Generated: {current_est.strftime('%Y-%m-%d %H:%M:%S EST')}", Colors.YELLOW)
    
    try:
        # Get data for first date
        query1 = """
        SELECT 
            HOUR(call_date) as hour,
            COUNT(*) as calls
        FROM vicidial_closer_log
        WHERE DATE(call_date) = %s
        GROUP BY HOUR(call_date)
        ORDER BY hour
        """
        
        data1 = db.execute_query(query1, (date1,))
        
        # Get data for second date
        query2 = """
        SELECT 
            HOUR(call_date) as hour,
            COUNT(*) as calls
        FROM vicidial_closer_log
        WHERE DATE(call_date) = %s
        GROUP BY HOUR(call_date)
        ORDER BY hour
        """
        
        data2 = db.execute_query(query2, (date2,))
        
        if not data1 and not data2:
            print_warning("No data found for either date")
            return
        
        # Create lookup dicts
        dict1 = {safe_int(r['hour']): safe_int(r['calls']) for r in data1} if data1 else {}
        dict2 = {safe_int(r['hour']): safe_int(r['calls']) for r in data2} if data2 else {}
        
        all_hours = sorted(set(list(dict1.keys()) + list(dict2.keys())))
        
        print(f"\n{'Hour':<8} {date1:<10} {date2:<10} {'Diff':<8} {'Bar'}")
        print("-" * 60)
        
        total1 = 0
        total2 = 0
        
        for hour in all_hours:
            calls1 = dict1.get(hour, 0)
            calls2 = dict2.get(hour, 0)
            diff = calls2 - calls1
            
            total1 += calls1
            total2 += calls2
            
            # Simple bar based on max of both
            max_calls = max(max(dict1.values()) if dict1 else 1, max(dict2.values()) if dict2 else 1)
            bar_length = int((max(calls1, calls2) / max_calls) * 20) if max_calls > 0 else 0
            bar = "█" * bar_length
            
            # Color code diff
            if diff > 0:
                diff_color = Colors.GREEN
                diff_symbol = "▲"
            elif diff < 0:
                diff_color = Colors.RED
                diff_symbol = "▼"
            else:
                diff_color = Colors.YELLOW
                diff_symbol = " "
            
            print(f"{hour:02d}:00    {calls1:<10} {calls2:<10} ", end='')
            print_color(f"{diff_symbol} {abs(diff):<3}", diff_color, end=False)
            print(f"     {bar}")
        
        print("-" * 60)
        total_diff = total2 - total1
        if total_diff > 0:
            print_color(f"TOTALS:    {total1:<10} {total2:<10} ▲ +{total_diff}", Colors.GREEN)
        elif total_diff < 0:
            print_color(f"TOTALS:    {total1:<10} {total2:<10} ▼ {total_diff}", Colors.RED)
        else:
            print(f"TOTALS:    {total1:<10} {total2:<10} = 0")
        
        print()
        print_color(f"🕒 All times are in Eastern Standard Time (EST)", Colors.YELLOW)
        
    except Exception as e:
        print_error(f"Error comparing days: {e}")
        import traceback
        traceback.print_exc()

def volume_analysis_menu():
    """Main call volume analysis menu"""
    while True:
        print_header("📊 CALL VOLUME OVER TIME", Colors.CYAN)
        print("  1. 📅 Today (In Progress)")
        print("  2. 📆 Yesterday")
        print("  3. 📊 Last 7 Days (Daily)")
        print("  4. 📈 Last 30 Days (Daily)")
        print("  5. ⏰ Hourly Patterns (Last 7 Days)")
        print("  6. 🔄 Compare Days")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_hourly_volume('today')
            input("\nPress Enter to continue...")
        elif choice == '2':
            show_hourly_volume('yesterday')
            input("\nPress Enter to continue...")
        elif choice == '3':
            show_daily_volume('last7')
            input("\nPress Enter to continue...")
        elif choice == '4':
            show_daily_volume('last30')
            input("\nPress Enter to continue...")
        elif choice == '5':
            show_hourly_volume('last7')
            input("\nPress Enter to continue...")
        elif choice == '6':
            compare_days()
            input("\nPress Enter to continue...")
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    volume_analysis_menu()