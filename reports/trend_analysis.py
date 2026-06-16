# reports/trend_analysis.py - Trend analysis over time

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms
from decimal import Decimal
from collections import defaultdict

def safe_value(value, default=0):
    """Safely convert database value to float/int"""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def show_daily_trends(days=30):
    """Show daily trends for the last X days"""
    print_header(f"📈 DAILY TRENDS (Last {days} Days)", Colors.CYAN)
    
    try:
        query = """
        SELECT 
            DATE(call_date) as date,
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') THEN 1 ELSE 0 END) as abandoned,
            AVG(queue_seconds) as avg_queue,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
            COUNT(DISTINCT campaign_id) as active_campaigns
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY DATE(call_date)
        ORDER BY date DESC
        """
        
        results = db.execute_query(query, (days,))
        
        if results:
            print(f"\n{'Date':<12} {'Calls':<8} {'Answered':<8} {'Abandoned':<8} {'Ans%':<6} {'Avg Queue':<10} {'Campaigns':<10}")
            print("-" * 70)
            
            total_calls = 0
            total_answered = 0
            
            for r in results:
                date_str = r['date'].strftime('%Y-%m-%d') if hasattr(r['date'], 'strftime') else str(r['date'])
                calls = r['calls']
                answered = r['answered'] or 0
                abandoned = r['abandoned'] or 0
                ans_pct = (answered/calls*100) if calls > 0 else 0
                avg_queue = f"{r['avg_queue']:.0f}s" if r['avg_queue'] else '0s'
                campaigns = r['active_campaigns'] or 0
                
                # Color code by volume
                if calls > 500:
                    color = Colors.RED
                elif calls > 300:
                    color = Colors.YELLOW
                else:
                    color = Colors.GREEN
                
                print_color(f"{date_str:<12} {calls:<8} {answered:<8} {abandoned:<8} {ans_pct:.0f}%{' ':<2} {avg_queue:<10} {campaigns:<10}", color)
                
                total_calls += calls
                total_answered += answered
            
            avg_daily = total_calls / len(results)
            avg_ans_rate = (total_answered / total_calls * 100) if total_calls > 0 else 0
            
            print("-" * 70)
            print(f"📊 AVERAGES: {avg_daily:.0f} calls/day | {avg_ans_rate:.1f}% answer rate")
            
            # Calculate trend
            if len(results) >= 7:
                recent = results[:7]
                older = results[-7:]
                
                recent_avg = sum(r['calls'] for r in recent) / 7
                older_avg = sum(r['calls'] for r in older) / 7
                
                trend = recent_avg - older_avg
                if trend > 0:
                    print_color(f"📈 Upward trend: +{trend:.0f} calls/day (last 7 days vs previous 7)", Colors.GREEN)
                elif trend < 0:
                    print_color(f"📉 Downward trend: {trend:.0f} calls/day (last 7 days vs previous 7)", Colors.RED)
                else:
                    print(f"📊 Stable trend (last 7 days vs previous 7)")
        
        else:
            print("No data available for trend analysis")
            
    except Exception as e:
        print_error(f"Error in trend analysis: {e}")

