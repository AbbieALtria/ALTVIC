#!/usr/bin/env python3
# =============================================================================
# File:         agent_alerts.py
# Version:      1.0.0
# Date:         2026-02-27
# Description:  Real-time agent behavior monitoring and alerts
# Location:     D:\Altria_Ops\alerts\agent_alerts.py
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import sec_to_hms, time_ago
from config.settings import load_agent_alerts_config, save_agent_alerts_config
import os
import time

# =============================================================================
# Alert Detection Functions
# =============================================================================

def check_acw_alerts():
    """Check for agents stuck in After Call Work (PAUSE) too long"""
    config = load_agent_alerts_config()
    thresholds = config["thresholds"]
    alerts = []
    
    if not config["enabled_alerts"].get("acw_alert", True):
        return alerts
    
    try:
        query = """
        SELECT 
            l.user,
            u.full_name,
            l.status,
            l.last_state_change,
            l.campaign_id,
            TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) as minutes_in_status
        FROM vicidial_live_agents l
        LEFT JOIN vicidial_users u ON l.user = u.user
        WHERE l.status = 'PAUSE'
          AND TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) >= %s
        ORDER BY minutes_in_status DESC
        """
        
        results = db.execute_query(query, (thresholds["acw_warning_minutes"],))
        
        for agent in results:
            minutes = agent['minutes_in_status']
            severity = "critical" if minutes >= thresholds["acw_critical_minutes"] else "warning"
            
            alerts.append({
                "type": "agent_acw",
                "severity": severity,
                "message": f"Agent {agent['user']} ({agent.get('full_name', 'Unknown')}) in PAUSE/ACW for {minutes} minutes",
                "agent": agent['user'],
                "data": agent
            })
            
            log_agent_alert(alerts[-1])
        
        return alerts
    except Exception as e:
        print_error(f"Error checking ACW alerts: {e}")
        return []

