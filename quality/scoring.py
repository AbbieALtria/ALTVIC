#!/usr/bin/env python3
# =============================================================================
# File:         scoring.py
# Version:      6.0.1
# Date:         2026-03-25
# Description:  Quality Scoring Module for Altria Ops
#               Complete advanced reports with AI integration and audit trail
# =============================================================================
# UPDATES:
#   6.0.1 (2026-03-25) - Fixed print_color end parameter usage
#   6.0.0 (2026-03-25) - Complete rewrite with all advanced reports
#         - Added show_quality_dashboard() - Overall quality metrics
#         - Added show_top_performers_advanced() - Top 10 agents with stability
#         - Added show_coaching_opportunities_advanced() - Agents needing coaching
#         - Added show_agent_quality_detail_advanced() - Detailed agent view
#         - Fixed show_calibration_report() - SQL error resolved
#         - Integrated AI Assistant (Option 8)
#         - All reports filter by status = 'ACTIVE'
# =============================================================================

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_header, print_success, print_error, print_info, print_warning, print_color
from utils.formatter import sec_to_hms

# Import AI Assistant
try:
    from quality.ai_assistant import show_ai_assistant
except ImportError:
    show_ai_assistant = None
    print_warning("AI Assistant module not found. Install quality/ai_assistant.py")


# =============================================================================
# QUALITY DASHBOARD
# =============================================================================

def show_quality_dashboard():
    """Show quality dashboard with overall stats"""
    print_header("📊 QUALITY DASHBOARD", Colors.CYAN)
    
    try:
        # Get overall stats
        query = """
        SELECT 
            COUNT(*) as total_evaluations,
            COUNT(DISTINCT a.user) as unique_agents,
            ROUND(AVG(total_score), 1) as avg_score,
            ROUND(MIN(total_score), 1) as min_score,
            ROUND(MAX(total_score), 1) as max_score,
            COUNT(CASE WHEN total_score >= 80 THEN 1 END) as excellent,
            COUNT(CASE WHEN total_score >= 70 AND total_score < 80 THEN 1 END) as good,
            COUNT(CASE WHEN total_score < 70 THEN 1 END) as needs_improvement
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        WHERE (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
        """
        
        stats = db.execute_query(query) or []
        
        if stats and stats[0]['total_evaluations'] > 0:
            s = stats[0]
            print(f"\n📈 OVERALL QUALITY METRICS:")
            print(f"  • Total Evaluations: {s['total_evaluations']}")
            print(f"  • Agents Evaluated: {s['unique_agents']}")
            print(f"  • Average Score: {s['avg_score']:.1f}%")
            print(f"  • Score Range: {s['min_score']}% - {s['max_score']}%")
            print(f"\n📊 SCORE DISTRIBUTION:")
            print(f"  • Excellent (80-100%): {s['excellent']} ({s['excellent']/s['total_evaluations']*100:.1f}%)")
            print(f"  • Good (70-79%): {s['good']} ({s['good']/s['total_evaluations']*100:.1f}%)")
            print(f"  • Needs Improvement (<70%): {s['needs_improvement']} ({s['needs_improvement']/s['total_evaluations']*100:.1f}%)")
        else:
            print_warning("\nNo quality data available yet.")
            print_info("   Use AI Assistant (Option 8) to generate evaluations.")
            
    except Exception as e:
        print_error(f"Error in quality dashboard: {e}")
    
    input("\nPress Enter to continue...")


# =============================================================================
# TOP PERFORMERS (ADVANCED)
# =============================================================================

