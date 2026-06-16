# agents/schedule_predictive.py - Bridge between schedule and predictive analytics

from datetime import datetime, timedelta
from core.database import db
from utils.colors import Colors, print_color, print_header, print_success, print_error

def get_schedule_gaps(start_date=None, days=14):
    """Compare scheduled agents vs predicted needs"""
    
    if not start_date:
        start_date = datetime.now().date()
    
    # Get predicted staffing needs from forecast
    try:
        from forecasting.predictive import get_staffing_forecast
        predictions = get_staffing_forecast(days)
    except ImportError:
        print_error("Predictive module not available")
        return []
    
    # Get actual scheduled agents for each day
    gaps = []
    for pred in predictions:
        # Query actual scheduled agents for this date
        scheduled = db.execute_query("""
            SELECT COUNT(*) as scheduled_count
            FROM agent_shifts
            WHERE shift_date = %s
              AND approved = TRUE
        """, (pred['date'],))
        
        scheduled_count = scheduled[0]['scheduled_count'] if scheduled else 0
        
        # Calculate gap
        needed = pred['agents_needed']
        gap = scheduled_count - needed
        gap_percent = (gap / needed * 100) if needed > 0 else 0
        
        gaps.append({
            'date': pred['date'],
            'day_name': pred['day_name'],
            'predicted_calls': pred['predicted_calls'],
            'agents_needed': needed,
            'agents_scheduled': scheduled_count,
            'gap': gap,
            'gap_percent': gap_percent,
            'status': 'UNDERSTAFFED' if gap < 0 else 'OVERSTAFFED' if gap > 0 else 'OPTIMAL'
        })
    
    return gaps

def show_schedule_gaps():
    """Display schedule gaps vs predictions"""
    print_header("📊 SCHEDULE VS PREDICTIONS", Colors.MAGENTA)
    
    days = input("Days to analyze (default 14): ").strip()
    days = int(days) if days.isdigit() else 14
    
    gaps = get_schedule_gaps(days=days)
    
    if not gaps:
        print_warning("No data available")
        return
    
    print(f"\n{'='*100}")
    print(f"{'Date':<12} {'Day':<10} {'Predicted':<10} {'Needed':<8} {'Scheduled':<10} {'Gap':<8} {'Status':<12}")
    print(f"{'='*100}")
    
    total_needed = 0
    total_scheduled = 0
    
    for g in gaps:
        if g['gap'] < 0:
            color = Colors.RED
            status_display = f"{Colors.RED}UNDERSTAFFED{Colors.RESET}"
        elif g['gap'] > 0:
            color = Colors.YELLOW
            status_display = f"{Colors.YELLOW}OVERSTAFFED{Colors.RESET}"
        else:
            color = Colors.GREEN
            status_display = f"{Colors.GREEN}OPTIMAL{Colors.RESET}"
        
        gap_display = f"{g['gap']:+d}" if g['gap'] != 0 else "0"
        
        print_color(
            f"{g['date']:<12} {g['day_name']:<10} {g['predicted_calls']:<10} "
            f"{g['agents_needed']:<8} {g['agents_scheduled']:<10} {gap_display:<8} {status_display}",
            color if g['gap'] != 0 else Colors.RESET
        )
        
        total_needed += g['agents_needed']
        total_scheduled += g['agents_scheduled']
    
    print(f"{'='*100}")
    
    total_gap = total_scheduled - total_needed
    total_color = Colors.GREEN if total_gap == 0 else Colors.RED if total_gap < 0 else Colors.YELLOW
    print_color(
        f"TOTAL: {' '*32} {total_needed:<8} {total_scheduled:<10} {total_gap:+d}",
        total_color
    )
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    understaffed = [g for g in gaps if g['gap'] < 0]
    overstaffed = [g for g in gaps if g['gap'] > 0]
    
    if understaffed:
        print_color(f"  • {len(understaffed)} understaffed days - consider adding shifts:", Colors.RED)
        for g in understaffed[:3]:
            print(f"    - {g['date']}: need {abs(g['gap'])} more agents")
    
    if overstaffed:
        print_color(f"  • {len(overstaffed)} overstaffed days - consider approving time off:", Colors.YELLOW)
        for g in overstaffed[:3]:
            print(f"    - {g['date']}: {g['gap']} extra agents")