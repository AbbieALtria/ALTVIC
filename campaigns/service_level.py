# campaigns/service_level.py - Service Level Analysis for Altria Ops

from utils.colors import Colors, print_header, print_color, print_error, print_warning, print_success
from core.database import db


def service_level_menu():
    """Service Level Analysis menu."""
    while True:
        print_header("📊 SERVICE LEVEL ANALYSIS", Colors.CYAN)
        print("  " + "─" * 60)
        print("   1. Current Service Level by Campaign")
        print("   2. Service Level Trend (Last 7 Days)")
        print("   3. Service Level Trend (Last 30 Days)")
        print("   4. Hourly Service Level Breakdown")
        print("   5. SLA Breach Report")
        print("   0. Back")
        print("  " + "─" * 60)

        choice = input(f"\n{Colors.CYAN}Select option: {Colors.RESET}").strip()

        if choice == '1':
            show_current_service_level()
        elif choice == '2':
            show_service_level_trend(days=7)
        elif choice == '3':
            show_service_level_trend(days=30)
        elif choice == '4':
            show_hourly_breakdown()
        elif choice == '5':
            show_sla_breach_report()
        elif choice == '0':
            break
        else:
            print_error("Invalid option")
            input("\nPress Enter to continue...")


def show_current_service_level():
    """Show today's service level per campaign."""
    print_header("📊 CURRENT SERVICE LEVEL", Colors.CYAN)

    query = """
        SELECT
            campaign_id,
            COUNT(*) AS total_calls,
            SUM(CASE WHEN queue_seconds <= 20 THEN 1 ELSE 0 END) AS answered_in_sla,
            AVG(queue_seconds) AS avg_wait_sec,
            SUM(CASE WHEN status = 'DROP' THEN 1 ELSE 0 END) AS abandoned
        FROM vicidial_log
        WHERE call_date >= CURDATE()
          AND queue_seconds IS NOT NULL
        GROUP BY campaign_id
        ORDER BY campaign_id
    """

    rows = db.execute_query(query)

    if not rows:
        print_warning("No inbound call data found for today.")
        input("\nPress Enter to continue...")
        return

    print(f"\n  {'Campaign':<20} {'Total':<8} {'In SLA':<8} {'SL%':<8} {'Avg Wait':<12} {'Abandoned'}")
    print("  " + "-" * 70)

    target_sl = 80.0  # default 80% target

    for row in rows:
        total = row['total_calls'] or 0
        in_sla = row['answered_in_sla'] or 0
        sl_pct = (in_sla / total * 100) if total > 0 else 0
        avg_wait = row['avg_wait_sec'] or 0
        abandoned = row['abandoned'] or 0

        color = Colors.GREEN if sl_pct >= target_sl else (Colors.YELLOW if sl_pct >= 60 else Colors.RED)
        sl_str = f"{sl_pct:.1f}%"

        print(f"  {row['campaign_id']:<20} {total:<8} {in_sla:<8} "
              f"{color}{sl_str:<8}{Colors.RESET} {avg_wait:.0f}s{'':<8} {abandoned}")

    print(f"\n  {Colors.CYAN}Target SLA: {target_sl}% of calls answered within 20 seconds{Colors.RESET}")
    input("\nPress Enter to continue...")


def show_service_level_trend(days=7):
    """Show daily service level trend over N days."""
    print_header(f"📈 SERVICE LEVEL TREND — LAST {days} DAYS", Colors.CYAN)

    query = """
        SELECT
            DATE(call_date) AS call_day,
            COUNT(*) AS total_calls,
            SUM(CASE WHEN queue_seconds <= 20 THEN 1 ELSE 0 END) AS answered_in_sla,
            AVG(queue_seconds) AS avg_wait_sec
        FROM vicidial_log
        WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
          AND queue_seconds IS NOT NULL
        GROUP BY DATE(call_date)
        ORDER BY call_day DESC
    """

    rows = db.execute_query(query, (days,))

    if not rows:
        print_warning("No data found for the selected period.")
        input("\nPress Enter to continue...")
        return

    print(f"\n  {'Date':<14} {'Total':<8} {'In SLA':<8} {'SL%':<10} {'Avg Wait'}")
    print("  " + "-" * 55)

    for row in rows:
        total = row['total_calls'] or 0
        in_sla = row['answered_in_sla'] or 0
        sl_pct = (in_sla / total * 100) if total > 0 else 0
        avg_wait = row['avg_wait_sec'] or 0

        color = Colors.GREEN if sl_pct >= 80 else (Colors.YELLOW if sl_pct >= 60 else Colors.RED)
        bar = _mini_bar(sl_pct)

        print(f"  {str(row['call_day']):<14} {total:<8} {in_sla:<8} "
              f"{color}{sl_pct:>5.1f}%{Colors.RESET}  {bar}  {avg_wait:.0f}s")

    input("\nPress Enter to continue...")


