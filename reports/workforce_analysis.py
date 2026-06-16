#!/usr/bin/env python3
# =============================================================================
# File:         workforce_analysis.py
# Version:      2.0.0
# Date:         2026-03-09
# Description:  Professional Workforce Management Analysis with Industry Standards
# Location:     D:/Altria_Ops/reports/workforce_analysis.py
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import sec_to_hms, format_datetime
import os
import csv
import time
from pathlib import Path
from decimal import Decimal

# =============================================================================
# Safe conversion helpers
# =============================================================================

def safe_int(value):
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

def safe_float(value):
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

# =============================================================================
# Optimized Query Functions with Timeouts
# =============================================================================

def check_data_exists(target_date):
    """Quick check if data exists for date (optimized)"""
    query = """
    SELECT COUNT(*) as count 
    FROM vicidial_closer_log 
    WHERE DATE(call_date) = %s
    LIMIT 1
    """
    result = db.execute_query(query, (target_date,))
    return safe_int(result[0]['count']) > 0 if result else False

def get_available_dates(limit=5):
    """Get recent available dates quickly"""
    query = """
    SELECT DISTINCT DATE(call_date) as date
    FROM vicidial_closer_log
    WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    ORDER BY date DESC
    LIMIT %s
    """
    return db.execute_query(query, (limit,)) or []

# =============================================================================
# Professional Workforce Analysis Functions
# =============================================================================

