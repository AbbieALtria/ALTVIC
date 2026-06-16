#!/usr/bin/env python3
# =============================================================================
# File:         performance.py
# Version:      1.3.0
# Date:         2026-03-10
# Description:  Campaign performance reports with full 30-day history
# Update:       Removed 10-day limit - now shows ALL 30 days in campaign details
# Author:       Altria Ops Team
# =============================================================================

# campaigns/performance.py - Campaign performance reports

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms

def get_campaign_list():
    """Get list of all campaigns"""
    query = """
    SELECT DISTINCT campaign_id
    FROM vicidial_closer_log
    WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    ORDER BY campaign_id
    """
    
    campaigns = db.execute_query(query)
    return [c['campaign_id'] for c in campaigns] if campaigns else []

def show_campaign_performance(period='30days'):
    """Show performance for all campaigns"""
    print_header("📊 CAMPAIGN PERFORMANCE REPORT", Colors.BLUE)
    
    try:
        if period == 'today':
            date_filter = "DATE(call_date) = CURDATE()"
            title = "TODAY"
        elif period == 'week':
            date_filter = "call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
            title = "LAST 7 DAYS"
        else:
            date_filter = "call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
            title = "LAST 30 DAYS"
        
        query = f"""
        SELECT 
            campaign_id,
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
            SUM(length_in_sec) as total_talk,
            AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
            AVG(queue_seconds) as avg_queue,
            MAX(call_date) as last_call
        FROM vicidial_closer_log
        WHERE {date_filter}
        GROUP BY campaign_id
        HAVING total_calls > 0
        ORDER BY total_calls DESC
        """
        
        results = db.execute_query(query)
        
        if results:
            print(f"\n📈 CAMPAIGN PERFORMANCE - {title}")
            print("-" * 100)
            print(f"{'Campaign':<20} {'Calls':<8} {'Answered':<10} {'Abandoned':<10} {'Ans%':<6} {'Abn%':<6} {'Avg Talk':<10} {'Last Call':<20}")
            print("-" * 100)
            
            total_calls_all = 0
            total_answered_all = 0
            total_abandoned_all = 0
            
            for camp in results:
                total = camp['total_calls']
                answered = camp['answered'] or 0
                abandoned = camp['abandoned'] or 0
                ans_pct = (answered/total*100) if total > 0 else 0
                abn_pct = (abandoned/total*100) if total > 0 else 0
                avg_talk = sec_to_hms(camp['avg_talk'] or 0)
                last_call = format_datetime(camp['last_call'])[5:16] if camp['last_call'] else 'Never'
                
                # Color code by performance
                if ans_pct >= 80:
                    color = Colors.GREEN
                elif ans_pct >= 60:
                    color = Colors.YELLOW
                else:
                    color = Colors.RED
                
                print_color(f"{camp['campaign_id']:<20} {total:<8} {answered:<10} {abandoned:<10} {ans_pct:.1f}%{' ':<2} {abn_pct:.1f}%{' ':<2} {avg_talk:<10} {last_call:<20}", color)
                
                total_calls_all += total
                total_answered_all += answered
                total_abandoned_all += abandoned
            
            # Summary
            print("-" * 100)
            overall_ans_pct = (total_answered_all/total_calls_all*100) if total_calls_all > 0 else 0
            overall_abn_pct = (total_abandoned_all/total_calls_all*100) if total_calls_all > 0 else 0
            print(f"📊 TOTAL: {total_calls_all} calls | Answered: {total_answered_all} ({overall_ans_pct:.1f}%) | Abandoned: {total_abandoned_all} ({overall_abn_pct:.1f}%)")
            
        else:
            print("  No campaign data found for this period")
            
    except Exception as e:
        print_error(f"Error getting campaign performance: {str(e)}")

