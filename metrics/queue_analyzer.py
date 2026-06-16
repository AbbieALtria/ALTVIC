#!/usr/bin/env python3
# =============================================================================
# File:         queue_analyzer.py
# Version:      1.1.0
# Date:         2026-03-10
# Description:  Advanced Queue Analysis with percentile tracking and abandon patterns
#               Added Manila timezone conversion (UTC+8) for better readability
# Location:     D:/Altria_Ops/metrics/queue_analyzer.py
# =============================================================================

import sys
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info
from utils.formatter import sec_to_hms, format_datetime

# Import goals config
import json
GOALS_FILE = Path(__file__).parent.parent / "config" / "callcenter_goals.json"
try:
    with open(GOALS_FILE, 'r') as f:
        GOALS = json.load(f)
except:
    GOALS = {
        "goals": {
            "service_level": {"threshold_seconds": 20, "target_percentage": 80},
            "abandon_rate": {"max_target": 5.0},
            "avg_queue_time": {"max_target": 30.0}
        }
    }

# =============================================================================
# Timezone Conversion Functions (Philippines/Manila Time UTC+8)
# =============================================================================

def convert_to_manila_time(server_time):
    """Convert server time to Manila time (UTC+8)
    
    Server is 12 hours behind Manila (from example: server 00:31:29 → Manila 12:31:29)
    """
    if server_time is None:
        return None, "Unknown"
    
    MANILA_OFFSET = 12  # hours
    
    try:
        if isinstance(server_time, str):
            server_time = datetime.strptime(server_time, '%Y-%m-%d %H:%M:%S')
        
        manila_time = server_time + timedelta(hours=MANILA_OFFSET)
        return manila_time, manila_time.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return None, "Unknown"

def format_manila_datetime(server_time):
    """Format datetime in Manila timezone"""
    if server_time is None:
        return "Unknown"
    
    manila_time, manila_str = convert_to_manila_time(server_time)
    return manila_str

def get_manila_hour(server_time):
    """Get hour in Manila time from server timestamp"""
    if server_time is None:
        return None
    
    manila_time, _ = convert_to_manila_time(server_time)
    if manila_time:
        return manila_time.hour
    return None

def get_current_manila_time():
    """Get current Manila time"""
    now_utc = datetime.utcnow()
    now_manila = now_utc + timedelta(hours=8)  # UTC to Manila (UTC+8)
    return now_manila

def get_time_ago_manila(timestamp):
    """Get 'X hours/minutes ago' in Manila time"""
    if timestamp is None:
        return "Unknown"
    
    try:
        # Convert to Manila time
        manila_time, _ = convert_to_manila_time(timestamp)
        if manila_time is None:
            return "Unknown"
        
        # Get current Manila time
        now_manila = get_current_manila_time()
        
        # Calculate difference
        diff = now_manila - manila_time
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return f"{int(seconds)} seconds ago"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minutes ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hours ago"
        elif seconds < 172800:
            return f"yesterday"
        else:
            days = int(seconds / 86400)
            return f"{days} days ago"
    except:
        return "Unknown"

# =============================================================================
# Helper Functions
# =============================================================================

def get_campaign_list():
    """Get list of campaigns with recent activity"""
    query = """
    SELECT DISTINCT campaign_id
    FROM vicidial_closer_log
    WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    ORDER BY campaign_id
    """
    try:
        results = db.execute_query(query)
        return [r['campaign_id'] for r in results] if results else []
    except:
        return []

def select_campaign_interactive():
    """Interactive campaign selection"""
    campaigns = get_campaign_list()
    
    if not campaigns:
        print_warning("No campaigns found with recent activity")
        return None
    
    print("\n📋 Available Campaigns:")
    for i, camp in enumerate(campaigns, 1):
        print(f"  {i:3}. {camp}")
        if i % 5 == 0:
            print()
    
    print("\nEnter campaign number, name, or 'all':")
    choice = input("> ").strip()
    
    if choice.lower() == 'all':
        return None  # None means all campaigns
    
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(campaigns):
            return campaigns[idx]
    else:
        if choice in campaigns:
            return choice
    
    print_error("Campaign not found")
    return None