def analyze_daily_staffing(target_date=None):
    """
    Professional workforce analysis using industry standard metrics:
    - Occupancy Rate: % of time agents spend on calls
    - Service Level: % of calls answered within target
    - Utilization: % of agents actively handling calls
    - Erlang calculations for optimal staffing
    """
    
    if target_date is None:
        target_date = datetime.now().date() - timedelta(days=1)  # default yesterday
    
    print_header(f"📊 WORKFORCE ANALYSIS - {target_date}", Colors.MAGENTA)
    print("⏳ Analyzing data using industry standard metrics...")
    
    # Quick data check
    if not check_data_exists(target_date):
        print_warning(f"No call data found for {target_date}")
        
        # Show available dates
        avail_dates = get_available_dates()
        if avail_dates:
            print("\n📅 Available recent dates:")
            for d in avail_dates:
                print(f"  • {d['date']}")
        return
    
    try:
        start_time = time.time()
        
        # Get detailed hourly data with agent performance metrics
        hourly_query = """
        SELECT 
            HOUR(c.call_date) as hour,
            COUNT(DISTINCT c.uniqueid) as calls,
            COUNT(DISTINCT a.user) as active_agents,
            COALESCE(AVG(c.queue_seconds), 0) as avg_queue,
            SUM(CASE WHEN c.term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (c.length_in_sec = 0 AND c.queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned,
            SUM(CASE WHEN a.talk_sec >= 5 THEN a.talk_sec ELSE 0 END) as total_talk_sec,
            COUNT(DISTINCT CASE WHEN a.talk_sec >= 5 THEN a.user END) as productive_agents,
            MAX(c.queue_seconds) as max_queue,
            SUM(CASE WHEN c.queue_seconds <= 30 AND a.talk_sec >= 5 THEN 1 ELSE 0 END) as service_level_hits
        FROM vicidial_closer_log c
        LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
        WHERE DATE(c.call_date) = %s
        GROUP BY HOUR(c.call_date)
        ORDER BY hour
        """
        
        hourly = db.execute_query(hourly_query, (target_date,))
        
        if not hourly:
            print_warning(f"No hourly data found for {target_date}")
            return
        
        # Calculate totals
        total_calls = sum(safe_int(h['calls']) for h in hourly)
        total_agents = sum(safe_int(h['active_agents']) for h in hourly)
        total_talk_time = sum(safe_int(h['total_talk_sec']) for h in hourly)
        
        elapsed = time.time() - start_time
        print(f"✅ Data loaded in {elapsed:.1f} seconds")
        
        print(f"\n📈 DAILY SUMMARY:")
        print("=" * 70)
        print(f"  Total Calls:          {total_calls}")
        print(f"  Total Agent Hours:    {total_agents}")
        print(f"  Total Talk Time:      {sec_to_hms(total_talk_time)}")
        print(f"  Avg Calls per Hour:   {total_calls/24:.1f}")
        print(f"  Avg Agents per Hour:  {total_agents/24:.1f}")
        
        # ===== PROFESSIONAL HOURLY ANALYSIS =====
        print(f"\n⏰ HOURLY STAFFING ANALYSIS (Industry Standard Metrics):")
        print("=" * 120)
        print(f"{'Hour':<6} {'Calls':<8} {'Agents':<8} {'Occ%':<8} {'Util%':<8} {'SL%':<8} {'Abandon':<8} {'Status':<15} {'Recommendation':<20}")
        print("-" * 120)
        
        # Industry standard thresholds
        OPTIMAL_OCCUPANCY_MIN = 65
        OPTIMAL_OCCUPANCY_MAX = 85
        TARGET_SERVICE_LEVEL = 80  # % answered within 30 seconds
        MAX_ACCEPTABLE_ABANDON = 5  # percentage
        TALK_TIME_PER_CALL = 180  # 3 minutes average (adjust based on your data)
        
        # Track issues
        unstaffed_hours = []
        understaffed_hours = []
        overstaffed_hours = []
        critical_hours = []
        
        for h in hourly:
            hour = h['hour']
            calls = safe_int(h['calls'])
            agents = safe_int(h['active_agents'])
            avg_queue = safe_float(h['avg_queue'])
            abandoned = safe_int(h['abandoned'])
            total_talk = safe_int(h['total_talk_sec'])
            productive = safe_int(h['productive_agents'])
            service_hits = safe_int(h['service_level_hits'])
            max_queue = safe_float(h['max_queue'])
            
            # Calculate industry metrics
            abandon_rate = (abandoned / calls * 100) if calls > 0 else 0
            
            # OCCUPANCY RATE: % of agent time spent on calls
            # Formula: (Total Talk Time) / (Agents × 3600) × 100
            if agents > 0 and calls > 0:
                max_possible_talk = agents * 3600  # 1 hour = 3600 seconds
                occupancy = (total_talk / max_possible_talk * 100) if max_possible_talk > 0 else 0
                
                # UTILIZATION: % of agents actually on calls
                utilization = (productive / agents * 100) if agents > 0 else 0
                
                # SERVICE LEVEL: % answered within 30 seconds
                service_level = (service_hits / calls * 100) if calls > 0 else 0
                
                # ERLANG CALCULATION: Optimal agents needed
                # Simplified Erlang: (Calls × Avg Handle Time) / 3600
                required_agents_erlang = (calls * TALK_TIME_PER_CALL) / 3600
                optimal_agents = max(1, round(required_agents_erlang * 1.2))  # 20% buffer
            else:
                occupancy = 0
                utilization = 0
                service_level = 0
                optimal_agents = 0
            
            # Determine staffing status using professional criteria
            if agents == 0:
                if calls > 0:
                    status = "🔴 UNSTAFFED"
                    status_color = Colors.RED
                    recommendation = f"NEED {max(1, round(calls/10))} agents"
                    unstaffed_hours.append(hour)
                    critical_hours.append(hour)
                else:
                    status = "⚪ NO CALLS"
                    status_color = Colors.RESET
                    recommendation = "No action needed"
            
            elif occupancy > OPTIMAL_OCCUPANCY_MAX:
                status = "🔴 OVER-UTILIZED"
                status_color = Colors.RED
                understaffed_hours.append(hour)
                recommendation = f"Add {max(1, round((occupancy-OPTIMAL_OCCUPANCY_MAX)/20))} agent(s)"
                if avg_queue > 30 or abandon_rate > MAX_ACCEPTABLE_ABANDON:
                    critical_hours.append(hour)
            
            elif occupancy < OPTIMAL_OCCUPANCY_MIN:
                status = "🟡 UNDER-UTILIZED"
                status_color = Colors.YELLOW
                overstaffed_hours.append(hour)
                reduction = max(1, round((OPTIMAL_OCCUPANCY_MIN - occupancy)/20))
                recommendation = f"Reduce by {reduction} agent(s)"
            
            else:
                status = "🟢 OPTIMAL"
                status_color = Colors.GREEN
                recommendation = "Maintain current"
            
            # Color code metrics
            sl_color = Colors.GREEN if service_level >= TARGET_SERVICE_LEVEL else Colors.YELLOW if service_level >= 60 else Colors.RED
            abandon_color = Colors.GREEN if abandon_rate <= MAX_ACCEPTABLE_ABANDON else Colors.YELLOW if abandon_rate <= 10 else Colors.RED
            
            # Print row
            print(f"{hour:02d}:00  {calls:<8} {agents:<8} ", end='')
            print_color(f"{occupancy:.0f}%{' ':<4} ", Colors.CYAN, end='')
            print_color(f"{utilization:.0f}%{' ':<4} ", Colors.CYAN, end='')
            print_color(f"{service_level:.0f}%{' ':<4} ", sl_color, end='')
            print_color(f"{abandon_rate:.0f}%{' ':<4} ", abandon_color, end='')
            print_color(f"{status:<15}", status_color, end='')
            print_color(f" {recommendation}", Colors.RESET)
        
        print("=" * 120)
        
        # ===== DETAILED ANALYSIS =====
        print(f"\n📊 DETAILED STAFFING ANALYSIS:")
        print("-" * 70)
        
        # 1. UNSTAFFED HOURS ANALYSIS
        if unstaffed_hours:
            unattended_calls = sum(safe_int(h['calls']) for h in hourly if safe_int(h['active_agents']) == 0)
            unattended_percent = (unattended_calls / total_calls * 100) if total_calls > 0 else 0
            
            print_color(f"\n  🔴 CRITICAL: {len(unstaffed_hours)} Unstaffed Hours", Colors.RED)
            print(f"     • {unattended_calls} calls ({unattended_percent:.1f}% of total) had NO agents available")
            print(f"     • Potential lost revenue: ${unattended_calls * 5:.2f} (est. $5/call)")
            
            # Show unstaffed hours
            print(f"\n     Unstaffed hours:")
            for h in sorted(unstaffed_hours):
                hour_data = next((x for x in hourly if x['hour'] == h), None)
                if hour_data and hour_data['calls'] > 0:
                    print(f"       • {h:02d}:00 - {hour_data['calls']} calls abandoned")
        
        # 2. UNDERSTAFFED HOURS ANALYSIS
        if understaffed_hours:
            print_color(f"\n  🔴 Understaffed Hours: {len(understaffed_hours)}", Colors.RED)
            print(f"     Hours with high occupancy (>85%):")
            for h in sorted(understaffed_hours[:5]):
                hour_data = next((x for x in hourly if x['hour'] == h), None)
                if hour_data:
                    print(f"       • {h:02d}:00 - {hour_data['calls']} calls, {hour_data['avg_queue']:.0f}s queue")
        
        # 3. OVERSTAFFED HOURS ANALYSIS
        if overstaffed_hours:
            wasted_hours = 0
            for h in overstaffed_hours:
                hour_data = next((x for x in hourly if x['hour'] == h), None)
                if hour_data:
                    agents = safe_int(hour_data['active_agents'])
                    calls = safe_int(hour_data['calls'])
                    optimal = max(1, round(calls / 10))  # 10 calls per agent is reasonable
                    wasted_hours += max(0, agents - optimal)
            
            print_color(f"\n  🟡 Overstaffed Hours: {len(overstaffed_hours)}", Colors.YELLOW)
            print(f"     • Wasted agent hours: {wasted_hours}")
            print(f"     • Estimated wasted cost: ${wasted_hours * 15:.2f} (at $15/hr)")
            
            # Show worst overstaffed hours
            print(f"\n     Most overstaffed hours:")
            overstaffed_details = []
            for h in overstaffed_hours:
                hour_data = next((x for x in hourly if x['hour'] == h), None)
                if hour_data:
                    calls_per_agent = hour_data['calls'] / hour_data['active_agents'] if hour_data['active_agents'] > 0 else 0
                    overstaffed_details.append((h, calls_per_agent))
            
            for h, cpa in sorted(overstaffed_details, key=lambda x: x[1])[:3]:
                print(f"       • {h:02d}:00 - {cpa:.1f} calls/agent")
        
        # ===== COST ANALYSIS =====
        print(f"\n💰 COST ANALYSIS:")
        print("-" * 70)
        
        HOURLY_RATE = 15  # Adjust as needed
        
        # Calculate total labor cost
        total_labor_cost = total_agents * HOURLY_RATE
        print(f"  Total labor cost:    ${total_labor_cost:,.2f}")
        
        # Calculate cost per call
        cost_per_call = total_labor_cost / total_calls if total_calls > 0 else 0
        print(f"  Cost per call:       ${cost_per_call:.2f}")
        
        # Calculate wasted cost from overstaffing
        wasted_hours = 0
        for h in hourly:
            agents = safe_int(h['active_agents'])
            calls = safe_int(h['calls'])
            if agents > 0 and calls > 0:
                # Erlang-inspired: optimal agents = ceil(calls * AHT / 3600)
                optimal = max(1, round(calls * 180 / 3600))  # 3min AHT
                wasted_hours += max(0, agents - optimal)
        
        if wasted_hours > 0:
            wasted_cost = wasted_hours * HOURLY_RATE
            print_color(f"  Wasted labor cost:    ${wasted_cost:,.2f}", Colors.YELLOW)
            print(f"     ({wasted_hours} excess agent hours)")
        
        # Calculate lost revenue from unattended calls
        if unstaffed_hours:
            unattended_calls = sum(safe_int(h['calls']) for h in hourly if safe_int(h['active_agents']) == 0)
            potential_sales = unattended_calls * 0.05  # Assume 5% conversion
            lost_revenue = potential_sales * 50  # Assume $50 per sale
            print_color(f"  Lost revenue potential: ${lost_revenue:,.2f}", Colors.RED)
            print(f"     ({unattended_calls} unattended calls)")
        
        # ===== RECOMMENDATIONS =====
        print(f"\n💡 PROFESSIONAL RECOMMENDATIONS:")
        print("-" * 70)
        
        # Priority 1: Fix unstaffed hours
        if unstaffed_hours:
            print_color(f"\n  🔴 PRIORITY 1 - Staff Unstaffed Hours:", Colors.RED)
            
            # Group unstaffed hours into shifts
            unstaffed_hours_sorted = sorted(unstaffed_hours)
            shifts = []
            current_shift = []
            
            for hour in unstaffed_hours_sorted:
                if not current_shift or hour == current_shift[-1] + 1:
                    current_shift.append(hour)
                else:
                    if current_shift:
                        shifts.append(current_shift)
                    current_shift = [hour]
            if current_shift:
                shifts.append(current_shift)
            
            for shift in shifts:
                if len(shift) == 1:
                    print(f"     • Add 1 agent at {shift[0]:02d}:00")
                else:
                    print(f"     • Add 1 agent from {shift[0]:02d}:00 to {shift[-1]+1:02d}:00")
            
            # Calculate total agents needed
            total_needed = len(shifts)  # One agent per continuous shift
            print_color(f"\n     TOTAL: Need {total_needed} additional agents for unstaffed hours", Colors.RED)
        
        # Priority 2: Optimize overstaffed hours
        if overstaffed_hours:
            print_color(f"\n  🟡 PRIORITY 2 - Optimize Overstaffed Hours:", Colors.YELLOW)
            
            # Find the most overstaffed hours
            overstaffed_with_metrics = []
            for h in overstaffed_hours:
                hour_data = next((x for x in hourly if x['hour'] == h), None)
                if hour_data:
                    calls_per_agent = hour_data['calls'] / hour_data['active_agents'] if hour_data['active_agents'] > 0 else 0
                    overstaffed_with_metrics.append((h, hour_data['active_agents'], calls_per_agent))
            
            overstaffed_with_metrics.sort(key=lambda x: x[2])  # Sort by calls/agent (lowest first)
            
            for h, agents, cpa in overstaffed_with_metrics[:3]:
                reduction = max(1, round(agents - (agents * 0.5)))  # Reduce by ~50%
                print(f"     • Reduce by {reduction} agent{'s' if reduction>1 else ''} at {h:02d}:00 ({cpa:.1f} calls/agent)")
        
        # Priority 3: Fine-tune understaffed hours
        if understaffed_hours and not unstaffed_hours:
            print_color(f"\n  🟡 PRIORITY 3 - Address Understaffed Hours:", Colors.YELLOW)
            print(f"     • Add 1 agent during peak hours to improve service levels")
        
        # Final summary recommendation
        print(f"\n  📊 EXECUTIVE SUMMARY:")
        print(f"     • Current staffing cost: ${total_labor_cost:,.2f}")
        
        if unstaffed_hours:
            additional_cost = total_needed * 4 * HOURLY_RATE  # Assume 4-hour shifts
            print(f"     • Recommended additional cost: ${additional_cost:,.2f}")
            print(f"     • Expected benefit: Recover {unattended_calls} abandoned calls")
        
        if wasted_hours > 0:
            savings = wasted_hours * HOURLY_RATE
            print(f"     • Potential savings from optimization: ${savings:,.2f}")
        
        print(f"\n  ⏱️  Analysis completed in {time.time()-start_time:.1f} seconds")
        
    except Exception as e:
        print_error(f"Error in workforce analysis: {e}")
        import traceback
        traceback.print_exc()

