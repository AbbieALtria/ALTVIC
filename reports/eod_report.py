#!/usr/bin/env python3
# =============================================================================
# File:         eod_report.py
# Version:      4.2.0
# Date:         2026-03-17
# Description:  Enhanced End of Day with Ghost Call separation - OPTIMIZED
# Update:       Fixed table alias issue in yesterday's comparison query
# Location:     D:/Altria_Ops/reports/eod_report.py
# =============================================================================

from core.database import db
from core.email_integration import get_email_stats_by_agent, get_email_summary, ensure_mapping_table
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info
from utils.formatter import sec_to_hms
import os
import csv
import pytz
import time
from collections import defaultdict
from pathlib import Path
from decimal import Decimal

# =============================================================================
# Safe conversion helpers
# =============================================================================

def safe_int(value):
    """Safely convert any value to int"""
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

def safe_float(value):
    """Safely convert any value to float"""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

# =============================================================================
# Exports Directory Helper (consistent with pdf_generator)
# =============================================================================

def ensure_exports_dir():
    """Get exports directory - consistent with pdf_generator"""
    import sys
    import os
    from pathlib import Path
    
    try:
        if getattr(sys, 'frozen', False):
            # Running as executable
            base_dir = Path(os.path.dirname(sys.executable))
            exports_dir = base_dir / 'exports'
        else:
            # Running as script
            exports_dir = Path(__file__).parent / 'exports'
        
        exports_dir.mkdir(parents=True, exist_ok=True)
        return exports_dir
    except Exception as e:
        print_warning(f"Exports dir fallback: {e}")
        import tempfile
        fallback_dir = Path(tempfile.gettempdir()) / 'Altria_Exports'
        fallback_dir.mkdir(exist_ok=True)
        return fallback_dir

# =============================================================================
# Timezone Helper (Server + EST + PST)
# =============================================================================

def get_timezone_info():
    """Return current time in Server, EST, and PST"""
    utc_now = datetime.utcnow()
    
    # Server time (from MySQL)
    server_row = db.execute_query("SELECT NOW() as now")
    server_now = server_row[0]['now'] if server_row else utc_now
    
    # EST & PST
    est_tz = pytz.timezone('America/New_York')
    pst_tz = pytz.timezone('America/Los_Angeles')
    
    est_now = utc_now.replace(tzinfo=pytz.UTC).astimezone(est_tz)
    pst_now = utc_now.replace(tzinfo=pytz.UTC).astimezone(pst_tz)
    
    return {
        'server': server_now,
        'est': est_now,
        'pst': pst_now,
        'est_date': est_now.date()
    }

def print_timezone_banner():
    """Show clear timezone info at top of every report"""
    tz = get_timezone_info()
    print_header("🕒 TIMEZONE STATUS", Colors.CYAN)
    print(f"  Server time : {tz['server'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  EST time    : {tz['est'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  PST time    : {tz['pst'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Using EST for EOD logic → Today = {tz['est_date']}")
    print("=" * 80)

# =============================================================================
# Date Logic (EST-based)
# =============================================================================

def get_est_target_date(choice):
    """Return correct date based on EST (what you want for EOD)"""
    tz = get_timezone_info()
    est_today = tz['est_date']
    
    if choice == '1':      # Today (EST)
        return est_today
    elif choice == '2':    # Yesterday (EST)
        return est_today - timedelta(days=1)
    elif choice == '3':    # Specific date
        date_str = input("Enter date (YYYY-MM-DD): ").strip()
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            print_error("Invalid date")
            return est_today - timedelta(days=1)
    else:
        return est_today - timedelta(days=1)  # default = yesterday

def get_selected_campaigns():
    """Get list of campaigns to include in report"""
    try:
        query = """
        SELECT DISTINCT campaign_id
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        ORDER BY campaign_id
        """
        campaigns = db.execute_query(query)
        campaign_list = [c['campaign_id'] for c in campaigns] if campaigns else []
        
        if not campaign_list:
            print_warning("No campaigns found with recent activity")
            return None
        
        print("\n📋 Available Campaigns:")
        print("-" * 80)
        
        # Display in columns
        col_width = 25
        cols = 3
        
        for i, camp in enumerate(campaign_list, 1):
            display = f"{i:3}. {camp}"
            if len(display) < col_width:
                display = display.ljust(col_width)
            print(display, end="")
            if i % cols == 0:
                print()
        
        if len(campaign_list) % cols != 0:
            print()
        
        print("-" * 80)
        print("Enter campaign numbers (comma-separated) or 'all':")
        choice = input("> ").strip().lower()
        
        if choice == 'all' or choice == '':
            return campaign_list
        else:
            selected = []
            for part in choice.split(','):
                part = part.strip()
                if '-' in part:
                    try:
                        start, end = map(int, part.split('-'))
                        for i in range(start, min(end, len(campaign_list)) + 1):
                            selected.append(campaign_list[i-1])
                    except:
                        pass
                elif part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(campaign_list):
                        selected.append(campaign_list[idx])
            return selected if selected else campaign_list
            
    except Exception as e:
        print_error(f"Error loading campaigns: {e}")
        return None

# =============================================================================
# Export Functions
# =============================================================================

