#!/usr/bin/env python3
# =============================================================================
# File:         report_viewer.py
# Version:      1.2.0 - FIXED
# Date:         2026-03-25
# Description:  QC Report Viewer with safe formatting
# =============================================================================

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_header, print_success, print_error, print_info, print_warning, print_color
from utils.formatter import sec_to_hms


def get_agents():
    """Get list of agents with evaluations"""
    query = """
    SELECT DISTINCT a.user, u.full_name
    FROM qc_results qcr
    JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
    LEFT JOIN vicidial_users u ON a.user = u.user
    WHERE (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
    ORDER BY a.user
    """
    results = db.execute_query(query) or []
    return results


def get_date_range(choice):
    """Get date range based on user choice"""
    today = datetime.now().date()
    
    if choice == '1':      # Today
        return today, today, "Today"
    elif choice == '2':    # Yesterday
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday, "Yesterday"
    elif choice == '3':    # Last 7 Days
        start = today - timedelta(days=7)
        return start, today, "Last 7 Days"
    elif choice == '4':    # Last 30 Days
        start = today - timedelta(days=30)
        return start, today, "Last 30 Days"
    elif choice == '5':    # This Month
        start = today.replace(day=1)
        return start, today, "This Month"
    elif choice == '6':    # Custom
        start_str = input("Start date (YYYY-MM-DD): ").strip()
        end_str = input("End date (YYYY-MM-DD): ").strip()
        try:
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
            end = datetime.strptime(end_str, '%Y-%m-%d').date()
            return start, end, f"{start_str} to {end_str}"
        except:
            print_error("Invalid date format")
            return None, None, None
    else:
        return today, today, "Today"


def show_evaluation_details(result_id):
    """Show detailed scores for a specific evaluation"""
    header_query = """
    SELECT 
        qcr.result_id,
        qcr.evaluation_date,
        qcr.total_score,
        qcr.ai_total_score,
        qcr.ai_confidence,
        qcr.source,
        qcr.comments,
        a.user as agent,
        u.full_name as agent_name,
        c.campaign_id,
        c.phone_number,
        c.length_in_sec
    FROM qc_results qcr
    JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
    JOIN vicidial_closer_log c ON qcr.uniqueid = c.uniqueid
    LEFT JOIN vicidial_users u ON a.user = u.user
    WHERE qcr.result_id = %s
      AND (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
    """
    
    header = db.execute_query(header_query, (result_id,))
    if not header:
        print_error(f"Evaluation {result_id} not found")
        return
    h = header[0]
    
    checkpoint_query = """
    SELECT 
        c.display_order,
        c.checkpoint_text,
        d.score_given,
        c.max_points,
        ROUND(d.score_given / c.max_points * 100, 1) as percentage
    FROM qc_results_detail d
    JOIN qc_checkpoints c ON d.checkpoint_id = c.checkpoint_id
    WHERE d.result_id = %s
    ORDER BY c.display_order
    """
    
    checkpoints = db.execute_query(checkpoint_query, (result_id,)) or []
    
    print_header(f"📋 EVALUATION DETAILS - ID: {result_id}", Colors.MAGENTA)
    
    print(f"\n📞 CALL INFORMATION:")
    print(f"  • Agent: {h.get('agent_name') or h.get('agent', 'Unknown')} ({h.get('agent', 'Unknown')})")
    print(f"  • Campaign: {h.get('campaign_id', 'Unknown')}")
    print(f"  • Phone: {h.get('phone_number', 'Unknown')}")
    print(f"  • Duration: {sec_to_hms(h.get('length_in_sec', 0))}")
    print(f"  • Date: {h['evaluation_date']}")
    
    print(f"\n📊 SCORE SUMMARY:")
    print(f"  • Final Score: {h.get('total_score', 0)}%")
    if h.get('ai_total_score') is not None:
        diff = h['total_score'] - h['ai_total_score']
        diff_color = Colors.GREEN if abs(diff) <= 5 else Colors.YELLOW
        print(f"  • AI Suggested: {h['ai_total_score']}%")
        print_color(f"  • Difference: {diff:+.1f}%", diff_color)
        print(f"  • AI Confidence: {h.get('ai_confidence', 0):.0f}%")
    print(f"  • Source: {h.get('source', 'Unknown')}")
    
    if h.get('comments'):
        print(f"\n📝 NOTES:")
        print(f"  {h['comments']}")
    
    print(f"\n📋 CHECKPOINT SCORES:")
    print("-" * 80)
    print(f"{'#':<4} {'Checkpoint':<45} {'Score':<10} {'%':<6}")
    print("-" * 80)
    
    for cp in checkpoints:
        bar_length = int(cp['percentage'] / 5)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        color = Colors.GREEN if cp['percentage'] >= 80 else Colors.YELLOW if cp['percentage'] >= 60 else Colors.RED
        
        print_color(
            f"{cp['display_order']:<4} {cp['checkpoint_text'][:45]:<45} "
            f"{cp['score_given']}/{cp['max_points']:<6} {cp['percentage']:.0f}% {bar}",
            color
        )
    
    print("-" * 80)
    input("\nPress Enter to continue...")