def show_campaign_details(campaign):
    """Show detailed performance for a specific campaign - NOW SHOWING ALL 30 DAYS"""
    print_header(f"📋 CAMPAIGN DETAILS: {campaign}", Colors.CYAN)
    
    try:
        # Last 30 days stats - SHOW ALL DAYS (no truncation)
        query = """
        SELECT 
            DATE(call_date) as call_date,
            COUNT(*) as daily_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as daily_answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as daily_abandoned,
            AVG(queue_seconds) as daily_avg_queue
        FROM vicidial_closer_log
        WHERE campaign_id = %s
          AND call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY DATE(call_date)
        ORDER BY call_date DESC
        """
        
        daily_stats = db.execute_query(query, (campaign,))
        
        if daily_stats:
            print(f"\n📊 DAILY STATISTICS (Last 30 days):")
            print("-" * 90)
            print(f"{'Date':<12} {'Calls':<8} {'Answered':<10} {'Abandoned':<10} {'Ans%':<6} {'Abn%':<6} {'Avg Queue':<10}")
            print("-" * 90)
            
            # Show ALL 30 days (removed the [:10] limit)
            for day in daily_stats:
                total = day['daily_calls']
                answered = day['daily_answered'] or 0
                abandoned = day['daily_abandoned'] or 0
                ans_pct = (answered/total*100) if total > 0 else 0
                abn_pct = (abandoned/total*100) if total > 0 else 0
                avg_queue = f"{day['daily_avg_queue']:.0f}s" if day['daily_avg_queue'] else 'N/A'
                
                date_str = day['call_date'].strftime('%Y-%m-%d') if hasattr(day['call_date'], 'strftime') else str(day['call_date'])
                print(f"{date_str:<12} {total:<8} {answered:<10} {abandoned:<10} {ans_pct:.1f}%{' ':<2} {abn_pct:.1f}%{' ':<2} {avg_queue:<10}")
            
            print("-" * 90)
            print(f"📈 Total days shown: {len(daily_stats)} (Full 30-day history)")
        else:
            print(f"\n  No call data found for {campaign} in the last 30 days")
        
        # Top agents for this campaign
        agent_query = """
        SELECT 
            a.user,
            COUNT(*) as calls,
            SUM(a.talk_sec) as total_talk,
            AVG(a.talk_sec) as avg_talk,
            MAX(a.event_time) as last_call
        FROM vicidial_agent_log a
        JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
        WHERE c.campaign_id = %s
          AND c.call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY a.user
        ORDER BY calls DESC
        LIMIT 10
        """
        
        top_agents = db.execute_query(agent_query, (campaign,))
        
        if top_agents:
            print(f"\n🏆 TOP AGENTS FOR {campaign}:")
            print("-" * 70)
            print(f"{'Agent':<15} {'Calls':<8} {'Talk Time':<12} {'Avg Call':<10} {'Last Call':<20}")
            print("-" * 70)
            
            for agent in top_agents:
                talk_time = sec_to_hms(agent['total_talk'] or 0)
                avg_talk = sec_to_hms(agent['avg_talk'] or 0)
                last_call = format_datetime(agent['last_call'])[5:16] if agent['last_call'] else 'Never'
                print(f"{agent['user']:<15} {agent['calls']:<8} {talk_time:<12} {avg_talk:<10} {last_call:<20}")
        else:
            print(f"\n  No agent activity found for {campaign} in the last 30 days")
        
    except Exception as e:
        print_error(f"Error getting campaign details: {str(e)}")

