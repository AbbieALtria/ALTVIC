#!/usr/bin/env python3
# =============================================================================
# File:         monitoring.py
# Version:      1.6.0
# Date:         2026-03-03
# Description:  Alerts & Monitoring system with clear alert explanations
# Update:       Improved alert messages with plain English explanations
# Author:       Altria Ops Team
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms, time_ago
import json
from pathlib import Path
import os
import time

# =============================================================================
# Paths & Defaults
# =============================================================================

ALERTS_CONFIG_FILE = Path(__file__).parent.parent / "config" / "alerts_config.json"

DEFAULT_THRESHOLDS = {
    "agent_pause_time": 15,       # minutes
    "queue_abandon_rate": 15,     # %
    "service_level": 80,          # % in <30s
    "call_volume_spike": 50,      # % increase
    "agent_idle_time": 30,        # minutes
    "campaign_health": 60,        # min answer rate %
}

DEFAULT_NOTIFICATION = {
    "email_enabled": False,
    "email_recipients": [],
    "slack_enabled": False,
    "slack_webhook": "",
    "dashboard_alerts": True
}

# =============================================================================
# Helpers
# =============================================================================

def table_exists(table_name: str) -> bool:
    try:
        return bool(db.execute_query(f"SHOW TABLES LIKE '{table_name}'"))
    except:
        return False

def column_exists(table_name: str, column_name: str) -> bool:
    try:
        return bool(db.execute_query(f"SHOW COLUMNS FROM `{table_name}` LIKE '{column_name}'"))
    except:
        return False

def log_alert_to_history(alert):
    config = load_alerts_config()
    if "alert_history" not in config:
        config["alert_history"] = []

    now = datetime.now()
    # Avoid near-duplicate logs
    recent = [a for a in config["alert_history"][-30:] if a.get("message") == alert["message"]]
    if recent and (now - datetime.fromisoformat(recent[-1]["timestamp"])) < timedelta(minutes=20):
        return

    alert_copy = alert.copy()
    alert_copy["timestamp"] = now.isoformat()
    alert_copy.setdefault("acknowledged", False)
    config["alert_history"].append(alert_copy)

    # Limit history size
    if len(config["alert_history"]) > 500:
        config["alert_history"] = config["alert_history"][-500:]

    save_alerts_config(config)

# =============================================================================
# Config Load / Save
# =============================================================================

def load_alerts_config():
    if ALERTS_CONFIG_FILE.exists():
        try:
            with open(ALERTS_CONFIG_FILE, 'r') as f:
                data = json.load(f)
                
                # Check if this is the agent alerts config (has different threshold keys)
                # If it has agent-specific thresholds, we need to create a proper alerts config
                if any(k in data.get("thresholds", {}) for k in ["acw_warning_minutes", "short_call_seconds"]):
                    # This is the agent alerts config - create a new one for system alerts
                    print_warning("Found agent alerts config - creating system alerts config")
                    data = {
                        "thresholds": DEFAULT_THRESHOLDS.copy(),
                        "notification": DEFAULT_NOTIFICATION.copy(),
                        "alert_history": []
                    }
                    save_alerts_config(data)
                    return data
                
                # Ensure thresholds exist with defaults
                if "thresholds" not in data:
                    data["thresholds"] = DEFAULT_THRESHOLDS.copy()
                else:
                    # Add any missing thresholds
                    for key, value in DEFAULT_THRESHOLDS.items():
                        if key not in data["thresholds"]:
                            data["thresholds"][key] = value
                
                # Ensure notification has all expected keys
                if "notification" not in data:
                    data["notification"] = DEFAULT_NOTIFICATION.copy()
                else:
                    for key, value in DEFAULT_NOTIFICATION.items():
                        if key not in data["notification"]:
                            data["notification"][key] = value
                
                data.setdefault("alert_history", [])
                return data
        except Exception as e:
            print_warning(f"Config load issue: {e} — using defaults")
    
    default = {
        "thresholds": DEFAULT_THRESHOLDS.copy(),
        "notification": DEFAULT_NOTIFICATION.copy(),
        "alert_history": []
    }
    save_alerts_config(default)
    return default

