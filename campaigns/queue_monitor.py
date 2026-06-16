# campaigns/queue_monitor.py - Live queue monitoring
# COMPLETELY REWRITTEN - No references to vicidial_live_inbound

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms, time_ago

def get_live_queue_stats():
    """Get live queue statistics for all campaigns"""
    print_header("⏱️ LIVE QUEUE MONITOR", Colors.CYAN)
    
    try:
        # Get recent calls that might be in queue
        print("\n🔍 Checking for calls in queue...")
        
        # Simple query to get recent unanswered calls
        queue_query = """
        SELECT 
            campaign_id,
            COUNT(*) as waiting_count
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
          AND length_in_sec = 0
          AND uniqueid NOT IN (
              SELECT uniqueid 
              FROM vicidial_agent_log 
              WHERE event_time >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
          )
        GROUP BY campaign_id
        ORDER BY waiting_count DESC
        """
        
        queue_data = db.execute_query(queue_query)
        
        if queue_data:
            print(f"\n📊 CALLS WAITING:")
            print("-" * 50)
            print(f"{'Campaign':<15} {'Waiting':<10}")
            print("-" * 50)
            
            for q in queue_data:
                print(f"{q['campaign_id']:<15} {q['waiting_count']:<10}")
        else:
            print("\n✅ No calls currently waiting in queue")
        
        # Show recent call activity
        print(f"\n📈 RECENT CALL ACTIVITY (Last 15 minutes):")
        print("-" * 80)
        
        activity_query = """
        SELECT 
            campaign_id,
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 15 MINUTE)
        GROUP BY campaign_id
        HAVING total_calls > 0
        ORDER BY total_calls DESC
        LIMIT 15
        """
        
        activity = db.execute_query(activity_query)
        
        if activity:
            print(f"{'Campaign':<15} {'Calls':<8} {'Answered':<10} {'Abandoned':<10} {'Ans%':<8}")
            print("-" * 60)
            
            for a in activity:
                total = a['total_calls']
                answered = a['answered'] or 0
                abandoned = a['abandoned'] or 0
                ans_pct = (answered/total*100) if total > 0 else 0
                
                # Color code by answer rate
                if ans_pct >= 80:
                    color = Colors.GREEN
                elif ans_pct >= 60:
                    color = Colors.YELLOW
                else:
                    color = Colors.RED
                
                print_color(f"{a['campaign_id']:<15} {total:<8} {answered:<10} {abandoned:<10} {ans_pct:.1f}%{' ':<3}", color)
        else:
            print("  No activity in last 15 minutes")
        
        # Show agent status
        print(f"\n👥 AGENT STATUS:")
        print("-" * 60)
        
        agent_query = """
        SELECT 
            status,
            COUNT(*) as count
        FROM vicidial_live_agents
        WHERE status IN ('READY', 'INCALL', 'PAUSE', 'QUEUE', 'CLOSER')
        GROUP BY status
        ORDER BY FIELD(status, 'INCALL', 'READY', 'QUEUE', 'CLOSER', 'PAUSE')
        """
        
        agent_status = db.execute_query(agent_query)
        
        if agent_status:
            for s in agent_status:
                status = s['status']
                count = s['count']
                
                if status == 'INCALL':
                    color = Colors.GREEN
                elif status == 'READY':
                    color = Colors.BLUE
                elif status == 'PAUSE':
                    color = Colors.YELLOW
                elif status == 'QUEUE':
                    color = Colors.CYAN
                else:
                    color = Colors.RESET
                
                print_color(f"  • {status}: {count} agents", color)
            
            total_agents = sum(s['count'] for s in agent_status)
            print(f"\n  📊 Total online: {total_agents} agents")
        else:
            print("  No agents currently online")
        
        return queue_data
        
    except Exception as e:
        print_error(f"Error getting queue stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_campaign_queue_details(campaign):
    """Get detailed queue info for a specific campaign"""
    print_header(f"⏱️ QUEUE DETAILS: {campaign}", Colors.CYAN)
    
    try:
        # Current queue for this campaign
        current_query = """
        SELECT 
            COUNT(*) as waiting,
            AVG(queue_seconds) as avg_wait,
            MAX(queue_seconds) as max_wait
        FROM vicidial_closer_log
        WHERE campaign_id = %s
          AND call_date >= DATE_SUB(NOW(), INTERVAL 15 MINUTE)
          AND length_in_sec = 0
          AND uniqueid NOT IN (
              SELECT uniqueid 
              FROM vicidial_agent_log 
              WHERE event_time >= DATE_SUB(NOW(), INTERVAL 15 MINUTE)
          )
        """
        
        current = db.execute_query(current_query, (campaign,))
        
        if current and current[0]['waiting'] > 0:
            data = current[0]
            print(f"\n📊 CURRENT QUEUE FOR {campaign}:")
            print(f"  • Calls waiting: {data['waiting']}")
            if data['avg_wait']:
                print(f"  • Average wait: {float(data['avg_wait']):.0f} seconds")
            if data['max_wait']:
                print(f"  • Maximum wait: {data['max_wait']} seconds")
        else:
            print(f"\n✅ No calls currently in queue for {campaign}")
        
        # Recent calls for this campaign
        recent_query = """
        SELECT 
            call_date,
            length_in_sec,
            queue_seconds,
            term_reason,
            phone_number
        FROM vicidial_closer_log
        WHERE campaign_id = %s
          AND call_date >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
        ORDER BY call_date DESC
        LIMIT 20
        """
        
        recent = db.execute_query(recent_query, (campaign,))
        
        if recent:
            print(f"\n📞 RECENT CALLS (Last Hour):")
            print("-" * 80)
            print(f"{'Time':<20} {'Duration':<10} {'Queue':<8} {'Status':<15}")
            print("-" * 80)
            
            for call in recent:
                time_str = call['call_date'].strftime('%H:%M:%S') if hasattr(call['call_date'], 'strftime') else str(call['call_date'])[11:19]
                duration = sec_to_hms(call['length_in_sec'] or 0)
                queue = f"{call['queue_seconds']}s" if call['queue_seconds'] else '0s'
                status = call['term_reason'] or 'ACTIVE'
                
                if status == 'ABANDON' or status == 'QUEUETIMEOUT':
                    color = Colors.RED
                elif call['length_in_sec'] >= 5:
                    color = Colors.GREEN
                else:
                    color = Colors.YELLOW
                
                print_color(f"{time_str:<20} {duration:<10} {queue:<8} {status:<15}", color)
        
    except Exception as e:
        print_error(f"Error getting campaign details: {str(e)}")

def queue_monitor_menu():
    """Main queue monitor menu"""
    while True:
        print_header("⏱️ QUEUE MONITOR", Colors.CYAN)
        print("  1. 👁️ Live Queue Overview")
        print("  2. 🔍 View Campaign Queue Details")
        print("  3. 🔄 Auto-Refresh (5 sec)")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Select option: {Colors.RESET}").strip()
        
        if choice == '1':
            get_live_queue_stats()
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            campaign = input("Enter campaign name: ").strip()
            if campaign:
                get_campaign_queue_details(campaign)
                input("\nPress Enter to continue...")
        
        elif choice == '3':
            print("\n🔄 Auto-refresh mode (Press Ctrl+C to stop)")
            try:
                while True:
                    print("\033[2J\033[H")  # Clear screen
                    get_live_queue_stats()
                    print(f"\n🔄 Refreshing... ({datetime.now().strftime('%H:%M:%S')})")
                    import time
                    time.sleep(5)
            except KeyboardInterrupt:
                print("\n\n✅ Auto-refresh stopped")
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid option")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    queue_monitor_menu()