def compare_campaigns():
    """Compare two campaigns side by side"""
    print_header("🔄 CAMPAIGN COMPARISON", Colors.MAGENTA)
    
    campaigns = get_campaign_list()
    if not campaigns:
        print_warning("No campaigns found")
        return
    
    print("\n📋 Available Campaigns:")
    for i, camp in enumerate(campaigns[:20], 1):
        print(f"  {i}. {camp}")
    
    print("\nSelect first campaign:")
    choice1 = input("Campaign name or number: ").strip()
    
    if choice1.isdigit() and 1 <= int(choice1) <= len(campaigns[:20]):
        camp1 = campaigns[int(choice1)-1]
    elif choice1 in campaigns:
        camp1 = choice1
    else:
        print_error("Campaign not found")
        return
    
    print("\nSelect second campaign:")
    choice2 = input("Campaign name or number: ").strip()
    
    if choice2.isdigit() and 1 <= int(choice2) <= len(campaigns[:20]):
        camp2 = campaigns[int(choice2)-1]
    elif choice2 in campaigns:
        camp2 = choice2
    else:
        print_error("Campaign not found")
        return
    
    print(f"\n📊 Comparing: {camp1} vs {camp2}")
    
    # Get data for both campaigns
    query = """
    SELECT 
        COUNT(*) as total_calls,
        SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
        SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                 OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
        AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk,
        AVG(queue_seconds) as avg_queue
    FROM vicidial_closer_log
    WHERE campaign_id = %s
      AND call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    """
    
    data1 = db.execute_query(query, (camp1,))
    data2 = db.execute_query(query, (camp2,))
    
    if not data1 or not data2:
        print_error("No data available for comparison")
        return
    
    d1 = data1[0]
    d2 = data2[0]
    
    print("\n" + "=" * 80)
    print(f"{'Metric':<25} {camp1:<25} {camp2:<25}")
    print("=" * 80)
    
    # Total Calls
    print(f"{'Total Calls':<25} {d1['total_calls']:<25} {d2['total_calls']:<25}")
    
    # Answered
    ans1_pct = (d1['answered']/d1['total_calls']*100) if d1['total_calls'] > 0 else 0
    ans2_pct = (d2['answered']/d2['total_calls']*100) if d2['total_calls'] > 0 else 0
    print(f"{'Answered':<25} {d1['answered']} ({ans1_pct:.1f}%){' ':<12} {d2['answered']} ({ans2_pct:.1f}%)")
    
    # Abandoned
    abd1_pct = (d1['abandoned']/d1['total_calls']*100) if d1['total_calls'] > 0 else 0
    abd2_pct = (d2['abandoned']/d2['total_calls']*100) if d2['total_calls'] > 0 else 0
    print(f"{'Abandoned':<25} {d1['abandoned']} ({abd1_pct:.1f}%){' ':<12} {d2['abandoned']} ({abd2_pct:.1f}%)")
    
    # Avg Talk
    print(f"{'Avg Talk Time':<25} {sec_to_hms(d1['avg_talk']):<25} {sec_to_hms(d2['avg_talk']):<25}")
    
    # Avg Queue
    print(f"{'Avg Queue Time':<25} {sec_to_hms(d1['avg_queue']):<25} {sec_to_hms(d2['avg_queue']):<25}")
    
    print("=" * 80)

def hourly_campaign_stats():
    """Show hourly statistics for a campaign"""
    print_header("⏰ HOURLY CAMPAIGN STATS", Colors.CYAN)
    
    campaigns = get_campaign_list()
    if not campaigns:
        print_warning("No campaigns found")
        return
    
    print("\n📋 Available Campaigns:")
    for i, camp in enumerate(campaigns[:20], 1):
        print(f"  {i}. {camp}")
    
    choice = input("\nEnter campaign name or number: ").strip()
    
    selected_campaign = None
    if choice.isdigit() and 1 <= int(choice) <= len(campaigns[:20]):
        selected_campaign = campaigns[int(choice)-1]
    elif choice in campaigns:
        selected_campaign = choice
    else:
        print_error("Campaign not found")
        return
    
    query = """
    SELECT 
        HOUR(call_date) as hour,
        COUNT(*) as total_calls,
        SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
        AVG(queue_seconds) as avg_queue
    FROM vicidial_closer_log
    WHERE campaign_id = %s
      AND call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    GROUP BY HOUR(call_date)
    ORDER BY hour
    """
    
    results = db.execute_query(query, (selected_campaign,))
    
    if results:
        print(f"\n📊 Hourly Stats for {selected_campaign}:")
        print("-" * 60)
        print(f"{'Hour':<8} {'Calls':<8} {'Answered':<10} {'Ans%':<6} {'Avg Queue':<10}")
        print("-" * 60)
        
        for r in results:
            hour = f"{r['hour']:02d}:00"
            calls = r['total_calls']
            answered = r['answered'] or 0
            ans_pct = (answered/calls*100) if calls > 0 else 0
            avg_queue = f"{r['avg_queue']:.0f}s" if r['avg_queue'] else 'N/A'
            print(f"{hour:<8} {calls:<8} {answered:<10} {ans_pct:.1f}%{' ':<2} {avg_queue:<10}")
        
        print("-" * 60)
    else:
        print(f"No data found for {selected_campaign}")

