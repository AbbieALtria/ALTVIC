#!/usr/bin/env python3
# =============================================================================
# File:         agent_monitor.py
# Version:      2.0.0
# Date:         2026-03-09
# Description:  Real-time agent status monitor with Manila timezone (UTC+8)
# Location:     D:/Altria_Ops/monitoring/agent_monitor.py
# =============================================================================

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_color, print_header, print_error, print_success, print_warning
from utils.formatter import sec_to_hms

class AgentMonitor:
    """Production-ready agent monitoring system with Manila timezone"""
    
    def __init__(self):
        self.refresh_interval = 10  # seconds
        # Server is 12 hours behind Manila (UTC+8)
        self.SERVER_TO_MANILA_OFFSET = 12  # hours
        
    def convert_to_manila_time(self, server_time):
        """Convert server time to Manila time (UTC+8)"""
        if server_time is None:
            return None
        if isinstance(server_time, str):
            try:
                server_time = datetime.strptime(server_time, '%Y-%m-%d %H:%M:%S')
            except:
                return None
        return server_time + timedelta(hours=self.SERVER_TO_MANILA_OFFSET)
    
    def get_current_manila_time(self):
        """Get current time in Manila (UTC+8)"""
        utc_now = datetime.utcnow()
        return utc_now + timedelta(hours=8)  # UTC to Manila
    
    def format_manila_time(self, timestamp, format_str='%H:%M:%S'):
        """Format timestamp in Manila time"""
        if timestamp is None:
            return 'Never'
        manila_time = self.convert_to_manila_time(timestamp)
        if manila_time:
            return manila_time.strftime(format_str)
        return 'Never'
    
    def get_live_agents(self):
        """Get all currently logged-in agents - USING YOUR ACTUAL COLUMNS"""
        try:
            query = """
            SELECT 
                l.user,
                l.status,
                l.campaign_id,
                l.pause_code,
                l.wait_sec,
                l.call_sec,
                l.last_call_time,
                l.last_state_change,
                u.full_name,
                TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) as minutes_in_status
            FROM vicidial_live_agents l
            LEFT JOIN vicidial_users u ON l.user = u.user
            WHERE l.status != 'LOGGEDOUT'
            ORDER BY 
                CASE l.status
                    WHEN 'INCALL' THEN 1
                    WHEN 'RING' THEN 2
                    WHEN 'QUEUE' THEN 3
                    WHEN 'READY' THEN 4
                    WHEN 'CLOSER' THEN 5
                    WHEN 'PAUSE' THEN 6
                    WHEN 'WRAPUP' THEN 7
                    ELSE 8
                END,
                l.last_state_change DESC
            """
            result = db.execute_query(query)
            return result if result else []
            
        except Exception as e:
            print_error(f"Database error: {e}")
            return []

    def get_status_color(self, status, minutes_in_status=None):
        """Get color code for agent status"""
        if status == 'INCALL':
            return Colors.GREEN
        elif status == 'RING':
            return Colors.GREEN
        elif status == 'READY':
            return Colors.BLUE
        elif status == 'PAUSE':
            if minutes_in_status and minutes_in_status > 15:
                return Colors.RED  # Long pause warning
            return Colors.YELLOW
        elif status == 'WRAPUP':
            return Colors.CYAN
        elif status in ('QUEUE', 'CLOSER'):
            return Colors.CYAN
        else:
            return Colors.RESET

    def display_status(self):
        """Display current agent status with Manila times"""
        # Get current Manila time for header
        manila_now = self.get_current_manila_time()
        
        print_header("🕐 REAL-TIME AGENT MONITOR", Colors.CYAN)
        print(f"  Server time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Manila time: {manila_now.strftime('%Y-%m-%d %H:%M:%S')} (UTC+8)")
        
        agents = self.get_live_agents()
        
        if not agents:
            print_warning("\n  No agents currently logged in")
            print("\n" + "=" * 100)
            return

        # Summary statistics
        total = len(agents)
        status_summary = {}
        for a in agents:
            status_summary[a['status']] = status_summary.get(a['status'], 0) + 1

        print(f"\n📊 SUMMARY: ", end='')
        for status, count in status_summary.items():
            color = self.get_status_color(status)
            print_color(f"{count} {status}  ", color, end='')
        print()

        # Header
        print("\n" + "=" * 150)
        print(f"{'Agent':<12} {'Full Name':<20} {'Status':<10} {'Campaign':<12} "
              f"{'Pause Code':<10} {'Wait':<8} {'Call':<8} "
              f"{'Last Call (Manila)':<20} {'In Status':<10}")
        print("=" * 150)

        # Agent rows
        for agent in agents:
            status = agent['status']
            color = self.get_status_color(status, agent.get('minutes_in_status'))
            name = (agent['full_name'] or 'Unknown')[:20]
            
            # Format timings in Manila time
            last_call_manila = self.format_manila_time(agent['last_call_time'], '%Y-%m-%d %H:%M:%S')
            in_status = f"{agent.get('minutes_in_status', 0):3d} min"
            
            # Format wait and call seconds
            wait_sec = sec_to_hms(agent.get('wait_sec', 0))
            call_sec = sec_to_hms(agent.get('call_sec', 0))
            
            # Handle long pauses warning
            if status == 'PAUSE' and agent.get('minutes_in_status', 0) > 15:
                in_status = f"{Colors.RED}{in_status}{Colors.RESET}"

            print_color(
                f"{agent['user']:<12} {name:<20} {status:<10} "
                f"{agent['campaign_id'] or 'N/A':<12} {agent.get('pause_code', '—'):<10} "
                f"{wait_sec:<8} {call_sec:<8} {last_call_manila:<20} {in_status:<10}",
                color
            )

        print("=" * 150)
        
        # Legend for long pauses
        if any(a['status'] == 'PAUSE' and a.get('minutes_in_status', 0) > 15 for a in agents):
            print(f"\n{Colors.RED}⚠️  Red time = Long pause (>15 minutes){Colors.RESET}")
        
        # Show timezone info
        print(f"\n🕒 Note: All times shown in Manila time (UTC+8)")

    def quick_view(self):
        """One-time status view"""
        self.display_status()
        input("\nPress Enter to continue...")

    def continuous_monitor(self):
        """Continuous monitoring with auto-refresh"""
        import time
        import os
        
        print_success("\nStarting continuous monitoring (Ctrl+C to stop)")
        time.sleep(1)
        
        try:
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')
                self.display_status()
                print(f"\n{Colors.CYAN}Auto-refreshing every {self.refresh_interval} seconds... "
                      f"Press Ctrl+C to exit{Colors.RESET}")
                time.sleep(self.refresh_interval)
        except KeyboardInterrupt:
            print_success("\n\nMonitoring stopped.")

def main():
    """Main entry point"""
    monitor = AgentMonitor()
    
    while True:
        print_header("🕐 AGENT MONITOR", Colors.MAGENTA)
        print("  1. Quick Status View")
        print("  2. Continuous Monitor (auto-refresh)")
        print("  0. Exit")
        print("-" * 60)
        print("   All times shown in Manila (UTC+8)")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Select option: {Colors.RESET}").strip()
        
        if choice == '1':
            monitor.quick_view()
        elif choice == '2':
            monitor.continuous_monitor()
        elif choice == '0':
            print_success("Exiting...")
            break
        else:
            print_error("Invalid option")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main()