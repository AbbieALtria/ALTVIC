#!/usr/bin/env python3
# =============================================================================
# File:         vicidial_qc_reports.py
# Version:      1.1.0
# Date:         2026-03-10
# Description:  Pull QC data from VICIdial with error handling for missing tables
# Location:     D:/Altria_Ops/quality/vicidial_qc_reports.py
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info
from utils.formatter import format_datetime, sec_to_hms

# =============================================================================
# Helper function to check if QC tables exist
# =============================================================================

def check_qc_tables():
    """Check if VICIdial QC tables exist in database"""
    try:
        # Check for qc_scorecards table
        result = db.execute_query("SHOW TABLES LIKE 'qc_scorecards'")
        if not result:
            return False, "qc_scorecards"
        
        # Check for qc_results table
        result = db.execute_query("SHOW TABLES LIKE 'qc_results'")
        if not result:
            return False, "qc_results"
        
        # Check for qc_checkpoints table
        result = db.execute_query("SHOW TABLES LIKE 'qc_checkpoints'")
        if not result:
            return False, "qc_checkpoints"
        
        return True, None
    except Exception as e:
        return False, str(e)

# =============================================================================
# QC Data Functions (with error handling)
# =============================================================================

def get_qc_scorecard_summary(scorecard_id=None, days=30):
    """Get summary of QC evaluations"""
    try:
        query = """
        SELECT 
            qcr.scorecard_id,
            qcs.scorecard_name,
            COUNT(*) as total_evaluations,
            AVG(qcr.total_score) as avg_score,
            MAX(qcr.total_score) as max_score,
            MIN(qcr.total_score) as min_score,
            SUM(CASE WHEN qcr.instant_kill = 1 THEN 1 ELSE 0 END) as instant_kills,
            AVG(qcr.time_to_complete) as avg_review_time
        FROM qc_results qcr
        JOIN qc_scorecards qcs ON qcr.scorecard_id = qcs.scorecard_id
        WHERE qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        
        params = [days]
        
        if scorecard_id:
            query += " AND qcr.scorecard_id = %s"
            params.append(scorecard_id)
        
        query += " GROUP BY qcr.scorecard_id"
        
        results = db.execute_query(query, params) or []
        return results
    except Exception as e:
        # Silent fail - tables might not exist
        return []

def get_agent_qc_scores(agent=None, days=30):
    """Get QC scores by agent"""
    try:
        query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as evaluations,
            AVG(qcr.total_score) as avg_score,
            SUM(CASE WHEN qcr.total_score >= 90 THEN 1 ELSE 0 END) as excellent,
            SUM(CASE WHEN qcr.total_score BETWEEN 70 AND 89 THEN 1 ELSE 0 END) as good,
            SUM(CASE WHEN qcr.total_score < 70 THEN 1 ELSE 0 END) as needs_improvement
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        """
        
        params = [days]
        
        if agent:
            query += " AND a.user = %s"
            params.append(agent)
        
        query += " GROUP BY a.user ORDER BY avg_score DESC"
        
        results = db.execute_query(query, params) or []
        return results
    except Exception as e:
        return []

def get_checkpoint_performance(scorecard_id, days=30):
    """Analyze how agents perform on each checkpoint"""
    try:
        query = """
        SELECT 
            qcc.checkpoint_text,
            AVG(qcr_d.score_given) as avg_score,
            MAX(qcc.max_points) as max_points,
            AVG(qcr_d.score_given / qcc.max_points * 100) as pct_achieved,
            COUNT(*) as times_evaluated,
            SUM(CASE WHEN qcr_d.score_given = qcc.max_points THEN 1 ELSE 0 END) as perfect_scores,
            SUM(CASE WHEN qcr_d.score_given = 0 THEN 1 ELSE 0 END) as zero_scores
        FROM qc_results_detail qcr_d
        JOIN qc_checkpoints qcc ON qcr_d.checkpoint_id = qcc.checkpoint_id
        JOIN qc_results qcr ON qcr_d.result_id = qcr.result_id
        WHERE qcr.scorecard_id = %s
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY qcc.checkpoint_id
        ORDER BY pct_achieved
        """
        
        results = db.execute_query(query, (scorecard_id, days)) or []
        return results
    except Exception as e:
        return []

# =============================================================================
# Display Functions (with graceful error handling)
# =============================================================================

