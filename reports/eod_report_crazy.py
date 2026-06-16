#!/usr/bin/env python3
# =============================================================================
# File:         eod_report.py
# Version:      1.4.0
# Date:         2026-03-03
# Description:  End of Day (EOD) Report – EST-based, PDF export, per-campaign option
#               Clean flow: no repeated date prompt for Today/Yesterday
# Location:     D:/Altria_Ops/reports/eod_report.py
# =============================================================================

import os
from datetime import datetime, timedelta
import pytz

from core.database import db
from utils.colors import Colors, print_header, print_success, print_error, print_warning, print_info
from utils.formatter import sec_to_hms

from fpdf import FPDF

# ────────────────────────────────────────────────
# Timezone Helpers
# ────────────────────────────────────────────────

def get_timezone_info():
    utc_now = datetime.utcnow()
    
    try:
        server_row = db.execute_query("SELECT NOW() as now", ())
        server_now = server_row[0]['now'] if server_row else utc_now
    except:
        server_now = utc_now

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
    tz = get_timezone_info()
    print_header("🕒 TIMEZONE STATUS", Colors.CYAN)
    print(f"  Server: {tz['server'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  EST:    {tz['est'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  PST:    {tz['pst'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Report uses EST calendar day")
    print("═" * 70)

# ────────────────────────────────────────────────
# Date & Campaign Selection
# ────────────────────────────────────────────────

def get_est_date(choice):
    tz = get_timezone_info()
    est_today = tz['est_date']

    if choice == '1':
        return est_today, "Today"
    elif choice == '2':
        return est_today - timedelta(days=1), "Yesterday"
    elif choice == '3':
        date_str = input("Enter date (YYYY-MM-DD): ").strip()
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
            return d, d.strftime('%A, %Y-%m-%d')
        except:
            print_error("Invalid date – using yesterday")
            return est_today - timedelta(days=1), "Yesterday"
    else:
        return est_today - timedelta(days=1), "Yesterday"

def select_campaigns():
    try:
        rows = db.execute_query("""
            SELECT DISTINCT campaign_id
            FROM vicidial_closer_log
            WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY campaign_id
        """, ())
        campaigns = [r['campaign_id'].strip() for r in rows if r['campaign_id']]
    except Exception as e:
        print_error(f"Cannot load campaigns: {e}")
        return []

    if not campaigns:
        print_warning("No campaigns found in last 30 days")
        return []

    print_header("📋 SELECT CAMPAIGNS", Colors.CYAN)
    print("\nAvailable campaigns:")

    col_width = 28
    cols = 3
    for i, c in enumerate(campaigns, 1):
        print(f"  {i:3}. {c:<{col_width}}", end="")
        if i % cols == 0:
            print()
    if len(campaigns) % cols:
        print()

    print("\nEnter: numbers (e.g. 1,3-6), 'all', or Enter = all")
    sel = input(f"\n{Colors.CYAN}Selection: {Colors.RESET}").strip().lower()

    if sel in ('', 'all'):
        return campaigns

    selected = []
    for p in sel.split(','):
        p = p.strip()
        if '-' in p:
            try:
                s, e = map(int, p.split('-'))
                selected.extend(campaigns[s-1:e])
            except:
                pass
        else:
            try:
                idx = int(p) - 1
                if 0 <= idx < len(campaigns):
                    selected.append(campaigns[idx])
            except:
                pass

    return selected or campaigns

# ────────────────────────────────────────────────
# Report Generation
# ────────────────────────────────────────────────