def save_alerts_config(config):
    try:
        ALERTS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERTS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print_error(f"Cannot save config: {e}")
        return False

# =============================================================================
# Alert Detection
# =============================================================================

def check_agent_pause_alerts(threshold_minutes=None):
    """Check for agents paused too long"""
    if threshold_minutes is None:
        config = load_alerts_config()
        threshold_minutes = config["thresholds"].get("agent_pause_time", 15)
    
    try:
        query = """
        SELECT 
            l.user,
            u.full_name,
            l.status,
            l.last_state_change,
            TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) as minutes_paused
        FROM vicidial_live_agents l
        LEFT JOIN vicidial_users u ON l.user = u.user
        WHERE l.status = 'PAUSE'
          AND TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) > %s
        ORDER BY minutes_paused DESC
        """
        
        results = db.execute_query(query, (threshold_minutes,))
        
        alerts = []
        for agent in results:
            minutes = agent['minutes_paused']
            severity = "warning" if minutes < 30 else "critical"
            
            # Create alert with clear explanation
            alerts.append({
                "type": "agent_pause",
                "severity": severity,
                "message": f"Agent {agent['user']} ({agent.get('full_name', 'Unknown')}) paused for {minutes} minutes",
                "explanation": f"This agent has been on break/pause for {minutes} minutes. "
                               f"{'This is getting long - consider checking on them.' if minutes < 30 else 'URGENT: Agent has been paused for over 30 minutes!'}",
                "data": agent
            })
        
        return alerts
    except Exception as e:
        print_error(f"Error checking agent pause alerts: {e}")
        return []

def check_queue_alerts():
    """Check for queue performance issues"""
    alerts = []
    tables = ["vicidial_auto_calls", "vicidial_live_calls", "vicidial_live_inbound", "vicidial_live_inbound_calls"]

    for table in tables:
        if not table_exists(table):
            continue
        try:
            base = f"""
                SELECT campaign_id, COUNT(*) AS waiting
                FROM `{table}`
                WHERE status IN ('LIVE','QUEUE','INCALL') OR call_type IN ('IN','QUEUE')
                GROUP BY campaign_id HAVING waiting > 0
            """
            q = base
            if column_exists(table, "queue_seconds"):
                q = base.replace(
                    "COUNT(*) AS waiting",
                    "COUNT(*) AS waiting, AVG(IFNULL(queue_seconds,0)) AS avg_wait, MAX(IFNULL(queue_seconds,0)) AS max_wait"
                )
            rows = db.execute_query(q) or []
            if rows:
                for r in rows:
                    msg = f"Campaign {r['campaign_id']}: {r['waiting']} calls waiting"
                    if "avg_wait" in r:
                        msg += f" (avg {float(r['avg_wait']):.0f}s)"
                    severity = "warning" if r['waiting'] > 8 else "info"
                    
                    # Create alert with clear explanation
                    explanation = f"There {'are' if r['waiting'] > 1 else 'is'} currently {r['waiting']} caller{'s' if r['waiting'] > 1 else ''} waiting"
                    if "avg_wait" in r and r['avg_wait']:
                        explanation += f". Average wait time is {float(r['avg_wait']):.0f} seconds."
                    
                    alerts.append({
                        "type": "queue_waiting", 
                        "severity": severity, 
                        "message": msg,
                        "explanation": explanation,
                        "data": r
                    })
                return alerts  # usable table found
        except:
            continue

    alerts.append({
        "type": "live_queue_unavailable",
        "severity": "info",
        "message": "Live queue data not available in this VICIdial version",
        "explanation": "Your ViciDial system doesn't have live queue tables. Showing historical alerts only.",
        "data": {}
    })
    return alerts