def show_weekly_trends(weeks=12):
    """Show weekly trends for the last X weeks"""
    print_header(f"📈 WEEKLY TRENDS (Last {weeks} Weeks)", Colors.BLUE)
    
    try:
        query = """
        SELECT 
            YEARWEEK(call_date) as week_num,
            MIN(DATE(call_date)) as week_start,
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') THEN 1 ELSE 0 END) as abandoned,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL %s WEEK)
        GROUP BY YEARWEEK(call_date)
        ORDER BY week_num DESC
        LIMIT %s
        """
        
        results = db.execute_query(query, (weeks, weeks))
        
        if results:
            print(f"\n{'Week':<12} {'Calls':<8} {'Answered':<8} {'Abandoned':<8} {'Ans%':<6} {'Avg Queue':<10} {'Trend'}")
            print("-" * 70)
            
            prev_calls = None
            for r in results:
                week_start = r['week_start'].strftime('%m/%d') if hasattr(r['week_start'], 'strftime') else str(r['week_start'])
                week_label = f"w/e {week_start}"
                calls = r['calls']
                answered = r['answered'] or 0
                abandoned = r['abandoned'] or 0
                ans_pct = (answered/calls*100) if calls > 0 else 0
                avg_queue = f"{r['avg_queue']:.0f}s" if r['avg_queue'] else '0s'
                
                # Calculate week-over-week change
                if prev_calls is not None:
                    change = calls - prev_calls
                    if change > 0:
                        trend = f"▲ +{change}"
                        trend_color = Colors.GREEN
                    elif change < 0:
                        trend = f"▼ {change}"
                        trend_color = Colors.RED
                    else:
                        trend = "— 0"
                        trend_color = Colors.YELLOW
                else:
                    trend = "—"
                    trend_color = Colors.RESET
                
                print_color(f"{week_label:<12} {calls:<8} {answered:<8} {abandoned:<8} {ans_pct:.0f}%{' ':<2} {avg_queue:<10} {trend}", trend_color)
                prev_calls = calls
            
            # Calculate growth rate
            if len(results) >= 2:
                first_week = results[-1]['calls']
                last_week = results[0]['calls']
                growth = ((last_week - first_week) / first_week * 100) if first_week > 0 else 0
                
                print("-" * 70)
                if growth > 0:
                    print_color(f"📈 {weeks}-week growth: +{growth:.1f}%", Colors.GREEN)
                elif growth < 0:
                    print_color(f"📉 {weeks}-week growth: {growth:.1f}%", Colors.RED)
                else:
                    print(f"📊 {weeks}-week growth: 0%")
        
        else:
            print("No data available for weekly trends")
            
    except Exception as e:
        print_error(f"Error in weekly trends: {e}")

def show_monthly_trends(months=6):
    """Show monthly trends for the last X months"""
    print_header(f"📈 MONTHLY TRENDS (Last {months} Months)", Colors.MAGENTA)
    
    try:
        query = """
        SELECT 
            DATE_FORMAT(call_date, '%%Y-%%m') as month,
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL %s MONTH)
        GROUP BY DATE_FORMAT(call_date, '%%Y-%%m')
        ORDER BY month DESC
        LIMIT %s
        """
        
        results = db.execute_query(query, (months, months))
        
        if results:
            print(f"\n{'Month':<10} {'Calls':<10} {'Answered':<10} {'Ans%':<8} {'Avg Queue':<10}")
            print("-" * 50)
            
            total_calls = 0
            total_answered = 0
            
            for r in results:
                calls = r['calls']
                answered = r['answered'] or 0
                ans_pct = (answered/calls*100) if calls > 0 else 0
                avg_queue = f"{r['avg_queue']:.0f}s" if r['avg_queue'] else '0s'
                
                # Color code by volume
                if calls > 1000:
                    color = Colors.RED
                elif calls > 500:
                    color = Colors.YELLOW
                else:
                    color = Colors.GREEN
                
                print_color(f"{r['month']:<10} {calls:<10} {answered:<10} {ans_pct:.0f}%{' ':<2} {avg_queue:<10}", color)
                
                total_calls += calls
                total_answered += answered
            
            avg_monthly = total_calls / len(results)
            avg_ans_rate = (total_answered / total_calls * 100) if total_calls > 0 else 0
            
            print("-" * 50)
            print(f"📊 AVERAGES: {avg_monthly:.0f} calls/month | {avg_ans_rate:.1f}% answer rate")
            
            # Calculate trend
            if len(results) >= 2:
                first_month = results[-1]['calls']
                last_month = results[0]['calls']
                change = last_month - first_month
                change_pct = (change / first_month * 100) if first_month > 0 else 0
                
                if change > 0:
                    print_color(f"📈 Upward trend: +{change} calls ({change_pct:.1f}%)", Colors.GREEN)
                elif change < 0:
                    print_color(f"📉 Downward trend: {change} calls ({change_pct:.1f}%)", Colors.RED)
                else:
                    print(f"📊 Stable trend")
        
        else:
            print("No data available for monthly trends")
            
    except Exception as e:
        print_error(f"Error in monthly trends: {e}")
        import traceback
        traceback.print_exc()