def analyze_weekly_staffing():
    """Analyze staffing patterns over the last 7 days"""
    print_header("📊 WEEKLY WORKFORCE ANALYSIS", Colors.CYAN)
    print("⏳ Loading weekly data...")
    
    try:
        query = """
        SELECT 
            DATE(call_date) as date,
            DAYNAME(call_date) as day_name,
            COUNT(DISTINCT c.uniqueid) as calls,
            COUNT(DISTINCT a.user) as unique_agents,
            AVG(c.queue_seconds) as avg_queue,
            SUM(CASE WHEN c.term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') THEN 1 ELSE 0 END) as abandoned,
            SUM(a.talk_sec) as total_talk
        FROM vicidial_closer_log c
        LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
        WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        GROUP BY DATE(call_date)
        ORDER BY date
        LIMIT 7
        """
        
        results = db.execute_query(query)
        
        if not results:
            print_warning("No data available for the last 7 days")
            return
        
        print(f"\n{'Day':<12} {'Date':<12} {'Calls':<8} {'Agents':<8} {'Calls/Agent':<12} {'Queue':<8} {'Abandon%':<8} {'Talk Time':<10}")
        print("-" * 90)
        
        total_calls = 0
        total_agents = 0
        total_talk = 0
        
        for r in results:
            date_str = r['date'].strftime('%m/%d')
            day = r['day_name'][:3]
            calls = safe_int(r['calls'])
            agents = safe_int(r['unique_agents'])
            avg_queue = safe_float(r['avg_queue'])
            abandoned = safe_int(r['abandoned'])
            talk = safe_int(r['total_talk'])
            abandon_rate = (abandoned / calls * 100) if calls > 0 else 0
            
            calls_per_agent = calls / agents if agents > 0 else 0
            talk_per_call = talk / calls if calls > 0 else 0
            
            # Color code by performance
            if avg_queue > 60 or abandon_rate > 10:
                color = Colors.RED
            elif avg_queue > 30 or abandon_rate > 5:
                color = Colors.YELLOW
            else:
                color = Colors.GREEN
            
            print_color(f"{day:<12} {date_str:<12} {calls:<8} {agents:<8} {calls_per_agent:<12.1f} {avg_queue:.0f}s{' ':<4} {abandon_rate:.0f}%{' ':<4} {sec_to_hms(talk_per_call)}", color)
            
            total_calls += calls
            total_agents += agents
            total_talk += talk
        
        print("-" * 90)
        avg_daily_calls = total_calls / len(results)
        avg_daily_agents = total_agents / len(results)
        avg_talk_per_call = total_talk / total_calls if total_calls > 0 else 0
        print(f"AVG: {avg_daily_calls:.0f} calls/day | {avg_daily_agents:.0f} agents/day | {sec_to_hms(avg_talk_per_call)} avg talk")
        
    except Exception as e:
        print_error(f"Error: {e}")

