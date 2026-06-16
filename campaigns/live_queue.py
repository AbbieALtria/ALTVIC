# campaigns/live_queue.py - Live queue monitor

from core.database import db
from datetime import datetime
from utils.colors import Colors, print_color, print_header, print_error

def show_live_queue():
    """Show live queue information"""
    print_header("LIVE QUEUE STATUS", Colors.CYAN)
    
    try:
        # Check for calls in queue
        queue_query = """
        SELECT 
            campaign_id,
            COUNT(*) as waiting
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
          AND length_in_sec = 0
          AND uniqueid NOT IN (
              SELECT uniqueid 
              FROM vicidial_agent_log 
              WHERE event_time >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
          )
        GROUP BY campaign_id
        ORDER BY waiting DESC
        """
        
        queue_data = db.execute_query(queue_query)
        
        if queue_data:
            has_waiting = False
            for q in queue_data:
                if q['waiting'] > 0:
                    if not has_waiting:
                        print("\nCALLS WAITING:")
                        print("-" * 30)
                        print(f"{'Campaign':<15} {'Waiting':<10}")
                        print("-" * 30)
                        has_waiting = True
                    print(f"{q['campaign_id']:<15} {q['waiting']:<10}")
            
            if not has_waiting:
                print("\nNo calls waiting")
        else:
            print("\nNo calls waiting")
        
        # Recent calls
        recent_query = """
        SELECT 
            campaign_id,
            COUNT(*) as calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 15 MINUTE)
        GROUP BY campaign_id
        HAVING calls > 0
        ORDER BY calls DESC
        LIMIT 10
        """
        
        recent = db.execute_query(recent_query)
        
        if recent:
            print("\nRECENT CALLS (15 min):")
            print("-" * 50)
            print(f"{'Campaign':<15} {'Calls':<8} {'Answered':<8} {'Rate':<8}")
            print("-" * 50)
            
            for r in recent:
                rate = (r['answered']/r['calls']*100) if r['calls'] > 0 else 0
                print(f"{r['campaign_id']:<15} {r['calls']:<8} {r['answered']:<8} {rate:.0f}%")
        
    except Exception as e:
        print_error(f"Error: {e}")

def queue_menu():
    """Queue monitor menu"""
    while True:
        print_header("QUEUE MONITOR", Colors.CYAN)
        print("  1. Refresh")
        print("  2. Auto-Refresh (5s)")
        print("  0. Back")
        print("-" * 30)
        
        choice = input("\nChoice: ").strip()
        
        if choice == '1':
            show_live_queue()
            input("\nPress Enter...")
        elif choice == '2':
            print("\nAuto-refresh (Ctrl+C to stop)")
            try:
                while True:
                    import os
                    os.system('cls')
                    show_live_queue()
                    print(f"\n{datetime.now().strftime('%H:%M:%S')}")
                    import time
                    time.sleep(5)
            except KeyboardInterrupt:
                print("\nStopped")
        elif choice == '0':
            break
        else:
            print_error("Invalid")
            input("\nPress Enter...")

if __name__ == "__main__":
    queue_menu()