def generate_eod_report(target_date, selected_campaigns=None):
    print_timezone_banner()
    print(f"📊 Generating EOD report for {target_date}")

    campaign_filter = ""
    params = [target_date]
    if selected_campaigns:
        ph = ','.join(['%s'] * len(selected_campaigns))
        campaign_filter = f" AND campaign_id IN ({ph})"
        params += selected_campaigns

    query = f"""
    SELECT
        campaign_id,
        COUNT(*) AS routed,
        SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered,
        SUM(CASE WHEN length_in_sec < 5 AND queue_seconds > 0 THEN 1 ELSE 0 END) AS abandoned,
        SUM(CASE WHEN queue_seconds <= 20 THEN 1 ELSE 0 END) AS sl20_count,
        SUM(CASE WHEN queue_seconds <= 30 THEN 1 ELSE 0 END) AS sl30_count,
        AVG(CASE WHEN length_in_sec >= 5 THEN length_in_sec END) AS avg_talk_sec,
        AVG(queue_seconds) AS avg_queue_sec,
        SUM(length_in_sec) AS total_talk_sec
    FROM vicidial_closer_log
    WHERE DATE(call_date) = %s {campaign_filter}
    GROUP BY campaign_id
    ORDER BY routed DESC
    """

    try:
        rows = db.execute_query(query, tuple(params))
    except Exception as e:
        print_error(f"Query failed: {e}")
        return None

    report = {
        'date_str': target_date.strftime('%Y-%m-%d'),
        'day_name': target_date.strftime('%A'),
        'campaigns': [],
        'totals': {
            'routed': 0, 'answered': 0, 'abandoned': 0,
            'sl20_count': 0, 'sl30_count': 0,
            'total_talk_sec': 0
        }
    }

    for r in rows or []:
        routed = int(r['routed'] or 0)
        answered = int(r['answered'] or 0)
        abandoned = int(r['abandoned'] or 0)

        camp = {
            'campaign': r['campaign_id'],
            'routed': routed,
            'answered': answered,
            'abandoned': abandoned,
            'sl20_pct': (r['sl20_count'] / routed * 100) if routed else 0,
            'sl30_pct': (r['sl30_count'] / routed * 100) if routed else 0,
            'abandon_pct': (abandoned / routed * 100) if routed else 0,
            'avg_talk_sec': r['avg_talk_sec'] or 0,
            'avg_queue_sec': r['avg_queue_sec'] or 0,
            'total_talk_sec': int(r['total_talk_sec'] or 0)
        }
        report['campaigns'].append(camp)

        t = report['totals']
        t['routed'] += routed
        t['answered'] += answered
        t['abandoned'] += abandoned
        t['sl20_count'] += int(r['sl20_count'] or 0)
        t['sl30_count'] += int(r['sl30_count'] or 0)
        t['total_talk_sec'] += int(r['total_talk_sec'] or 0)

    if t['routed'] > 0:
        t['sl20_pct'] = t['sl20_count'] / t['routed'] * 100
        t['sl30_pct'] = t['sl30_count'] / t['routed'] * 100
        t['abandon_pct'] = t['abandoned'] / t['routed'] * 100
        t['avg_talk_sec'] = t['total_talk_sec'] / t['answered'] if t['answered'] else 0

    return report

# ────────────────────────────────────────────────
# Display
# ────────────────────────────────────────────────

def display_eod_report(report):
    if not report or not report['campaigns']:
        print_warning("No data to show")
        return

    print_timezone_banner()
    print(f"\nEnd of Day Report – {report['date_str']} ({report['day_name']})")
    print("═" * 100)

    print(f"{'Campaign':<24} {'Routed':>9} {'Answered':>10} {'SL20%':>7} {'Aband':>8} {'Aband%':>7} {'Avg Talk':>12}")
    print("─" * 100)

    for c in report['campaigns']:
        print(f"{c['campaign']:<24} {c['routed']:>9,} {c['answered']:>10,} {c['sl20_pct']:>6.1f}% {c['abandoned']:>8,} {c['abandon_pct']:>6.1f}% {sec_to_hms(c['avg_talk_sec']):>12}")

    t = report['totals']
    print("─" * 100)
    print(f"{'TOTAL':<24} {t['routed']:>9,} {t['answered']:>10,} {t['sl20_pct']:>6.1f}% {t['abandoned']:>8,} {t['abandon_pct']:>6.1f}% {sec_to_hms(t['avg_talk_sec']):>12}")

# ────────────────────────────────────────────────
# PDF Export
# ────────────────────────────────────────────────