def staffing_recommendations():
    """Generate automated staffing recommendations based on historical patterns"""
    print_header("💡 STAFFING RECOMMENDATIONS", Colors.GREEN)
    print("⏳ Analyzing historical patterns (last 14 days)...")
    
    try:
        # Use last 14 days for pattern analysis
        query = """
        SELECT 
            HOUR(call_date) as hour,
            AVG(calls) as avg_calls,
            AVG(agents) as avg_agents,
            AVG(queue) as avg_queue,
            AVG(abandon_rate) as avg_abandon,
            AVG(talk_time) as avg_talk
        FROM (
            SELECT 
                DATE(call_date) as day,
                HOUR(call_date) as hour,
                COUNT(DISTINCT c.uniqueid) as calls,
                COUNT(DISTINCT a.user) as agents,
                AVG(c.queue_seconds) as queue,
                AVG(CASE WHEN c.term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') THEN 100 ELSE 0 END) as abandon_rate,
                AVG(a.talk_sec) as talk_time
            FROM vicidial_closer_log c
            LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
            WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
            GROUP BY DATE(call_date), HOUR(call_date)
        ) daily
        WHERE calls > 0
        GROUP BY hour
        ORDER BY hour
        """
        
        hourly_patterns = db.execute_query(query)
        
        if not hourly_patterns:
            print_warning("Insufficient data for recommendations")
            return
        
        print(f"\n📋 RECOMMENDED STAFFING BY HOUR (Based on 14-day average):")
        print("=" * 100)
        print(f"{'Hour':<6} {'Avg Calls':<10} {'Current':<8} {'Recommended':<12} {'Change':<10} {'Status':<15}")
        print("-" * 100)
        
        # Industry standard: 1 agent can handle ~10 calls per hour with 3min average handle time
        AVERAGE_HANDLE_TIME = 180  # 3 minutes
        CALLS_PER_AGENT = 3600 / AVERAGE_HANDLE_TIME  # ~20 calls per hour maximum
        SAFE_CALLS_PER_AGENT = 15  # Conservative estimate with buffer
        
        total_current = 0
        total_recommended = 0
        
        for h in hourly_patterns:
            hour = safe_int(h['hour'])
            avg_calls = safe_float(h['avg_calls'])
            current_agents = safe_float(h['avg_agents'])
            avg_queue = safe_float(h['avg_queue'])
            avg_abandon = safe_float(h['avg_abandon'])
            
            if avg_calls == 0:
                continue
            
            # Calculate recommended agents using Erlang-like formula
            # Base recommendation: calls / SAFE_CALLS_PER_AGENT
            base_recommended = avg_calls / SAFE_CALLS_PER_AGENT
            
            # Adjust for poor service levels
            if avg_queue > 30 or avg_abandon > 5:
                base_recommended *= 1.3  # Add 30% more agents
            elif avg_queue < 10 and avg_abandon < 2:
                base_recommended *= 0.9  # Can reduce 10%
            
            recommended = max(1, round(base_recommended))
            change = recommended - current_agents
            
            total_current += current_agents
            total_recommended += recommended
            
            # Determine status
            if avg_queue > 60 or avg_abandon > 10:
                status = "🔴 CRITICAL"
                status_color = Colors.RED
            elif avg_queue > 30 or avg_abandon > 5:
                status = "🟡 NEEDS WORK"
                status_color = Colors.YELLOW
            else:
                status = "🟢 GOOD"
                status_color = Colors.GREEN
            
            # Color code change
            if change > 1:
                change_color = Colors.RED
                change_symbol = "▲ +"
            elif change < -1:
                change_color = Colors.GREEN
                change_symbol = "▼ "
            else:
                change_color = Colors.YELLOW
                change_symbol = "→ "
            
            print(f"{hour:02d}:00  {avg_calls:<10.1f} {current_agents:<8.1f} ", end='')
            print_color(f"{recommended:<12} ", Colors.CYAN, end='')
            print_color(f"{change_symbol}{abs(change):.0f}{' ':<4} ", change_color, end='')
            print_color(f"{status}", status_color)
        
        print("=" * 100)
        
        # Summary
        print(f"\n📊 STAFFING SUMMARY:")
        print("-" * 50)
        print(f"  Current daily agent hours:  {total_current:.0f}")
        print(f"  Recommended daily agent hours: {total_recommended:.0f}")
        print(f"  Difference: {total_recommended - total_current:+.0f} hours")
        
        # Cost impact
        HOURLY_RATE = 15
        current_cost = total_current * HOURLY_RATE
        recommended_cost = total_recommended * HOURLY_RATE
        cost_diff = recommended_cost - current_cost
        
        print(f"\n💰 COST IMPACT:")
        print("-" * 50)
        print(f"  Current daily cost:  ${current_cost:,.2f}")
        print(f"  Recommended daily cost: ${recommended_cost:,.2f}")
        
        if cost_diff > 0:
            print_color(f"  ⚠️ Additional investment needed: +${cost_diff:,.2f}/day", Colors.YELLOW)
        elif cost_diff < 0:
            print_color(f"  ✅ Potential savings: ${abs(cost_diff):,.2f}/day", Colors.GREEN)
        else:
            print(f"  No cost impact")
        
        # Recommendations
        print(f"\n💡 ACTION ITEMS:")
        print("-" * 50)
        
        # Find hours needing most attention
        needs_agents = []
        can_reduce = []
        
        for h in hourly_patterns:
            hour = safe_int(h['hour'])
            avg_calls = safe_float(h['avg_calls'])
            current = safe_float(h['avg_agents'])
            avg_queue = safe_float(h['avg_queue'])
            avg_abandon = safe_float(h['avg_abandon'])
            
            if avg_calls == 0:
                continue
            
            base_recommended = avg_calls / SAFE_CALLS_PER_AGENT
            recommended = max(1, round(base_recommended))
            
            if avg_queue > 30 or avg_abandon > 5:
                needs_agents.append((hour, recommended - current))
            elif current > recommended + 1 and avg_queue < 10:
                can_reduce.append((hour, current - recommended))
        
        if needs_agents:
            print_color(f"  🔴 NEED MORE AGENTS:", Colors.RED)
            for hour, need in sorted(needs_agents, key=lambda x: x[1], reverse=True)[:3]:
                print(f"     • Add {need:.0f} agent(s) at {hour:02d}:00")
        
        if can_reduce:
            print_color(f"  🟡 CAN REDUCE AGENTS:", Colors.YELLOW)
            for hour, reduce in sorted(can_reduce, key=lambda x: x[1], reverse=True)[:3]:
                print(f"     • Reduce by {reduce:.0f} agent(s) at {hour:02d}:00")
        
    except Exception as e:
        print_error(f"Error: {e}")