def check_historical_alerts():
    """Check historical performance alerts"""
    config = load_alerts_config()
    thresholds = config["thresholds"]
    alerts = []
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()

    try:
        # Abandon rate
        q = """
            SELECT campaign_id, 
                   COUNT(*) AS total,
                   SUM(CASE WHEN term_reason IN ('ABANDON','QUEUETIMEOUT','NOAGENT')
                            OR (length_in_sec=0 AND queue_seconds>0) THEN 1 ELSE 0 END) AS aband
            FROM vicidial_closer_log
            WHERE DATE(call_date) = %s
            GROUP BY campaign_id
        """
        for r in db.execute_query(q, (yesterday,)) or []:
            total = float(r["total"])
            aband = float(r["aband"])
            rate = (aband / total * 100) if total > 0 else 0.0
            abandon_threshold = thresholds.get("queue_abandon_rate", 15)
            if rate > abandon_threshold:
                # Create alert with clear explanation
                explanation = f"Out of {int(total)} calls yesterday, {int(aband)} callers hung up before reaching an agent."
                if rate > 25:
                    explanation += " This is critically high! Customers are not getting through."
                else:
                    explanation += " This is above the acceptable threshold."
                
                alerts.append({
                    "type": "high_abandon",
                    "severity": "warning",
                    "message": f"Campaign {r['campaign_id']}: {rate:.1f}% abandon rate ({int(aband)}/{int(total)})",
                    "explanation": explanation,
                    "data": r
                })

        # Service level
        q = """
            SELECT campaign_id, 
                   COUNT(*) AS total,
                   SUM(CASE WHEN queue_seconds <= 30 THEN 1 ELSE 0 END) AS insl
            FROM vicidial_closer_log
            WHERE DATE(call_date) = %s AND length_in_sec > 0
            GROUP BY campaign_id
        """
        for r in db.execute_query(q, (yesterday,)) or []:
            total = float(r["total"])
            insl = float(r["insl"])
            rate = (insl / total * 100) if total > 0 else 0.0
            sl_threshold = thresholds.get("service_level", 80)
            if rate < sl_threshold:
                # Create alert with clear explanation
                not_insl = int(total) - int(insl)
                explanation = f"Out of {int(total)} answered calls, only {int(insl)} were answered within 30 seconds. "
                explanation += f"{not_insl} callers had to wait longer than 30 seconds."
                
                if rate < 50:
                    explanation += " This is critically slow service!"
                
                alerts.append({
                    "type": "low_service_level",
                    "severity": "warning",
                    "message": f"Campaign {r['campaign_id']}: {rate:.1f}% service level ({int(insl)}/{int(total)} in <30s)",
                    "explanation": explanation,
                    "data": r
                })

    except Exception as e:
        print_warning(f"Historical alerts check failed: {e}")

    return alerts

def check_call_volume_spike():
    """Detect unusual call volume spikes"""
    config = load_alerts_config()
    spike_threshold = config["thresholds"].get("call_volume_spike", 50)
    
    try:
        # Compare today's hour with same hour last week
        query = """
        SELECT 
            HOUR(call_date) as hour,
            COUNT(*) as current_hour_calls
        FROM vicidial_closer_log
        WHERE DATE(call_date) = CURDATE()
        GROUP BY HOUR(call_date)
        """
        
        current = db.execute_query(query)
        
        query_last_week = """
        SELECT 
            HOUR(call_date) as hour,
            COUNT(*) as last_week_calls
        FROM vicidial_closer_log
        WHERE DATE(call_date) = DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY HOUR(call_date)
        """
        
        last_week = db.execute_query(query_last_week)
        
        # Create lookup dict
        last_week_dict = {l['hour']: l['last_week_calls'] for l in last_week}
        
        alerts = []
        current_hour = datetime.now().hour
        
        for c in current:
            if c['hour'] <= current_hour:  # Only check past hours
                last = last_week_dict.get(c['hour'], 0)
                if last > 0:
                    increase = ((c['current_hour_calls'] - last) / last) * 100
                    if increase > spike_threshold:
                        # Create alert with clear explanation
                        explanation = f"This hour ({c['hour']:02d}:00) had {c['current_hour_calls']} calls compared to {int(last)} calls last week."
                        explanation += f" That's a {increase:.0f}% increase!"
                        
                        if increase > 100:
                            explanation += " Your call volume has more than doubled!"
                        
                        alerts.append({
                            "type": "volume_spike",
                            "severity": "warning",
                            "message": f"Hour {c['hour']:02d}:00: {c['current_hour_calls']} calls ({increase:.0f}% increase from last week)",
                            "explanation": explanation,
                            "data": {"hour": c['hour'], "current": c['current_hour_calls'], "last": last, "increase": increase}
                        })
        
        return alerts
    except Exception as e:
        print_error(f"Error checking volume spike: {e}")
        return []