def show_evaluations_list(agent=None, start_date=None, end_date=None, limit=50):
    """Show list of evaluations with SAFE formatting"""
    
    query = """
    SELECT 
        qcr.result_id,
        DATE(qcr.evaluation_date) as eval_date,
        TIME(qcr.evaluation_date) as eval_time,
        qcr.total_score,
        qcr.ai_total_score,
        qcr.ai_confidence,
        qcr.source,
        a.user as agent,
        u.full_name as agent_name,
        c.campaign_id,
        c.length_in_sec
    FROM qc_results qcr
    JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
    LEFT JOIN vicidial_users u ON a.user = u.user
    JOIN vicidial_closer_log c ON qcr.uniqueid = c.uniqueid
    WHERE (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
    """
    
    params = []
    
    if agent:
        query += " AND a.user = %s"
        params.append(agent)
    
    if start_date and end_date:
        query += " AND DATE(qcr.evaluation_date) BETWEEN %s AND %s"
        params.append(start_date)
        params.append(end_date)
    
    query += " ORDER BY qcr.evaluation_date DESC LIMIT %s"
    params.append(limit)
    
    results = db.execute_query(query, params) or []
    
    if not results:
        print_warning("\nNo evaluations found matching your criteria")
        return None
    
    print("\n" + "=" * 120)
    print(f"{'ID':<6} {'Date':<12} {'Time':<10} {'Agent':<15} {'Score':<8} {'AI':<8} {'Conf':<8} {'Campaign':<12} {'Dur':<8}")
    print("=" * 120)
    
    for r in results:
        # Safe date formatting
        eval_date = r.get('eval_date')
        date_str = str(eval_date)[:10] if eval_date else 'Unknown'
        
        # Safe time formatting (handles timedelta)
        eval_time = r.get('eval_time')
        if isinstance(eval_time, timedelta):
            total_sec = int(eval_time.total_seconds())
            time_str = f"{total_sec//3600:02d}:{(total_sec%3600)//60:02d}:{total_sec%60:02d}"
        else:
            time_str = str(eval_time)[:8] if eval_time else '00:00:00'
        
        duration_sec = r.get('length_in_sec', 0) or 0
        duration = f"{duration_sec//60}:{duration_sec%60:02d}"
        
        agent_display = str(r.get('agent_name') or r.get('agent') or 'Unknown')[:15]
        
        score = r.get('total_score', 0)
        if score >= 80:
            score_color = Colors.GREEN
        elif score >= 70:
            score_color = Colors.YELLOW
        else:
            score_color = Colors.RED
        
        print(f"{r['result_id']:<6} {date_str:<12} {time_str:<10} {agent_display:<15} ", end='')
        print_color(f"{score}%", score_color, end='')
        print(f"{' ':<3} {r.get('ai_total_score', 'N/A'):<8} {r.get('ai_confidence', 'N/A'):<8} ", end='')
        print(f"{r.get('campaign_id', 'Unknown'):<12} {duration:<8}")
    
    print("=" * 120)
    return results


