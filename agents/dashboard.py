#!/usr/bin/env python3
# =============================================================================
# File:         dashboard.py
# Version:      5.9.0
# Date:         2026-03-28
# Description:  Agent Performance Dashboard - with campaign visibility, Manila time support,
#               improved login history with daily grouping, session analysis, productivity metrics,
#               and PDF export capability
# Location:     D:/Altria_Ops/agents/dashboard.py
# Changes:      - Fixed print_info import error
#               - Added PDF export functionality for login history reports
#               - Added option to save reports as PDF at end of browsing
#               - Enhanced report formatting for professional PDF output
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms, time_ago
import sys
from decimal import Decimal
from collections import defaultdict
import os
from pathlib import Path

# Try to import PDF libraries
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print_warning("PDF export requires reportlab. Install with: pip install reportlab")

# =============================================================================
# Helper function for Decimal conversion
# =============================================================================

def to_float(value):
    """Safely convert any value to float, handling None and Decimal"""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def to_int(value):
    """Safely convert any value to int, handling None and Decimal"""
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

# =============================================================================
# Configuration - Campaign classification
# =============================================================================

OUTBOUND_CAMPAIGNS = [
    'UpliftDeals', 'K1', 'TikTok', 'Zappify', 'YPDirect', 
    'Hotpro', 'BabiTrump', 'Boxco', 'Aiven', 'NutraPrice',
    'Revitol', 'RealCBDketo', 'MarketNice', 'Patriots'
]

INBOUND_CAMPAIGNS = [
    'Xshield', 'SAVVYCS', 'TodosGamersCS', 'DignityBioLabs', 
    'ShopMyHealth', 'XCHANGE', 'AAASUP', 'AGENTDIRECT'
]

# =============================================================================
# PDF Export Directory
# =============================================================================

REPORTS_DIR = Path(__file__).parent.parent / "exports" / "agent_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# Timezone Helpers (Manila = UTC+8, server is UTC-12 → +12h offset)
# =============================================================================

PH_OFFSET_HOURS = 12  # Server is 12 hours behind Manila

def convert_to_ph_time(server_time):
    """Convert server datetime to Philippines time"""
    if server_time is None:
        return None, "—"
    try:
        ph_time = server_time + timedelta(hours=PH_OFFSET_HOURS)
        return ph_time, ph_time.strftime('%Y-%m-%d %H:%M:%S PH')
    except:
        return None, "—"

def time_ago_ph(server_time):
    """'X hours ago' in Manila time"""
    if server_time is None:
        return "Unknown"
    ph_time, _ = convert_to_ph_time(server_time)
    if ph_time is None:
        return "Unknown"
    
    now_utc = datetime.utcnow()
    now_ph = now_utc + timedelta(hours=8)  # UTC to Manila
    
    diff = now_ph - ph_time
    hours = diff.total_seconds() / 3600
    
    if hours < 1:
        return f"{int(hours*60)} min ago (PH)"
    elif hours < 24:
        return f"{int(hours)} hrs ago (PH)"
    elif hours < 48:
        return "yesterday (PH)"
    else:
        return f"{int(hours/24)} days ago (PH)"

def get_campaign_type(campaign_id):
    """Get campaign type classification"""
    if campaign_id in OUTBOUND_CAMPAIGNS:
        return 'OUTBOUND'
    elif campaign_id in INBOUND_CAMPAIGNS:
        return 'INBOUND'
    else:
        return 'UNKNOWN'

# =============================================================================
# Agent Campaign Summary
# =============================================================================

def get_agent_campaigns_summary(agent, date_filter):
    """
    Returns:
    - list of formatted lines: "  • CampaignName (TYPE) - N calls"
    - overall detected type: OUTBOUND / INBOUND / MIXED / UNKNOWN
    - count of outbound campaigns
    - count of inbound campaigns
    """
    try:
        query = f"""
        SELECT 
            c.campaign_id,
            COUNT(DISTINCT a.uniqueid) as call_count,
            CASE 
                WHEN c.campaign_id IN ({','.join(['%s']*len(OUTBOUND_CAMPAIGNS))}) THEN 'OUTBOUND'
                WHEN c.campaign_id IN ({','.join(['%s']*len(INBOUND_CAMPAIGNS))}) THEN 'INBOUND'
                ELSE 'UNKNOWN'
            END as camp_type
        FROM vicidial_agent_log a
        JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
        WHERE a.user = %s 
          AND {date_filter}
        GROUP BY c.campaign_id, camp_type
        ORDER BY camp_type, call_count DESC
        """
        
        params = OUTBOUND_CAMPAIGNS + INBOUND_CAMPAIGNS + [agent]
        rows = db.execute_query(query, params) or []
        
        if not rows:
            return [], "UNKNOWN", 0, 0
        
        lines = []
        outbound_count = 0
        inbound_count = 0
        
        for row in rows:
            camp = row['campaign_id']
            calls = to_int(row['call_count'])
            typ = row['camp_type']
            
            line = f"  • {camp:<18} ({typ}) - {calls} calls"
            lines.append(line)
            
            if typ == 'OUTBOUND':
                outbound_count += 1
            elif typ == 'INBOUND':
                inbound_count += 1
        
        if outbound_count > 0 and inbound_count > 0:
            agent_type = "MIXED"
        elif outbound_count > 0:
            agent_type = "OUTBOUND"
        elif inbound_count > 0:
            agent_type = "INBOUND"
        else:
            agent_type = "UNKNOWN"
        
        return lines, agent_type, outbound_count, inbound_count
        
    except Exception as e:
        print_error(f"Error fetching agent campaign summary: {e}")
        return [], "UNKNOWN", 0, 0

# =============================================================================
# Agent Helpers
# =============================================================================

def get_agent_name(username):
    """Get agent's full name from username"""
    try:
        query = "SELECT full_name FROM vicidial_users WHERE user = %s"
        result = db.execute_query(query, (username,))
        if result and result[0]['full_name']:
            return result[0]['full_name']
    except Exception:
        pass
    return username

def get_all_agents():
    """Get list of all agents from database"""
    try:
        query = """
        SELECT user, full_name, active 
        FROM vicidial_users 
        WHERE user IS NOT NULL AND user != ''
        ORDER BY user
        """
        agents = db.execute_query(query)
        
        valid_agents = []
        for a in agents or []:
            if a['user'] and a['user'].strip():
                valid_agents.append({
                    'user': a['user'],
                    'name': a['full_name'] or 'Unknown',
                    'active': a.get('active', 'Y')
                })
        return valid_agents
    except Exception as e:
        print_error(f"Error getting agent list: {e}")
        return []

