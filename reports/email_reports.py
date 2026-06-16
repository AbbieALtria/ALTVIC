#!/usr/bin/env python3
# =============================================================================
# File:         email_reports.py
# Version:      1.0.0
# Date:         2026-02-28
# Description:  Automated email reports for call center analytics
# Location:     D:/Altria_Ops/reports/email_reports.py
# =============================================================================

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
import sys
from pathlib import Path
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_color, print_success, print_error, print_warning
from utils.formatter import sec_to_hms
from config.settings import load_config


# ── pinktools helpers ──────────────────────────────────────────────────────────
def _email_channel_html(target_date):
    """Return an HTML block with pinktools email stats for target_date, or '' on error."""
    try:
        from core.email_integration import get_email_summary, get_email_stats_by_agent, ensure_mapping_table
        ensure_mapping_table()
        summary = get_email_summary(target_date)
        agents  = get_email_stats_by_agent(target_date)

        if not summary or summary['total_emails'] == 0:
            return ""

        agents.sort(key=lambda x: x['total_emails'], reverse=True)

        # Build agent rows
        agent_rows_html = ""
        for a in agents[:15]:
            linked  = a['altria_username'] or '<em style="color:#e67e22">Unlinked</em>'
            top_type = max(a['by_type'], key=a['by_type'].get) if a['by_type'] else '—'
            agent_rows_html += f"""
            <tr>
                <td><strong>{a['pinktools_name']}</strong></td>
                <td>{linked}</td>
                <td style="text-align:center">{a['total_emails']}</td>
                <td style="text-align:center">{a['cancellations']}</td>
                <td style="text-align:center">{a['refund_count']}</td>
                <td style="text-align:right">${a['refund_total']:,.2f}</td>
                <td style="font-size:11px">{top_type}</td>
            </tr>"""

        return f"""
        <h2 style="margin-top:30px">📧 Email Channel — {target_date}</h2>
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin:12px 0">
            <div style="background:#f0f4ff;padding:14px 20px;border-radius:6px;text-align:center;min-width:110px">
                <div style="font-size:11px;color:#666">Total Emails</div>
                <div style="font-size:26px;font-weight:bold">{summary['total_emails']:,}</div>
            </div>
            <div style="background:#fff4e6;padding:14px 20px;border-radius:6px;text-align:center;min-width:110px">
                <div style="font-size:11px;color:#666">Cancellations</div>
                <div style="font-size:26px;font-weight:bold;color:#e67e22">{summary['cancellations']}</div>
            </div>
            <div style="background:#fff0f0;padding:14px 20px;border-radius:6px;text-align:center;min-width:110px">
                <div style="font-size:11px;color:#666">Full Refunds</div>
                <div style="font-size:26px;font-weight:bold;color:#e74c3c">{summary['full_refunds']}</div>
            </div>
            <div style="background:#fff8e6;padding:14px 20px;border-radius:6px;text-align:center;min-width:110px">
                <div style="font-size:11px;color:#666">Partial Refunds</div>
                <div style="font-size:26px;font-weight:bold;color:#f39c12">{summary['partial_refunds']}</div>
            </div>
            <div style="background:#f0fff4;padding:14px 20px;border-radius:6px;text-align:center;min-width:110px">
                <div style="font-size:11px;color:#666">Refund Value</div>
                <div style="font-size:22px;font-weight:bold;color:#27ae60">${summary['refund_total']:,.2f}</div>
            </div>
            <div style="background:#f5f0ff;padding:14px 20px;border-radius:6px;text-align:center;min-width:110px">
                <div style="font-size:11px;color:#666">Order Status</div>
                <div style="font-size:26px;font-weight:bold">{summary['order_status']}</div>
            </div>
            <div style="background:#f0f9ff;padding:14px 20px;border-radius:6px;text-align:center;min-width:110px">
                <div style="font-size:11px;color:#666">Reshipments</div>
                <div style="font-size:26px;font-weight:bold">{summary['reshipments']}</div>
            </div>
        </div>

        <h3>📋 Email Agent Breakdown</h3>
        <table style="width:100%;border-collapse:collapse;margin:10px 0;font-size:13px">
            <tr style="background:#764ba2;color:white">
                <th style="padding:8px;text-align:left">Agent (pinktools)</th>
                <th style="padding:8px;text-align:left">VICIdial User</th>
                <th style="padding:8px;text-align:center">Emails</th>
                <th style="padding:8px;text-align:center">Cancels</th>
                <th style="padding:8px;text-align:center">Refunds</th>
                <th style="padding:8px;text-align:right">Refund $</th>
                <th style="padding:8px">Top Type</th>
            </tr>
            {agent_rows_html}
        </table>
        """
    except Exception as ex:
        return f'<p style="color:#999;font-size:12px">Email channel data unavailable: {ex}</p>'