def show_top_performers_advanced():
    """Advanced top performers report with AI confidence and score stability"""
    print_header("🏆 TOP PERFORMERS - ADVANCED", Colors.GREEN)
    
    print("\nSelect period:")
    print("  1. Last 7 days")
    print("  2. Last 30 days")
    print("  3. Last 90 days")
    print("  4. All time")
    print("  5. Custom")
    
    period_choice = input("\nChoice (1-5): ").strip()
    
    if period_choice == '1':
        days = 7
        period_name = "Last 7 days"
    elif period_choice == '2':
        days = 30
        period_name = "Last 30 days"
    elif period_choice == '3':
        days = 90
        period_name = "Last 90 days"
    elif period_choice == '4':
        days = 9999
        period_name = "All time"
    elif period_choice == '5':
        days_input = input("Number of days: ").strip()
        days = int(days_input) if days_input.isdigit() else 30
        period_name = f"Last {days} days"
    else:
        days = 30
        period_name = "Last 30 days"
    
    try:
        # Get top performers
        query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as evaluations,
            ROUND(AVG(qcr.total_score), 1) as avg_score,
            ROUND(STDDEV(qcr.total_score), 1) as score_stddev,
            MIN(qcr.total_score) as min_score,
            MAX(qcr.total_score) as max_score,
            COUNT(CASE WHEN qcr.source = 'HYBRID' THEN 1 END) as hybrid_count
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY a.user
        HAVING evaluations >= 1
        ORDER BY avg_score DESC
        LIMIT 10
        """
        
        results = db.execute_query(query, (days,)) or []
        
        if not results:
            print_warning(f"No data available for {period_name}")
            input("\nPress Enter to continue...")
            return
        
        print(f"\n{'=' * 110}")
        print(f"🏆 TOP PERFORMERS - {period_name.upper()}")
        print(f"{'=' * 110}")
        
        print(f"{'Rank':<6} {'Agent':<12} {'Name':<20} {'Evals':<8} {'Avg%':<8} "
              f"{'Range':<12} {'Stability':<12} {'Source':<12}")
        print("-" * 110)
        
        for i, r in enumerate(results, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
            
            # Determine stability
            stddev = r['score_stddev'] if r['score_stddev'] else 0
            if stddev < 5:
                stability = "🌟 Very Stable"
                stability_color = Colors.GREEN
            elif stddev < 10:
                stability = "📊 Stable"
                stability_color = Colors.CYAN
            else:
                stability = "⚠️ Variable"
                stability_color = Colors.YELLOW
            
            # Score range
            score_range = f"{r['min_score']}% - {r['max_score']}%"
            
            # Source badge
            if r['hybrid_count'] > 0:
                source_badge = f"🤖 AI+QA ({r['hybrid_count']})"
            else:
                source_badge = "👤 Manual"
            
            name_display = r['full_name'][:20] if r['full_name'] else 'Unknown'
            
            # Color for top 3
            if i == 1:
                color = Colors.GREEN
            elif i == 2:
                color = Colors.CYAN
            elif i == 3:
                color = Colors.BLUE
            else:
                color = Colors.RESET
            
            # Build the line without using end parameter
            line1 = f"{medal:<6} {r['user']:<12} {name_display:<20} {r['evaluations']:<8} "
            line2 = f"{r['avg_score']:.1f}%{' ':<4} {score_range:<12} "
            
            # Print the first part with color
            print_color(line1 + line2, color)
            
            # Print stability and source on the same line
            print_color(stability, stability_color)
            print("  ", end="")
            print_color(source_badge, Colors.MAGENTA if r['hybrid_count'] > 0 else Colors.RESET)
        
        print("-" * 110)
        
        # Additional insights
        if results:
            print(f"\n📊 PERFORMANCE INSIGHTS:")
            print(f"  • Top performer: {results[0]['user']} ({results[0]['avg_score']:.1f}%)")
            print(f"  • Average score of top {len(results)}: {sum(r['avg_score'] for r in results) / len(results):.1f}%")
            
            # Most consistent
            consistent = min(results, key=lambda x: x['score_stddev'] or 100)
            if consistent['score_stddev']:
                print(f"  • Most consistent: {consistent['user']} (std dev: {consistent['score_stddev']:.1f})")
            
            # Highest volume
            highest_volume = max(results, key=lambda x: x['evaluations'])
            print(f"  • Most evaluated: {highest_volume['user']} ({highest_volume['evaluations']} evaluations)")
        
    except Exception as e:
        print_error(f"Error in top performers: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to continue...")


# =============================================================================
# COACHING OPPORTUNITIES (ADVANCED)
# =============================================================================

def show_coaching_opportunities_advanced():
    """Advanced coaching opportunities report with AI confidence"""
    print_header("📈 COACHING OPPORTUNITIES - ADVANCED", Colors.YELLOW)
    
    try:
        # Get agents with low scores
        query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as total_evaluations,
            ROUND(AVG(qcr.total_score), 1) as avg_score,
            MIN(qcr.total_score) as min_score,
            MAX(qcr.total_score) as max_score,
            COUNT(CASE WHEN qcr.source = 'HYBRID' THEN 1 END) as hybrid_count
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY a.user
        HAVING avg_score < 70
        ORDER BY avg_score
        """
        
        results = db.execute_query(query) or []
        
        if not results:
            print_success("\n✅ No agents currently need coaching!")
            input("\nPress Enter to continue...")
            return
        
        print(f"\n{'=' * 100}")
        print(f"Agents below 70% average quality score (Last 30 days)")
        print(f"{'=' * 100}")
        
        print(f"{'Agent':<15} {'Name':<20} {'Evals':<8} {'Avg%':<8} {'Range':<12} {'Priority':<12}")
        print("-" * 100)
        
        for r in results:
            # Determine priority
            if r['avg_score'] < 50:
                priority = "🔴 IMMEDIATE"
                priority_color = Colors.RED
            elif r['avg_score'] < 60:
                priority = "🟡 URGENT"
                priority_color = Colors.YELLOW
            else:
                priority = "🟢 SCHEDULED"
                priority_color = Colors.GREEN
            
            name_display = r['full_name'][:20] if r['full_name'] else 'Unknown'
            score_range = f"{r['min_score']}% - {r['max_score']}%"
            
            # Build the line
            line = f"{r['user']:<15} {name_display:<20} {r['total_evaluations']:<8} "
            line += f"{r['avg_score']:.1f}%{' ':<4} {score_range:<12} {priority}"
            
            print_color(line, priority_color)
        
        print("-" * 100)
        
        # Summary
        if results:
            avg_overall = sum(r['avg_score'] for r in results) / len(results)
            print(f"\n📊 COACHING SUMMARY:")
            print(f"  • Agents needing coaching: {len(results)}")
            print(f"  • Average score among these agents: {avg_overall:.1f}%")
        
        # Action recommendations
        if results:
            print(f"\n💡 RECOMMENDED ACTIONS:")
            for r in results[:5]:
                if r['avg_score'] < 50:
                    print(f"  • {r['user']}: Immediate coaching session required")
                elif r['avg_score'] < 60:
                    print(f"  • {r['user']}: Schedule coaching within 5 days")
                else:
                    print(f"  • {r['user']}: Monitor and provide feedback")
        
    except Exception as e:
        print_error(f"Error in coaching opportunities: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to continue...")