def show_agent_list():
    """Display paginated agent list for selection"""
    agents = get_all_agents()
    if not agents:
        print_warning("No agents found in database")
        return None
    
    print_header("📋 SELECT AGENT", Colors.CYAN)
    print(f"\nTotal: {len(agents)} agents")
    print("=" * 100)
    
    col_width = 45
    cols = 2
    
    for i in range(0, len(agents), cols):
        line = ""
        for j in range(cols):
            if i + j < len(agents):
                agent = agents[i + j]
                agent_num = i + j + 1
                name = agent['name'][:20] if agent['name'] else 'Unknown'
                
                status = '✅' if agent.get('active') == 'Y' else '❌'
                color = Colors.GREEN if status == '✅' else Colors.RED
                
                display = f"{agent_num:3}. {agent['user']} ({name}) {status}"
                display = display.ljust(col_width)
                line += f"{color}{display}{Colors.RESET}"
        
        print(line)
    
    print("=" * 100)
    print("\n💡 Enter NUMBER or username directly | Enter to go back")
    return agents

def get_agent_by_selection(agents):
    """Interactive agent selection by number or username"""
    while True:
        choice = input("\nEnter number or username: ").strip()
        if not choice:
            return None
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(agents):
                selected = agents[idx]['user']
                print_color(f"✅ Selected: {selected}", Colors.GREEN)
                return selected
            print_error(f"Invalid number. Use 1-{len(agents)}")
            continue
        
        matches = [a for a in agents if a['user'].lower() == choice.lower()]
        if matches:
            print_color(f"✅ Selected: {matches[0]['user']}", Colors.GREEN)
            return matches[0]['user']
        
        partial = [a for a in agents if choice.lower() in a['user'].lower()]
        if len(partial) == 1:
            print_color(f"✅ Selected: {partial[0]['user']}", Colors.GREEN)
            return partial[0]['user']
        elif len(partial) > 1:
            print(f"\n🔍 Multiple matches ({len(partial)}):")
            for i, a in enumerate(partial[:10], 1):
                print(f"  {i}. {a['user']} ({a['name']}) {'✅' if a.get('active')=='Y' else '❌'}")
            continue
        else:
            print_error(f"Agent '{choice}' not found")

# =============================================================================
# PDF Export Function for Login History
# =============================================================================

def export_login_history_pdf(agent_id, days, daily_data, overall_summary):
    """Export agent login history to PDF"""
    if not PDF_AVAILABLE:
        print_warning("PDF export not available. Install reportlab: pip install reportlab")
        return None
    
    # Create filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"Agent_{agent_id}_LoginHistory_{days}days_{timestamp}.pdf"
    filepath = REPORTS_DIR / filename
    
    try:
        # Create PDF document
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=landscape(A4),
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )
        
        styles = getSampleStyleSheet()
        story = []
        
        # Title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
            textColor=colors.HexColor('#2c3e50')
        )
        
        # Header style
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=12,
            textColor=colors.HexColor('#3498db')
        )
        
        # Normal style
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=9,
            spaceAfter=6
        )
        
        # Company Header
        story.append(Paragraph("ALTRIA OPERATIONS SYSTEM", title_style))
        story.append(Paragraph(f"Agent Login History Report - {agent_id}", title_style))
        story.append(Spacer(1, 12))
        
        # Report Info
        agent_name = get_agent_name(agent_id)
        report_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        info_data = [
            ["Agent ID:", agent_id],
            ["Agent Name:", agent_name],
            ["Period:", f"Last {days} days"],
            ["Report Generated:", report_date],
            ["Timezone:", "Philippines Time (UTC+8)"]
        ]
        
        info_table = Table(info_data, colWidths=[120, 380])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 20))
        
        # Overall Summary
        story.append(Paragraph("Overall Summary", header_style))
        
        overall_data = [
            ["Metric", "Value"],
            ["Days Analyzed", str(overall_summary['total_days'])],
            ["Total Talk Time", overall_summary['total_talk_str']],
            ["Total Wait Time", overall_summary['total_wait_str']],
            ["Total Pause Time", overall_summary['total_pause_str']],
            ["Total Unique Calls", str(overall_summary['unique_calls_total'])],
            ["Avg Talk/Day", overall_summary['avg_talk_str']],
            ["Avg Calls/Day", f"{overall_summary['avg_calls_per_day']:.1f}"],
            ["Performance Rating", overall_summary['performance_rating']]
        ]
        
        overall_table = Table(overall_data, colWidths=[150, 350])
        overall_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#3498db')),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(overall_table)
        story.append(Spacer(1, 20))
        
        # Daily Reports
        for day_data in daily_data:
            story.append(PageBreak())
            story.append(Paragraph(f"Daily Report: {day_data['date']}", header_style))
            story.append(Spacer(1, 10))
            
            # Daily Summary Table
            daily_summary_data = [
                ["Metric", "Value"],
                ["Active Hours", f"{day_data['active_hours']:.2f} hrs ({day_data['active_period']})"],
                ["Talk Time", day_data['talk_str']],
                ["Wait Time", day_data['wait_str']],
                ["Pause Time", day_data['pause_str']],
                ["Actual Work Time", day_data['work_str']],
                ["Total Unique Calls", str(day_data['unique_calls'])],
                ["Efficiency", f"{day_data['efficiency']:.1f}%"],
                ["Productivity", day_data['productivity_rating']]
            ]
            
            daily_table = Table(daily_summary_data, colWidths=[150, 350])
            daily_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#27ae60')),
                ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('PADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(daily_table)
            story.append(Spacer(1, 15))
            
            # Sessions
            if day_data['sessions']:
                story.append(Paragraph("Session Breakdown", header_style))
                
                for session in day_data['sessions'][:10]:  # Limit to 10 sessions per day for PDF
                    session_data = [
                        [f"Session {session['index']}: {session['start']} - {session['end']} ({session['duration']} min)", ""],
                        ["Calls:", str(session['calls'])],
                        ["Talk Time:", session['talk_str']],
                        ["Wait Time:", session['wait_str']],
                        ["Pause Time:", session['pause_str']]
                    ]
                    
                    session_table = Table(session_data, colWidths=[120, 380])
                    session_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f39c12')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ]))
                    story.append(session_table)
                    story.append(Spacer(1, 8))
            
            # Hourly Activity
            if day_data['hourly_data']:
                story.append(Spacer(1, 10))
                story.append(Paragraph("Hourly Activity", header_style))
                
                hourly_table_data = [["Hour", "Events", "Talk Time"]]
                for hour_data in day_data['hourly_data']:
                    hourly_table_data.append([
                        hour_data['hour'],
                        str(hour_data['count']),
                        hour_data['talk_str']
                    ])
                
                hourly_table = Table(hourly_table_data, colWidths=[100, 100, 150])
                hourly_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                ]))
                story.append(hourly_table)
        
        # Footer
        story.append(PageBreak())
        story.append(Paragraph("Report Summary", header_style))
        footer_text = f"""
        This report was generated automatically by Altria Operations System.<br/>
        Agent: {agent_id} ({agent_name})<br/>
        Period: Last {days} days<br/>
        Generation Date: {report_date}<br/>
        Timezone: Philippines Time (UTC+8)<br/>
        <br/>
        For questions or support, contact Altria Ops Team.
        """
        footer_para = Paragraph(footer_text, normal_style)
        story.append(footer_para)
        
        # Build PDF
        doc.build(story)
        return filepath
        
    except Exception as e:
        print_error(f"PDF generation error: {e}")
        import traceback
        traceback.print_exc()
        return None