def campaign_performance_menu():
    """Main campaign performance menu"""
    while True:
        print_header("📊 CAMPAIGN PERFORMANCE", Colors.BLUE)
        print("  1. 📈 Today's Performance")
        print("  2. 📊 Last 7 Days Performance")
        print("  3. 📉 Last 30 Days Performance")
        print("  4. 🔍 View Specific Campaign (FULL 30-DAY HISTORY)")
        print("  5. 📋 List All Campaigns")
        print("  6. 🔄 Compare Two Campaigns")
        print("  7. ⏰ Hourly Campaign Stats")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Select option: {Colors.RESET}").strip()
        
        if choice == '1':
            show_campaign_performance('today')
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            show_campaign_performance('week')
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            show_campaign_performance('30days')
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            campaigns = get_campaign_list()
            if campaigns:
                print("\n📋 Available Campaigns:")
                print(f"   (Total: {len(campaigns)} — showing first {min(20, len(campaigns))})")
                
                for i, camp in enumerate(campaigns[:20], 1):
                    print(f"  {i}. {camp}")
                
                # Professional unified search integration
                camp_choice = input("\nEnter campaign name or number (or / to search): ").strip()
                
                # Check if user wants to use unified search
                if camp_choice == "/":
                    try:
                        from utils.unified_search import unified_search_menu
                        # unified_search_menu returns the selected campaign or None
                        selected_from_search = unified_search_menu(return_result=True)
                        if selected_from_search:
                            show_campaign_details(selected_from_search)
                        else:
                            print_warning("No campaign selected")
                        input("\nPress Enter to continue...")
                        continue
                    except ImportError:
                        print_error("Unified search module not found.")
                        input("\nPress Enter to continue...")
                        continue
                    except Exception as e:
                        print_error(f"Search error: {str(e)}")
                        input("\nPress Enter to continue...")
                        continue
                
                selected_campaign = None
                
                if camp_choice.isdigit():
                    idx = int(camp_choice) - 1
                    if 0 <= idx < len(campaigns):
                        selected_campaign = campaigns[idx]
                    else:
                        print_error(f"Invalid number. Please enter 1-{len(campaigns)}")
                        input("\nPress Enter to continue...")
                        continue
                else:
                    # Try exact match first
                    matching = [c for c in campaigns if c.lower() == camp_choice.lower()]
                    if matching:
                        selected_campaign = matching[0]
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
                            input("\nPress Enter to continue...")
                            continue
                        else:
                            print_error(f"Campaign '{camp_choice}' not found")
                            input("\nPress Enter to continue...")
                            continue
                
                if selected_campaign:
                    show_campaign_details(selected_campaign)
                    input("\nPress Enter to continue...")
        
        elif choice == '5':
            campaigns = get_campaign_list()
            if campaigns:
                print(f"\n📋 All Campaigns ({len(campaigns)}):")
                # Display in 4 columns for better visibility
                col_width = 20
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
            input("\nPress Enter to continue...")
        
        elif choice == '6':
            compare_campaigns()
            input("\nPress Enter to continue...")
        
        elif choice == '7':
            hourly_campaign_stats()
            input("\nPress Enter to continue...")
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid option")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    campaign_performance_menu()