def show_qc_dashboard():
    """Display QC dashboard in Altria Ops"""
    
    print_header("📋 VICIdial Quality Control Dashboard", Colors.CYAN)
    
    # Check if QC tables exist
    tables_exist, missing = check_qc_tables()
    
    if not tables_exist:
        print_warning("⚠️ VICIdial QC tables not found in your database")
        print("\nThis feature requires VICIdial Quality Control modules to be enabled.")
        print("\n📋 To enable QC in VICIdial:")
        print("   1. Log into VICIdial Admin panel")
        print("   2. Go to 'Admin' → 'System Settings'")
        print("   3. Enable 'qc_enabled' option")
        print("   4. Run: http://[your-server]/vicidial/QC_setup.php")
        print("\n💡 Use options 1-4 for built-in quality scoring instead.")
        input("\nPress Enter to continue...")
        return
    
    # Get scorecard summary
    summaries = get_qc_scorecard_summary(days=30)
    
    if not summaries:
        print_warning("No QC data available for last 30 days")
        print("\nThis could mean:")
        print("  • No quality evaluations have been performed yet")
        print("  • The QC tables are empty")
        print("  • You need to create scorecards in VICIdial first")
        input("\nPress Enter to continue...")
        return
    
    print(f"\n📊 SCORECARD SUMMARY (Last 30 days):")
    print("-" * 90)
    
    for s in summaries:
        print(f"\n{s['scorecard_name']} ({s['scorecard_id']}):")
        print(f"  • Evaluations: {s['total_evaluations']}")
        print(f"  • Average Score: {s['avg_score']:.1f}%")
        print(f"  • Range: {s['min_score']}% - {s['max_score']}%")
        print(f"  • Instant Kills: {s['instant_kills']}")
        print(f"  • Avg Review Time: {s['avg_review_time']:.0f} seconds")
    
    # Get agent performance
    agents = get_agent_qc_scores(days=30)
    
    if agents:
        print(f"\n👥 AGENT QUALITY SCORES:")
        print("-" * 90)
        print(f"{'Agent':<15} {'Name':<20} {'Evals':<8} {'Avg%':<8} {'Excellent':<10} {'Good':<8} {'Needs Work':<10}")
        print("-" * 90)
        
        for a in agents[:10]:
            color = Colors.GREEN if a['avg_score'] >= 90 else Colors.YELLOW if a['avg_score'] >= 75 else Colors.RED
            print_color(
                f"{a['user']:<15} {a['full_name']:<20} {a['evaluations']:<8} "
                f"{a['avg_score']:.1f}%{' ':<4} {a['excellent']:<10} {a['good']:<8} {a['needs_improvement']:<10}",
                color
            )
    else:
        print("\nNo agent QC data available.")

def show_sop_compliance_report():
    """Show SOP compliance by checkpoint - with error handling"""
    
    print_header("📋 SOP COMPLIANCE ANALYSIS", Colors.MAGENTA)
    
    # Check if QC tables exist
    tables_exist, missing = check_qc_tables()
    
    if not tables_exist:
        print_warning("⚠️ VICIdial QC tables not found in your database")
        print("\nThis feature requires VICIdial Quality Control modules to be enabled.")
        print("\n📋 To enable QC in VICIdial:")
        print("   1. Log into VICIdial Admin panel")
        print("   2. Go to 'Admin' → 'System Settings'")
        print("   3. Enable 'qc_enabled' option")
        print("   4. Run: http://[your-server]/vicidial/QC_setup.php")
        print("\n💡 Use options 1-4 for built-in quality scoring instead.")
        input("\nPress Enter to continue...")
        return
    
    # Get list of scorecards
    try:
        scorecards = db.execute_query("SELECT scorecard_id, scorecard_name FROM qc_scorecards WHERE active = 'Y'")
    except Exception as e:
        print_error(f"Error accessing scorecards: {e}")
        input("\nPress Enter to continue...")
        return
    
    if not scorecards:
        print_warning("No active scorecards found")
        print("\nPlease create a scorecard in VICIdial QC module first.")
        input("\nPress Enter to continue...")
        return
    
    print("\nSelect scorecard:")
    for i, sc in enumerate(scorecards, 1):
        print(f"  {i}. {sc['scorecard_name']} ({sc['scorecard_id']})")
    
    choice = input("\nChoice: ").strip()
    
    if choice.isdigit() and 1 <= int(choice) <= len(scorecards):
        sc = scorecards[int(choice)-1]
        
        checkpoints = get_checkpoint_performance(sc['scorecard_id'])
        
        if checkpoints:
            print(f"\n📊 CHECKPOINT ANALYSIS - {sc['scorecard_name']}")
            print("-" * 100)
            print(f"{'Checkpoint':<50} {'Avg%':<8} {'Perfect':<10} {'Failed':<8} {'Status'}")
            print("-" * 100)
            
            for cp in checkpoints:
                bar_length = int(cp['pct_achieved'] / 5)
                bar = "█" * bar_length
                
                if cp['pct_achieved'] >= 90:
                    color = Colors.GREEN
                    status = "✅ Good"
                elif cp['pct_achieved'] >= 75:
                    color = Colors.YELLOW
                    status = "⚠️ Needs Review"
                else:
                    color = Colors.RED
                    status = "🔴 Needs Training"
                
                print_color(
                    f"{cp['checkpoint_text'][:47]:<50} {cp['pct_achieved']:.1f}%{' ':<3} "
                    f"{cp['perfect_scores']:<10} {cp['zero_scores']:<8} {status}",
                    color
                )
        else:
            print_warning("No checkpoint data available for this scorecard")
    else:
        print_error("Invalid choice")
    
    input("\nPress Enter to continue...")