def export_to_csv(report_data, filename=None):
    """Export report to CSV with ghost calls separated"""
    if not report_data:
        print_warning("No data to export")
        return False
    
    # Use consistent exports directory
    exports_dir = ensure_exports_dir()
    
    if not filename:
        filename = exports_dir / f"eod_report_{report_data['date']}.csv"
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow(['EOD Report', str(report_data['date'])])
            writer.writerow([])
            
            # Overall stats with ghost calls
            writer.writerow(['OVERALL STATISTICS (including ghost calls)'])
            writer.writerow(['Total Calls', 'Valid Calls', 'Ghost Calls', 'Ghost %', 
                           'Answered', 'Answer %', 'Abandoned', 'Abandon %', 
                           'Service Level', 'Avg Talk (valid)', 'Total Talk'])
            writer.writerow([
                report_data['total_calls'],
                report_data['valid_calls'],
                report_data['ghost_calls'],
                f"{report_data['ghost_pct']:.1f}%",
                report_data['answered'],
                f"{report_data['ans_rate']:.1f}%",
                report_data['abandoned'],
                f"{report_data['abd_rate']:.1f}%",
                f"{report_data.get('sl_pct', 0):.1f}%",
                sec_to_hms(report_data['avg_talk']),
                sec_to_hms(report_data['total_talk_sec'])
            ])
            writer.writerow([])
            
            # Campaign breakdown
            writer.writerow(['CAMPAIGN BREAKDOWN'])
            writer.writerow(['Campaign', 'Total', 'Valid', 'Ghost', 'Ghost%', 
                           'Answered', 'Ans%', 'Abandoned', 'Abd%', 'SL%'])
            for c in report_data['by_campaign']:
                writer.writerow([
                    c['campaign_id'],
                    c['calls'],
                    c['valid_calls'],
                    c['ghost_calls'],
                    f"{c['ghost_pct']:.1f}",
                    c['answered'] or 0,
                    f"{c['ans_pct']:.1f}",
                    c['abandoned'] or 0,
                    f"{c['abd_pct']:.1f}",
                    f"{c.get('sl_pct', 0):.1f}"
                ])
            writer.writerow([])
            
            # Hourly breakdown
            writer.writerow(['HOURLY BREAKDOWN'])
            writer.writerow(['Hour', 'Total', 'Valid', 'Ghost', 'Answered', 'Ans%'])
            for h in report_data['hourly']:
                writer.writerow([
                    f"{h['hour']:02d}:00",
                    h['calls'],
                    h['valid_calls'],
                    h['ghost_calls'],
                    h['answered'] or 0,
                    f"{h['ans_pct']:.1f}"
                ])
            writer.writerow([])
            
            # Top agents (valid calls only)
            writer.writerow(['TOP AGENTS (Valid Calls Only)'])
            writer.writerow(['Agent', 'Name', 'Valid Calls', 'Ghost Calls', 'Talk Time', 'Avg Call'])
            for a in report_data['agents']:
                writer.writerow([
                    a['user'],
                    a.get('full_name', 'Unknown'),
                    a['valid_calls'],
                    a['ghost_calls'],
                    sec_to_hms(a['total_talk'] or 0),
                    sec_to_hms(a['avg_talk'] or 0)
                ])
        
        print_success(f"✅ Exported to: {filename}")
        return True
        
    except Exception as e:
        print_error(f"Export failed: {e}")
        return False

def export_to_excel(report_data):
    """Export to Excel with formatting and ghost call separation"""
    try:
        import pandas as pd
    except ImportError:
        print_error("Excel export requires pandas. Install: pip install pandas openpyxl")
        return False
    
    exports_dir = ensure_exports_dir()
    filename = exports_dir / f"eod_report_{report_data['date']}.xlsx"
    
    try:
        # Create DataFrames
        overall_df = pd.DataFrame([{
            'Date': report_data['date'],
            'Total Calls': report_data['total_calls'],
            'Valid Calls': report_data['valid_calls'],
            'Ghost Calls': report_data['ghost_calls'],
            'Ghost %': f"{report_data['ghost_pct']:.1f}",
            'Answered': report_data['answered'],
            'Answer %': f"{report_data['ans_rate']:.1f}",
            'Abandoned': report_data['abandoned'],
            'Abandon %': f"{report_data['abd_rate']:.1f}",
            'Service Level %': f"{report_data.get('sl_pct', 0):.1f}",
            'Avg Talk (valid)': sec_to_hms(report_data['avg_talk']),
            'Total Talk': sec_to_hms(report_data['total_talk_sec'])
        }])
        
        campaign_data = []
        for c in report_data['by_campaign']:
            campaign_data.append({
                'Campaign': c['campaign_id'],
                'Total': c['calls'],
                'Valid': c['valid_calls'],
                'Ghost': c['ghost_calls'],
                'Ghost %': f"{c['ghost_pct']:.1f}",
                'Answered': c['answered'] or 0,
                'Answer %': f"{c['ans_pct']:.1f}",
                'Abandoned': c['abandoned'] or 0,
                'Abandon %': f"{c['abd_pct']:.1f}",
                'Service Level %': f"{c.get('sl_pct', 0):.1f}"
            })
        campaign_df = pd.DataFrame(campaign_data)
        
        hourly_data = []
        for h in report_data['hourly']:
            hourly_data.append({
                'Hour': f"{h['hour']:02d}:00",
                'Total': h['calls'],
                'Valid': h['valid_calls'],
                'Ghost': h['ghost_calls'],
                'Answered': h['answered'] or 0,
                'Answer %': f"{h['ans_pct']:.1f}"
            })
        hourly_df = pd.DataFrame(hourly_data)
        
        agent_data = []
        for a in report_data['agents']:
            agent_data.append({
                'Agent': a['user'],
                'Name': a.get('full_name', 'Unknown'),
                'Valid Calls': a['valid_calls'],
                'Ghost Calls': a['ghost_calls'],
                'Talk Time': sec_to_hms(a['total_talk'] or 0),
                'Avg Call': sec_to_hms(a['avg_talk'] or 0)
            })
        agent_df = pd.DataFrame(agent_data)
        
        # Write to Excel
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            overall_df.to_excel(writer, sheet_name='Overview', index=False)
            campaign_df.to_excel(writer, sheet_name='Campaigns', index=False)
            hourly_df.to_excel(writer, sheet_name='Hourly', index=False)
            agent_df.to_excel(writer, sheet_name='Top Agents', index=False)
        
        print_success(f"✅ Exported to Excel: {filename}")
        return True
        
    except Exception as e:
        print_error(f"Excel export failed: {e}")
        return False