def check_campaign_health():
    """Monitor overall campaign health"""
    config = load_alerts_config()
    health_threshold = config["thresholds"].get("campaign_health", 60)
    
    try:
        query = """
        SELECT 
            campaign_id,
            COUNT(*) as total_calls,
            SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
            ROUND(100.0 * SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) / COUNT(*), 1) as answer_rate
        FROM vicidial_closer_log
        WHERE DATE(call_date) = CURDATE()
        GROUP BY campaign_id
        HAVING total_calls > 10 AND answer_rate < %s
        ORDER BY answer_rate
        """
        
        results = db.execute_query(query, (health_threshold,))
        
        alerts = []
        for r in results:
            severity = "critical" if r['answer_rate'] < 40 else "warning"
            
            # Create alert with clear explanation
            not_answered = r['total_calls'] - r['answered']
            explanation = f"Out of {r['total_calls']} calls today, only {r['answered']} were answered. "
            explanation += f"{not_answered} callers hung up or got disconnected."
            
            if r['answer_rate'] < 40:
                explanation += " This is critically low - more than half your callers are not getting through!"
            
            alerts.append({
                "type": "campaign_health",
                "severity": severity,
                "message": f"Campaign {r['campaign_id']}: {r['answer_rate']}% answer rate ({r['answered']}/{r['total_calls']} calls)",
                "explanation": explanation,
                "data": r
            })
        
        return alerts
    except Exception as e:
        print_error(f"Error checking campaign health: {e}")
        return []

def get_active_alerts():
    alerts = []
    alerts.extend(check_queue_alerts())
    alerts.extend(check_historical_alerts())
    alerts.extend(check_agent_pause_alerts())
    alerts.extend(check_call_volume_spike())
    alerts.extend(check_campaign_health())
    
    seen = set()
    unique = []
    for a in alerts:
        key = (a["type"], a.get("message", ""))
        if key not in seen:
            seen.add(key)
            unique.append(a)

    order = {"critical": 0, "warning": 1, "info": 2}
    unique.sort(key=lambda x: order.get(x.get("severity", "info"), 99))

    for a in unique:
        log_alert_to_history(a)

    return unique

# =============================================================================
# Display Functions - UPDATED with clear explanations
# =============================================================================

