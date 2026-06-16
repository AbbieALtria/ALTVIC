# campaigns/trends.py - Campaign trends and historical analysis

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms

def get_campaign_list():
    """Get list of active campaigns from last 30 days"""
    try:
        query = """
        SELECT DISTINCT campaign_id
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        ORDER BY campaign_id
        """
        results = db.execute_query(query)
        
        # Get the list from database
        db_campaigns = [r['campaign_id'] for r in results] if results else []
        
        # Add known campaigns that might not have calls in last 30 days
        known_campaigns = [
            'AAASUP', 'Aiven', 'ALTRIA', 'Boxco', 'CL_TESTCAMP',
            'DignityBioLabs', 'HealthBuy', 'K1', 'NutraPrice', 'NyxAds',
            'PublisherPayment', 'Revitol', 'SAVVYCS', 'ShopMyHealth',
            'TikTok', 'TodosGamersCS', 'UpliftDeals', 'Xshield',
            'YPDirect', 'Zappify'
        ]
        
        # Combine and remove duplicates
        all_campaigns = list(set(db_campaigns + known_campaigns))
        return sorted(all_campaigns)
        
    except Exception as e:
        print_error(f"Error getting campaign list: {e}")
        return []

def show_hourly_trends(campaign=None):
    """Show hourly call distribution"""
    print_header("📊 HOURLY CALL TRENDS", Colors.CYAN)
    
    try:
        where_clause = "WHERE call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        params = []
        
        if campaign:
            where_clause += " AND campaign_id = %s"
            params.append(campaign)
        
        query = f"""
        SELECT 
            HOUR(call_date) as hour,
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') THEN 1 ELSE 0 END) as abandoned
        FROM vicidial_closer_log
        {where_clause}
        GROUP BY HOUR(call_date)
        ORDER BY hour
        """
        
        results = db.execute_query(query, params) if params else db.execute_query(query)
        
        if results:
            print(f"\n📈 HOURLY DISTRIBUTION (Last 7 days){' for ' + campaign if campaign else ''}:")
            print("-" * 70)
            print(f"{'Hour':<8} {'Calls':<10} {'Answered':<10} {'Abandoned':<10} {'Ans%':<8} {'Visual'}")
            print("-" * 70)
            
            max_calls = max(r['total_calls'] for r in results)
            
            for r in results:
                hour = f"{int(r['hour']):02d}:00"
                total = r['total_calls']
                answered = r['answered'] or 0
                abandoned = r['abandoned'] or 0
                ans_pct = (answered/total*100) if total > 0 else 0
                
                # Create a simple bar chart
                bar_length = int((total / max_calls) * 20) if max_calls > 0 else 0
                bar = "█" * bar_length
                
                # Color code by volume
                if total > max_calls * 0.7:
                    color = Colors.RED
                elif total > max_calls * 0.4:
                    color = Colors.YELLOW
                else:
                    color = Colors.GREEN
                
                print_color(f"{hour:<8} {total:<10} {answered:<10} {abandoned:<10} {ans_pct:.1f}%{' ':<3} {bar}", color)
            
            # Find peak hours
            peak_hour = max(results, key=lambda x: x['total_calls'])
            print(f"\n⏰ Peak hour: {int(peak_hour['hour']):02d}:00 with {peak_hour['total_calls']} calls")
            
        else:
            print("No data available for hourly trends")
            
    except Exception as e:
        print_error(f"Error getting hourly trends: {e}")

