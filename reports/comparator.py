# reports/comparator.py - Historical comparisons

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms
from decimal import Decimal

def get_period_dates(period_choice):
    """Get start and end dates for a period choice"""
    today = datetime.now().date()
    
    if period_choice == '1':  # Today
        start_date = today
        end_date = today
    elif period_choice == '2':  # Yesterday
        start_date = today - timedelta(days=1)
        end_date = start_date
    elif period_choice == '3':  # This Week (last 7 days)
        start_date = today - timedelta(days=6)
        end_date = today
    elif period_choice == '4':  # Last Week
        start_date = today - timedelta(days=13)
        end_date = today - timedelta(days=7)
    elif period_choice == '5':  # This Month
        start_date = today - timedelta(days=29)
        end_date = today
    elif period_choice == '6':  # Last Month
        start_date = today - timedelta(days=59)
        end_date = today - timedelta(days=30)
    elif period_choice == '7':  # Last 30 Days
        start_date = today - timedelta(days=29)
        end_date = today
    elif period_choice == '8':  # Custom Range
        print("\n📅 Enter custom range (YYYY-MM-DD):")
        s = input("Start date: ").strip()
        e = input("End date (or Enter for same as start): ").strip()
        
        try:
            start_date = datetime.strptime(s, '%Y-%m-%d').date()
            end_date = start_date if not e else datetime.strptime(e, '%Y-%m-%d').date()
            if end_date < start_date:
                start_date, end_date = end_date, start_date
        except ValueError:
            print_error("Invalid date format. Using today.")
            start_date = today
            end_date = today
    else:
        start_date = today
        end_date = today
    
    return start_date, end_date

def get_period_stats(start_date, end_date):
    """Get campaign statistics for a period"""
    
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    
    # Ensure at least 1 day of data
    days = (end_date - start_date).days + 1
    if days <= 0:
        days = 1
    
    query = """
    SELECT 
        COUNT(*) as total_calls,
        SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
        SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                 OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
        SUM(length_in_sec) as total_talk,
        AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
        AVG(queue_seconds) as avg_queue,
        COUNT(DISTINCT campaign_id) as campaigns
    FROM vicidial_closer_log
    WHERE call_date BETWEEN %s AND %s
    """
    
    result = db.execute_query(query, (start_dt, end_dt))
    
    if result and result[0]['total_calls'] > 0:
        stats = result[0]
        stats['days'] = days
        return stats
    else:
        # Return empty stats with days count
        return {
            'total_calls': 0,
            'answered': 0,
            'abandoned': 0,
            'total_talk': 0,
            'avg_talk': 0,
            'avg_queue': 0,
            'campaigns': 0,
            'days': days
        }

def format_change(value1, value2, is_percentage=False):
    """Format change between two values with arrow indicators"""
    if value2 is None or value1 is None:
        return "N/A"
    
    try:
        # Convert to float for calculation
        v1 = float(value1) if value1 else 0
        v2 = float(value2) if value2 else 0
        
        if v2 == 0:
            if v1 > 0:
                return f"{Colors.GREEN}▲ New{Colors.RESET}"
            else:
                return f"{Colors.YELLOW}— 0{Colors.RESET}"
        
        change = v1 - v2
        pct_change = (change / v2 * 100) if v2 != 0 else 0
        
        if change > 0:
            arrow = "▲"
            color = Colors.GREEN
        elif change < 0:
            arrow = "▼"
            color = Colors.RED
        else:
            arrow = "—"
            color = Colors.YELLOW
        
        if is_percentage:
            return f"{color}{arrow} {change:+.1f}% ({pct_change:+.1f}%){Colors.RESET}"
        else:
            return f"{color}{arrow} {change:+.0f} ({pct_change:+.1f}%){Colors.RESET}"
    except (TypeError, ValueError):
        return "N/A"