# =============================================================================
# AGENT QUALITY DETAIL (ADVANCED)
# =============================================================================

def show_agent_quality_detail_advanced():
    """Advanced agent quality report with AI vs QA comparison"""
    from agents.dashboard import show_agent_list, get_agent_by_selection
    
    # Show agent list
    agents = show_agent_list()
    if not agents:
        input("\nPress Enter to continue...")
        return
    
    selected_agent = get_agent_by_selection(agents)
    if not selected_agent:
        return
    
    # Get period
    print("\nSelect period:")
    print("  1. Last 7 days")
    print("  2. Last 30 days")
    print("  3. Last 90 days")
    print("  4. All time")
    
    period_choice = input("\nChoice (1-4): ").strip()
    
    if period_choice == '1':
        days = 7
        period_name = "Last 7 days"
    elif period_choice == '2':
        days = 30
        period_name = "Last 30 days"
    elif period_choice == '3':
        days = 90
        period_name = "Last 90 days"
    else:
        days = 9999
        period_name = "All time"
    
    try:
        # Get agent summary
        query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as total_evaluations,
            ROUND(AVG(qcr.total_score), 1) as avg_score,
            ROUND(STDDEV(qcr.total_score), 1) as score_stddev,
            MIN(qcr.total_score) as min_score,
            MAX(qcr.total_score) as max_score,
            COUNT(CASE WHEN qcr.source = 'HYBRID' THEN 1 END) as hybrid_count
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE a.user = %s
          AND (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY a.user
        """
        
        data = db.execute_query(query, (selected_agent, days)) or []
        
        if not data:
            print_warning(f"No QC data found for agent {selected_agent} in {period_name}")
            input("\nPress Enter to continue...")
            return
        
        r = data[0]
        
        print_header(f"📊 AGENT QUALITY DETAIL: {selected_agent} ({r['full_name'] or 'Unknown'})", Colors.MAGENTA)
        print(f"Period: {period_name}")
        print(f"{'=' * 80}")
        
        # Overall stats
        print(f"\n📈 OVERALL PERFORMANCE:")
        print(f"  • Evaluations: {r['total_evaluations']}")
        print(f"  • Average Score: {r['avg_score']:.1f}%")
        print(f"  • Range: {r['min_score']}% - {r['max_score']}%")
        print(f"  • Consistency: {'Very Stable' if r['score_stddev'] and r['score_stddev'] < 5 else 'Stable' if r['score_stddev'] and r['score_stddev'] < 10 else 'Variable'}")
        
        # Recent evaluations
        recent_query = """
        SELECT 
            qcr.result_id,
            qcr.evaluation_date,
            qcr.total_score as final_score,
            qcr.source,
            c.campaign_id,
            c.phone_number
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        JOIN vicidial_closer_log c ON qcr.uniqueid = c.uniqueid
        WHERE a.user = %s
          AND (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
        ORDER BY qcr.evaluation_date DESC
        LIMIT 10
        """
        
        recent = db.execute_query(recent_query, (selected_agent,)) or []
        
        if recent:
            print(f"\n📋 RECENT EVALUATIONS (Last 10):")
            print("-" * 80)
            print(f"{'Date':<12} {'Campaign':<12} {'Score':<8} {'Source':<12}")
            print("-" * 80)
            
            for ev in recent:
                date_str = ev['evaluation_date'].strftime('%Y-%m-%d') if hasattr(ev['evaluation_date'], 'strftime') else str(ev['evaluation_date'])[:10]
                source_badge = "🤖 AI+QA" if ev['source'] == 'HYBRID' else "👤 Manual" if ev['source'] == 'MANUAL' else "🤖 AI"
                print(f"{date_str:<12} {ev['campaign_id']:<12} {ev['final_score']}%{' ':<4} {source_badge:<12}")
        
        print("\n" + "=" * 80)
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if r['avg_score'] < 60:
            print(f"  • Immediate coaching recommended")
        elif r['avg_score'] < 70:
            print(f"  • Schedule coaching session")
        else:
            print(f"  • Performance is good - maintain current practices")
        
        if r['score_stddev'] and r['score_stddev'] > 15:
            print(f"  • High variability in scores - focus on consistency")
        
    except Exception as e:
        print_error(f"Error in agent quality detail: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to continue...")


# =============================================================================
# CALIBRATION REPORT (FIXED)
# =============================================================================

def show_calibration_report():
    """Show AI vs QA score calibration report - FIXED"""
    print_header("📊 AI vs QA CALIBRATION REPORT", Colors.CYAN)
   
    try:
        # Check if we have enough data
        count_query = """
        SELECT COUNT(*) as total_evaluations
        FROM qc_results qcr
        WHERE qcr.ai_total_score IS NOT NULL
          AND (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
       
        count_result = db.execute_query(count_query) or [{'total_evaluations': 0}]
        total_evals = count_result[0].get('total_evaluations', 0)
       
        if total_evals < 3:
            print_warning(f"\nNot enough data for calibration (need at least 3 evaluations)")
            print_info(f"   Current evaluations with AI scores: {total_evals}")
            print_info("   Use AI Assistant (Option 8) to generate more evaluations.")
            input("\nPress Enter to continue...")
            return
       
        query = """
        SELECT
            a.user,
            u.full_name,
            COUNT(*) as total_evaluations,
            ROUND(AVG(qcr.total_score), 1) as avg_final,
            ROUND(AVG(qcr.ai_total_score), 1) as avg_ai,
            ROUND(AVG(qcr.total_score - qcr.ai_total_score), 1) as avg_diff,
            ROUND(AVG(qcr.ai_confidence), 1) as avg_confidence,
            COUNT(CASE WHEN qcr.source = 'HYBRID' THEN 1 END) as reviewed_count
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE qcr.ai_total_score IS NOT NULL
          AND (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY a.user
        HAVING total_evaluations >= 1
        ORDER BY ABS(AVG(qcr.total_score - qcr.ai_total_score)) DESC
        """
       
        results = db.execute_query(query) or []
       
        if not results:
            print_warning("\nNo calibration data found yet.")
            input("\nPress Enter to continue...")
            return
       
        print(f"\n{'=' * 110}")
        print("AI vs QA Calibration Report - Last 30 Days")
        print(f"{'=' * 110}")
       
        print(f"{'Agent':<12} {'Name':<20} {'Evals':<8} {'AI Avg':<8} {'QA Avg':<8} {'Diff':<8} {'Conf':<10} {'Reviewed':<10}")
        print("-" * 110)
       
        agents_with_issues = 0
       
        for r in results:
            diff = r.get('avg_diff') or 0
           
            if abs(diff) > 10:
                status_color = Colors.RED
                agents_with_issues += 1
            elif abs(diff) > 5:
                status_color = Colors.YELLOW
            else:
                status_color = Colors.GREEN
           
            name_display = str(r.get('full_name') or r['user'])[:20]
           
            line = f"{r['user']:<12} {name_display:<20} {r['total_evaluations']:<8} "
            line += f"{r.get('avg_ai', 0):.1f}%  {r.get('avg_final', 0):.1f}%  "
            line += f"{diff:+.1f}   {r.get('avg_confidence', 0):.0f}%   {r.get('reviewed_count', 0)}"
           
            print_color(line, status_color)
       
        print("-" * 110)
       
        if results:
            avg_diff_overall = sum(abs(r.get('avg_diff') or 0) for r in results) / len(results)
            print(f"\n📊 SUMMARY:")
            print(f" • Agents analyzed : {len(results)}")
            print(f" • Agents needing review : {agents_with_issues}")
            print(f" • Average AI/QA difference : {avg_diff_overall:.1f}%")
           
            if agents_with_issues > 0:
                print_color(f"   → Please review the {agents_with_issues} agents with large differences", Colors.YELLOW)
            else:
                print_success("   → AI and QA scores are well aligned!")
       
    except Exception as e:
        print_error(f"Error in calibration report: {e}")
        import traceback
        traceback.print_exc()
   
    input("\nPress Enter to continue...")


# =============================================================================
# CONFIGURE QUALITY SETTINGS
# =============================================================================

def configure_quality_settings():
    """Configure quality scoring settings"""
    print_header("⚙️ CONFIGURE QUALITY SETTINGS", Colors.CYAN)
    print_info("Quality settings - Coming Soon")
    print("\nFuture features:")
    print("  • AI confidence thresholds")
    print("  • Coaching thresholds")
    print("  • Score weights")
    print("  • Notification settings")
    input("\nPress Enter to continue...")


# =============================================================================
# MAIN QUALITY MENU
# =============================================================================

def show_quality_menu():
    """Main Call Quality Scoring Menu"""
    while True:
        print_header("🎯 CALL QUALITY SCORING", Colors.CYAN)
        print("  ────────────────────────────────────────────────────────────")
        print("   1. 📊 Quality Dashboard")
        print("   2. 👤 Agent Quality Report (Advanced)")
        print("   3. 🏆 Top Performers (Advanced)")
        print("   4. 📈 Coaching Opportunities (Advanced)")
        print("   5. 📋 VICIdial QC Dashboard")
        print("   6. 📋 SOP Compliance Analysis")
        print("   7. ✨ Add QC Evaluation")
        print("   8. 🤖 AI Assistant (Auto-Score)")
        print("   9. 📊 AI vs QA Calibration Report")
        print("  10. ⚙️ Configure Quality Settings")
        print("   0. 🔙 Back to Main Menu")
        print("  ────────────────────────────────────────────────────────────")

        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

        if choice == '1':
            show_quality_dashboard()
        elif choice == '2':
            show_agent_quality_detail_advanced()
        elif choice == '3':
            show_top_performers_advanced()
        elif choice == '4':
            show_coaching_opportunities_advanced()
        elif choice == '5':
            print_info("VICIdial QC Dashboard - Use external VICIdial interface")
            input("\nPress Enter to continue...")
        elif choice == '6':
            print_info("SOP Compliance Analysis - Coming Soon")
            input("\nPress Enter to continue...")
        elif choice == '7':
            print_info("Add QC Evaluation - Use AI Assistant (Option 8) for automated evaluation")
            input("\nPress Enter to continue...")
        elif choice == '8':
            if show_ai_assistant:
                show_ai_assistant()
            else:
                print_error("AI Assistant module not found")
                input("\nPress Enter to continue...")
        elif choice == '9':
            show_calibration_report()
        elif choice == '10':
            configure_quality_settings()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    show_quality_menu()