# =============================================================================
# Leaderboards with campaign visibility
# =============================================================================

def get_top_outbound_performers(period='today'):
    """Display top outbound performers based on sales"""
    period_display = {'today':'TODAY', 'yesterday':'YESTERDAY', 'week':'THIS WEEK', 'month':'THIS MONTH'}
    title = period_display.get(period, period.upper())
    
    print_header(f"💰 TOP OUTBOUND PERFORMERS - {title}", Colors.GREEN)
    print("   (Sales-focused campaigns only)")
    
    try:
        date_filter_map = {
            'today': "DATE(c.call_date) = CURDATE()",
            'yesterday': "DATE(c.call_date) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)",
            'week': "c.call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
            'month': "c.call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)",
        }
        date_filter = date_filter_map.get(period, date_filter_map['week'])
        
        if not OUTBOUND_CAMPAIGNS:
            print_warning("No outbound campaigns configured")
            return
        
        placeholders = ','.join(['%s'] * len(OUTBOUND_CAMPAIGNS))
        
        sales_query = f"""
        SELECT 
            a.user,
            u.full_name,
            COUNT(DISTINCT a.uniqueid) as calls,
            SUM(CASE WHEN a.status IN ('SALE','YPSALE','UPSELL','CROSSSELL') THEN 1 ELSE 0 END) as sales,
            (SUM(CASE WHEN a.status IN ('SALE','YPSALE','UPSELL','CROSSSELL') THEN 1 ELSE 0 END) / 
             NULLIF(COUNT(DISTINCT a.uniqueid), 0)) * 100 as conv_rate
        FROM vicidial_agent_log a
        JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE {date_filter}
          AND c.campaign_id IN ({placeholders})
        GROUP BY a.user
        HAVING sales > 0 OR calls >= 10
        ORDER BY sales DESC, conv_rate DESC
        LIMIT 10
        """
        
        top_by_sales = db.execute_query(sales_query, OUTBOUND_CAMPAIGNS)
        
        if top_by_sales:
            print(f"\n{'═'*110}")
            print(f"{'💰 TOP OUTBOUND PERFORMERS – ' + title.upper():^110}")
            print(f"{'═'*110}")
            print("Sales-focused campaigns – ranked by Sales count (minimum 10 calls or any sale)\n")
            
            print(f"{'Rank':<6} {'Agent':<14} {'Name':<18} {'Calls':>8} {'Sales':>8} {'Conv%':>8} {'Dials/Sale':>12} {'Campaign Activity':<30}")
            print("─" * 110)
            
            for i, agent in enumerate(top_by_sales, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
                name = (agent['full_name'] or 'Unknown')[:18]
                calls = to_int(agent['calls'])
                sales = to_int(agent['sales'])
                conv = to_float(agent['conv_rate'])
                
                dials_sale = f"{calls // sales}" if sales > 0 else '∞'
                color = Colors.GREEN if conv >= 5 else Colors.YELLOW if conv >= 2 else Colors.RED
                
                # Print main row
                print_color(
                    f"{medal:<6} {agent['user']:<14} {name:<18} {calls:>8,} {sales:>8,} {conv:>7.1f}% {dials_sale:>12}",
                    color
                )
                
                # Get campaign info
                campaigns_lines, agent_type, outb_count, inb_count = get_agent_campaigns_summary(agent['user'], date_filter)
                
                if campaigns_lines:
                    for line in campaigns_lines:
                        print(" " * 74 + line)  # align under "Campaign Activity"
                    
                    # Summary line
                    if agent_type == "MIXED":
                        summary = "→ Mixed / Blended agent"
                    elif agent_type == "OUTBOUND":
                        summary = "→ Pure Outbound agent"
                    elif agent_type == "INBOUND":
                        summary = "→ Pure Inbound agent (unusual in outbound ranking)"
                    else:
                        summary = "→ Unknown activity pattern"
                    
                    print(" " * 74 + summary)
                
                print()  # space between agents
            
            print("═" * 110)
        else:
            print("\nNo outbound sales activity found in this period")
    
    except Exception as e:
        print_error(f"Error in outbound leaderboard: {e}")

def get_top_inbound_performers(period='today'):
    """Display top inbound performers based on weighted score"""
    titles = {'today':'TODAY', 'yesterday':'YESTERDAY', 'week':'THIS WEEK', 'month':'THIS MONTH'}
    title = titles.get(period, period.upper())

    print(f"\n{'═' * 120}")
    print(f"{'🎯  TOP INBOUND PERFORMERS – ' + title:^120}")
    print(f"{'═' * 120}")
    print(" Service & Support campaigns · ranked by Weighted Performance Score (Answer Rate 50% + AHT 30% + Volume 20%)\n")

    print(f"{'Rank':<6}  {'Agent ID':<12}  {'Name':<22}  {'Calls':>6}  {'Ans':>6}  {'Ans%':>7}  {'AHT':>8}  {'Score':>10}")
    print("─" * 120)

    date_filter_map = {
        'today':     "DATE(c.call_date) = CURDATE()",
        'yesterday': "DATE(c.call_date) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)",
        'week':      "c.call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
        'month':     "c.call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)",
    }
    date_filter = date_filter_map.get(period, date_filter_map['week'])

    if not INBOUND_CAMPAIGNS:
        print_warning("No inbound campaigns defined.")
        return

    placeholders = ','.join(['%s'] * len(INBOUND_CAMPAIGNS))

    query = f"""
    SELECT
        a.user,
        u.full_name,
        COUNT(DISTINCT a.uniqueid) as total_calls,
        SUM(CASE WHEN a.talk_sec >= 5 THEN 1 ELSE 0 END) as answered,
        AVG(CASE WHEN a.talk_sec >= 5 THEN a.talk_sec END) as avg_talk_sec,
        (SUM(CASE WHEN a.talk_sec >= 5 THEN 1 ELSE 0 END) / 
         NULLIF(COUNT(DISTINCT a.uniqueid), 0)) * 100 as answer_rate
    FROM vicidial_agent_log a
    JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
    LEFT JOIN vicidial_users u ON a.user = u.user
    WHERE {date_filter}
      AND c.campaign_id IN ({placeholders})
    GROUP BY a.user
    HAVING total_calls >= 10
    """

    rows = db.execute_query(query, INBOUND_CAMPAIGNS)

    if not rows:
        print(f"\n{'═' * 120}")
        print(f"{'🎯  TOP INBOUND PERFORMERS – ' + title:^120}")
        print(f"{'═' * 120}")
        print("  No agents with ≥10 inbound calls in this period.\n")
        print("═" * 120)
        return

    # Calculate weighted scores with proper type conversion
    scored_rows = []
    for row in rows:
        # Convert Decimal values to float explicitly
        ar_pct = to_float(row['answer_rate'])
        aht_sec = to_float(row['avg_talk_sec'] or 300)  # default 5 min
        calls = to_int(row['total_calls'])
        answered = to_int(row['answered'])

        # 1. Answer Rate component (0–50)
        ar_score = 0.0
        if ar_pct >= 70.0:
            ar_score = min(50.0, (ar_pct - 70.0) / 30.0 * 50.0)

        # 2. AHT component (0–30) — ideal 180–420 seconds
        ideal_low, ideal_high = 180.0, 420.0
        if ideal_low <= aht_sec <= ideal_high:
            aht_score = 30.0
        elif aht_sec < ideal_low:
            aht_score = max(0.0, 30.0 * (aht_sec / ideal_low))
        else:
            decay = 30.0 * (1.0 - (aht_sec - ideal_high) / 300.0)
            aht_score = max(0.0, decay)

        # 3. Volume component (0–20) — 40 calls = full points
        volume_score = min(20.0, (calls / 40.0) * 20.0)

        # All values are now float
        total_score = ar_score + aht_score + volume_score

        scored_rows.append({
            **row,
            'ar_score': round(ar_score, 1),
            'aht_score': round(aht_score, 1),
            'volume_score': round(volume_score, 1),
            'total_score': round(total_score, 1),
            'aht_display': sec_to_hms(aht_sec),
            'total_calls': calls,
            'answered': answered,
            'answer_rate': ar_pct
        })

    # Sort by total_score descending
    scored_rows.sort(key=lambda x: x['total_score'], reverse=True)

    # Display
    for idx, r in enumerate(scored_rows, 1):
        rank = f"🥇" if idx == 1 else f"🥈" if idx == 2 else f"🥉" if idx == 3 else f"{idx:2d}."
        uid = r['user']
        name = (r['full_name'] or '—')[:22]
        calls = r['total_calls']
        answered = r['answered']
        ans_pct = r['answer_rate']

        color = Colors.GREEN if r['total_score'] >= 80 else Colors.YELLOW if r['total_score'] >= 65 else Colors.RESET

        print_color(
            f"{rank:<6}  {uid:<12}  {name:<22}  {calls:>6,}  {answered:>6}  {ans_pct:>6.1f}%  {r['aht_display']:>8}  "
            f"{r['total_score']:>9.1f}",
            color
        )
        print()

    print("═" * 120)
    print(" Score = 50% Answer Rate + 30% AHT balance + 20% Call Volume")
    print("═" * 120 + "\n")

# =============================================================================
# Team Summary
# =============================================================================

def get_team_summary(period='today'):
    """Display team summary for inbound and outbound campaigns"""
    period_display = {'today':'TODAY', 'yesterday':'YESTERDAY', 'week':'THIS WEEK', 'month':'THIS MONTH'}
    title = period_display.get(period, period.upper())
    print_header(f"📊 TEAM SUMMARY - {title}", Colors.MAGENTA)
    
    try:
        date_filter_map = {
            'today': "DATE(c.call_date) = CURDATE()",
            'yesterday': "DATE(c.call_date) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)",
            'week': "c.call_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
            'month': "c.call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)",
        }
        date_filter = date_filter_map.get(period, date_filter_map['week'])
        
        # ===== OUTBOUND SUMMARY =====
        if OUTBOUND_CAMPAIGNS:
            placeholders = ','.join(['%s'] * len(OUTBOUND_CAMPAIGNS))

            totals_query = f"""
            SELECT 
                COUNT(DISTINCT a.user) as active_agents,
                COUNT(DISTINCT a.uniqueid) as total_calls,
                SUM(CASE WHEN a.status IN ('SALE','YPSALE','UPSELL','CROSSSELL') THEN 1 ELSE 0 END) as total_sales,
                SUM(a.talk_sec) as total_talk
            FROM vicidial_agent_log a
            JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
            WHERE {date_filter}
              AND c.campaign_id IN ({placeholders})
            """
            totals = db.execute_query(totals_query, OUTBOUND_CAMPAIGNS)
            
            if totals and totals[0]['total_calls'] > 0:
                o = totals[0]
                calls = to_int(o['total_calls'])
                sales = to_int(o['total_sales'])
                conv = (sales / calls * 100.0) if calls > 0 else 0.0
                active_agents = to_int(o['active_agents'])
                total_talk = to_int(o['total_talk'])

                print(f"\n💰 OUTBOUND TEAM (Sales Campaigns):")
                print("-" * 60)
                print(f"  • Active Agents: {active_agents}")
                print(f"  • Total Calls: {calls:,}")
                print(f"  • Sales: {sales}")
                print(f"  • Conversion Rate: {conv:.2f}%")
                print(f"  • Total Talk Time: {sec_to_hms(total_talk)}")

                if conv > 3.0:
                    print_color("  📈 Sales Performance: EXCELLENT", Colors.GREEN)
                elif conv > 1.0:
                    print_color("  📊 Sales Performance: ACCEPTABLE", Colors.YELLOW)
                else:
                    print_color("  📉 Sales Performance: NEEDS IMPROVEMENT", Colors.RED)

                # List active outbound agents
                agents_query = f"""
                SELECT 
                    a.user,
                    u.full_name,
                    GROUP_CONCAT(DISTINCT c.campaign_id ORDER BY c.campaign_id SEPARATOR ', ') as campaigns,
                    COUNT(DISTINCT a.uniqueid) as agent_calls
                FROM vicidial_agent_log a
                JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
                LEFT JOIN vicidial_users u ON a.user = u.user
                WHERE {date_filter}
                  AND c.campaign_id IN ({placeholders})
                GROUP BY a.user
                ORDER BY agent_calls DESC, a.user
                """

                active_agents_list = db.execute_query(agents_query, OUTBOUND_CAMPAIGNS)

                if active_agents_list:
                    print("\nActive outbound agents:")
                    print("  " + "─" * 70)
                    for i, ag in enumerate(active_agents_list, 1):
                        name = ag['full_name'] or ag['user']
                        campaigns = ag['campaigns'] or '—'
                        calls_count = to_int(ag['agent_calls'])
                        print(f"  {i:2d}. {ag['user']:<12}  ({name:<20})  → {campaigns}  [{calls_count} calls]")
                    print("  " + "─" * 70)
        
        # ===== INBOUND SUMMARY =====
        if INBOUND_CAMPAIGNS:
            placeholders = ','.join(['%s'] * len(INBOUND_CAMPAIGNS))

            totals_query = f"""
            SELECT 
                COUNT(DISTINCT a.user) as active_agents,
                COUNT(DISTINCT a.uniqueid) as total_calls,
                SUM(CASE WHEN a.talk_sec >= 5 THEN 1 ELSE 0 END) as answered,
                SUM(a.talk_sec) as total_talk
            FROM vicidial_agent_log a
            JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
            WHERE {date_filter}
              AND c.campaign_id IN ({placeholders})
            """
            totals = db.execute_query(totals_query, INBOUND_CAMPAIGNS)
            
            if totals and totals[0]['total_calls'] > 0:
                i = totals[0]
                calls = to_int(i['total_calls'])
                answered = to_int(i['answered'])
                rate = (answered / calls * 100.0) if calls > 0 else 0.0
                active_agents = to_int(i['active_agents'])
                total_talk = to_int(i['total_talk'])

                print(f"\n🎯 INBOUND TEAM (Service Campaigns):")
                print("-" * 60)
                print(f"  • Active Agents: {active_agents}")
                print(f"  • Total Calls: {calls:,}")
                print(f"  • Answered: {answered}")
                print(f"  • Answer Rate: {rate:.1f}%")
                print(f"  • Total Talk Time: {sec_to_hms(total_talk)}")

                if rate >= 90.0:
                    print_color("  🎯 Service Level: EXCELLENT", Colors.GREEN)
                elif rate >= 80.0:
                    print_color("  🎯 Service Level: GOOD", Colors.YELLOW)
                else:
                    print_color("  🎯 Service Level: NEEDS IMPROVEMENT", Colors.RED)

                # List active inbound agents
                agents_query = f"""
                SELECT 
                    a.user,
                    u.full_name,
                    GROUP_CONCAT(DISTINCT c.campaign_id ORDER BY c.campaign_id SEPARATOR ', ') as campaigns,
                    COUNT(DISTINCT a.uniqueid) as agent_calls
                FROM vicidial_agent_log a
                JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
                LEFT JOIN vicidial_users u ON a.user = u.user
                WHERE {date_filter}
                  AND c.campaign_id IN ({placeholders})
                GROUP BY a.user
                ORDER BY agent_calls DESC, a.user
                """

                active_agents_list = db.execute_query(agents_query, INBOUND_CAMPAIGNS)

                if active_agents_list:
                    print("\nActive inbound agents:")
                    print("  " + "─" * 70)
                    for i, ag in enumerate(active_agents_list, 1):
                        name = ag['full_name'] or ag['user']
                        campaigns = ag['campaigns'] or '—'
                        calls_count = to_int(ag['agent_calls'])
                        print(f"  {i:2d}. {ag['user']:<12}  ({name:<20})  → {campaigns}  [{calls_count} calls]")
                    print("  " + "─" * 70)
        
        print("\n" + "=" * 70)
    
    except Exception as e:
        print_error(f"Error in team summary: {e}")

# =============================================================================
# Real-time Agent Status
# =============================================================================

def realtime_agent_status():
    """Real-time agent status monitor"""
    print_header("🕐 REAL-TIME AGENT STATUS", Colors.CYAN)
    try:
        query = """
        SELECT 
            l.user,
            u.full_name,
            l.status,
            l.pause_code,
            l.campaign_id,
            l.calls_today,
            TIMESTAMPDIFF(MINUTE, l.last_state_change, NOW()) AS minutes_in_status,
            l.last_call_time
        FROM vicidial_live_agents l
        LEFT JOIN vicidial_users u ON l.user = u.user
        WHERE l.status != 'LOGGEDOUT'
        ORDER BY 
            CASE l.status
                WHEN 'INCALL' THEN 1
                WHEN 'QUEUE' THEN 2
                WHEN 'CLOSER' THEN 3
                WHEN 'READY' THEN 4
                WHEN 'PAUSED' THEN 5
                ELSE 6
            END,
            l.last_state_change DESC
        """
        agents = db.execute_query(query) or []
        
        if agents:
            print(f"\n{'Agent':<12} {'Name':<20} {'Status':<10} {'Campaign':<12} {'Pause':<10} {'Calls Today':<12} {'In Status':<12} {'Last Call':<15}")
            print("-" * 110)
            
            for a in agents:
                name = (a['full_name'] or a['user'])[:20]
                status = a['status']
                color = Colors.GREEN if status == 'INCALL' else Colors.BLUE if status == 'READY' else Colors.YELLOW if status == 'PAUSED' else Colors.RESET
                minutes = to_int(a['minutes_in_status'])
                calls_today = to_int(a['calls_today'])
                
                in_status = f"{minutes} min" if minutes < 60 else f"{minutes//60}h {minutes%60}m"
                last_call = a['last_call_time'].strftime('%H:%M:%S') if a['last_call_time'] else '—'
                
                print_color(
                    f"{a['user']:<12} {name:<20} {status:<10} {a['campaign_id'] or '—':<12} {a['pause_code'] or '—':<10} {calls_today:<12} {in_status:<12} {last_call:<15}",
                    color
                )
        else:
            print_warning("No agents currently logged in")
    except Exception as e:
        print_error(f"Error loading real-time status: {e}")

# =============================================================================
# Agent Dashboard
# =============================================================================

def agent_dashboard():
    """Main agent dashboard function"""
    agents = show_agent_list()
    if not agents:
        return
    
    selected_agent = get_agent_by_selection(agents)
    if not selected_agent:
        return
    
    # Period selection
    print("\nSelect period:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. Last 7 Days")
    print("  4. Last 30 Days")
    period_choice = input("Choice (1-4) [default 3]: ").strip() or '3'
    
    period_map = {'1':'today', '2':'yesterday', '3':'week', '4':'month'}
    period = period_map.get(period_choice, 'week')
    
    # Date filter based on period
    if period == 'today':
        date_filter = "DATE(event_time) = CURDATE()"
        title = "TODAY"
    elif period == 'yesterday':
        date_filter = "DATE(event_time) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
        title = "YESTERDAY"
    elif period == 'week':
        date_filter = "event_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        title = "LAST 7 DAYS"
    else:
        date_filter = "event_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
        title = "LAST 30 DAYS"

    print_header(f"📊 AGENT DASHBOARD - {selected_agent} ({get_agent_name(selected_agent)}) – {title}", Colors.MAGENTA)

    # Basic stats
    stats_query = f"""
    SELECT 
        COUNT(*) AS total_calls,
        SUM(CASE WHEN status IN ('SALE','YPSALE','UPSELL','CROSSSELL') THEN 1 ELSE 0 END) AS sales,
        AVG(talk_sec) AS avg_talk_sec,
        SUM(talk_sec) AS total_talk_sec,
        COUNT(DISTINCT campaign_id) AS campaigns_used,
        MAX(event_time) AS last_call
    FROM vicidial_agent_log
    WHERE user = %s AND {date_filter}
    """

    stats = db.execute_query(stats_query, (selected_agent,))
    
    if stats and stats[0]['total_calls'] > 0:
        s = stats[0]
        total_calls = to_int(s['total_calls'])
        sales = to_int(s['sales'])
        conv = (sales / total_calls * 100.0) if total_calls > 0 else 0.0
        avg_talk_sec = to_float(s['avg_talk_sec'])
        total_talk_sec = to_int(s['total_talk_sec'])
        campaigns_used = to_int(s['campaigns_used'])
        
        print(f"\nPerformance Summary ({title}):")
        print(f"  • Total Calls:          {total_calls:,}")
        print(f"  • Sales:                {sales}")
        print(f"  • Conversion Rate:      {conv:.1f}%")
        print(f"  • Avg Talk Time:        {sec_to_hms(avg_talk_sec)}")
        print(f"  • Total Talk Time:      {sec_to_hms(total_talk_sec)}")
        print(f"  • Campaigns Worked On:  {campaigns_used}")
        
        # Last call with Philippines time
        if s['last_call']:
            # Get Philippines time for last call
            ph_time, ph_time_str = convert_to_ph_time(s['last_call'])
            ph_ago = time_ago_ph(s['last_call'])
            
            print(f"\n  📞 Last Call (Server): {format_datetime(s['last_call'])}")
            if ph_time:
                print_color(f"  📞 Last Call (Philippines): {ph_time_str} ({ph_ago})", Colors.YELLOW)
    else:
        print(f"\nNo activity recorded for {selected_agent} in this period.")
    
    # Recent activity (last 10 events)
    recent_query = f"""
    SELECT 
        event_time,
        status,
        campaign_id,
        talk_sec
    FROM vicidial_agent_log
    WHERE user = %s AND {date_filter}
    ORDER BY event_time DESC
    LIMIT 10
    """
    
    recent = db.execute_query(recent_query, (selected_agent,))
    
    if recent:
        print("\nRecent Activity (last 10 events):")
        print(f"{'Server Time':<20} {'Manila Time':<20} {'Status':<8} {'Campaign':<12} {'Talk Time':<12}")
        print("-" * 85)
        
        for r in recent:
            server_t = r['event_time']
            manila_t, manila_str = convert_to_ph_time(server_t)
            status = r['status'] or '—'
            camp = r['campaign_id'] or '—'
            
            talk_sec = to_int(r['talk_sec'])
            talk_str = sec_to_hms(talk_sec) if talk_sec is not None else "—"
            
            print(f"  {format_datetime(server_t):<20} {manila_str:<20} {status:<8} {camp:<12} {talk_str:<12}")
    else:
        print("  No recent events in this period.")

    input("\nPress Enter to continue...")

# =============================================================================
# Agent Login History - ENHANCED with daily grouping and productivity metrics
# =============================================================================

def agent_login_history(agent_id, days=7):
    """Show agent login/logout history grouped by day with Manila time conversion,
       session analysis, productivity metrics, and PDF export option"""
    print_header(f"📅 LOGIN HISTORY - {agent_id} (Last {days} days)", Colors.CYAN)
    try:
        # Use vicidial_agent_log with actual columns from the table
        query = """
        SELECT 
            event_time,
            status as event_type,
            campaign_id,
            talk_sec,
            wait_sec,
            pause_sec,
            dispo_sec,
            user_group,
            uniqueid
        FROM vicidial_agent_log
        WHERE user = %s 
          AND event_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY event_time DESC
        """
        
        history = db.execute_query(query, (agent_id, days))
        
        if not history:
            print_warning(f"No activity found for {agent_id} in the last {days} days")
            input("\nPress Enter to continue...")
            return
        
        # Group records by date (Manila time)
        daily_records = defaultdict(list)
        
        for h in history:
            # Convert to Manila time for grouping
            server_t = h['event_time']
            ph_time, ph_str = convert_to_ph_time(server_t)
            if ph_time:
                date_key = ph_time.strftime('%Y-%m-%d')
                daily_records[date_key].append({
                    **h,
                    'ph_time': ph_time,
                    'ph_time_str': ph_str,
                    'server_time': server_t
                })
        
        # Sort dates in descending order
        sorted_dates = sorted(daily_records.keys(), reverse=True)
        
        # Prepare data for PDF export
        pdf_daily_data = []
        
        # For each day, display activity grouped by session
        for date_key in sorted_dates:
            records = daily_records[date_key]
            # Sort records chronologically for session analysis
            records.sort(key=lambda x: x['ph_time'])
            
            # Calculate daily statistics
            daily_talk_sec = sum(to_int(r.get('talk_sec', 0)) for r in records)
            daily_wait_sec = sum(to_int(r.get('wait_sec', 0)) for r in records)
            daily_pause_sec = sum(to_int(r.get('pause_sec', 0)) for r in records)
            unique_calls = len(set(r.get('uniqueid') for r in records if r.get('uniqueid')))
            
            # Determine login and logout times
            login_times = [r['ph_time'] for r in records if 'LOGIN' in str(r['event_type'])]
            logout_times = [r['ph_time'] for r in records if 'LOGOUT' in str(r['event_type'])]
            
            # Calculate active hours (from first login to last logout)
            active_hours = 0
            first_login = None
            last_logout = None
            active_period = "N/A"
            if login_times and logout_times:
                first_login = min(login_times)
                last_logout = max(logout_times)
                active_hours = (last_logout - first_login).total_seconds() / 3600
                active_period = f"{first_login.strftime('%H:%M')} - {last_logout.strftime('%H:%M')}"
            
            # Calculate actual work time (talk + wait + pause)
            actual_work_sec = daily_talk_sec + daily_wait_sec + daily_pause_sec
            actual_work_hours = actual_work_sec / 3600
            
            # Calculate efficiency (talk time / active hours)
            efficiency = (daily_talk_sec / (active_hours * 3600) * 100) if active_hours > 0 else 0
            
            # Productivity rating
            if efficiency >= 70:
                productivity_rating = "🌟 EXCELLENT - High talk time ratio"
                prod_color = Colors.GREEN
            elif efficiency >= 50:
                productivity_rating = "✅ GOOD - Good talk time ratio"
                prod_color = Colors.CYAN
            elif efficiency >= 30:
                productivity_rating = "⚠️ FAIR - Moderate talk time ratio"
                prod_color = Colors.YELLOW
            else:
                productivity_rating = "❌ POOR - Low talk time ratio"
                prod_color = Colors.RED
            
            # Display daily header
            print("\n" + "=" * 120)
            print_color(f"📆 {date_key}", Colors.YELLOW)
            print("=" * 120)
            
            # Daily summary
            print(f"\n📊 DAILY SUMMARY:")
            print(f"  • Active Hours:        {active_hours:.2f} hrs ({active_period})")
            print(f"  • Talk Time:           {sec_to_hms(daily_talk_sec)} ({daily_talk_sec/3600:.2f} hrs)")
            print(f"  • Wait Time:           {sec_to_hms(daily_wait_sec)}")
            print(f"  • Pause Time:          {sec_to_hms(daily_pause_sec)}")
            print(f"  • Actual Work Time:    {sec_to_hms(actual_work_sec)} ({actual_work_hours:.2f} hrs)")
            print(f"  • Total Calls:         {unique_calls} unique calls")
            print(f"  • Efficiency (Talk/Active): {efficiency:.1f}%")
            print_color(f"  • Productivity:        {productivity_rating}", prod_color)
            
            # Session breakdown (group by session between login/logout)
            print(f"\n📋 SESSION BREAKDOWN:")
            print(f"{'Time (PH)':<25} {'Status':<15} {'Campaign':<12} {'Talk':<10} {'Wait':<8} {'Pause':<8} {'UniqueID':<15}")
            print("-" * 110)
            
            # Group into sessions based on login/logout
            session_records = []
            current_session = []
            sessions_data = []
            
            for r in records:
                event_type = r['event_type'] or 'UNKNOWN'
                current_session.append(r)
                
                # When we see a LOGOUT, end current session
                if 'LOGOUT' in str(event_type) and current_session:
                    session_records.append(current_session)
                    current_session = []
            
            # Add any remaining records as a session
            if current_session:
                session_records.append(current_session)
            
            # Display each session and collect data for PDF
            session_idx = 0
            for session in session_records:
                if not session:
                    continue
                
                session_idx += 1
                session_start = session[0]['ph_time']
                session_end = session[-1]['ph_time']
                session_duration = (session_end - session_start).total_seconds() / 60  # minutes
                
                # Calculate session stats
                session_talk = sum(to_int(r.get('talk_sec', 0)) for r in session)
                session_wait = sum(to_int(r.get('wait_sec', 0)) for r in session)
                session_pause = sum(to_int(r.get('pause_sec', 0)) for r in session)
                session_calls = len(set(r.get('uniqueid') for r in session if r.get('uniqueid')))
                
                # Store session data for PDF
                sessions_data.append({
                    'index': session_idx,
                    'start': session_start.strftime('%H:%M'),
                    'end': session_end.strftime('%H:%M'),
                    'duration': int(session_duration),
                    'calls': session_calls,
                    'talk_str': sec_to_hms(session_talk),
                    'wait_str': sec_to_hms(session_wait),
                    'pause_str': sec_to_hms(session_pause)
                })
                
                print_color(f"\n  Session {session_idx}: {session_start.strftime('%H:%M')} - {session_end.strftime('%H:%M')} ({session_duration:.0f} min)", Colors.MAGENTA)
                print(f"    Calls: {session_calls} | Talk: {sec_to_hms(session_talk)} | Wait: {sec_to_hms(session_wait)} | Pause: {sec_to_hms(session_pause)}")
                
                # Show detailed events in this session (limit to 15 for readability)
                for r in session[:15]:
                    event_type = r['event_type'] or 'UNKNOWN'
                    talk_sec = to_int(r.get('talk_sec', 0))
                    wait_sec = to_int(r.get('wait_sec', 0))
                    pause_sec = to_int(r.get('pause_sec', 0))
                    uniqueid = r.get('uniqueid', '')[-12:] if r.get('uniqueid') else '—'
                    
                    # Color code by status
                    if 'INCALL' in str(event_type):
                        color = Colors.GREEN
                    elif 'READY' in str(event_type):
                        color = Colors.BLUE
                    elif 'PAUSE' in str(event_type):
                        color = Colors.YELLOW
                    elif 'LOGOUT' in str(event_type):
                        color = Colors.RED
                    elif 'LOGIN' in str(event_type):
                        color = Colors.GREEN
                    else:
                        color = Colors.RESET
                    
                    talk_str = sec_to_hms(talk_sec) if talk_sec > 0 else "—"
                    wait_str = sec_to_hms(wait_sec) if wait_sec > 0 else "—"
                    pause_str = sec_to_hms(pause_sec) if pause_sec > 0 else "—"
                    
                    print_color(
                        f"    {r['ph_time_str'][11:19]:<25} {event_type:<15} {r['campaign_id'] or '—':<12} {talk_str:<10} {wait_str:<8} {pause_str:<8} {uniqueid:<15}",
                        color
                    )
                
                if len(session) > 15:
                    print(f"    ... and {len(session) - 15} more events")
            
            # Display the detailed daily timeline (compact view)
            print(f"\n📈 HOURLY ACTIVITY HEATMAP:")
            hourly_counts = defaultdict(int)
            hourly_talk = defaultdict(int)
            hourly_data = []
            
            for r in records:
                hour = r['ph_time'].strftime('%H:00')
                hourly_counts[hour] += 1
                hourly_talk[hour] += to_int(r.get('talk_sec', 0))
            
            # Display hourly breakdown
            print(f"{'Hour':<10} {'Events':<8} {'Talk Time':<12} {'Activity':<50}")
            print("-" * 80)
            
            # Find max count for scaling the bar
            max_count = max(hourly_counts.values()) if hourly_counts else 1
            
            for hour in range(0, 24):
                hour_key = f"{hour:02d}:00"
                count = hourly_counts.get(hour_key, 0)
                talk_sec = hourly_talk.get(hour_key, 0)
                talk_str = sec_to_hms(talk_sec)
                
                if count > 0 or talk_sec > 0:
                    # Create activity bar
                    bar_length = int((count / max_count) * 40) if max_count > 0 else 0
                    bar = "█" * bar_length + "░" * (40 - bar_length)
                    
                    # Color based on activity level
                    if count >= 10:
                        color = Colors.GREEN
                    elif count >= 5:
                        color = Colors.YELLOW
                    elif count > 0:
                        color = Colors.CYAN
                    else:
                        color = Colors.RESET
                    
                    print_color(f"{hour_key:<10} {count:<8} {talk_str:<12} {bar}", color)
                    
                    # Store hourly data for PDF
                    hourly_data.append({
                        'hour': hour_key,
                        'count': count,
                        'talk_str': talk_str
                    })
            
            print("-" * 80)
            
            # Store daily data for PDF
            pdf_daily_data.append({
                'date': date_key,
                'active_hours': active_hours,
                'active_period': active_period,
                'talk_str': sec_to_hms(daily_talk_sec),
                'wait_str': sec_to_hms(daily_wait_sec),
                'pause_str': sec_to_hms(daily_pause_sec),
                'work_str': sec_to_hms(actual_work_sec),
                'unique_calls': unique_calls,
                'efficiency': efficiency,
                'productivity_rating': productivity_rating,
                'sessions': sessions_data,
                'hourly_data': hourly_data
            })
        
        # Overall summary for all days
        print("\n" + "=" * 120)
        print_color("📊 OVERALL SUMMARY (All Days)", Colors.CYAN)
        print("=" * 120)
        
        total_talk = sum(to_int(r.get('talk_sec', 0)) for r in history)
        total_wait = sum(to_int(r.get('wait_sec', 0)) for r in history)
        total_pause = sum(to_int(r.get('pause_sec', 0)) for r in history)
        unique_calls_total = len(set(r.get('uniqueid') for r in history if r.get('uniqueid')))
        total_days = len(sorted_dates)
        
        print(f"  • Days Analyzed:        {total_days}")
        print(f"  • Total Talk Time:      {sec_to_hms(total_talk)} ({total_talk/3600:.2f} hrs)")
        print(f"  • Total Wait Time:      {sec_to_hms(total_wait)}")
        print(f"  • Total Pause Time:     {sec_to_hms(total_pause)}")
        print(f"  • Total Unique Calls:   {unique_calls_total}")
        
        if total_days > 0:
            print(f"  • Avg Talk/Day:         {sec_to_hms(total_talk / total_days)}")
            print(f"  • Avg Calls/Day:        {unique_calls_total / total_days:.1f}")
        
        # Performance rating
        avg_talk_per_day = total_talk / total_days if total_days > 0 else 0
        avg_calls_per_day = unique_calls_total / total_days if total_days > 0 else 0
        
        if avg_talk_per_day >= 14400:  # 4 hours
            performance_rating = "🌟 EXCELLENT (High talk volume)"
            perf_color = Colors.GREEN
        elif avg_talk_per_day >= 7200:  # 2 hours
            performance_rating = "✅ GOOD (Moderate talk volume)"
            perf_color = Colors.CYAN
        elif avg_talk_per_day >= 3600:  # 1 hour
            performance_rating = "⚠️ FAIR (Low talk volume)"
            perf_color = Colors.YELLOW
        else:
            performance_rating = "❌ POOR (Very low talk volume)"
            perf_color = Colors.RED
        
        print(f"\n💡 PERFORMANCE ASSESSMENT:")
        print_color(f"  • Talk Time: {sec_to_hms(avg_talk_per_day)}/day - {performance_rating}", perf_color)
        
        if avg_calls_per_day >= 30:
            print_color(f"  • Call Volume: {avg_calls_per_day:.1f} calls/day - 🌟 HIGH", Colors.GREEN)
        elif avg_calls_per_day >= 15:
            print_color(f"  • Call Volume: {avg_calls_per_day:.1f} calls/day - ✅ MODERATE", Colors.CYAN)
        elif avg_calls_per_day >= 5:
            print_color(f"  • Call Volume: {avg_calls_per_day:.1f} calls/day - ⚠️ LOW", Colors.YELLOW)
        else:
            print_color(f"  • Call Volume: {avg_calls_per_day:.1f} calls/day - ❌ VERY LOW", Colors.RED)
        
        print("\n" + "=" * 120)
        
        # PDF Export Option
        print("\n" + "=" * 80)
        print_color("📄 PDF EXPORT OPTION", Colors.CYAN)
        print("=" * 80)
        
        # Prepare overall summary for PDF
        overall_summary = {
            'total_days': total_days,
            'total_talk_str': sec_to_hms(total_talk),
            'total_wait_str': sec_to_hms(total_wait),
            'total_pause_str': sec_to_hms(total_pause),
            'unique_calls_total': unique_calls_total,
            'avg_talk_str': sec_to_hms(total_talk / total_days) if total_days > 0 else "0:00",
            'avg_calls_per_day': avg_calls_per_day,
            'performance_rating': performance_rating
        }
        
        export_choice = input("\n💾 Save this report as PDF? (y/n): ").strip().lower()
        
        if export_choice == 'y':
            print("\n📄 Generating PDF report...")
            pdf_path = export_login_history_pdf(agent_id, days, pdf_daily_data, overall_summary)
            
            if pdf_path:
                print(f"✅ PDF Report saved to: {pdf_path}")
                
                open_file = input(f"\n{Colors.CYAN}Open PDF report? (y/N): {Colors.RESET}").strip().lower()
                if open_file == 'y' and os.path.exists(pdf_path):
                    os.startfile(str(pdf_path))
            else:
                print("❌ Failed to generate PDF report")
        else:
            print("📝 Report not saved to PDF")
        
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to continue...")

# =============================================================================
# Main Menu
# =============================================================================

def show_top_performers():
    """Main top performers menu"""
    while True:
        print_header("🏆 TOP PERFORMERS LEADERBOARDS", Colors.GREEN)
        print("  1. Top Inbound Performers (Weighted Score)")
        print("  2. Top Outbound Performers")
        print("  3. Team Summary (Inbound + Outbound)")
        print("  4. Agent Dashboard (Individual)")
        print("  5. Real-time Agent Status")
        print("  6. Agent Login/Logout History (with PDF Export)")
        print("  0. Back")
        print("-"*60)
        
        ch = input("Select: ").strip()
        
        if ch == '0':
            break
        elif ch == '4':
            agent_dashboard()
        elif ch == '5':
            realtime_agent_status()
            input("\nPress Enter to continue...")
        elif ch == '6':
            agent_id = input("\nEnter agent username: ").strip()
            if agent_id:
                days_input = input("Days to analyze (default 7): ").strip()
                days = int(days_input) if days_input.isdigit() else 7
                agent_login_history(agent_id, days)
        elif ch in ('1','2','3'):
            print("\n  1. Today   2. Yesterday   3. This Week   4. This Month")
            p = input("Period (1-4) [default 3]: ").strip() or '3'
            period = {'1':'today','2':'yesterday','3':'week','4':'month'}.get(p, 'week')
            
            if ch == '1':
                get_top_inbound_performers(period)
            elif ch == '2':
                get_top_outbound_performers(period)
            elif ch == '3':
                get_team_summary(period)
            input("\nPress Enter to continue...")
        else:
            print_error("Invalid choice")

if __name__ == "__main__":
    show_top_performers()