def compare_periods():
    """Compare two time periods"""
    print_header("📊 COMPARE TIME PERIODS", Colors.MAGENTA)
    
    try:
        # Get first period
        print("\nSelect first period:")
        print("  1. Today")
        print("  2. Yesterday")
        print("  3. This Week")
        print("  4. Last Week")
        print("  5. This Month")
        print("  6. Last Month")
        print("  7. Last 30 Days")
        print("  8. Custom Range")
        
        choice1 = input(f"\n{Colors.CYAN}Choice (1-8): {Colors.RESET}").strip()
        
        # Get second period
        print("\nSelect second period:")
        print("  1. Today")
        print("  2. Yesterday")
        print("  3. This Week")
        print("  4. Last Week")
        print("  5. This Month")
        print("  6. Last Month")
        print("  7. Last 30 Days")
        print("  8. Custom Range")
        
        choice2 = input(f"\n{Colors.CYAN}Choice (1-8): {Colors.RESET}").strip()
        
        # Get dates for both periods
        start1, end1 = get_period_dates(choice1)
        start2, end2 = get_period_dates(choice2)
        
        # Get stats for both periods
        stats1 = get_period_stats(start1, end1)
        stats2 = get_period_stats(start2, end2)
        
        # Display comparison
        print_header(" CAMPAIGN COMPARISON ", Colors.CYAN)
        
        print(f"\n{'=' * 90}")
        print(f"📅 Period 1: {start1} to {end1} ({stats1['days']} days)")
        print(f"📅 Period 2: {start2} to {end2} ({stats2['days']} days)")
        print(f"{'=' * 90}")
        
        print(f"\n{'Metric':<30} {'Period 1':<20} {'Period 2':<20} {'Change':<20}")
        print("-" * 90)
        
        # Total Calls
        change = format_change(stats1['total_calls'], stats2['total_calls'])
        print(f"{'Total Calls':<30} {stats1['total_calls']:<20} {stats2['total_calls']:<20} {change:<20}")
        
        # Daily Average Calls
        avg1 = stats1['total_calls'] / stats1['days'] if stats1['days'] > 0 else 0
        avg2 = stats2['total_calls'] / stats2['days'] if stats2['days'] > 0 else 0
        change = format_change(avg1, avg2)
        print(f"{'Daily Avg Calls':<30} {avg1:.1f}{' ':<16} {avg2:.1f}{' ':<16} {change:<20}")
        
        # Answered Calls
        change = format_change(stats1['answered'], stats2['answered'])
        print(f"{'Answered Calls':<30} {stats1['answered']:<20} {stats2['answered']:<20} {change:<20}")
        
        # Answer Rate
        rate1 = (stats1['answered'] / stats1['total_calls'] * 100) if stats1['total_calls'] > 0 else 0
        rate2 = (stats2['answered'] / stats2['total_calls'] * 100) if stats2['total_calls'] > 0 else 0
        change = format_change(rate1, rate2, is_percentage=True)
        print(f"{'Answer Rate':<30} {rate1:.1f}%{' ':<16} {rate2:.1f}%{' ':<16} {change:<20}")
        
        # Abandoned Calls
        change = format_change(stats1['abandoned'], stats2['abandoned'])
        print(f"{'Abandoned Calls':<30} {stats1['abandoned']:<20} {stats2['abandoned']:<20} {change:<20}")
        
        # Abandon Rate
        abn_rate1 = (stats1['abandoned'] / stats1['total_calls'] * 100) if stats1['total_calls'] > 0 else 0
        abn_rate2 = (stats2['abandoned'] / stats2['total_calls'] * 100) if stats2['total_calls'] > 0 else 0
        change = format_change(abn_rate1, abn_rate2, is_percentage=True)
        print(f"{'Abandon Rate':<30} {abn_rate1:.1f}%{' ':<16} {abn_rate2:.1f}%{' ':<16} {change:<20}")
        
        # Total Talk Time
        talk1 = sec_to_hms(stats1['total_talk'] or 0)
        talk2 = sec_to_hms(stats2['total_talk'] or 0)
        talk_change = (stats1['total_talk'] or 0) - (stats2['total_talk'] or 0)
        talk_change_str = sec_to_hms(abs(talk_change))
        if talk_change > 0:
            change = f"{Colors.GREEN}▲ +{talk_change_str}{Colors.RESET}"
        elif talk_change < 0:
            change = f"{Colors.RED}▼ -{talk_change_str}{Colors.RESET}"
        else:
            change = f"{Colors.YELLOW}— 0{Colors.RESET}"
        print(f"{'Total Talk Time':<30} {talk1:<20} {talk2:<20} {change:<20}")
        
        # Average Talk Time
        avg_talk1 = sec_to_hms(stats1['avg_talk'] or 0)
        avg_talk2 = sec_to_hms(stats2['avg_talk'] or 0)
        change = format_change(stats1['avg_talk'] or 0, stats2['avg_talk'] or 0)
        print(f"{'Avg Talk Time':<30} {avg_talk1:<20} {avg_talk2:<20} {change:<20}")
        
        # Average Queue Time
        avg_q1 = f"{stats1['avg_queue']:.0f}s" if stats1['avg_queue'] else '0s'
        avg_q2 = f"{stats2['avg_queue']:.0f}s" if stats2['avg_queue'] else '0s'
        change = format_change(stats1['avg_queue'] or 0, stats2['avg_queue'] or 0)
        print(f"{'Avg Queue Time':<30} {avg_q1:<20} {avg_q2:<20} {change:<20}")
        
        # Active Campaigns
        change = format_change(stats1['campaigns'], stats2['campaigns'])
        print(f"{'Active Campaigns':<30} {stats1['campaigns']:<20} {stats2['campaigns']:<20} {change:<20}")
        
        print("-" * 90)
        
        # Summary
        print(f"\n📊 SUMMARY:")
        if stats1['total_calls'] > stats2['total_calls']:
            print(f"  • Period 1 had {stats1['total_calls'] - stats2['total_calls']} more calls than Period 2")
        elif stats1['total_calls'] < stats2['total_calls']:
            print(f"  • Period 2 had {stats2['total_calls'] - stats1['total_calls']} more calls than Period 1")
        else:
            print(f"  • Both periods had the same number of calls")
        
        if rate1 > rate2:
            print(f"  • Answer rate was {rate1 - rate2:.1f}% higher in Period 1")
        elif rate1 < rate2:
            print(f"  • Answer rate was {rate2 - rate1:.1f}% higher in Period 2")
        
    except Exception as e:
        print_error(f"Error comparing campaigns: {e}")

def comparison_menu():
    """Main comparison menu"""
    while True:
        print_header("📊 HISTORICAL COMPARISONS", Colors.MAGENTA)
        print("  1. 🔄 Compare Two Periods")
        print("  2. 📈 Week-over-Week")
        print("  3. 📉 Month-over-Month")
        print("  4. 📊 Year-over-Year")
        print("  0. 🔙 Back")
        print("-" * 40)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            compare_periods()
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            print("\n🚧 Week-over-Week - Coming Soon! 🚧")
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            print("\n🚧 Month-over-Month - Coming Soon! 🚧")
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            print("\n🚧 Year-over-Year - Coming Soon! 🚧")
            input("\nPress Enter to continue...")
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    comparison_menu()