def display_alert(alert):
    """Display a single alert with clear explanation"""
    severity = alert.get('severity', 'info')
    
    # Choose symbol and color based on severity
    if severity == 'critical':
        symbol = "🔴"
        color = Colors.RED
        severity_text = "CRITICAL"
    elif severity == 'warning':
        symbol = "🟡"
        color = Colors.YELLOW
        severity_text = "WARNING"
    else:
        symbol = "🔵"
        color = Colors.BLUE
        severity_text = "INFO"
    
    # Print the main alert
    print_color(f"{symbol} [{severity_text}] {alert['message']}", color)
    
    # Print the explanation (indented)
    if 'explanation' in alert:
        print(f"     📌 {alert['explanation']}")
    
    # Add specific details based on alert type
    if alert['type'] == 'high_abandon' and 'data' in alert:
        data = alert['data']
        aband = data.get('abandoned', 0)
        total = data.get('total_calls', 0)
        print(f"     📊 {aband} out of {total} callers hung up")
        
    elif alert['type'] == 'low_service_level' and 'data' in alert:
        data = alert['data']
        insl = data.get('insl', 0)
        total = data.get('total', 0)
        waiting = total - insl
        print(f"     ⏱️ {waiting} callers had to wait more than 30 seconds")
        
    elif alert['type'] == 'queue_backlog' and 'data' in alert:
        data = alert['data']
        waiting = data.get('waiting_calls', 0)
        if 'avg_wait' in data:
            print(f"     ⏳ Average wait time: {data['avg_wait']:.0f} seconds")
            
    elif alert['type'] == 'volume_spike' and 'data' in alert:
        data = alert['data']
        print(f"     📈 Last week: {data['last']} calls → Today: {data['current']} calls")
        print(f"     📊 Increase: {data['increase']:.0f}%")

def show_active_alerts():
    """Display currently active alerts with clear explanations"""
    print_header("🚨 ACTIVE ALERTS", Colors.RED)
    alerts = get_active_alerts()
    
    if not alerts:
        print_success("✅ No active alerts at the moment - System is healthy!")
        print("   All metrics are within normal ranges.")
        return
    
    # Count by severity
    critical_count = len([a for a in alerts if a['severity'] == 'critical'])
    warning_count = len([a for a in alerts if a['severity'] == 'warning'])
    info_count = len([a for a in alerts if a['severity'] == 'info'])
    
    print(f"\n📊 Alert Summary:")
    if critical_count > 0:
        print_color(f"  🔴 Critical: {critical_count} - Immediate attention needed!", Colors.RED)
    if warning_count > 0:
        print_color(f"  🟡 Warning:  {warning_count} - Should be reviewed", Colors.YELLOW)
    if info_count > 0:
        print_color(f"  🔵 Info:     {info_count} - For your information", Colors.BLUE)
    
    print(f"\n{'='*80}")
    print(f"DETAILED ALERTS:")
    print(f"{'='*80}")
    
    for i, alert in enumerate(alerts, 1):
        print(f"\n{i}. ", end='')
        display_alert(alert)
    
    print(f"\n{'='*80}")
    print("💡 Use option 5 to view alert history")

def show_alert_dashboard():
    """Show comprehensive alert monitoring dashboard"""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("📊 ALERT MONITOR DASHBOARD — Live", Colors.CYAN)
        print(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 90)

        alerts = get_active_alerts()
        
        # Summary stats
        critical = len([a for a in alerts if a['severity'] == 'critical'])
        warnings = len([a for a in alerts if a['severity'] == 'warning'])
        info = len([a for a in alerts if a['severity'] == 'info'])
        
        print(f"\n📊 ALERT SUMMARY:")
        print_color(f"  🔴 Critical: {critical}", Colors.RED)
        print_color(f"  🟡 Warning:  {warnings}", Colors.YELLOW)
        print_color(f"  🔵 Info:     {info}", Colors.BLUE)
        
        if alerts:
            print(f"\n📋 CURRENT ALERTS:")
            print("-" * 90)
            
            for i, alert in enumerate(alerts[:5], 1):  # Show top 5
                display_alert(alert)
                
            if len(alerts) > 5:
                print(f"\n  ... and {len(alerts) - 5} more alerts. Use option 1 to see all.")
        else:
            print_success("\n  ✅ All clear — no active alerts")
            print("     All systems operating normally.")
        
        # Quick health stats
        print("\n📈 QUICK HEALTH:")
        print("-" * 90)
        try:
            # Agent status
            agent_query = "SELECT status, COUNT(*) cnt FROM vicidial_live_agents WHERE status IN ('READY', 'INCALL', 'PAUSE') GROUP BY status"
            agents = db.execute_query(agent_query) or []
            agent_dict = {r['status']: r['cnt'] for r in agents}
            
            total_agents = sum(agent_dict.values())
            print(f"  👥 Agents Online: {total_agents}")
            print(f"     • In Call: {agent_dict.get('INCALL', 0)}")
            print(f"     • Ready:   {agent_dict.get('READY', 0)}")
            print(f"     • Pause:   {agent_dict.get('PAUSE', 0)}")
            
            # Recent calls
            call_query = "SELECT COUNT(*) c FROM vicidial_closer_log WHERE call_date >= NOW() - INTERVAL 1 HOUR"
            calls = db.execute_query(call_query)
            print(f"\n  📞 Calls (last hour): {calls[0]['c'] if calls else 0}")
            
        except Exception as e:
            print_warning(f"  Stats unavailable: {e}")

        print("\n" + "=" * 90)
        print("  Controls:  Q = Quit    R = Refresh now    Enter = Auto-refresh in 10s")
        print("=" * 90)

        user_input = input(" → ").strip().lower()
        if user_input in ('q', 'quit', 'exit'):
            print("\n👋 Exiting dashboard...")
            break
        elif user_input in ('r', 'refresh'):
            continue
        else:
            try:
                time.sleep(10)
            except KeyboardInterrupt:
                print("\n👋 Interrupted — exiting dashboard")
                break