def show_hourly_breakdown():
    """Show service level broken down by hour for today."""
    print_header("⏰ HOURLY SERVICE LEVEL — TODAY", Colors.CYAN)

    query = """
        SELECT
            HOUR(call_date) AS hour_of_day,
            COUNT(*) AS total_calls,
            SUM(CASE WHEN queue_seconds <= 20 THEN 1 ELSE 0 END) AS answered_in_sla,
            AVG(queue_seconds) AS avg_wait_sec
        FROM vicidial_log
        WHERE call_date >= CURDATE()
          AND queue_seconds IS NOT NULL
        GROUP BY HOUR(call_date)
        ORDER BY hour_of_day
    """

    rows = db.execute_query(query)

    if not rows:
        print_warning("No data found for today.")
        input("\nPress Enter to continue...")
        return

    print(f"\n  {'Hour':<8} {'Total':<8} {'In SLA':<8} {'SL%':<10} {'Avg Wait'}")
    print("  " + "-" * 50)

    for row in rows:
        total = row['total_calls'] or 0
        in_sla = row['answered_in_sla'] or 0
        sl_pct = (in_sla / total * 100) if total > 0 else 0
        avg_wait = row['avg_wait_sec'] or 0
        hour = int(row['hour_of_day'])
        hour_label = f"{hour:02d}:00"

        color = Colors.GREEN if sl_pct >= 80 else (Colors.YELLOW if sl_pct >= 60 else Colors.RED)
        bar = _mini_bar(sl_pct)

        print(f"  {hour_label:<8} {total:<8} {in_sla:<8} "
              f"{color}{sl_pct:>5.1f}%{Colors.RESET}  {bar}  {avg_wait:.0f}s")

    input("\nPress Enter to continue...")


def show_sla_breach_report():
    """Show campaigns that breached SLA target in the last 7 days."""
    print_header("🚨 SLA BREACH REPORT — LAST 7 DAYS", Colors.RED)

    query = """
        SELECT
            campaign_id,
            DATE(call_date) AS call_day,
            COUNT(*) AS total_calls,
            SUM(CASE WHEN queue_seconds <= 20 THEN 1 ELSE 0 END) AS answered_in_sla,
            AVG(queue_seconds) AS avg_wait_sec,
            MAX(queue_seconds) AS max_wait_sec
        FROM vicidial_log
        WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
          AND queue_seconds IS NOT NULL
        GROUP BY campaign_id, DATE(call_date)
        HAVING (answered_in_sla / total_calls * 100) < 80
        ORDER BY call_day DESC, campaign_id
    """

    rows = db.execute_query(query)

    if not rows:
        print_success("No SLA breaches detected in the last 7 days.")
        input("\nPress Enter to continue...")
        return

    print(f"\n  Found {len(rows)} SLA breach(es):\n")
    print(f"  {'Date':<14} {'Campaign':<20} {'Total':<8} {'SL%':<8} {'Avg Wait':<12} {'Max Wait'}")
    print("  " + "-" * 75)

    for row in rows:
        total = row['total_calls'] or 0
        in_sla = row['answered_in_sla'] or 0
        sl_pct = (in_sla / total * 100) if total > 0 else 0
        avg_wait = row['avg_wait_sec'] or 0
        max_wait = row['max_wait_sec'] or 0

        print(f"  {str(row['call_day']):<14} {row['campaign_id']:<20} {total:<8} "
              f"{Colors.RED}{sl_pct:>5.1f}%{Colors.RESET}   {avg_wait:.0f}s{'':<8} {max_wait:.0f}s")

    input("\nPress Enter to continue...")


def _mini_bar(pct, width=10):
    """Return a simple ASCII progress bar for a percentage value."""
    filled = int((pct / 100) * width)
    filled = max(0, min(width, filled))
    bar = '█' * filled + '░' * (width - filled)
    return f"[{bar}]"