# =============================================================================
# Email Configuration
# =============================================================================

def get_email_config():
    """Get email configuration from settings"""
    config = load_config()
    return config.get('email', {
        'enabled': False,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'username': '',
        'password': '',
        'recipients': []
    })

# =============================================================================
# Report Generators
# =============================================================================

def generate_daily_report_html(date=None):
    """Generate HTML daily report"""
    if not date:
        date = datetime.now().date()
    
    # Get yesterday's data
    yesterday = date - timedelta(days=1)
    
    # Overall stats
    stats_query = """
    SELECT 
        COUNT(*) as total_calls,
        SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
        SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                 OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
        AVG(queue_seconds) as avg_queue,
        AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) as avg_talk
    FROM vicidial_closer_log
    WHERE DATE(call_date) = %s
    """
    
    stats = db.execute_query(stats_query, (yesterday,))
    
    # Top agents
    agents_query = """
    SELECT 
        a.user,
        u.full_name,
        COUNT(*) as calls,
        SUM(a.talk_sec) as talk_time,
        AVG(a.talk_sec) as avg_talk
    FROM vicidial_agent_log a
    LEFT JOIN vicidial_users u ON a.user = u.user
    WHERE DATE(a.event_time) = %s
    GROUP BY a.user
    ORDER BY calls DESC
    LIMIT 10
    """
    
    top_agents = db.execute_query(agents_query, (yesterday,))
    
    # Campaign breakdown
    campaign_query = """
    SELECT 
        campaign_id,
        COUNT(*) as calls,
        SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
        AVG(queue_seconds) as avg_queue
    FROM vicidial_closer_log
    WHERE DATE(call_date) = %s
    GROUP BY campaign_id
    ORDER BY calls DESC
    """
    
    campaigns = db.execute_query(campaign_query, (yesterday,))
    
    # Build HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                      color: white; padding: 20px; text-align: center; }}
            .summary {{ display: flex; justify-content: space-around; margin: 20px 0; }}
            .card {{ background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }}
            .card h3 {{ margin: 0; color: #666; }}
            .card .value {{ font-size: 24px; font-weight: bold; color: #333; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background: #667eea; color: white; padding: 10px; text-align: left; }}
            td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
            .footer {{ text-align: center; color: #999; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Altria Ops Daily Report</h1>
            <h2>{yesterday.strftime('%B %d, %Y')}</h2>
        </div>
    """
    
    if stats:
        s = stats[0]
        ans_rate = (s['answered'] / s['total_calls'] * 100) if s['total_calls'] > 0 else 0
        abd_rate = (s['abandoned'] / s['total_calls'] * 100) if s['total_calls'] > 0 else 0
        
        html += f"""
        <div class="summary">
            <div class="card">
                <h3>Total Calls</h3>
                <div class="value">{s['total_calls']}</div>
            </div>
            <div class="card">
                <h3>Answer Rate</h3>
                <div class="value">{ans_rate:.1f}%</div>
            </div>
            <div class="card">
                <h3>Abandon Rate</h3>
                <div class="value">{abd_rate:.1f}%</div>
            </div>
            <div class="card">
                <h3>Avg Talk</h3>
                <div class="value">{sec_to_hms(s['avg_talk'])}</div>
            </div>
        </div>
        """
    
    # Top Agents
    if top_agents:
        html += """
        <h2>🏆 Top Performers</h2>
        <table>
            <tr>
                <th>Rank</th>
                <th>Agent</th>
                <th>Name</th>
                <th>Calls</th>
                <th>Talk Time</th>
                <th>Avg Call</th>
            </tr>
        """
        
        for i, agent in enumerate(top_agents, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else ""
            html += f"""
            <tr>
                <td>{medal} {i}</td>
                <td><strong>{agent['user']}</strong></td>
                <td>{agent['full_name'] or 'Unknown'}</td>
                <td>{agent['calls']}</td>
                <td>{sec_to_hms(agent['talk_time'])}</td>
                <td>{sec_to_hms(agent['avg_talk'])}</td>
            </tr>
            """
        
        html += "</table>"
    
    # Campaign Breakdown
    if campaigns:
        html += """
        <h2>📋 Campaign Performance</h2>
        <table>
            <tr>
                <th>Campaign</th>
                <th>Calls</th>
                <th>Answered</th>
                <th>Answer %</th>
                <th>Avg Queue</th>
            </tr>
        """
        
        for camp in campaigns[:10]:
            ans_rate = (camp['answered'] / camp['calls'] * 100) if camp['calls'] > 0 else 0
            html += f"""
            <tr>
                <td><strong>{camp['campaign_id']}</strong></td>
                <td>{camp['calls']}</td>
                <td>{camp['answered']}</td>
                <td>{ans_rate:.1f}%</td>
                <td>{camp['avg_queue']:.0f}s</td>
            </tr>
            """
        
        html += "</table>"
    
    # ── pinktools email channel section ───────────────────────────────────────
    html += _email_channel_html(yesterday)

    html += """
        <div class="footer">
            <p>Generated by Altria Operations System</p>
        </div>
    </body>
    </html>
    """

    return html

def generate_weekly_report_html():
    """Generate HTML weekly report"""
    end_date = datetime.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=6)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                      color: white; padding: 20px; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th {{ background: #667eea; color: white; padding: 10px; }}
            td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Altria Ops Weekly Report</h1>
            <h2>{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}</h2>
        </div>
    """
    
    # Daily breakdown
    daily_query = """
    SELECT 
        DATE(call_date) as date,
        COUNT(*) as calls,
        SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered
    FROM vicidial_closer_log
    WHERE call_date BETWEEN %s AND %s
    GROUP BY DATE(call_date)
    ORDER BY date
    """
    
    daily = db.execute_query(daily_query, (start_date, end_date))
    
    if daily:
        html += "<h2>📅 Daily Breakdown</h2>"
        html += "<table><tr><th>Date</th><th>Calls</th><th>Answered</th><th>Answer %</th></tr>"
        
        for day in daily:
            ans_rate = (day['answered'] / day['calls'] * 100) if day['calls'] > 0 else 0
            html += f"<tr><td>{day['date']}</td><td>{day['calls']}</td><td>{day['answered']}</td><td>{ans_rate:.1f}%</td></tr>"
        
        html += "</table>"
    
    # ── pinktools email channel section (weekly) ──────────────────────────────
    html += _email_channel_html(end_date)

    html += "<div class='footer'><p>Generated by Altria Operations System</p></div></body></html>"

    return html

# =============================================================================
# Email Sending
# =============================================================================

def send_report(recipients, subject, html_content, attachments=None):
    """Send email report"""
    config = get_email_config()
    
    if not config['enabled']:
        print_warning("Email is disabled in configuration")
        return False
    
    if not recipients:
        recipients = config['recipients']
    
    if not recipients:
        print_error("No email recipients configured")
        return False
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = config['username']
    msg['To'] = ', '.join(recipients)
    
    # Attach HTML
    msg.attach(MIMEText(html_content, 'html'))
    
    # Attachments
    if attachments:
        for filepath in attachments:
            with open(filepath, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename={os.path.basename(filepath)}'
                )
                msg.attach(part)
    
    try:
        # Send email
        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
        server.starttls()
        server.login(config['username'], config['password'])
        server.send_message(msg)
        server.quit()
        
        print_success(f"Report sent to {len(recipients)} recipient(s)")
        return True
        
    except Exception as e:
        print_error(f"Failed to send email: {e}")
        return False

# =============================================================================
# Scheduled Reports
# =============================================================================

def send_daily_report():
    """Send daily report (to be called by scheduler)"""
    html = generate_daily_report_html()
    subject = f"📊 Daily Report - {datetime.now().strftime('%Y-%m-%d')}"
    return send_report(None, subject, html)

def send_weekly_report():
    """Send weekly report"""
    html = generate_weekly_report_html()
    subject = f"📊 Weekly Report - Week of {datetime.now().strftime('%Y-%m-%d')}"
    return send_report(None, subject, html)

# =============================================================================
# Menu Interface
# =============================================================================

def email_reports_menu():
    """Menu for email reports"""
    while True:
        print_header("📧 EMAIL REPORTS", Colors.CYAN)
        print("  1. 📧 Send Daily Report Now")
        print("  2. 📧 Send Weekly Report Now")
        print("  3. ⚙️ Configure Email Settings")
        print("  4. 👥 Manage Recipients")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            print("\n📊 Generating daily report...")
            send_daily_report()
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            print("\n📊 Generating weekly report...")
            send_weekly_report()
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            configure_email()
        
        elif choice == '4':
            manage_recipients()
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

def configure_email():
    """Configure email settings"""
    config = load_config()
    email_config = config.get('email', {})
    
    print_header("⚙️ EMAIL CONFIGURATION", Colors.GREEN)
    
    print(f"\nCurrent Settings:")
    print(f"  Enabled: {email_config.get('enabled', False)}")
    print(f"  SMTP Server: {email_config.get('smtp_server', 'Not set')}")
    print(f"  SMTP Port: {email_config.get('smtp_port', 587)}")
    print(f"  Username: {email_config.get('username', 'Not set')}")
    
    print("\nEnter new values (press Enter to keep current):")
    
    enabled = input(f"Enable email? (y/n) [{'y' if email_config.get('enabled') else 'n'}]: ").strip().lower()
    if enabled:
        email_config['enabled'] = enabled == 'y'
    
    server = input(f"SMTP Server [{email_config.get('smtp_server', 'smtp.gmail.com')}]: ").strip()
    if server:
        email_config['smtp_server'] = server
    
    port = input(f"SMTP Port [{email_config.get('smtp_port', 587)}]: ").strip()
    if port:
        try:
            email_config['smtp_port'] = int(port)
        except:
            print_warning("Invalid port number")
    
    username = input(f"Username [{email_config.get('username', '')}]: ").strip()
    if username:
        email_config['username'] = username
    
    password = input(f"Password: ").strip()
    if password:
        email_config['password'] = password
    
    config['email'] = email_config
    from config.settings import save_config
    save_config(config)
    
    print_success("Email configuration saved!")

def manage_recipients():
    """Manage email recipients"""
    config = load_config()
    email_config = config.get('email', {})
    recipients = email_config.get('recipients', [])
    
    print_header("👥 EMAIL RECIPIENTS", Colors.CYAN)
    
    if recipients:
        print("\nCurrent recipients:")
        for i, r in enumerate(recipients, 1):
            print(f"  {i}. {r}")
    else:
        print("\nNo recipients configured")
    
    print("\nOptions:")
    print("  1. Add recipient")
    print("  2. Remove recipient")
    print("  3. Clear all")
    print("  0. Back")
    
    choice = input("\nChoice: ").strip()
    
    if choice == '1':
        email = input("Enter email address: ").strip()
        if email:
            recipients.append(email)
            print_success(f"Added {email}")
    
    elif choice == '2' and recipients:
        idx = input(f"Enter number to remove (1-{len(recipients)}): ").strip()
        if idx.isdigit() and 1 <= int(idx) <= len(recipients):
            removed = recipients.pop(int(idx)-1)
            print_success(f"Removed {removed}")
    
    elif choice == '3':
        if input("Clear all recipients? (y/N): ").strip().lower() == 'y':
            recipients.clear()
            print_success("All recipients removed")
    
    email_config['recipients'] = recipients
    config['email'] = email_config
    from config.settings import save_config
    save_config(config)

if __name__ == "__main__":
    email_reports_menu()