def report_viewer_menu():
    """Main Report Viewer Menu"""
    while True:
        print_header("📊 QC REPORT VIEWER", Colors.CYAN)
        print("This tool allows you to retrieve and view old QC evaluations.\n")
        
        print("  1. 📅 View by Date Range")
        print("  2. 👤 View by Agent")
        print("  3. 🔍 View by Agent + Date Range")
        print("  4. 📋 View All Recent Evaluations")
        print("  5. 🔎 Search by Evaluation ID")
        print("  0. 🔙 Back")
        print("-" * 50)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            print("\nSelect date range:")
            print("  1. Today")
            print("  2. Yesterday")
            print("  3. Last 7 Days")
            print("  4. Last 30 Days")
            print("  5. This Month")
            print("  6. Custom Range")
            
            range_choice = input("\nChoice (1-6): ").strip()
            start_date, end_date, period_name = get_date_range(range_choice)
            
            if start_date is None:
                continue
            
            print_info(f"\n📅 Showing evaluations for: {period_name}")
            results = show_evaluations_list(start_date=start_date, end_date=end_date, limit=100)
            
            if results:
                eval_id = input("\nEnter Evaluation ID to view details (or Enter to skip): ").strip()
                if eval_id.isdigit():
                    show_evaluation_details(int(eval_id))
            else:
                input("\nPress Enter to continue...")
        
        elif choice == '2':
            agents = get_agents()
            if not agents:
                print_warning("No agents with evaluations found")
                input("\nPress Enter to continue...")
                continue
            
            print("\n📋 SELECT AGENT:")
            for i, a in enumerate(agents, 1):
                name = a.get('full_name', a['user'])
                print(f"  {i}. {a['user']} ({name})")
            print("  0. Cancel")
            
            agent_choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
            
            if agent_choice == '0':
                continue
            elif agent_choice.isdigit() and 1 <= int(agent_choice) <= len(agents):
                selected_agent = agents[int(agent_choice)-1]['user']
                results = show_evaluations_list(agent=selected_agent, limit=100)
                
                if results:
                    eval_id = input("\nEnter Evaluation ID to view details (or Enter to skip): ").strip()
                    if eval_id.isdigit():
                        show_evaluation_details(int(eval_id))
            else:
                print_error("Invalid choice")
        
        elif choice == '3':
            agents = get_agents()
            if not agents:
                print_warning("No agents with evaluations found")
                input("\nPress Enter to continue...")
                continue
            
            print("\n📋 SELECT AGENT:")
            for i, a in enumerate(agents, 1):
                name = a.get('full_name', a['user'])
                print(f"  {i}. {a['user']} ({name})")
            print("  0. Cancel")
            
            agent_choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
            
            if agent_choice == '0':
                continue
            elif agent_choice.isdigit() and 1 <= int(agent_choice) <= len(agents):
                selected_agent = agents[int(agent_choice)-1]['user']
                
                print("\nSelect date range:")
                print("  1. Today")
                print("  2. Yesterday")
                print("  3. Last 7 Days")
                print("  4. Last 30 Days")
                print("  5. Custom Range")
                
                range_choice = input("\nChoice (1-5): ").strip()
                start_date, end_date, period_name = get_date_range(range_choice)
                
                if start_date is None:
                    continue
                
                results = show_evaluations_list(agent=selected_agent, start_date=start_date, end_date=end_date, limit=100)
                
                if results:
                    eval_id = input("\nEnter Evaluation ID to view details (or Enter to skip): ").strip()
                    if eval_id.isdigit():
                        show_evaluation_details(int(eval_id))
            else:
                print_error("Invalid choice")
        
        elif choice == '4':
            print_info("\n📋 Showing 50 most recent evaluations")
            results = show_evaluations_list(limit=50)
            
            if results:
                eval_id = input("\nEnter Evaluation ID to view details (or Enter to skip): ").strip()
                if eval_id.isdigit():
                    show_evaluation_details(int(eval_id))
            else:
                input("\nPress Enter to continue...")
        
        elif choice == '5':
            eval_id = input("\nEnter Evaluation ID: ").strip()
            if eval_id.isdigit():
                show_evaluation_details(int(eval_id))
            else:
                print_error("Invalid Evaluation ID")
                input("\nPress Enter to continue...")
        
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    report_viewer_menu()