def show_week_over_week():
    """Show week-over-week comparison"""
    print_header("🔄 WEEK-OVER-WEEK COMPARISON", Colors.YELLOW)
    
    try:
        # Get current week data (last 7 complete days)
        current_query = """
        SELECT 
            DATE(call_date) as date,
            DAYNAME(call_date) as day_name,
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') THEN 1 ELSE 0 END) as abandoned,
            AVG(queue_seconds) as avg_queue,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
          AND call_date < CURDATE()
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        
        # Get previous week data (7-14 days ago)
        previous_query = """
        SELECT 
            DATE(call_date) as date,
            DAYNAME(call_date) as day_name,
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') THEN 1 ELSE 0 END) as abandoned,
            AVG(queue_seconds) as avg_queue,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
          AND call_date < DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        
        current_week = db.execute_query(current_query)
        previous_week = db.execute_query(previous_query)
        
        if not current_week and not previous_week:
            print_error("\nNo data available for comparison")
            return
        
        # Create lookup dictionaries
        prev_dict = {}
        for row in previous_week:
            day_name = row['day_name']
            prev_dict[day_name] = row
        
        # Display header
        print(f"\n{'='*120}")
        print(f"{'Day':<12} {'Current Week':^50} {'Previous Week':^50} {'Change':>10}")
        print(f"{'':<12} {'Calls':>8} {'Ans%':>6} {'Abd%':>6} {'Queue':>8} {'Talk':>8} | "
              f"{'Calls':>8} {'Ans%':>6} {'Abd%':>6} {'Queue':>8} {'Talk':>8} || "
              f"{'Calls':>8} {'Ans%':>6}")
        print(f"{'='*120}")
        
        # Process each day
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        totals_current = {'calls': 0, 'answered': 0, 'abandoned': 0}
        totals_prev = {'calls': 0, 'answered': 0, 'abandoned': 0}
        
        for day in days_order:
            current = next((r for r in current_week if r['day_name'] == day), None)
            prev = prev_dict.get(day, None)
            
            if current:
                totals_current['calls'] += current['calls']
                totals_current['answered'] += current['answered'] or 0
                totals_current['abandoned'] += current['abandoned'] or 0
            
            if prev:
                totals_prev['calls'] += prev['calls']
                totals_prev['answered'] += prev['answered'] or 0
                totals_prev['abandoned'] += prev['abandoned'] or 0
            
            # Format current week data
            if current:
                cur_ans_pct = (current['answered'] / current['calls'] * 100) if current['calls'] > 0 else 0
                cur_abd_pct = (current['abandoned'] / current['calls'] * 100) if current['calls'] > 0 else 0
                cur_queue = f"{current['avg_queue']:.0f}s" if current['avg_queue'] else '0s'
                cur_talk = f"{current['avg_talk']:.0f}s" if current['avg_talk'] else '0s'
                cur_str = f"{current['calls']:>8} {cur_ans_pct:>5.0f}% {cur_abd_pct:>5.0f}% {cur_queue:>8} {cur_talk:>8}"
            else:
                cur_str = f"{'N/A':>8} {'N/A':>5} {'N/A':>5} {'N/A':>8} {'N/A':>8}"
            
            # Format previous week data
            if prev:
                prev_ans_pct = (prev['answered'] / prev['calls'] * 100) if prev['calls'] > 0 else 0
                prev_abd_pct = (prev['abandoned'] / prev['calls'] * 100) if prev['calls'] > 0 else 0
                prev_queue = f"{prev['avg_queue']:.0f}s" if prev['avg_queue'] else '0s'
                prev_talk = f"{prev['avg_talk']:.0f}s" if prev['avg_talk'] else '0s'
                prev_str = f"{prev['calls']:>8} {prev_ans_pct:>5.0f}% {prev_abd_pct:>5.0f}% {prev_queue:>8} {prev_talk:>8}"
            else:
                prev_str = f"{'N/A':>8} {'N/A':>5} {'N/A':>5} {'N/A':>8} {'N/A':>8}"
            
            # Calculate changes
            if current and prev:
                calls_change = ((current['calls'] - prev['calls']) / prev['calls'] * 100) if prev['calls'] > 0 else 0
                ans_change = cur_ans_pct - prev_ans_pct
                
                # Color code changes
                if calls_change > 10:
                    calls_color = Colors.GREEN
                    calls_symbol = "▲"
                elif calls_change < -10:
                    calls_color = Colors.RED
                    calls_symbol = "▼"
                else:
                    calls_color = Colors.YELLOW
                    calls_symbol = "→"
                
                if ans_change > 5:
                    ans_color = Colors.GREEN
                    ans_symbol = "▲"
                elif ans_change < -5:
                    ans_color = Colors.RED
                    ans_symbol = "▼"
                else:
                    ans_color = Colors.YELLOW
                    ans_symbol = "→"
                
                # Build the change strings
                calls_change_str = f"{calls_change:>+6.0f}% {calls_symbol}"
                ans_change_str = f"{ans_change:>+5.0f}% {ans_symbol}"
                
                # Print the line without using print_color with end parameter
                print(f"{day:<12} {cur_str} | {prev_str} || ", end='')
                
                # Print colored parts using direct color codes
                print(f"{calls_color}{calls_change_str:>8}{Colors.RESET} ", end='')
                print(f"{ans_color}{ans_change_str:>8}{Colors.RESET}")
            else:
                print(f"{day:<12} {cur_str} | {prev_str} || {'N/A':>8} {'N/A':>8}")
        
        # Print totals
        print(f"{'='*120}")
        
        # Calculate totals
        total_cur_ans = (totals_current['answered'] / totals_current['calls'] * 100) if totals_current['calls'] > 0 else 0
        total_cur_abd = (totals_current['abandoned'] / totals_current['calls'] * 100) if totals_current['calls'] > 0 else 0
        total_prev_ans = (totals_prev['answered'] / totals_prev['calls'] * 100) if totals_prev['calls'] > 0 else 0
        total_prev_abd = (totals_prev['abandoned'] / totals_prev['calls'] * 100) if totals_prev['calls'] > 0 else 0
        
        cur_total_str = f"{totals_current['calls']:>8} {total_cur_ans:>5.0f}% {total_cur_abd:>5.0f}% {'':>8} {'':>8}"
        prev_total_str = f"{totals_prev['calls']:>8} {total_prev_ans:>5.0f}% {total_prev_abd:>5.0f}% {'':>8} {'':>8}"
        
        calls_change = ((totals_current['calls'] - totals_prev['calls']) / totals_prev['calls'] * 100) if totals_prev['calls'] > 0 else 0
        ans_change = total_cur_ans - total_prev_ans
        
        print(f"{'TOTAL':<12} {cur_total_str} | {prev_total_str} || "
              f"{calls_change:>+6.0f}% {ans_change:>+5.0f}%")
        
        print(f"{'='*120}")
        
        # Summary section
        print(f"\n📊 WEEKLY SUMMARY:")
        
        # Volume comparison
        if totals_current['calls'] > totals_prev['calls']:
            print_color(f"  • Volume: ▲ +{totals_current['calls'] - totals_prev['calls']} calls ({calls_change:+.1f}%)", Colors.GREEN)
        else:
            print_color(f"  • Volume: ▼ {totals_current['calls'] - totals_prev['calls']} calls ({calls_change:+.1f}%)", Colors.RED)
        
        # Answer rate comparison
        if total_cur_ans > total_prev_ans:
            print_color(f"  • Answer Rate: ▲ +{ans_change:+.1f}%", Colors.GREEN)
        else:
            print_color(f"  • Answer Rate: ▼ {ans_change:+.1f}%", Colors.RED)
        
        # Best and worst days
        if current_week:
            best_day = max(current_week, key=lambda x: x['calls'])
            worst_day = min(current_week, key=lambda x: x['calls'])
            print(f"  • Best Day: {best_day['day_name']} ({best_day['calls']} calls)")
            print(f"  • Worst Day: {worst_day['day_name']} ({worst_day['calls']} calls)")
        
    except Exception as e:
        print_error(f"Error in week-over-week comparison: {e}")
        import traceback
        traceback.print_exc()

def trend_analysis_menu():
    """Main trend analysis menu"""
    while True:
        print_header("📈 TREND ANALYSIS", Colors.CYAN)
        print("  1. 📅 Daily Trends (Last 30 days)")
        print("  2. 📆 Daily Trends (Last 7 days)")
        print("  3. 📊 Weekly Trends (Last 12 weeks)")
        print("  4. 📈 Monthly Trends (Last 6 months)")
        print("  5. 🔄 Compare Week-over-Week")
        print("  0. 🔙 Back")
        print("-" * 40)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_daily_trends(30)
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            show_daily_trends(7)
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            show_weekly_trends(12)
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            show_monthly_trends(6)
            input("\nPress Enter to continue...")
        
        elif choice == '5':
            show_week_over_week()
            input("\nPress Enter to continue...")
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    trend_analysis_menu()