def show_alert_history():
    """Display historical alerts"""
    config = load_alerts_config()
    history = config.get("alert_history", [])
    
    if not history:
        print_warning("No alert history recorded yet.")
        input("\nPress Enter...")
        return

    print_header("📜 ALERT HISTORY", Colors.YELLOW)
    print(f"Total entries: {len(history)} (showing most recent 30)")
    print("-" * 90)

    for entry in sorted(history[-30:], key=lambda x: x["timestamp"], reverse=True):
        ts = datetime.fromisoformat(entry["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        
        # Choose symbol based on severity
        if entry.get("severity") == 'critical':
            sym = "🔴"
        elif entry.get("severity") == 'warning':
            sym = "🟡"
        else:
            sym = "🔵"
            
        ack = " [ACK]" if entry.get("acknowledged") else ""
        print(f"{ts}  {sym} {entry['message']}{ack}")
        
        # Show explanation if available
        if 'explanation' in entry:
            print(f"      📌 {entry['explanation']}")

    print("-" * 90)
    print("Options: [A] Acknowledge all new   [C] Clear history   [Enter] back")
    action = input(" → ").strip().upper()
    
    if action == 'A':
        for e in history:
            if not e.get("acknowledged"):
                e["acknowledged"] = True
        save_alerts_config(config)
        print_success("All visible alerts acknowledged.")
    elif action == 'C':
        if input("Really clear ALL history? (y/N): ").strip().lower() == 'y':
            config["alert_history"] = []
            save_alerts_config(config)
            print_success("History cleared.")
    input("\nPress Enter...")

def configure_thresholds():
    """Configure alert thresholds"""
    config = load_alerts_config()
    thresholds = config["thresholds"]

    while True:
        print_header("⚙️ CONFIGURE ALERT THRESHOLDS", Colors.GREEN)
        print("Current values:")
        for k, v in sorted(thresholds.items()):
            unit = " min" if any(word in k for word in ["time", "idle", "pause"]) else "%"
            print(f"  {k.replace('_', ' ').title():<22} : {v}{unit}")
        print("-" * 60)
        print("Enter key to change (or 'done' to save & exit):")
        key = input(" → ").strip().lower()
        if key == 'done':
            break
        if key in thresholds:
            try:
                new_val = input(f"New value for {key} (current: {thresholds[key]}): ").strip()
                thresholds[key] = float(new_val)
                print_success(f"Updated {key} → {thresholds[key]}")
            except ValueError:
                print_error("Invalid number.")
        else:
            print_warning("Unknown threshold key.")
        input("Press Enter...")

    if save_alerts_config(config):
        print_success("Thresholds saved.")
    else:
        print_error("Failed to save thresholds.")
    input("\nPress Enter...")

def configure_notifications():
    """Configure notification settings"""
    print_header("🔔 NOTIFICATION SETTINGS", Colors.CYAN)
    
    config = load_alerts_config()
    notification = config.get("notification", DEFAULT_NOTIFICATION)
    
    # Ensure all expected keys exist
    if 'dashboard_alerts' not in notification:
        notification['dashboard_alerts'] = True
    
    print("\nCurrent Settings:")
    print("-" * 40)
    print(f"Email Enabled     : {'✅ Yes' if notification.get('email_enabled') else '❌ No'}")
    if notification.get('email_recipients'):
        print(f"Email Recipients  : {', '.join(notification['email_recipients'])}")
    else:
        print(f"Email Recipients  : (none)")
    print(f"Slack Enabled     : {'✅ Yes' if notification.get('slack_enabled') else '❌ No'}")
    print(f"Slack Webhook     : {'Set' if notification.get('slack_webhook') else '(not set)'}")
    print(f"Dashboard Alerts  : {'✅ Enabled' if notification.get('dashboard_alerts', True) else '❌ Disabled'}")
    print("-" * 40)
    
    print("\nConfigure Settings:")
    
    # Dashboard alerts
    current_dash = notification.get('dashboard_alerts', True)
    dash_input = input(f"Enable dashboard alerts? (y/n) [{'y' if current_dash else 'n'}]: ").strip().lower()
    if dash_input:
        notification['dashboard_alerts'] = dash_input == 'y'
    
    # Email settings
    current_email = notification.get('email_enabled', False)
    email_input = input(f"Enable email notifications? (y/n) [{'y' if current_email else 'n'}]: ").strip().lower()
    if email_input:
        notification['email_enabled'] = email_input == 'y'
    
    if notification['email_enabled']:
        current_recipients = notification.get('email_recipients', [])
        recipients_display = ', '.join(current_recipients) if current_recipients else 'none'
        recipients = input(f"Email recipients (comma-separated) [current: {recipients_display}]: ").strip()
        if recipients:
            notification['email_recipients'] = [r.strip() for r in recipients.split(',')]
    
    # Slack settings
    current_slack = notification.get('slack_enabled', False)
    slack_input = input(f"Enable Slack notifications? (y/n) [{'y' if current_slack else 'n'}]: ").strip().lower()
    if slack_input:
        notification['slack_enabled'] = slack_input == 'y'
    
    if notification['slack_enabled']:
        current_webhook = notification.get('slack_webhook', '')
        webhook = input(f"Slack webhook URL [current: {current_webhook or 'not set'}]: ").strip()
        if webhook:
            notification['slack_webhook'] = webhook
    
    config['notification'] = notification
    if save_alerts_config(config):
        print_success("\n✅ Notification settings updated successfully!")
    else:
        print_error("\n❌ Failed to save notification settings")
    
    input("\nPress Enter to continue...")

# =============================================================================
# Main Menu
# =============================================================================

def alerts_menu():
    while True:
        print_header(" ALERTS & MONITORING ", Colors.RED)
        print("  1. 🚨 Active Alerts")
        print("  2. 📊 Alert Monitor Dashboard")
        print("  3. ⚙️ Configure Alert Thresholds")
        print("  4. 🔔 Notification Settings")
        print("  5. 📜 Alert History")
        print("  0. 🔙 Back to Main Menu")
        print("-" * 60)

        choice = input(f"{Colors.CYAN}Select option: {Colors.RESET}").strip()

        if choice == '1':
            show_active_alerts()
            input("\nPress Enter to continue...")
        elif choice == '2':
            show_alert_dashboard()
        elif choice == '3':
            configure_thresholds()
        elif choice == '4':
            configure_notifications()
        elif choice == '5':
            show_alert_history()
        elif choice == '0':
            break
        else:
            print_error("Invalid option")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    alerts_menu()