def check_short_calls_alerts():
    """Check for agents with too many consecutive short calls (potential hang-ups)"""
    config = load_agent_alerts_config()
    thresholds = config["thresholds"]
    alerts = []
    
    if not config["enabled_alerts"].get("short_calls_alert", True):
        return alerts
    
    try:
        # Get agents with recent short calls
        query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as short_calls,
            GROUP_CONCAT(c.length_in_sec) as call_lengths,
            MIN(c.call_date) as first_short,
            MAX(c.call_date) as last_short
        FROM vicidial_agent_log a
        JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE c.call_date >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
          AND c.length_in_sec < %s
          AND c.length_in_sec > 0
        GROUP BY a.user
        HAVING short_calls >= %s
        ORDER BY short_calls DESC
        """
        
        results = db.execute_query(query, (thresholds["short_call_seconds"], 
                                          thresholds["short_call_consecutive"]))
        
        for agent in results:
            alerts.append({
                "type": "short_calls",
                "severity": "warning",
                "message": f"Agent {agent['user']} has {agent['short_calls']} short calls (<{thresholds['short_call_seconds']}s) in last hour",
                "agent": agent['user'],
                "data": agent
            })
            
            log_agent_alert(alerts[-1])
        
        return alerts
    except Exception as e:
        print_error(f"Error checking short calls: {e}")
        return []

def check_idle_agents_alerts():
    """Check for agents READY but not receiving calls"""
    config = load_agent_alerts_config()
    thresholds = config["thresholds"]
    alerts = []
    
    if not config["enabled_alerts"].get("idle_alert", True):
        return alerts
    
    try:
        query = """
        SELECT 
            l.user,
            u.full_name,
            l.status,
            l.last_state_change,
            l.campaign_id,
            TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) as minutes_ready,
            l.last_call_time
        FROM vicidial_live_agents l
        LEFT JOIN vicidial_users u ON l.user = u.user
        WHERE l.status = 'READY'
          AND TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) >= %s
          AND (l.last_call_time IS NULL OR l.last_call_time < DATE_SUB(NOW(), INTERVAL %s MINUTE))
        ORDER BY minutes_ready DESC
        """
        
        results = db.execute_query(query, (thresholds["idle_ready_minutes"], 
                                          thresholds["idle_ready_minutes"]))
        
        for agent in results:
            alerts.append({
                "type": "agent_idle",
                "severity": "warning",
                "message": f"Agent {agent['user']} READY but no calls for {agent['minutes_ready']} minutes",
                "agent": agent['user'],
                "data": agent
            })
            
            log_agent_alert(alerts[-1])
        
        return alerts
    except Exception as e:
        print_error(f"Error checking idle agents: {e}")
        return []

def check_pause_alerts():
    """Check for agents on break/pause too long"""
    config = load_agent_alerts_config()
    thresholds = config["thresholds"]
    alerts = []
    
    if not config["enabled_alerts"].get("pause_alert", True):
        return alerts
    
    try:
        query = """
        SELECT 
            l.user,
            u.full_name,
            l.status,
            l.last_state_change,
            l.campaign_id,
            TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) as minutes_paused
        FROM vicidial_live_agents l
        LEFT JOIN vicidial_users u ON l.user = u.user
        WHERE l.status = 'PAUSE'
          AND TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) >= %s
        ORDER BY minutes_paused DESC
        """
        
        results = db.execute_query(query, (thresholds["pause_warning_minutes"],))
        
        for agent in results:
            minutes = agent['minutes_paused']
            severity = "critical" if minutes >= thresholds["pause_critical_minutes"] else "warning"
            
            alerts.append({
                "type": "agent_pause",
                "severity": severity,
                "message": f"Agent {agent['user']} on PAUSE for {minutes} minutes",
                "agent": agent['user'],
                "data": agent
            })
            
            log_agent_alert(alerts[-1])
        
        return alerts
    except Exception as e:
        print_error(f"Error checking pause alerts: {e}")
        return []

def check_wrap_up_alerts():
    """Check for agents in wrap-up/after-call work too long"""
    config = load_agent_alerts_config()
    thresholds = config["thresholds"]
    alerts = []
    
    if not config["enabled_alerts"].get("wrap_up_alert", True):
        return alerts
    
    try:
        # Common wrap-up statuses: WRAPUP, AFTERCALL, ACW, etc.
        query = """
        SELECT 
            l.user,
            u.full_name,
            l.status,
            l.last_state_change,
            TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) as minutes_in_wrap
        FROM vicidial_live_agents l
        LEFT JOIN vicidial_users u ON l.user = u.user
        WHERE l.status IN ('WRAPUP', 'AFTERCALL', 'ACW')
          AND TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) >= %s
        ORDER BY minutes_in_wrap DESC
        """
        
        results = db.execute_query(query, (thresholds["wrap_up_warning_minutes"],))
        
        for agent in results:
            minutes = agent['minutes_in_wrap']
            severity = "critical" if minutes >= thresholds["wrap_up_critical_minutes"] else "warning"
            
            alerts.append({
                "type": "wrap_up",
                "severity": severity,
                "message": f"Agent {agent['user']} in wrap-up for {minutes} minutes",
                "agent": agent['user'],
                "data": agent
            })
            
            log_agent_alert(alerts[-1])
        
        return alerts
    except Exception as e:
        # Silently fail if wrap-up status isn't available
        return []

def check_transfer_alerts():
    """Check for agents with excessive transfers (if transfer tracking is available)"""
    config = load_agent_alerts_config()
    thresholds = config["thresholds"]
    alerts = []
    
    if not config["enabled_alerts"].get("transfer_alert", True):
        return alerts
    
    try:
        # This query assumes transfers are logged in agent_log with a specific status
        # You may need to adjust based on your actual schema
        query = """
        SELECT 
            user,
            COUNT(*) as transfer_count
        FROM vicidial_agent_log
        WHERE event_time >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
          AND status = 'TRANSFER'
        GROUP BY user
        HAVING transfer_count >= %s
        ORDER BY transfer_count DESC
        """
        
        results = db.execute_query(query, (thresholds["transfers_per_hour"],))
        
        for agent in results:
            alerts.append({
                "type": "excessive_transfers",
                "severity": "warning",
                "message": f"Agent {agent['user']} has {agent['transfer_count']} transfers in last hour",
                "agent": agent['user'],
                "data": agent
            })
            
            log_agent_alert(alerts[-1])
        
        return alerts
    except Exception as e:
        # Silently fail if transfer tracking isn't available
        return []

def log_agent_alert(alert):
    """Log alert to history"""
    config = load_agent_alerts_config()
    
    if "alert_history" not in config:
        config["alert_history"] = []
    
    # Avoid duplicate alerts in quick succession
    now = datetime.now()
    recent = [a for a in config["alert_history"][-20:] 
              if a.get("message") == alert["message"] 
              and (now - datetime.fromisoformat(a["timestamp"])).total_seconds() < 300]
    
    if not recent:
        alert_copy = alert.copy()
        alert_copy["timestamp"] = now.isoformat()
        alert_copy.setdefault("acknowledged", False)
        config["alert_history"].append(alert_copy)
        
        # Keep last 500 alerts
        if len(config["alert_history"]) > 500:
            config["alert_history"] = config["alert_history"][-500:]
        
        save_agent_alerts_config(config)

def check_all_agent_alerts():
    """Run all agent alert checks"""
    all_alerts = []
    all_alerts.extend(check_acw_alerts())
    all_alerts.extend(check_short_calls_alerts())
    all_alerts.extend(check_idle_agents_alerts())
    all_alerts.extend(check_pause_alerts())
    all_alerts.extend(check_wrap_up_alerts())
    all_alerts.extend(check_transfer_alerts())
    
    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_alerts.sort(key=lambda x: severity_order.get(x['severity'], 3))
    
    return all_alerts

# =============================================================================
# Display Functions
# =============================================================================

def show_active_alerts():
    """Display current agent alerts"""
    print_header("🚨 ACTIVE AGENT ALERTS", Colors.RED)
    
    alerts = check_all_agent_alerts()
    
    if not alerts:
        print_success("\n✅ No active agent alerts - All agents behaving normally!")
        return
    
    print(f"\nTotal Active Alerts: {len(alerts)}")
    print("-" * 80)
    
    for i, alert in enumerate(alerts, 1):
        if alert['severity'] == 'critical':
            color = Colors.RED
            badge = "🔴 CRITICAL"
        elif alert['severity'] == 'warning':
            color = Colors.YELLOW
            badge = "🟡 WARNING"
        else:
            color = Colors.BLUE
            badge = "🔵 INFO"
        
        print_color(f"{i:2}. [{badge}] {alert['message']}", color)
    
    print("-" * 80)

def show_agent_dashboard():
    """Interactive agent behavior dashboard"""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("👥 AGENT BEHAVIOR DASHBOARD", Colors.CYAN)
        print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 90)
        
        # Get all alerts
        alerts = check_all_agent_alerts()
        
        # Summary statistics
        critical = len([a for a in alerts if a['severity'] == 'critical'])
        warnings = len([a for a in alerts if a['severity'] == 'warning'])
        
        print(f"\n📊 ALERT SUMMARY:")
        print(f"  🔴 Critical: {critical}")
        print(f"  🟡 Warnings: {warnings}")
        print(f"  Total:       {len(alerts)}")
        
        # Group alerts by agent
        if alerts:
            print("\n📋 ACTIVE ALERTS BY AGENT:")
            print("-" * 90)
            
            agent_alerts = {}
            for alert in alerts:
                agent = alert['agent']
                if agent not in agent_alerts:
                    agent_alerts[agent] = []
                agent_alerts[agent].append(alert)
            
            for agent, agent_alert_list in agent_alerts.items():
                print(f"\n👤 Agent: {agent}")
                for a in agent_alert_list:
                    sym = "🔴" if a['severity'] == 'critical' else "🟡"
                    print(f"  {sym} {a['message']}")
        
        # Agent status summary
        print("\n📈 AGENT STATUS SUMMARY:")
        print("-" * 90)
        
        try:
            query = """
            SELECT 
                status,
                COUNT(*) as count,
                AVG(TIMESTAMPDIFF(MINUTE, last_state_change, NOW())) as avg_duration
            FROM vicidial_live_agents
            WHERE status IN ('READY', 'INCALL', 'PAUSE')
            GROUP BY status
            """
            
            statuses = db.execute_query(query)
            for s in statuses:
                status = s['status']
                count = s['count']
                avg_dur = s['avg_duration'] or 0
                
                if status == 'INCALL':
                    color = Colors.GREEN
                elif status == 'READY':
                    color = Colors.BLUE
                elif status == 'PAUSE':
                    color = Colors.YELLOW
                else:
                    color = Colors.RESET
                
                print_color(f"  {status:<10}: {count:3} agents (avg {avg_dur:.0f} min)", color)
        except Exception as e:
            print_warning(f"Could not get status summary: {e}")
        
        print("\n" + "=" * 90)
        print("Controls: [R]efresh  [H]istory  [Q]uit")
        choice = input("\nChoice: ").strip().upper()
        
        if choice == 'Q':
            break
        elif choice == 'R':
            continue
        elif choice == 'H':
            show_alert_history()

def show_alert_history():
    """Show historical agent alerts"""
    config = load_agent_alerts_config()
    history = config.get("alert_history", [])
    
    print_header("📜 AGENT ALERT HISTORY", Colors.BLUE)
    
    if not history:
        print_warning("No agent alert history found")
        input("\nPress Enter to continue...")
        return
    
    # Group by date
    from collections import defaultdict
    by_date = defaultdict(list)
    
    for alert in history[-100:]:  # Last 100 alerts
        dt = datetime.fromisoformat(alert['timestamp'])
        date_str = dt.strftime('%Y-%m-%d')
        by_date[date_str].append(alert)
    
    for date_str, alerts in sorted(by_date.items(), reverse=True):
        print_color(f"\n📅 {date_str}", Colors.CYAN)
        print("-" * 60)
        
        for alert in alerts:
            time_str = datetime.fromisoformat(alert['timestamp']).strftime('%H:%M:%S')
            sym = "🔴" if alert['severity'] == 'critical' else "🟡"
            ack = "✓" if alert.get('acknowledged') else "○"
            print(f"  {ack} {sym} [{time_str}] {alert['message']}")
    
    print("\n" + "=" * 60)
    print("Options: [A]cknowledge all  [C]lear  [Enter] back")
    action = input("Choice: ").strip().upper()
    
    if action == 'A':
        for alert in config["alert_history"]:
            alert['acknowledged'] = True
        save_agent_alerts_config(config)
        print_success("All alerts acknowledged")
    elif action == 'C':
        if input("Clear all history? (y/N): ").strip().lower() == 'y':
            config["alert_history"] = []
            save_agent_alerts_config(config)
            print_success("History cleared")
    
    input("\nPress Enter to continue...")

def show_agent_stats():
    """Show agent performance statistics"""
    print_header("📊 AGENT PERFORMANCE STATS", Colors.MAGENTA)
    
    try:
        query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as total_calls,
            SUM(a.talk_sec) as total_talk,
            AVG(a.talk_sec) as avg_talk,
            MAX(a.event_time) as last_call
        FROM vicidial_agent_log a
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE a.event_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        GROUP BY a.user
        HAVING total_calls > 0
        ORDER BY total_calls DESC
        LIMIT 20
        """
        
        stats = db.execute_query(query)
        
        if stats:
            print(f"\n{'Agent':<15} {'Name':<20} {'Calls':<8} {'Talk Time':<12} {'Avg Call':<10} {'Last Call':<20}")
            print("-" * 90)
            
            for s in stats:
                talk_time = sec_to_hms(s['total_talk'] or 0)
                avg_talk = sec_to_hms(s['avg_talk'] or 0)
                last_call = time_ago(s['last_call']) if s['last_call'] else 'Never'
                name = s['full_name'] or 'Unknown'
                name = name[:20]
                
                # Color code by volume
                if s['total_calls'] > 100:
                    color = Colors.GREEN
                elif s['total_calls'] > 50:
                    color = Colors.YELLOW
                else:
                    color = Colors.RESET
                
                print_color(f"{s['user']:<15} {name:<20} {s['total_calls']:<8} {talk_time:<12} {avg_talk:<10} {last_call:<20}", color)
        else:
            print_warning("No agent statistics available")
            
    except Exception as e:
        print_error(f"Error getting agent stats: {e}")
    
    input("\nPress Enter to continue...")

# =============================================================================
# Main Menu
# =============================================================================

def agent_alerts_menu():
    """Main agent alerts menu"""
    while True:
        print_header("👤 AGENT BEHAVIOR MONITORING", Colors.MAGENTA)
        print("  1. 🚨 Active Agent Alerts")
        print("  2. 📊 Agent Behavior Dashboard")
        print("  3. 📈 Agent Performance Stats")
        print("  4. 📜 Alert History")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_active_alerts()
            input("\nPress Enter to continue...")
        elif choice == '2':
            show_agent_dashboard()
        elif choice == '3':
            show_agent_stats()
        elif choice == '4':
            show_alert_history()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    agent_alerts_menu()