def show_daily_trends(campaign=None):
    """Show daily call trends for last 30 days"""
    print_header("📊 DAILY CALL TRENDS", Colors.BLUE)
    
    try:
        where_clause = "WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        params = []
        
        if campaign:
            where_clause += " AND campaign_id = %s"
            params.append(campaign)
        
        query = f"""
        SELECT 
            DATE(call_date) as call_date,
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') THEN 1 ELSE 0 END) as abandoned
        FROM vicidial_closer_log
        {where_clause}
        GROUP BY DATE(call_date)
        ORDER BY call_date DESC
        LIMIT 30
        """
        
        results = db.execute_query(query, params) if params else db.execute_query(query)
        
        if results:
            print(f"\n📈 DAILY TRENDS (Last 30 days){' for ' + campaign if campaign else ''}:")
            print("-" * 80)
            print(f"{'Date':<12} {'Calls':<8} {'Answered':<8} {'Abandoned':<8} {'Ans%':<6} {'Change':<10}")
            print("-" * 80)
            
            prev_total = None
            for r in results:
                date_str = r['call_date'].strftime('%Y-%m-%d') if hasattr(r['call_date'], 'strftime') else str(r['call_date'])
                total = r['total_calls']
                answered = r['answered'] or 0
                abandoned = r['abandoned'] or 0
                ans_pct = (answered/total*100) if total > 0 else 0
                
                # Calculate day-over-day change
                if prev_total is not None:
                    change = total - prev_total
                    if change > 0:
                        change_str = f"▲ +{change}"
                        change_color = Colors.GREEN
                    elif change < 0:
                        change_str = f"▼ {change}"
                        change_color = Colors.RED
                    else:
                        change_str = "0"
                        change_color = Colors.YELLOW
                else:
                    change_str = "—"
                    change_color = Colors.RESET
                
                print_color(f"{date_str:<12} {total:<8} {answered:<8} {abandoned:<8} {ans_pct:.1f}%{' ':<2} {change_str:<10}", change_color)
                prev_total = total
            
            # Calculate averages
            avg_calls = sum(r['total_calls'] for r in results) / len(results)
            print(f"\n📊 Average daily calls: {avg_calls:.1f}")
            
        else:
            print("No data available for daily trends")
            
    except Exception as e:
        print_error(f"Error getting daily trends: {e}")

def show_weekly_trends(campaign=None):
    """Show weekly trends"""
    print_header("📊 WEEKLY TRENDS", Colors.MAGENTA)
    
    try:
        where_clause = "WHERE call_date >= DATE_SUB(NOW(), INTERVAL 12 WEEK)"
        params = []
        
        if campaign:
            where_clause += " AND campaign_id = %s"
            params.append(campaign)
        
        query = f"""
        SELECT 
            YEARWEEK(call_date) as week,
            MIN(DATE(call_date)) as week_start,
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        {where_clause}
        GROUP BY YEARWEEK(call_date)
        ORDER BY week DESC
        LIMIT 12
        """
        
        results = db.execute_query(query, params) if params else db.execute_query(query)
        
        if results:
            print(f"\n📈 WEEKLY TRENDS (Last 12 weeks){' for ' + campaign if campaign else ''}:")
            print("-" * 70)
            print(f"{'Week Starting':<15} {'Calls':<8} {'Answered':<8} {'Ans%':<6} {'Avg Queue':<10}")
            print("-" * 70)
            
            for r in results:
                week_start = r['week_start'].strftime('%m/%d') if hasattr(r['week_start'], 'strftime') else str(r['week_start'])
                total = r['total_calls']
                answered = r['answered'] or 0
                ans_pct = (answered/total*100) if total > 0 else 0
                avg_queue = f"{r['avg_queue']:.0f}s" if r['avg_queue'] else 'N/A'
                
                print(f"{week_start:<15} {total:<8} {answered:<8} {ans_pct:.1f}%{' ':<2} {avg_queue:<10}")
            
        else:
            print("No data available for weekly trends")
            
    except Exception as e:
        print_error(f"Error getting weekly trends: {e}")

def show_busiest_times():
    """Show busiest times of day/week"""
    print_header("⏰ BUSIEST TIMES", Colors.YELLOW)
    
    try:
        # Busiest hours
        hour_query = """
        SELECT 
            HOUR(call_date) as hour,
            COUNT(*) as total_calls,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY HOUR(call_date)
        ORDER BY total_calls DESC
        LIMIT 5
        """
        
        hours = db.execute_query(hour_query)
        
        if hours:
            print("\n🔥 BUSIEST HOURS:")
            print("-" * 40)
            print(f"{'Hour':<8} {'Calls':<10} {'Avg Queue':<10}")
            print("-" * 40)
            for h in hours:
                hour_str = f"{int(h['hour']):02d}:00"
                avg_queue = f"{h['avg_queue']:.0f}s" if h['avg_queue'] else 'N/A'
                print(f"{hour_str:<8} {h['total_calls']:<10} {avg_queue:<10}")
        
        # Busiest weekdays
        weekday_query = """
        SELECT 
            DAYNAME(call_date) as weekday,
            COUNT(*) as total_calls,
            AVG(queue_seconds) as avg_queue
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY DAYNAME(call_date)
        ORDER BY total_calls DESC
        """
        
        weekdays = db.execute_query(weekday_query)
        
        if weekdays:
            print("\n📅 BUSIEST WEEKDAYS:")
            print("-" * 40)
            print(f"{'Weekday':<10} {'Calls':<10} {'Avg Queue':<10}")
            print("-" * 40)
            for w in weekdays:
                avg_queue = f"{w['avg_queue']:.0f}s" if w['avg_queue'] else 'N/A'
                print(f"{w['weekday']:<10} {w['total_calls']:<10} {avg_queue:<10}")
        
    except Exception as e:
        print_error(f"Error getting busiest times: {e}")