# =============================================================================
# Main Report Function - OPTIMIZED Single Query Approach
# =============================================================================

def generate_eod_report(target_date=None, campaigns=None):
    """Generate EOD report for specified date and campaigns - OPTIMIZED for speed"""
    if target_date is None:
        target_date = get_est_target_date('2')  # default = yesterday EST
    
    print_timezone_banner()
    print(f"📊 Generating EOD report for **EST date**: {target_date}")
    print(f"   Ghost calls: 0-second calls with no agent (excluded from averages)")
    
    # Build date range (EST day)
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())
    
    # Build campaign filter for main query (with alias 'c')
    campaign_filter = ""
    params = [start_dt, end_dt]
    
    if campaigns and len(campaigns) > 0:
        placeholders = ','.join(['%s'] * len(campaigns))
        campaign_filter = f" AND c.campaign_id IN ({placeholders})"
        params.extend(campaigns)
    
    try:
        # Check live agents (fast query)
        live_count = db.execute_query("""
            SELECT COUNT(*) as count FROM vicidial_live_agents 
            WHERE status IN ('READY', 'INCALL', 'PAUSE')
        """)[0]['count']
        
        # ===== SINGLE QUERY TO GET ALL DATA =====
        print("   Loading data... (this may take a moment)")
        start_time = time.time()
        
        # Optimized query to get all needed data in one pass
        all_data_query = f"""
        SELECT 
            c.campaign_id,
            HOUR(c.call_date) as hour,
            c.uniqueid,
            c.length_in_sec,
            c.queue_seconds,
            c.term_reason,
            a.user,
            a.talk_sec,
            u.full_name
        FROM vicidial_closer_log c
        LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE c.call_date BETWEEN %s AND %s
        {campaign_filter}
        ORDER BY c.call_date
        """
        
        rows = db.execute_query(all_data_query, params) or []
        
        elapsed = time.time() - start_time
        print(f"   Loaded {len(rows)} records in {elapsed:.1f} seconds")
        
        if not rows:
            print_warning(f"No data found for {target_date}")
            return None
        
        # ===== PROCESS DATA IN MEMORY =====
        print("   Processing data...")
        process_start = time.time()
        
        # Initialize counters
        total_calls = len(rows)
        valid_calls = 0
        ghost_calls = 0
        answered = 0
        abandoned = 0
        sl_20 = 0
        total_talk_sec = 0
        total_queue_sec = 0
        queue_count = 0
        
        # Use dictionaries for aggregation
        campaigns_dict = {}
        hourly_dict = {}
        agents_dict = {}
        unique_agents = set()
        
        for row in rows:
            length = safe_int(row['length_in_sec'])
            queue = safe_int(row['queue_seconds'])
            talk = safe_int(row['talk_sec'])
            term = row['term_reason'] or ''
            has_agent = row['user'] is not None
            
            # Determine call types
            is_valid = has_agent and length >= 5
            is_ghost = not has_agent and length == 0
            is_answered = talk >= 5
            is_abandoned = term in ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') or (length == 0 and queue > 0)
            is_sl_20 = queue <= 20 and is_answered
            
            # Update totals
            if is_valid:
                valid_calls += 1
                total_talk_sec += length
            if is_ghost:
                ghost_calls += 1
            if is_answered:
                answered += 1
            if is_abandoned:
                abandoned += 1
            if is_sl_20:
                sl_20 += 1
            
            # Track unique agents
            if row['user']:
                unique_agents.add(row['user'])
            
            # Queue time tracking (only for answered calls)
            if queue > 0 and is_answered:
                total_queue_sec += queue
                queue_count += 1
            
            # Campaign aggregation
            camp_id = row['campaign_id'] or 'UNKNOWN'
            if camp_id not in campaigns_dict:
                campaigns_dict[camp_id] = {
                    'calls': 0, 'valid_calls': 0, 'ghost_calls': 0,
                    'answered': 0, 'abandoned': 0, 'sl_20': 0,
                    'total_talk': 0, 'queue_total': 0, 'queue_count': 0
                }
            
            camp = campaigns_dict[camp_id]
            camp['calls'] += 1
            if is_valid:
                camp['valid_calls'] += 1
                camp['total_talk'] += length
            if is_ghost:
                camp['ghost_calls'] += 1
            if is_answered:
                camp['answered'] += 1
            if is_abandoned:
                camp['abandoned'] += 1
            if is_sl_20:
                camp['sl_20'] += 1
            if queue > 0 and is_answered:
                camp['queue_total'] += queue
                camp['queue_count'] += 1
            
            # Hourly aggregation
            hour = row['hour'] if row['hour'] is not None else 0
            if hour not in hourly_dict:
                hourly_dict[hour] = {
                    'calls': 0, 'valid_calls': 0, 'ghost_calls': 0, 'answered': 0
                }
            
            hr = hourly_dict[hour]
            hr['calls'] += 1
            if is_valid:
                hr['valid_calls'] += 1
            if is_ghost:
                hr['ghost_calls'] += 1
            if is_answered:
                hr['answered'] += 1
            
            # Agent aggregation (only for valid calls)
            if row['user'] and is_valid:
                user = row['user']
                if user not in agents_dict:
                    agents_dict[user] = {
                        'user': user,
                        'full_name': row['full_name'] or user,
                        'valid_calls': 0,
                        'ghost_calls': 0,
                        'total_talk': 0,
                        'talk_count': 0
                    }
                
                agent = agents_dict[user]
                agent['valid_calls'] += 1
                agent['total_talk'] += talk
                agent['talk_count'] += 1
                
                # Count ghost calls for agent (if any)
                if is_ghost:
                    agent['ghost_calls'] += 1
        
        # Calculate averages
        avg_talk_sec = total_talk_sec / valid_calls if valid_calls > 0 else 0
        avg_queue_sec = total_queue_sec / queue_count if queue_count > 0 else 0
        
        # Calculate percentages
        ghost_pct = (ghost_calls / total_calls * 100) if total_calls > 0 else 0
        ans_rate = (answered / valid_calls * 100) if valid_calls > 0 else 0
        abd_rate = (abandoned / valid_calls * 100) if valid_calls > 0 else 0
        sl_pct = (sl_20 / answered * 100) if answered > 0 else 0
        
        # Format campaign data
        by_campaign = []
        for camp_id, camp in campaigns_dict.items():
            c_valid = camp['valid_calls']
            c_answered = camp['answered']
            by_campaign.append({
                'campaign_id': camp_id,
                'calls': camp['calls'],
                'valid_calls': c_valid,
                'ghost_calls': camp['ghost_calls'],
                'ghost_pct': (camp['ghost_calls'] / camp['calls'] * 100) if camp['calls'] > 0 else 0,
                'answered': camp['answered'],
                'ans_pct': (camp['answered'] / c_valid * 100) if c_valid > 0 else 0,
                'abandoned': camp['abandoned'],
                'abd_pct': (camp['abandoned'] / c_valid * 100) if c_valid > 0 else 0,
                'sl_20': camp['sl_20'],
                'sl_pct': (camp['sl_20'] / c_answered * 100) if c_answered > 0 else 0,
                'avg_talk': camp['total_talk'] / c_valid if c_valid > 0 else 0,
                'avg_queue': camp['queue_total'] / camp['queue_count'] if camp['queue_count'] > 0 else 0
            })
        
        # Sort campaigns by calls
        by_campaign.sort(key=lambda x: x['calls'], reverse=True)
        
        # Format hourly data
        hourly = []
        for hour in sorted(hourly_dict.keys()):
            hr = hourly_dict[hour]
            hourly.append({
                'hour': hour,
                'calls': hr['calls'],
                'valid_calls': hr['valid_calls'],
                'ghost_calls': hr['ghost_calls'],
                'answered': hr['answered'],
                'ans_pct': (hr['answered'] / hr['valid_calls'] * 100) if hr['valid_calls'] > 0 else 0
            })
        
        # Format agent data
        agents = []
        for user, agent in agents_dict.items():
            agents.append({
                'user': user,
                'full_name': agent['full_name'],
                'valid_calls': agent['valid_calls'],
                'ghost_calls': agent['ghost_calls'],
                'total_talk': agent['total_talk'],
                'avg_talk': agent['total_talk'] / agent['talk_count'] if agent['talk_count'] > 0 else 0
            })
        
        # Sort agents by valid calls
        agents.sort(key=lambda x: x['valid_calls'], reverse=True)
        agents = agents[:20]  # Limit to top 20
        
        # ===== GET YESTERDAY'S DATA FOR COMPARISON =====
        # Build a separate filter without the 'c.' alias for this query
        yesterday = target_date - timedelta(days=1)
        yest_start = datetime.combine(yesterday, datetime.min.time())
        yest_end = datetime.combine(yesterday, datetime.max.time())
        
        yest_campaign_filter = ""
        yest_params = [yest_start, yest_end]
        
        if campaigns and len(campaigns) > 0:
            placeholders = ','.join(['%s'] * len(campaigns))
            yest_campaign_filter = f" AND campaign_id IN ({placeholders})"
            yest_params.extend(campaigns)
        
        yest_query = f"""
        SELECT COUNT(DISTINCT uniqueid) as calls
        FROM vicidial_closer_log
        WHERE call_date BETWEEN %s AND %s
        {yest_campaign_filter}
        """
        
        yest_result = db.execute_query(yest_query, yest_params)
        yest_calls = safe_int(yest_result[0]['calls']) if yest_result else 0
        
        process_elapsed = time.time() - process_start
        total_elapsed = time.time() - start_time
        print(f"   Processed in {process_elapsed:.1f} seconds")
        print(f"✅ Report generated in {total_elapsed:.1f} seconds total")
        
        report_data = {
            'date': target_date,
            'total_calls': total_calls,
            'valid_calls': valid_calls,
            'ghost_calls': ghost_calls,
            'ghost_pct': ghost_pct,
            'answered': answered,
            'abandoned': abandoned,
            'ans_rate': ans_rate,
            'abd_rate': abd_rate,
            'sl_pct': sl_pct,
            'avg_talk': avg_talk_sec,
            'avg_queue': avg_queue_sec,
            'total_talk_sec': total_talk_sec,
            'by_campaign': by_campaign,
            'hourly': hourly,
            'agents': agents,
            'live_count': live_count,
            'yesterday_calls': yest_calls,
            'unique_agents': len(unique_agents)
        }
        
        return report_data
        
    except Exception as e:
        print_error(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()
        return None

# =============================================================================
# Display Functions
# =============================================================================

def display_eod_report(report_data):
    """Display EOD report in a clean format with ghost call separation"""
    if not report_data:
        print_warning("No data available")
        return
    
    print_timezone_banner()
    print_header(f"📊 END OF DAY REPORT: {report_data['date']}", Colors.MAGENTA)
    
    # Overall stats with ghost calls
    print("\n📈 OVERALL STATISTICS:")
    print("-" * 70)
    print(f"  Total Calls     : {report_data['total_calls']:,}")
    print_color(f"  Ghost Calls     : {report_data['ghost_calls']:,} ({report_data['ghost_pct']:.1f}%)", Colors.YELLOW)
    print(f"  Valid Calls     : {report_data['valid_calls']:,}")
    print(f"  Unique Agents   : {report_data.get('unique_agents', 0)}")
    print("-" * 70)
    
    # Color code answer rate
    if report_data['ans_rate'] >= 80:
        ans_color = Colors.GREEN
    elif report_data['ans_rate'] >= 60:
        ans_color = Colors.YELLOW
    else:
        ans_color = Colors.RED
    
    # Print answered line with color (based on valid calls)
    print(f"  Answered        : ", end='')
    print_color(f"{report_data['answered']:,} ", ans_color)
    print(f"({report_data['ans_rate']:.1f}% of valid calls)")
    
    # Color code abandon rate
    if report_data['abd_rate'] <= 5:
        abd_color = Colors.GREEN
    elif report_data['abd_rate'] <= 10:
        abd_color = Colors.YELLOW
    else:
        abd_color = Colors.RED
    
    # Print abandoned line with color
    print(f"  Abandoned       : ", end='')
    print_color(f"{report_data['abandoned']:,} ", abd_color)
    print(f"({report_data['abd_rate']:.1f}% of valid calls)")
    
    # Color code service level
    if report_data['sl_pct'] >= 80:
        sl_color = Colors.GREEN
    elif report_data['sl_pct'] >= 60:
        sl_color = Colors.YELLOW
    else:
        sl_color = Colors.RED
    
    print(f"  Service Level   : ", end='')
    print_color(f"{report_data['sl_pct']:.1f}%", sl_color)
    print(f" (≤20s, of answered calls)")
    
    print(f"  Avg Talk Time   : {sec_to_hms(report_data['avg_talk'])} (valid calls only)")
    print(f"  Avg Queue Time  : {report_data['avg_queue']:.0f}s")
    print(f"  Total Talk Time : {sec_to_hms(report_data['total_talk_sec'])}")
    print(f"  👥 Agents Online : {report_data['live_count']}")
    
    # Comparison to yesterday
    if report_data['yesterday_calls'] > 0:
        change = report_data['total_calls'] - report_data['yesterday_calls']
        change_pct = (change / report_data['yesterday_calls'] * 100)
        if change > 0:
            print_color(f"  📈 +{change} calls vs yesterday (+{change_pct:.1f}%)", Colors.GREEN)
        elif change < 0:
            print_color(f"  📉 {change} calls vs yesterday ({change_pct:.1f}%)", Colors.RED)
        else:
            print(f"  📊 Same as yesterday")
    
    # Campaign breakdown with ghost calls
    if report_data['by_campaign']:
        print("\n📋 CAMPAIGN BREAKDOWN:")
        print("-" * 110)
        print(f"{'Campaign':<15} {'Total':<6} {'Valid':<6} {'Ghost':<6} {'Ghost%':<6} {'Ans%':<6} {'Abd%':<6} {'SL%':<6}")
        print("-" * 110)
        
        problem_campaigns = []
        for camp in report_data['by_campaign']:
            total = camp['calls']
            valid = camp['valid_calls']
            ghost = camp['ghost_calls']
            ghost_pct = camp['ghost_pct']
            ans_pct = camp['ans_pct']
            abd_pct = camp['abd_pct']
            sl_pct = camp.get('sl_pct', 0)
            
            # Color code by ghost rate
            if ghost_pct > 20:
                ghost_color = Colors.RED
            elif ghost_pct > 10:
                ghost_color = Colors.YELLOW
            else:
                ghost_color = Colors.GREEN
            
            print(f"{camp['campaign_id']:<15} {total:<6} {valid:<6} ", end='')
            print_color(f"{ghost:<6} ", ghost_color, end='')
            print(f"{ghost_pct:.1f}%{' ':<2} ", end='')
            
            # Color code answer rate
            if ans_pct >= 80:
                ans_color = Colors.GREEN
            elif ans_pct >= 60:
                ans_color = Colors.YELLOW
            else:
                ans_color = Colors.RED
            
            print_color(f"{ans_pct:.0f}%{' ':<3} ", ans_color, end='')
            
            # Color code abandon rate
            if abd_pct <= 5:
                abd_color = Colors.GREEN
            elif abd_pct <= 10:
                abd_color = Colors.YELLOW
            else:
                abd_color = Colors.RED
            
            print_color(f"{abd_pct:.0f}%{' ':<3} ", abd_color, end='')
            
            # Color code service level
            if sl_pct >= 80:
                sl_color = Colors.GREEN
            elif sl_pct >= 60:
                sl_color = Colors.YELLOW
            else:
                sl_color = Colors.RED
            
            print_color(f"{sl_pct:.0f}%", sl_color)
            
            if ans_pct < 60 and total > 10:
                problem_campaigns.append(camp)
        
        # Highlight problem campaigns
        if problem_campaigns:
            print("\n⚠️ CAMPAIGNS NEEDING ATTENTION:")
            for c in problem_campaigns[:5]:
                print_color(f"  • {c['campaign_id']}: {c['ans_pct']:.0f}% answer rate, {c['ghost_pct']:.0f}% ghost", Colors.RED)
    
    # Hourly breakdown with ghost calls
    if report_data['hourly']:
        print("\n⏰ HOURLY BREAKDOWN:")
        print("-" * 70)
        print(f"{'Hour':<8} {'Total':<6} {'Valid':<6} {'Ghost':<6} {'Answered':<8} {'Ans%':<6}")
        print("-" * 70)
        
        total_hourly = 0
        peak_hour = max(report_data['hourly'], key=lambda x: x['calls'])
        
        for h in report_data['hourly']:
            hour = h['hour']
            calls = h['calls']
            valid = h['valid_calls'] or 0
            ghost = h['ghost_calls'] or 0
            answered = h['answered'] or 0
            ans_pct = h['ans_pct']
            
            # Highlight peak hour
            if calls == peak_hour['calls']:
                print_color(f"{hour:02d}:00   {calls:<6} {valid:<6} {ghost:<6} {answered:<8} {ans_pct:.0f}% ★", Colors.YELLOW)
            else:
                print(f"{hour:02d}:00   {calls:<6} {valid:<6} {ghost:<6} {answered:<8} {ans_pct:.0f}%")
            
            total_hourly += calls
        
        print("-" * 70)
        print(f"TOTAL: {total_hourly} calls")
        print_color(f"⏰ Peak hour: {peak_hour['hour']:02d}:00 ({peak_hour['calls']} calls)", Colors.YELLOW)
    
    # Top agents (valid calls only)
    if report_data['agents']:
        print("\n👥 TOP AGENTS (Valid Calls Only):")
        print("-" * 90)
        print(f"{'Agent':<15} {'Name':<20} {'Valid':<6} {'Ghost':<6} {'Talk Time':<12} {'Avg Call':<10}")
        print("-" * 90)
        
        for i, agent in enumerate(report_data['agents']):
            name = agent.get('full_name', 'Unknown')[:20]
            valid = agent['valid_calls']
            ghost = agent.get('ghost_calls', 0)
            talk_time = sec_to_hms(agent['total_talk'] or 0)
            avg_talk = sec_to_hms(agent['avg_talk'] or 0)
            
            # Color code top 3
            if i == 0:
                color = Colors.GREEN
            elif i == 1:
                color = Colors.CYAN
            elif i == 2:
                color = Colors.BLUE
            else:
                color = Colors.RESET
            
            # Color code ghost rate
            ghost_pct = (ghost / (valid + ghost) * 100) if (valid + ghost) > 0 else 0
            if ghost_pct > 20:
                ghost_display = f"{Colors.RED}{ghost}{Colors.RESET}"
            elif ghost_pct > 10:
                ghost_display = f"{Colors.YELLOW}{ghost}{Colors.RESET}"
            else:
                ghost_display = str(ghost)
            
            print_color(f"{agent['user']:<15} {name:<20} {valid:<6} ", color, end='')
            print(f"{ghost_display:<6} {talk_time:<12} {avg_talk:<10}")
    
    # ── Email channel section ──────────────────────────────────────────────────
    try:
        ensure_mapping_table()
        email_summary = get_email_summary(report_data['date'])
        email_agents  = get_email_stats_by_agent(report_data['date'])

        if email_summary['total_emails'] > 0:
            print("\n📧 EMAIL CHANNEL SUMMARY:")
            print("-" * 70)
            print(f"  Total Emails    : {email_summary['total_emails']:,}")
            print(f"  Agents Active   : {email_summary['agents_active']}")
            print(f"  Cancellations   : {email_summary['cancellations']}")
            print(f"  Full Refunds    : {email_summary['full_refunds']}")
            print(f"  Partial Refunds : {email_summary['partial_refunds']}")
            print(f"  Order Status    : {email_summary['order_status']}")
            print(f"  Gen Inquiry     : {email_summary['gen_inquiry']}")
            print(f"  Reshipments     : {email_summary['reshipments']}")
            print_color(f"  Refund Value    : ${email_summary['refund_total']:,.2f}  ({email_summary['refund_count']} tickets)", Colors.YELLOW)

            if email_agents:
                print("\n📧 EMAIL AGENTS BREAKDOWN:")
                print("-" * 90)
                print(f"{'Agent (pinktools)':<22} {'Linked':<15} {'Emails':<7} {'Cancels':<8} {'Refunds':<8} {'Refund $':<12} {'Top Type'}")
                print("-" * 90)

                unlinked = []
                for a in sorted(email_agents, key=lambda x: x['total_emails'], reverse=True):
                    top_type = max(a['by_type'], key=a['by_type'].get) if a['by_type'] else '-'
                    altria   = a['altria_username'] or ''
                    if not altria:
                        unlinked.append(a['pinktools_name'])

                    color = Colors.RESET if altria else Colors.YELLOW
                    linked_display = altria if altria else '⚠ Unlinked'
                    print_color(
                        f"{a['pinktools_name']:<22} {linked_display:<15} "
                        f"{a['total_emails']:<7} {a['cancellations']:<8} "
                        f"{a['refund_count']:<8} ${a['refund_total']:<11,.2f} {top_type}",
                        color
                    )

                if unlinked:
                    print_color(f"\n  ⚠  {len(unlinked)} agent(s) not linked to VICIdial: {', '.join(unlinked)}", Colors.YELLOW)
                    print(    "     Run agent mapping setup to link them.")
        else:
            print_color("\n📧 Email channel: no data for this date", Colors.YELLOW)

    except Exception as _e:
        print_color(f"\n📧 Email channel unavailable: {_e}", Colors.YELLOW)

    # Summary box
    print("\n" + "▁" * 70)
    print(f"📊 SUMMARY: {report_data['total_calls']} total | {report_data['ghost_calls']} ghost ({report_data['ghost_pct']:.1f}%) | "
          f"{report_data['ans_rate']:.1f}% answer | {report_data['abd_rate']:.1f}% abandon")
    print("▔" * 70)

def show_week_summary():
    """Show summary of last 7 days"""
    print_header("📊 LAST 7 DAYS SUMMARY", Colors.CYAN)
    
    tz = get_timezone_info()
    end_date = tz['est_date'] - timedelta(days=1)  # yesterday
    start_date = end_date - timedelta(days=6)
    
    campaigns = get_selected_campaigns()
    if not campaigns:
        return
    
    print(f"\nPeriod: {start_date} to {end_date} (EST)")
    
    # Build query
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    
    placeholders = ','.join(['%s'] * len(campaigns))
    
    query = f"""
    SELECT 
        DATE(call_date) as call_date,
        COUNT(DISTINCT c.uniqueid) as total_calls,
        COUNT(DISTINCT CASE WHEN a.uniqueid IS NOT NULL AND c.length_in_sec >= 5 THEN c.uniqueid END) as valid_calls,
        COUNT(DISTINCT CASE WHEN a.uniqueid IS NULL AND c.length_in_sec = 0 THEN c.uniqueid END) as ghost_calls,
        COUNT(DISTINCT CASE WHEN a.talk_sec >= 5 THEN c.uniqueid END) as answered
    FROM vicidial_closer_log c
    LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
    WHERE call_date BETWEEN %s AND %s
      AND campaign_id IN ({placeholders})
    GROUP BY DATE(call_date)
    ORDER BY call_date
    """
    
    params = [start_dt, end_dt] + campaigns
    results = db.execute_query(query, params)
    
    if results:
        print("\n📈 DAILY TOTALS:")
        print("-" * 80)
        print(f"{'Date':<12} {'Total':<6} {'Valid':<6} {'Ghost':<6} {'Ghost%':<6} {'Answered':<8} {'Ans%':<6}")
        print("-" * 80)
        
        total_calls = 0
        total_valid = 0
        total_ghost = 0
        total_answered = 0
        daily_data = []
        
        for r in results:
            date_str = r['call_date'].strftime('%m/%d')
            calls = safe_int(r['total_calls'])
            valid = safe_int(r['valid_calls'])
            ghost = safe_int(r['ghost_calls'])
            ghost_pct = (ghost / calls * 100) if calls > 0 else 0
            answered = safe_int(r['answered'])
            ans_pct = (answered / valid * 100) if valid > 0 else 0
            
            # Color code by ghost rate
            if ghost_pct > 20:
                color = Colors.RED
            elif ghost_pct > 10:
                color = Colors.YELLOW
            else:
                color = Colors.GREEN
            
            print_color(f"{date_str:<12} {calls:<6} {valid:<6} {ghost:<6} {ghost_pct:.1f}%{' ':<2} {answered:<8} {ans_pct:.0f}%", color)
            
            total_calls += calls
            total_valid += valid
            total_ghost += ghost
            total_answered += answered
            daily_data.append(calls)
        
        print("-" * 80)
        avg_ghost = (total_ghost / total_calls * 100) if total_calls > 0 else 0
        avg_ans = (total_answered / total_valid * 100) if total_valid > 0 else 0
        avg_daily = total_calls / 7
        
        print(f"AVG: {avg_daily:.0f}/day | Ghost: {avg_ghost:.1f}% | Answer Rate: {avg_ans:.1f}%")
        
        # Trend indicator
        if len(daily_data) >= 7:
            first_3_avg = sum(daily_data[:3]) / 3
            last_3_avg = sum(daily_data[-3:]) / 3
            trend = last_3_avg - first_3_avg
            
            if trend > 10:
                print_color(f"📈 Upward trend: +{trend:.0f} calls", Colors.GREEN)
            elif trend < -10:
                print_color(f"📉 Downward trend: {trend:.0f} calls", Colors.RED)

def compare_two_days():
    """Compare two specific days"""
    print_header("🔄 COMPARE TWO DAYS", Colors.CYAN)
    
    print("\nSelect first date:")
    date1_str = input("Enter date 1 (YYYY-MM-DD): ").strip()
    print("\nSelect second date:")
    date2_str = input("Enter date 2 (YYYY-MM-DD): ").strip()
    
    try:
        date1 = datetime.strptime(date1_str, '%Y-%m-%d').date()
        date2 = datetime.strptime(date2_str, '%Y-%m-%d').date()
    except:
        print_error("Invalid date format")
        return
    
    campaigns = get_selected_campaigns()
    if not campaigns:
        return
    
    print(f"\n📊 Generating reports...")
    report1 = generate_eod_report(date1, campaigns)
    report2 = generate_eod_report(date2, campaigns)
    
    if not report1 or not report2:
        print_error("Could not generate reports for both dates")
        return
    
    print_header(f"COMPARISON: {date1} vs {date2}", Colors.MAGENTA)
    print("-" * 100)
    print(f"{'Metric':<30} {date1} {date2} {'Change':>20}")
    print("-" * 100)
    
    # Total Calls
    calls_change = report2['total_calls'] - report1['total_calls']
    calls_pct = (calls_change / report1['total_calls'] * 100) if report1['total_calls'] > 0 else 0
    print(f"{'Total Calls':<30} {report1['total_calls']:<8} {report2['total_calls']:<8} ", end="")
    if calls_change > 0:
        print_color(f"▲ +{calls_change} (+{calls_pct:.0f}%)", Colors.GREEN)
    elif calls_change < 0:
        print_color(f"▼ {calls_change} ({calls_pct:.0f}%)", Colors.RED)
    else:
        print("→ 0")
    
    # Ghost Calls
    ghost_change = report2['ghost_calls'] - report1['ghost_calls']
    ghost_pct_change = report2['ghost_pct'] - report1['ghost_pct']
    print(f"{'Ghost Calls':<30} {report1['ghost_calls']} ({report1['ghost_pct']:.1f}%) {' ':<3} {report2['ghost_calls']} ({report2['ghost_pct']:.1f}%) ", end="")
    if ghost_change < 0:  # Fewer ghost calls is better
        print_color(f"▼ {ghost_change} (better)", Colors.GREEN)
    elif ghost_change > 0:
        print_color(f"▲ +{ghost_change} (worse)", Colors.RED)
    else:
        print("→ 0")
    
    # Answer Rate (based on valid calls)
    ans_change = report2['ans_rate'] - report1['ans_rate']
    print(f"{'Answer Rate':<30} {report1['ans_rate']:.1f}%{' ':<4} {report2['ans_rate']:.1f}%{' ':<4} ", end="")
    if ans_change > 0:
        print_color(f"▲ +{ans_change:.1f}%", Colors.GREEN)
    elif ans_change < 0:
        print_color(f"▼ {ans_change:.1f}%", Colors.RED)
    else:
        print("→ 0")
    
    # Abandon Rate
    abd_change = report2['abd_rate'] - report1['abd_rate']
    print(f"{'Abandon Rate':<30} {report1['abd_rate']:.1f}%{' ':<4} {report2['abd_rate']:.1f}%{' ':<4} ", end="")
    if abd_change < 0:  # Lower abandon rate is better
        print_color(f"▼ {abd_change:.1f}% (better)", Colors.GREEN)
    elif abd_change > 0:
        print_color(f"▲ +{abd_change:.1f}% (worse)", Colors.RED)
    else:
        print("→ 0")
    
    # Service Level
    sl_change = report2['sl_pct'] - report1['sl_pct']
    print(f"{'Service Level':<30} {report1['sl_pct']:.1f}%{' ':<4} {report2['sl_pct']:.1f}%{' ':<4} ", end="")
    if sl_change > 0:
        print_color(f"▲ +{sl_change:.1f}%", Colors.GREEN)
    elif sl_change < 0:
        print_color(f"▼ {sl_change:.1f}%", Colors.RED)
    else:
        print("→ 0")

def configure_report_settings():
    """Configure report settings"""
    print_header("⚙️ REPORT SETTINGS", Colors.YELLOW)
    print("\nSettings will be saved to config file.")
    print("  • Default date range")
    print("  • Ghost call threshold (seconds)")
    print("  • Preferred timezone")
    print("  • Export format preferences")
    input("\nPress Enter to continue...")

def show_export_menu():
    """Show export options"""
    print_header("📤 EXPORT OPTIONS", Colors.GREEN)
    print("\n  1. Export to CSV")
    print("  2. Export to Excel")
    print("  3. Export to PDF (coming soon)")
    print("  4. Email Report (coming soon)")
    print("  0. Back")
    
    export_choice = input("\nChoice: ").strip()
    
    if export_choice == '1':
        # Get date for export
        tz = get_timezone_info()
        date = get_est_target_date('2')
        campaigns = get_selected_campaigns()
        if campaigns:
            report = generate_eod_report(date, campaigns)
            if report:
                export_to_csv(report)
    
    elif export_choice == '2':
        tz = get_timezone_info()
        date = get_est_target_date('2')
        campaigns = get_selected_campaigns()
        if campaigns:
            report = generate_eod_report(date, campaigns)
            if report:
                export_to_excel(report)
    
    elif export_choice in ['3', '4']:
        print("\n🚧 Coming Soon! 🚧")
        input("\nPress Enter to continue...")

def show_eod_report():
    """Show EOD report for specific date"""
    print_header("📊 END OF DAY REPORT", Colors.MAGENTA)
    
    print("\nSelect date (EST-based):")
    print("  1. Today (EST)")
    print("  2. Yesterday (EST) ← default")
    print("  3. Specific date")
    
    date_choice = input("\nChoice (1-3): ").strip() or '2'
    
    target_date = get_est_target_date(date_choice)
    
    campaigns = get_selected_campaigns()
    if not campaigns:
        return
    
    report = generate_eod_report(target_date, campaigns)
    display_eod_report(report)

def eod_report_menu():
    """Main EOD report menu"""
    while True:
        print_header("📊 END OF DAY (EOD) REPORTS", Colors.CYAN)
        print("  1. 📅 Today's Report (in progress)")
        print("  2. 📆 Yesterday's Report")
        print("  3. 📅 Specific Date")
        print("  4. 📊 Last 7 Days Summary")
        print("  5. 🔄 Compare Two Days")
        print("  6. ⚙️ Report Settings")
        print("  7. 📤 Export Options")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            tz = get_timezone_info()
            campaigns = get_selected_campaigns()
            if campaigns:
                print("⏳ Generating today's report...")
                report = generate_eod_report(tz['est_date'], campaigns)
                if report:
                    display_eod_report(report)
                else:
                    print_warning("No data for today yet")
            input("\nPress Enter to continue...")
            
        elif choice == '2':
            tz = get_timezone_info()
            campaigns = get_selected_campaigns()
            if campaigns:
                print("⏳ Generating yesterday's report...")
                report = generate_eod_report(tz['est_date'] - timedelta(days=1), campaigns)
                if report:
                    display_eod_report(report)
                else:
                    print_warning("No data for yesterday")
            input("\nPress Enter to continue...")
            
        elif choice == '3':
            show_eod_report()
            
        elif choice == '4':
            show_week_summary()
            input("\nPress Enter to continue...")
            
        elif choice == '5':
            compare_two_days()
            input("\nPress Enter to continue...")
            
        elif choice == '6':
            configure_report_settings()
            
        elif choice == '7':
            show_export_menu()
            
        elif choice == '0':
            break
            
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    eod_report_menu()