def get_date_range():
    """Get date range from user with Manila time display"""
    print("\nSelect period:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. Last 7 Days")
    print("  4. Last 30 Days")
    print("  5. Custom Range")
    
    choice = input("\nChoice (1-5): ").strip()
    
    now = datetime.now()
    now_manila = get_current_manila_time()
    
    print_info(f"Current Manila time: {now_manila.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if choice == '1':
        start = datetime.combine(now.date(), datetime.min.time())
        end = datetime.combine(now.date(), datetime.max.time())
        period = "Today"
    elif choice == '2':
        yesterday = now.date() - timedelta(days=1)
        start = datetime.combine(yesterday, datetime.min.time())
        end = datetime.combine(yesterday, datetime.max.time())
        period = "Yesterday"
    elif choice == '3':
        start = now - timedelta(days=7)
        end = now
        period = "Last 7 Days"
    elif choice == '4':
        start = now - timedelta(days=30)
        end = now
        period = "Last 30 Days"
    elif choice == '5':
        print("\nEnter dates in Manila time (YYYY-MM-DD):")
        start_str = input("Start date: ").strip()
        end_str = input("End date: ").strip()
        try:
            # Convert Manila date input to server time (subtract 12 hours)
            manila_start = datetime.strptime(start_str, '%Y-%m-%d')
            manila_end = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            
            # Convert to server time (subtract 12 hours)
            start = manila_start - timedelta(hours=12)
            end = manila_end - timedelta(hours=12)
            period = f"{start_str} to {end_str} (Manila time)"
        except:
            print_error("Invalid date format")
            return None, None, None
    else:
        start = now - timedelta(days=7)
        end = now
        period = "Last 7 Days"
    
    # Display date range in both timezones
    print_info(f"\nServer time range: {start} to {end}")
    print_info(f"Manila time range: {format_manila_datetime(start)} to {format_manila_datetime(end)}")
    
    return start, end, period

# =============================================================================
# Queue Analysis Functions
# =============================================================================

def analyze_queue_performance(campaign=None, start_date=None, end_date=None):
    """
    Comprehensive queue analysis with percentiles and abandon patterns
    
    Returns:
        dict with queue statistics and analysis
    """
    
    # Build query conditions
    conditions = ["1=1"]
    params = []
    
    if campaign:
        conditions.append("c.campaign_id = %s")
        params.append(campaign)
    
    if start_date and end_date:
        conditions.append("c.call_date BETWEEN %s AND %s")
        params.append(start_date)
        params.append(end_date)
    
    where_clause = " AND ".join(conditions)
    
    # Main queue statistics query
    queue_query = f"""
    SELECT 
        COUNT(*) as total_calls,
        SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
        SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                 OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
        SUM(CASE WHEN length_in_sec = 0 AND queue_seconds = 0 THEN 1 ELSE 0 END) as ghost_calls,
        AVG(CASE WHEN length_in_sec >= 5 THEN queue_seconds END) as avg_queue_answered,
        AVG(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                 THEN queue_seconds END) as avg_wait_abandoned,
        MAX(queue_seconds) as max_queue,
        SUM(CASE WHEN queue_seconds <= 20 AND length_in_sec >= 5 THEN 1 ELSE 0 END) as sl_20,
        SUM(CASE WHEN queue_seconds <= 30 AND length_in_sec >= 5 THEN 1 ELSE 0 END) as sl_30,
        SUM(CASE WHEN queue_seconds <= 60 AND length_in_sec >= 5 THEN 1 ELSE 0 END) as sl_60
    FROM vicidial_closer_log c
    WHERE {where_clause}
    """
    
    try:
        results = db.execute_query(queue_query, params)
        if not results or results[0]['total_calls'] == 0:
            return None
        
        stats = results[0]
        
        # Calculate basic metrics
        total = stats['total_calls'] or 0
        answered = stats['answered'] or 0
        abandoned = stats['abandoned'] or 0
        ghost = stats['ghost_calls'] or 0
        
        # Format period with Manila time
        if start_date and end_date:
            period_display = f"{format_manila_datetime(start_date)} to {format_manila_datetime(end_date)} (Manila time)"
        else:
            period_display = "All time"
        
        analysis = {
            'campaign': campaign if campaign else 'ALL CAMPAIGNS',
            'period': period_display,
            'total_calls': total,
            'answered': answered,
            'abandoned': abandoned,
            'ghost_calls': ghost,
            'answer_rate': (answered / total * 100) if total > 0 else 0,
            'abandon_rate': (abandoned / total * 100) if total > 0 else 0,
            'ghost_rate': (ghost / total * 100) if total > 0 else 0,
            'avg_queue_answered': stats['avg_queue_answered'] or 0,
            'avg_wait_abandoned': stats['avg_wait_abandoned'] or 0,
            'max_queue': stats['max_queue'] or 0,
            'service_level': {
                '20s': (stats['sl_20'] / answered * 100) if answered > 0 else 0,
                '30s': (stats['sl_30'] / answered * 100) if answered > 0 else 0,
                '60s': (stats['sl_60'] / answered * 100) if answered > 0 else 0
            }
        }
        
        # Get queue time percentiles
        percentile_query = f"""
        SELECT 
            queue_seconds
        FROM vicidial_closer_log
        WHERE {where_clause}
          AND queue_seconds > 0
        ORDER BY queue_seconds
        """
        
        queue_times = db.execute_query(percentile_query, params)
        if queue_times and len(queue_times) > 10:
            values = [q['queue_seconds'] for q in queue_times]
            analysis['percentiles'] = {
                '50th': np.percentile(values, 50),
                '75th': np.percentile(values, 75),
                '90th': np.percentile(values, 90),
                '95th': np.percentile(values, 95),
                '99th': np.percentile(values, 99)
            }
        
        # Get hourly abandon patterns (by Manila hour)
        hourly_query = f"""
        SELECT 
            HOUR(DATE_ADD(c.call_date, INTERVAL 12 HOUR)) as manila_hour,
            COUNT(*) as calls,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned
        FROM vicidial_closer_log c
        WHERE {where_clause}
        GROUP BY manila_hour
        ORDER BY manila_hour
        """
        
        hourly = db.execute_query(hourly_query, params)
        if hourly:
            analysis['hourly'] = []
            for h in hourly:
                hour = h['manila_hour']
                h_calls = h['calls'] or 0
                h_abandoned = h['abandoned'] or 0
                analysis['hourly'].append({
                    'hour': hour,
                    'calls': h_calls,
                    'abandoned': h_abandoned,
                    'abandon_rate': (h_abandoned / h_calls * 100) if h_calls > 0 else 0
                })
        
        # Get abandon time distribution
        abandon_dist_query = f"""
        SELECT 
            CASE 
                WHEN queue_seconds <= 15 THEN '0-15s'
                WHEN queue_seconds <= 30 THEN '15-30s'
                WHEN queue_seconds <= 60 THEN '30-60s'
                WHEN queue_seconds <= 120 THEN '1-2min'
                WHEN queue_seconds <= 300 THEN '2-5min'
                ELSE '5min+'
            END as time_bucket,
            COUNT(*) as count
        FROM vicidial_closer_log
        WHERE {where_clause}
          AND (term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
               OR (length_in_sec = 0 AND queue_seconds > 0))
        GROUP BY time_bucket
        ORDER BY 
            CASE time_bucket
                WHEN '0-15s' THEN 1
                WHEN '15-30s' THEN 2
                WHEN '30-60s' THEN 3
                WHEN '1-2min' THEN 4
                WHEN '2-5min' THEN 5
                ELSE 6
            END
        """
        
        dist = db.execute_query(abandon_dist_query, params)
        if dist:
            analysis['abandon_distribution'] = dist
        
        return analysis
        
    except Exception as e:
        print_error(f"Error analyzing queue: {e}")
        import traceback
        traceback.print_exc()
        return None

def check_against_goals(analysis):
    """Check queue metrics against configured goals"""
    if not analysis:
        return []
    
    goals = GOALS.get('goals', {})
    findings = []
    
    # Check answer rate
    min_answer = goals.get('answer_rate', {}).get('min_target', 90)
    if analysis['answer_rate'] < min_answer:
        findings.append({
            'metric': 'Answer Rate',
            'value': f"{analysis['answer_rate']:.1f}%",
            'target': f">{min_answer}%",
            'status': 'CRITICAL',
            'color': Colors.RED,
            'recommendation': 'Review staffing levels and queue configuration'
        })
    
    # Check abandon rate
    max_abandon = goals.get('abandon_rate', {}).get('max_target', 5)
    if analysis['abandon_rate'] > max_abandon:
        status = 'WARNING' if analysis['abandon_rate'] < goals.get('abandon_rate', {}).get('warning_threshold', 8) else 'CRITICAL'
        findings.append({
            'metric': 'Abandon Rate',
            'value': f"{analysis['abandon_rate']:.1f}%",
            'target': f"<{max_abandon}%",
            'status': status,
            'color': Colors.YELLOW if status == 'WARNING' else Colors.RED,
            'recommendation': 'Consider adding more agents during peak hours'
        })
    
    # Check queue time
    max_queue = goals.get('avg_queue_time', {}).get('max_target', 30)
    if analysis['avg_queue_answered'] > max_queue:
        findings.append({
            'metric': 'Avg Queue Time',
            'value': f"{analysis['avg_queue_answered']:.0f}s",
            'target': f"<{max_queue}s",
            'status': 'WARNING',
            'color': Colors.YELLOW,
            'recommendation': 'Queue times are high - review call routing'
        })
    
    # Check service level
    sl_target = goals.get('service_level', {}).get('target_percentage', 80)
    if analysis['service_level']['20s'] < sl_target:
        findings.append({
            'metric': 'Service Level (20s)',
            'value': f"{analysis['service_level']['20s']:.1f}%",
            'target': f">{sl_target}%",
            'status': 'CRITICAL',
            'color': Colors.RED,
            'recommendation': 'Service level below target - immediate attention needed'
        })
    
    return findings

def get_recommendations(analysis):
    """Generate actionable recommendations based on analysis"""
    if not analysis:
        return []
    
    recommendations = []
    
    # Check abandon patterns
    if analysis.get('abandon_distribution'):
        early_abandons = [d for d in analysis['abandon_distribution'] 
                         if d['time_bucket'] in ['0-15s', '15-30s']]
        if early_abandons:
            total_early = sum(d['count'] for d in early_abandons)
            if total_early > analysis['abandoned'] * 0.3:  # >30% abandon early
                recommendations.append({
                    'issue': 'High early abandonment',
                    'detail': f"{total_early} calls abandoned within 30 seconds",
                    'action': 'Check IVR menu and welcome message - customers may be frustrated',
                    'priority': 'HIGH'
                })
    
    # Check peak abandon hours (Manila time)
    if analysis.get('hourly'):
        peak_hours = sorted(analysis['hourly'], key=lambda x: x['abandon_rate'], reverse=True)[:3]
        peak_hours = [h for h in peak_hours if h['abandon_rate'] > 10 and h['calls'] > 10]
        if peak_hours:
            hours_str = ', '.join([f"{h['hour']:02d}:00" for h in peak_hours])
            recommendations.append({
                'issue': 'Peak abandon hours identified (Manila time)',
                'detail': f"Highest abandon rates at: {hours_str} Manila time",
                'action': 'Schedule more agents during these Manila hours',
                'priority': 'MEDIUM'
            })
    
    # Check 90th percentile queue times
    if analysis.get('percentiles'):
        p90 = analysis['percentiles'].get('90th', 0)
        if p90 > 60:
            recommendations.append({
                'issue': 'Long queue times for 90th percentile',
                'detail': f"90% of callers wait {p90:.0f}s or less",
                'action': 'Implement callback feature for long wait times',
                'priority': 'MEDIUM'
            })
        
        p95 = analysis['percentiles'].get('95th', 0)
        if p95 > 120:
            recommendations.append({
                'issue': 'Extreme queue times',
                'detail': f"5% of callers wait over {p95:.0f}s",
                'action': 'Review staffing during peak periods',
                'priority': 'HIGH'
            })
    
    # Check ghost calls
    if analysis['ghost_rate'] > 10:
        recommendations.append({
            'issue': 'High ghost call rate',
            'detail': f"{analysis['ghost_rate']:.1f}% of calls are ghost calls",
            'action': 'Check dialer configuration and network stability',
            'priority': 'MEDIUM'
        })
    
    return recommendations

# =============================================================================
# Display Functions
# =============================================================================

def display_queue_analysis(analysis):
    """Display queue analysis results"""
    if not analysis:
        print_warning("No data available for analysis")
        return
    
    campaign = analysis['campaign']
    period = analysis['period']
    
    print_header(f"🔍 QUEUE ANALYSIS - {campaign}", Colors.MAGENTA)
    print(f"Period (Manila Time): {period}")
    print("=" * 90)
    
    # Basic stats
    print(f"\n📊 OVERVIEW:")
    print(f"  • Total Calls:   {analysis['total_calls']:,}")
    print(f"  • Answered:      {analysis['answered']:,} ({analysis['answer_rate']:.1f}%)")
    print(f"  • Abandoned:     {analysis['abandoned']:,} ({analysis['abandon_rate']:.1f}%)")
    print(f"  • Ghost Calls:   {analysis['ghost_calls']:,} ({analysis['ghost_rate']:.1f}%)")
    
    # Queue metrics
    print(f"\n⏱️ QUEUE METRICS:")
    print(f"  • Avg Queue (answered):  {analysis['avg_queue_answered']:.0f}s")
    print(f"  • Avg Wait (abandoned):  {analysis['avg_wait_abandoned']:.0f}s")
    print(f"  • Max Queue Time:        {analysis['max_queue']:.0f}s")
    
    # Service levels
    sl = analysis['service_level']
    print(f"\n🎯 SERVICE LEVEL:")
    
    sl_color = Colors.GREEN if sl['20s'] >= 80 else Colors.YELLOW if sl['20s'] >= 60 else Colors.RED
    print_color(f"  • Within 20s:  {sl['20s']:.1f}%", sl_color)
    print(f"  • Within 30s:  {sl['30s']:.1f}%")
    print(f"  • Within 60s:  {sl['60s']:.1f}%")
    
    # Percentiles
    if analysis.get('percentiles'):
        print(f"\n📈 QUEUE TIME PERCENTILES:")
        p = analysis['percentiles']
        print(f"  • 50th (Median): {p['50th']:.0f}s")
        print(f"  • 75th:           {p['75th']:.0f}s")
        print_color(f"  • 90th:           {p['90th']:.0f}s", Colors.YELLOW if p['90th'] > 60 else Colors.RESET)
        print_color(f"  • 95th:           {p['95th']:.0f}s", Colors.RED if p['95th'] > 120 else Colors.RESET)
        print(f"  • 99th:           {p['99th']:.0f}s")
    
    # Abandon distribution
    if analysis.get('abandon_distribution'):
        print(f"\n⏰ ABANDON TIME DISTRIBUTION:")
        print(f"{'Wait Time':<15} {'Calls':<8} {'% of Abandons':<15} {'Bar'} (Manila time)")
        print("-" * 60)
        
        total_abandons = analysis['abandoned']
        for d in analysis['abandon_distribution']:
            bucket = d['time_bucket']
            count = d['count']
            pct = (count / total_abandons * 100) if total_abandons > 0 else 0
            bar = "█" * int(pct / 5)
            
            # Color code
            if bucket in ['0-15s', '15-30s'] and pct > 30:
                color = Colors.RED
            elif bucket in ['0-15s', '15-30s']:
                color = Colors.YELLOW
            else:
                color = Colors.RESET
            
            print_color(f"  {bucket:<15} {count:<8} {pct:.1f}%{' ':<8} {bar}", color)
    
    # Hourly breakdown (Manila time)
    if analysis.get('hourly'):
        print(f"\n⏰ HOURLY ABANDON RATES (Manila Time):")
        print(f"{'Hour (Manila)':<15} {'Calls':<8} {'Aband':<8} {'Rate':<8} {'Bar'}")
        print("-" * 60)
        
        for h in analysis['hourly']:
            if h['calls'] > 0:
                bar = "█" * int(h['abandon_rate'] / 2)
                color = Colors.GREEN if h['abandon_rate'] < 5 else Colors.YELLOW if h['abandon_rate'] < 10 else Colors.RED
                print_color(f"  {h['hour']:02d}:00          {h['calls']:<8} {h['abandoned']:<8} {h['abandon_rate']:.0f}%{' ':<3} {bar}", color)
        
        # Show busiest hours (Manila time)
        busiest = sorted(analysis['hourly'], key=lambda x: x['calls'], reverse=True)[:5]
        if busiest:
            print(f"\n🔥 BUSIEST HOURS (Manila Time):")
            print(f"{'Hour':<8} {'Calls':<8} {'Avg Queue':<10}")
            print("-" * 30)
            for h in busiest:
                print(f"  {h['hour']:02d}:00    {h['calls']:<8} -")
    
    # Check against goals
    findings = check_against_goals(analysis)
    if findings:
        print(f"\n⚠️ GOALS CHECK:")
        for f in findings:
            print_color(f"  • {f['metric']}: {f['value']} (target {f['target']}) - {f['status']}", f['color'])
    
    # Recommendations
    recommendations = get_recommendations(analysis)
    if recommendations:
        print(f"\n💡 RECOMMENDATIONS:")
        for rec in recommendations:
            priority_color = Colors.RED if rec['priority'] == 'HIGH' else Colors.YELLOW
            print_color(f"  • [{rec['priority']}] {rec['issue']}", priority_color)
            print(f"    {rec['detail']}")
            print(f"    → {rec['action']}")
    else:
        print(f"\n✅ Queue performance looks good! No recommendations at this time.")

def queue_analyzer_menu():
    """Main queue analyzer menu"""
    while True:
        print_header("🔍 QUEUE ANALYZER", Colors.CYAN)
        print(f"Current Manila Time: {get_current_manila_time().strftime('%Y-%m-%d %H:%M:%S')}")
        print("  " + "─" * 60)
        print("  1. 📊 Analyze All Campaigns")
        print("  2. 🎯 Analyze Specific Campaign")
        print("  3. ⏰ Peak Hour Analysis (Manila Time)")
        print("  4. 📈 Compare Two Periods")
        print("  5. ⚙️ Configure Goals")
        print("  0. 🔙 Back")
        print("  " + "─" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            start, end, period = get_date_range()
            if start:
                analysis = analyze_queue_performance(None, start, end)
                display_queue_analysis(analysis)
                input("\nPress Enter to continue...")
        
        elif choice == '2':
            campaign = select_campaign_interactive()
            if campaign is not None:
                start, end, period = get_date_range()
                if start:
                    analysis = analyze_queue_performance(campaign, start, end)
                    display_queue_analysis(analysis)
                    input("\nPress Enter to continue...")
        
        elif choice == '3':
            # Peak hour analysis (Manila time)
            print_header("⏰ PEAK HOUR ANALYSIS (Manila Time)", Colors.YELLOW)
            print("\nThis will show the busiest hours by call volume and abandon rate")
            
            campaign = select_campaign_interactive()
            start, end, period = get_date_range()
            
            if start:
                analysis = analyze_queue_performance(campaign, start, end)
                if analysis and analysis.get('hourly'):
                    print(f"\n🔥 BUSIEST HOURS BY CALL VOLUME (Manila Time):")
                    sorted_by_calls = sorted(analysis['hourly'], key=lambda x: x['calls'], reverse=True)
                    for h in sorted_by_calls[:5]:
                        if h['calls'] > 0:
                            print(f"  • {h['hour']:02d}:00 - {h['calls']} calls ({h['abandon_rate']:.1f}% abandon)")
                    
                    print(f"\n⚠️ PEAK HOURS BY ABANDON RATE (Manila Time):")
                    sorted_by_abandon = sorted(analysis['hourly'], key=lambda x: x['abandon_rate'], reverse=True)
                    for h in sorted_by_abandon[:5]:
                        if h['calls'] > 0 and h['abandon_rate'] > 0:
                            print(f"  • {h['hour']:02d}:00 - {h['abandon_rate']:.1f}% abandon ({h['calls']} calls)")
                input("\nPress Enter to continue...")
        
        elif choice == '4':
            # Compare two periods
            print_header("🔄 COMPARE TWO PERIODS (Manila Time)", Colors.BLUE)
            
            print("\n--- FIRST PERIOD ---")
            start1, end1, period1 = get_date_range()
            
            print("\n--- SECOND PERIOD ---")
            start2, end2, period2 = get_date_range()
            
            if start1 and start2:
                campaign = select_campaign_interactive()
                
                analysis1 = analyze_queue_performance(campaign, start1, end1)
                analysis2 = analyze_queue_performance(campaign, start2, end2)
                
                if analysis1 and analysis2:
                    print_header(f"COMPARISON: {period1} vs {period2}", Colors.MAGENTA)
                    print("=" * 80)
                    print(f"{'Metric':<30} {period1:<20} {period2:<20} {'Change':>10}")
                    print("-" * 80)
                    
                    # Answer rate
                    change = analysis2['answer_rate'] - analysis1['answer_rate']
                    change_color = Colors.GREEN if change > 0 else Colors.RED
                    print(f"{'Answer Rate':<30} {analysis1['answer_rate']:.1f}%{' ':<14} {analysis2['answer_rate']:.1f}%{' ':<14} ", end='')
                    print_color(f"{change:>+5.1f}%", change_color)
                    
                    # Abandon rate
                    change = analysis2['abandon_rate'] - analysis1['abandon_rate']
                    change_color = Colors.GREEN if change < 0 else Colors.RED
                    print(f"{'Abandon Rate':<30} {analysis1['abandon_rate']:.1f}%{' ':<14} {analysis2['abandon_rate']:.1f}%{' ':<14} ", end='')
                    print_color(f"{change:>+5.1f}%", change_color)
                    
                    # Avg queue
                    change = analysis2['avg_queue_answered'] - analysis1['avg_queue_answered']
                    change_color = Colors.GREEN if change < 0 else Colors.RED
                    print(f"{'Avg Queue':<30} {analysis1['avg_queue_answered']:.0f}s{' ':<16} {analysis2['avg_queue_answered']:.0f}s{' ':<16} ", end='')
                    print_color(f"{change:>+5.0f}s", change_color)
                    
                    # Service level
                    change = analysis2['service_level']['20s'] - analysis1['service_level']['20s']
                    change_color = Colors.GREEN if change > 0 else Colors.RED
                    print(f"{'Service Level (20s)':<30} {analysis1['service_level']['20s']:.1f}%{' ':<14} {analysis2['service_level']['20s']:.1f}%{' ':<14} ", end='')
                    print_color(f"{change:>+5.1f}%", change_color)
                    
                    print("=" * 80)
                
                input("\nPress Enter to continue...")
        
        elif choice == '5':
            # Configure goals
            print_header("⚙️ CONFIGURE QUEUE GOALS", Colors.YELLOW)
            print_info(f"\nEdit the goals file at: {GOALS_FILE}")
            print_info("\nCurrent goals:")
            goals = GOALS.get('goals', {})
            for g, v in goals.items():
                if isinstance(v, dict):
                    print(f"  • {g}: {v}")
            
            input("\nPress Enter to continue...")
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    queue_analyzer_menu()