def show_campaign_list_full():
    """Display ALL campaigns in a formatted table"""
    campaigns = get_campaign_list()
    
    if not campaigns:
        print_warning("No campaigns found")
        return None
    
    print_header(f"📋 ALL CAMPAIGNS (Total: {len(campaigns)})", Colors.CYAN)
    print("-" * 80)
    
    # Display in 4 columns for better visibility
    col_width = 20
    cols = 4
    
    for i, camp in enumerate(campaigns, 1):
        # Format with number
        display = f"{i:3}. {camp}"
        
        # Pad to column width
        if len(display) < col_width:
            display = display.ljust(col_width)
        
        print(display, end="")
        
        # New line after every 4 items
        if i % cols == 0:
            print()
    
    # Print newline if last row wasn't complete
    if len(campaigns) % cols != 0:
        print()
    
    print("-" * 80)
    return campaigns

def trends_menu():
    """Main trends menu"""
    while True:
        print_header("📊 CAMPAIGN TRENDS", Colors.CYAN)
        print("  1. ⏰ Hourly Trends (All Campaigns)")
        print("  2. 📅 Daily Trends (All Campaigns)")
        print("  3. 📆 Weekly Trends (All Campaigns)")
        print("  4. 🔥 Busiest Times")
        print("  5. 🎯 Specific Campaign Trends")
        print("  0. 🔙 Back")
        print("-" * 50)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_hourly_trends()
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            show_daily_trends()
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            show_weekly_trends()
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            show_busiest_times()
            input("\nPress Enter to continue...")
        
        elif choice == '5':
            # Show ALL campaigns first
            campaigns = show_campaign_list_full()
            
            if not campaigns:
                input("\nPress Enter to continue...")
                continue
            
            print("\n💡 Enter the NUMBER or the CAMPAIGN NAME")
            print("-" * 50)
            
            camp_choice = input("\nEnter campaign name or number: ").strip()
            
            selected_campaign = None
            
            # Check if input is a number
            if camp_choice.isdigit():
                idx = int(camp_choice) - 1
                if 0 <= idx < len(campaigns):
                    selected_campaign = campaigns[idx]
                    print(f"\n✅ Selected: {selected_campaign}")
                else:
                    print_error(f"Invalid number. Please enter 1-{len(campaigns)}")
                    input("\nPress Enter to continue...")
                    continue
            else:
                # Try to find by name (case-insensitive)
                matching = [c for c in campaigns if c.lower() == camp_choice.lower()]
                if matching:
                    selected_campaign = matching[0]
                    print(f"\n✅ Selected: {selected_campaign}")
                else:
                    # Try partial match
                    partial_matches = [c for c in campaigns if camp_choice.lower() in c.lower()]
                    if partial_matches:
                        if len(partial_matches) == 1:
                            selected_campaign = partial_matches[0]
                            print(f"\n✅ Selected: {selected_campaign}")
                        else:
                            print(f"\n🔍 Multiple matches found ({len(partial_matches)}):")
                            # Show all partial matches
                            for i, match in enumerate(partial_matches, 1):
                                print(f"   {i:2}. {match}")
                            
                            sub_choice = input("\nEnter the exact name from list: ").strip()
                            if sub_choice in partial_matches:
                                selected_campaign = sub_choice
                            else:
                                print_error("Campaign not found")
                                input("\nPress Enter to continue...")
                                continue
                    else:
                        print_error(f"Campaign '{camp_choice}' not found")
                        input("\nPress Enter to continue...")
                        continue
            
            # Show trends for selected campaign
            if selected_campaign:
                print(f"\n{'=' * 60}")
                print(f"📊 TRENDS FOR: {selected_campaign}")
                print(f"{'=' * 60}")
                show_hourly_trends(selected_campaign)
                print()
                show_daily_trends(selected_campaign)
                print()
                show_weekly_trends(selected_campaign)
                input("\nPress Enter to continue...")
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    trends_menu()