def workforce_menu():
    """Main workforce management menu"""
    while True:
        print_header("📊 WORKFORCE MANAGEMENT", Colors.CYAN)
        print("  1. 📅 Daily Staffing Analysis (Professional)")
        print("  2. 📆 Weekly Staffing Analysis")
        print("  3. 💡 Staffing Recommendations (14-day pattern)")
        print("  4. 📈 Peak Hour Analysis")
        print("  5. 📉 Efficiency Report")
        print("  0. 🔙 Back")
        print("-" * 70)
        print("   Using Industry Standards: Occupancy, Service Level, Erlang")
        print("-" * 70)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            print("\nSelect date:")
            print("  1. Today")
            print("  2. Yesterday")
            print("  3. Specific date")
            date_choice = input("Choice (1-3): ").strip()
            
            if date_choice == '1':
                target = datetime.now().date()
                print(f"\n📅 Selected: Today ({target})")
            elif date_choice == '2':
                target = datetime.now().date() - timedelta(days=1)
                print(f"\n📅 Selected: Yesterday ({target})")
            elif date_choice == '3':
                date_str = input("Enter date (YYYY-MM-DD): ").strip()
                try:
                    target = datetime.strptime(date_str, '%Y-%m-%d').date()
                    print(f"\n📅 Selected: {target}")
                except:
                    print_error("Invalid date format")
                    continue
            else:
                target = datetime.now().date() - timedelta(days=1)
                print(f"\n📅 Selected: Yesterday ({target})")
            
            analyze_daily_staffing(target)
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            analyze_weekly_staffing()
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            staffing_recommendations()
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            print_header("📈 PEAK HOUR ANALYSIS", Colors.YELLOW)
            print("\n🚧 Coming soon: Detailed peak hour optimization with Erlang-C")
            input("\nPress Enter to continue...")
        
        elif choice == '5':
            print_header("📉 EFFICIENCY REPORT", Colors.MAGENTA)
            print("\n🚧 Coming soon: Agent efficiency metrics with benchmarking")
            input("\nPress Enter to continue...")
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    workforce_menu()