def export_eod_pdf(report, filename=None):
    if not report or not report['campaigns']:
        print_warning("No data for PDF")
        return

    date_str = report['date_str']
    if filename is None:
        filename = f"EOD_{date_str}.pdf"

    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()

    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 12, f"EOD Report – {date_str} ({report['day_name']})", ln=1, align='C')
    pdf.ln(5)

    tz = get_timezone_info()
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f"Server: {tz['server']:%Y-%m-%d %H:%M:%S}", ln=1)
    pdf.cell(0, 8, f"EST:    {tz['est']:%Y-%m-%d %H:%M:%S %Z}", ln=1)
    pdf.cell(0, 8, f"PST:    {tz['pst']:%Y-%m-%d %H:%M:%S %Z}", ln=1)
    pdf.ln(10)

    headers = ["Campaign", "Routed", "Answered", "SL20%", "Aband.", "Aband%", "Avg Talk"]
    widths = [50, 25, 25, 20, 20, 20, 35]

    pdf.set_font('Arial', 'B', 10)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 10, h, 1, 0, 'C')
    pdf.ln()

    pdf.set_font('Arial', '', 9)
    for c in report['campaigns']:
        row = [
            c['campaign'],
            f"{c['routed']:,}",
            f"{c['answered']:,}",
            f"{c['sl20_pct']:.1f}%",
            f"{c['abandoned']:,}",
            f"{c['abandon_pct']:.1f}%",
            sec_to_hms(c['avg_talk_sec'])
        ]
        for i, v in enumerate(row):
            pdf.cell(widths[i], 8, str(v), 1, 0, 'C')
        pdf.ln()

    pdf.output(filename)
    print_success(f"PDF saved → {os.path.abspath(filename)}")

# ────────────────────────────────────────────────
# Main Flow
# ────────────────────────────────────────────────

def show_eod_report(menu_choice):
    print_header("📊 END OF DAY REPORT", Colors.MAGENTA)

    if menu_choice in ('1', '2'):
        target_date, label = get_est_date(menu_choice)
        print_info(f"→ {label} (EST): {target_date}")
    else:
        target_date, label = get_est_date('3')

    campaigns = select_campaigns()
    if not campaigns:
        return

    report = generate_eod_report(target_date, campaigns)
    if report:
        display_eod_report(report)

        # Per-campaign export
        print("\n" + "─" * 60)
        print("Create separate files per campaign?")
        print("  1. No")
        print("  2. Yes – PDF per campaign")
        print("  3. Yes – CSV per campaign")
        ch = input("Choice (1-3) [1]: ").strip() or '1'

        if ch in ('2', '3'):
            fmt = "PDF" if ch == '2' else "CSV"
            print_info(f"Generating individual {fmt} files...")
            for camp in campaigns:
                single = generate_eod_report(target_date, [camp])
                if single:
                    date_str = target_date.strftime('%Y-%m-%d')
                    camp_clean = camp.replace('/', '_').replace('\\', '_')
                    if ch == '2':
                        fname = f"EOD_{camp_clean}_{date_str}.pdf"
                        export_eod_pdf(single, fname)
                    else:
                        fname = f"EOD_{camp_clean}_{date_str}.csv"
                        print(f"[CSV placeholder] → {fname}")
                        # → call your CSV function here

    input("\nPress Enter to return...")

# ────────────────────────────────────────────────
# EOD Menu
# ────────────────────────────────────────────────

def eod_report_menu():
    while True:
        print_header("📊 END OF DAY (EOD) REPORTS", Colors.CYAN)
        print("  1. Today's Report (EST)")
        print("  2. Yesterday's Report (EST)")
        print("  3. Specific Date Report")
        print("  4. Last 7 Days Summary")
        print("  5. Compare Two Days")
        print("  6. Report Settings")
        print("  7. Export Options")
        print("  0. Back")
        print("─" * 60)

        ch = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

        if ch in ('1', '2', '3'):
            show_eod_report(ch)
        elif ch == '0':
            break
        else:
            print_error("Invalid choice")
            input("Press Enter...")

if __name__ == "__main__":
    eod_report_menu()