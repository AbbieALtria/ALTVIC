#!/usr/bin/env python3
# =============================================================================
# File:         email_channel_reports.py
# Version:      1.0.0
# Date:         2026-06-05
# Description:  Dedicated Email Channel Reports — pinktools integration
#               Agent performance, type breakdown, refund value, email vs call
# Location:     D:/Altria_Ops/reports/email_channel_reports.py
# =============================================================================

import csv
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.email_database import email_db
from core.email_integration import (
    get_email_stats_by_agent, get_email_summary,
    get_all_mappings, ensure_mapping_table
)
from core.database import db
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info
from utils.formatter import sec_to_hms


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _server_today():
    """Get TODAY from the email DB server — avoids Windows local clock mismatch."""
    try:
        row = email_db.execute_query("SELECT DATE(NOW()) AS d")
        if row and row[0]['d']:
            return row[0]['d']
    except Exception:
        pass
    return date.today()  # fallback to local if DB unreachable


def _ask_date_range():
    """Prompt user for a date range, return (start_date, end_date)."""
    print("\n  Date range options:")
    print("   1. Today")
    print("   2. Yesterday")
    print("   3. Last 7 days")
    print("   4. Last 30 days")
    print("   5. Custom range")
    choice = input(f"\n{Colors.CYAN}  Choice [2]: {Colors.RESET}").strip() or '2'

    today = _server_today()   # ← uses DB server date, not Windows clock
    print_info(f"  Server date: {today}")

    if choice == '1':
        return today, today
    elif choice == '2':
        d = today - timedelta(days=1)
        return d, d
    elif choice == '3':
        return today - timedelta(days=6), today
    elif choice == '4':
        return today - timedelta(days=29), today
    else:
        try:
            s = input("  Start date (YYYY-MM-DD): ").strip()
            e = input("  End date   (YYYY-MM-DD): ").strip()
            return datetime.strptime(s, '%Y-%m-%d').date(), datetime.strptime(e, '%Y-%m-%d').date()
        except Exception:
            print_warning("Invalid date — defaulting to yesterday.")
            d = today - timedelta(days=1)
            return d, d


def _safe(val, typ=int):
    if val is None:
        return typ(0)
    if isinstance(val, Decimal):
        return typ(val)
    try:
        return typ(val)
    except Exception:
        return typ(0)


def _exports_dir():
    exports = Path(__file__).parent / 'exports'
    exports.mkdir(parents=True, exist_ok=True)
    return exports


# ──────────────────────────────────────────────────────────────────────────────
# Report 1 — Agent Email Performance
# ──────────────────────────────────────────────────────────────────────────────

def report_agent_email_performance():
    """Per-agent email stats for a date range."""
    print_header("📧 AGENT EMAIL PERFORMANCE", Colors.CYAN)
    start, end = _ask_date_range()
    print(f"\n  Period: {start}  →  {end}")

    ensure_mapping_table()
    mapping = get_all_mappings()

    rows = email_db.execute_query(
        """
        SELECT
            agent_name,
            COUNT(*)                            AS total,
            SUM(email_type='CANCELATION REQ')   AS cancels,
            SUM(email_type='FULL REFUND')        AS full_ref,
            SUM(email_type='PARTIAL REFUND')     AS part_ref,
            SUM(email_type='ORDER STATUS')       AS order_st,
            SUM(email_type='GEN INQUIRY')        AS gen_inq,
            SUM(email_type='RESHIPMENT')         AS reship,
            SUM(refund > 0)                      AS ref_cnt,
            COALESCE(SUM(refund), 0)             AS ref_val
        FROM tbl_email
        WHERE DATE(created_2) BETWEEN %s AND %s
          AND agent_name IS NOT NULL AND agent_name != ''
        GROUP BY agent_name
        ORDER BY total DESC
        """,
        (start, end)
    )

    if not rows:
        print_warning("  No email data for this period.")
        input("\nPress Enter to continue...")
        return

    print()
    print(f"  {'Agent':<24} {'Linked':<14} {'Total':<7} {'Cancel':<7} {'FullRef':<8} {'PartRef':<8} {'RefVal':>10}")
    print("  " + "─" * 85)

    totals = dict(total=0, cancels=0, full_ref=0, part_ref=0, ref_cnt=0, ref_val=0.0)
    for r in rows:
        name    = r['agent_name']
        linked  = mapping.get(name, '')
        total   = _safe(r['total'])
        cancels = _safe(r['cancels'])
        full_r  = _safe(r['full_ref'])
        part_r  = _safe(r['part_ref'])
        ref_val = _safe(r['ref_val'], float)

        totals['total']    += total
        totals['cancels']  += cancels
        totals['full_ref'] += full_r
        totals['part_ref'] += part_r
        totals['ref_val']  += ref_val

        color  = Colors.RESET if linked else Colors.YELLOW
        linked_disp = linked if linked else '⚠ Unlinked'
        print_color(
            f"  {name:<24} {linked_disp:<14} {total:<7} {cancels:<7} {full_r:<8} {part_r:<8} ${ref_val:>9,.2f}",
            color
        )

    print("  " + "─" * 85)
    print(f"  {'TOTAL':<24} {'':<14} {totals['total']:<7} {totals['cancels']:<7} "
          f"{totals['full_ref']:<8} {totals['part_ref']:<8} ${totals['ref_val']:>9,.2f}")

    # Export option
    print()
    if input("  Export to CSV? (y/N): ").strip().lower() == 'y':
        _export_agent_perf_csv(rows, mapping, start, end)

    input("\nPress Enter to continue...")


def _export_agent_perf_csv(rows, mapping, start, end):
    fn = _exports_dir() / f"email_agent_perf_{start}_{end}.csv"
    with open(fn, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Agent (pinktools)', 'VICIdial User', 'Total Emails',
                    'Cancellations', 'Full Refunds', 'Partial Refunds',
                    'Order Status', 'Gen Inquiry', 'Reshipments',
                    'Refund Tickets', 'Refund Value'])
        for r in rows:
            name = r['agent_name']
            w.writerow([
                name, mapping.get(name, ''),
                _safe(r['total']), _safe(r['cancels']),
                _safe(r['full_ref']), _safe(r['part_ref']),
                _safe(r['order_st']), _safe(r['gen_inq']),
                _safe(r['reship']), _safe(r['ref_cnt']),
                f"{_safe(r['ref_val'], float):.2f}"
            ])
    print_success(f"  Exported: {fn}")


# ──────────────────────────────────────────────────────────────────────────────
# Report 2 — Email Type Breakdown
# ──────────────────────────────────────────────────────────────────────────────

def report_email_type_breakdown():
    """Daily/weekly breakdown by email_type."""
    print_header("📋 EMAIL TYPE BREAKDOWN", Colors.CYAN)
    start, end = _ask_date_range()
    print(f"\n  Period: {start}  →  {end}")

    rows = email_db.execute_query(
        """
        SELECT
            DATE(created_2)   AS day,
            email_type,
            COUNT(*)          AS cnt,
            COALESCE(SUM(refund), 0) AS ref_val
        FROM tbl_email
        WHERE DATE(created_2) BETWEEN %s AND %s
        GROUP BY DATE(created_2), email_type
        ORDER BY day, cnt DESC
        """,
        (start, end)
    )

    if not rows:
        print_warning("  No data for this period.")
        input("\nPress Enter to continue...")
        return

    # Group by day
    from collections import defaultdict, OrderedDict
    days = OrderedDict()
    all_types = set()
    for r in rows:
        d = str(r['day'])
        if d not in days:
            days[d] = {}
        etype = r['email_type'] or 'OTHER'
        days[d][etype] = {'cnt': _safe(r['cnt']), 'ref_val': _safe(r['ref_val'], float)}
        all_types.add(etype)

    all_types = sorted(all_types)

    # Print table
    print()
    header = f"  {'Date':<12}" + "".join(f" {t[:10]:<12}" for t in all_types)
    print(header)
    print("  " + "─" * (12 + 13 * len(all_types)))

    type_totals = {t: 0 for t in all_types}
    for d, type_data in days.items():
        row_str = f"  {d:<12}"
        for t in all_types:
            cnt = type_data.get(t, {}).get('cnt', 0)
            type_totals[t] += cnt
            row_str += f" {cnt:<12}"
        print(row_str)

    print("  " + "─" * (12 + 13 * len(all_types)))
    total_row = f"  {'TOTAL':<12}" + "".join(f" {type_totals[t]:<12}" for t in all_types)
    print_color(total_row, Colors.CYAN)

    if input("\n  Export to CSV? (y/N): ").strip().lower() == 'y':
        fn = _exports_dir() / f"email_type_breakdown_{start}_{end}.csv"
        with open(fn, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Date'] + all_types)
            for d, type_data in days.items():
                w.writerow([d] + [type_data.get(t, {}).get('cnt', 0) for t in all_types])
            w.writerow(['TOTAL'] + [type_totals[t] for t in all_types])
        print_success(f"  Exported: {fn}")

    input("\nPress Enter to continue...")


# ──────────────────────────────────────────────────────────────────────────────
# Report 3 — Refund Value Report
# ──────────────────────────────────────────────────────────────────────────────

def report_refund_value():
    """Refund value per agent and campaign."""
    print_header("💰 REFUND VALUE REPORT", Colors.YELLOW)
    start, end = _ask_date_range()
    ensure_mapping_table()
    mapping = get_all_mappings()

    # By agent
    agent_rows = email_db.execute_query(
        """
        SELECT
            agent_name,
            COUNT(*)                        AS tickets,
            SUM(refund > 0)                 AS refund_cnt,
            COALESCE(SUM(refund), 0)        AS refund_total,
            COALESCE(MAX(refund), 0)        AS max_refund,
            COALESCE(AVG(NULLIF(refund,0)), 0) AS avg_refund
        FROM tbl_email
        WHERE DATE(created_2) BETWEEN %s AND %s
          AND agent_name IS NOT NULL
        GROUP BY agent_name
        ORDER BY refund_total DESC
        """,
        (start, end)
    )

    # By campaign
    camp_rows = email_db.execute_query(
        """
        SELECT
            campaign,
            SUM(refund > 0)                 AS refund_cnt,
            COALESCE(SUM(refund), 0)        AS refund_total
        FROM tbl_email
        WHERE DATE(created_2) BETWEEN %s AND %s
        GROUP BY campaign
        ORDER BY refund_total DESC
        """,
        (start, end)
    )

    print(f"\n  Period: {start}  →  {end}\n")

    if agent_rows:
        print_color("  BY AGENT:", Colors.CYAN)
        print(f"  {'Agent':<24} {'Linked':<14} {'Tickets':<8} {'# Refunds':<10} {'Total $':>10} {'Avg $':>9} {'Max $':>9}")
        print("  " + "─" * 90)
        grand = 0.0
        for r in agent_rows:
            name    = r['agent_name']
            linked  = mapping.get(name, '')
            ref_tot = _safe(r['refund_total'], float)
            grand  += ref_tot
            color   = Colors.RESET if linked else Colors.YELLOW
            print_color(
                f"  {name:<24} {(linked or '⚠ Unlinked'):<14} "
                f"{_safe(r['tickets']):<8} {_safe(r['refund_cnt']):<10} "
                f"${ref_tot:>9,.2f} ${_safe(r['avg_refund'],float):>8,.2f} ${_safe(r['max_refund'],float):>8,.2f}",
                color
            )
        print("  " + "─" * 90)
        print_color(f"  {'GRAND TOTAL':<50} ${grand:>9,.2f}", Colors.YELLOW)

    if camp_rows:
        print(f"\n  {'BY CAMPAIGN':}")
        print(f"  {'Campaign':<20} {'# Refunds':<12} {'Total $':>10}")
        print("  " + "─" * 45)
        for r in camp_rows:
            print(f"  {(r['campaign'] or 'UNKNOWN'):<20} {_safe(r['refund_cnt']):<12} ${_safe(r['refund_total'],float):>9,.2f}")

    if input("\n  Export to CSV? (y/N): ").strip().lower() == 'y':
        fn = _exports_dir() / f"refund_report_{start}_{end}.csv"
        with open(fn, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Agent', 'VICIdial User', 'Total Tickets', 'Refund Count',
                        'Total Refund $', 'Avg Refund $', 'Max Refund $'])
            for r in agent_rows:
                name = r['agent_name']
                w.writerow([
                    name, mapping.get(name, ''),
                    _safe(r['tickets']), _safe(r['refund_cnt']),
                    f"{_safe(r['refund_total'],float):.2f}",
                    f"{_safe(r['avg_refund'],float):.2f}",
                    f"{_safe(r['max_refund'],float):.2f}"
                ])
        print_success(f"  Exported: {fn}")

    input("\nPress Enter to continue...")


# ──────────────────────────────────────────────────────────────────────────────
# Report 4 — Email vs Call Volume (per linked agent)
# ──────────────────────────────────────────────────────────────────────────────

def report_email_vs_calls():
    """Side-by-side call volume vs email volume per linked agent."""
    print_header("📊 EMAIL vs CALL VOLUME (per Agent)", Colors.MAGENTA)
    start, end = _ask_date_range()
    ensure_mapping_table()
    mapping = get_all_mappings()          # {pinktools_name: altria_username}
    reverse = {v: k for k, v in mapping.items()}  # {altria_username: pinktools_name}

    # Email counts per pinktools agent
    email_rows = email_db.execute_query(
        """
        SELECT agent_name, COUNT(*) AS email_cnt
        FROM tbl_email
        WHERE DATE(created_2) BETWEEN %s AND %s
          AND agent_name IS NOT NULL
        GROUP BY agent_name
        """,
        (start, end)
    )
    email_by_pt = {r['agent_name']: _safe(r['email_cnt']) for r in (email_rows or [])}

    # Call counts per VICIdial user
    call_rows = db.execute_query(
        """
        SELECT a.user, u.full_name, COUNT(*) AS call_cnt,
               SUM(a.talk_sec) AS talk_sec
        FROM vicidial_agent_log a
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE DATE(a.event_time) BETWEEN %s AND %s
        GROUP BY a.user
        ORDER BY call_cnt DESC
        """,
        (start, end)
    )
    call_by_user = {r['user']: r for r in (call_rows or [])}

    # Build combined table — all mapped agents
    combined = []
    seen_pt = set()

    for altria_user, call_data in call_by_user.items():
        pt_name = reverse.get(altria_user, '')
        email_cnt = email_by_pt.get(pt_name, 0) if pt_name else 0
        combined.append({
            'altria_user': altria_user,
            'full_name':   (call_data.get('full_name') or altria_user),
            'pt_name':     pt_name,
            'calls':       _safe(call_data['call_cnt']),
            'talk_sec':    _safe(call_data.get('talk_sec') or 0),
            'emails':      email_cnt
        })
        if pt_name:
            seen_pt.add(pt_name)

    # Add pinktools agents with no call mapping
    for pt_name, email_cnt in email_by_pt.items():
        if pt_name not in seen_pt:
            altria_user = mapping.get(pt_name, '')
            combined.append({
                'altria_user': altria_user or '—',
                'full_name':   pt_name,
                'pt_name':     pt_name,
                'calls':       0,
                'talk_sec':    0,
                'emails':      email_cnt
            })

    combined.sort(key=lambda x: x['calls'] + x['emails'], reverse=True)

    print(f"\n  Period: {start}  →  {end}\n")
    print(f"  {'Agent':<22} {'VICIdial':<14} {'Calls':>7} {'Talk Time':<12} {'Emails':>7} {'Total':>7}")
    print("  " + "─" * 75)

    t_calls = t_emails = 0
    for ag in combined:
        linked_mark = '' if ag['altria_user'] != '—' else Colors.YELLOW
        total = ag['calls'] + ag['emails']
        t_calls  += ag['calls']
        t_emails += ag['emails']
        line = (
            f"  {ag['full_name'][:22]:<22} {ag['altria_user']:<14} "
            f"{ag['calls']:>7} {sec_to_hms(ag['talk_sec']):<12} "
            f"{ag['emails']:>7} {total:>7}"
        )
        if ag['altria_user'] == '—':
            print_color(line, Colors.YELLOW)
        else:
            print(line)

    print("  " + "─" * 75)
    print(f"  {'TOTAL':<22} {'':<14} {t_calls:>7} {'':<12} {t_emails:>7} {t_calls+t_emails:>7}")

    if input("\n  Export to CSV? (y/N): ").strip().lower() == 'y':
        fn = _exports_dir() / f"email_vs_calls_{start}_{end}.csv"
        with open(fn, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Agent Name', 'VICIdial User', 'Calls', 'Talk Time', 'Emails', 'Total'])
            for ag in combined:
                w.writerow([
                    ag['full_name'], ag['altria_user'],
                    ag['calls'], sec_to_hms(ag['talk_sec']),
                    ag['emails'], ag['calls'] + ag['emails']
                ])
        print_success(f"  Exported: {fn}")

    input("\nPress Enter to continue...")


# ──────────────────────────────────────────────────────────────────────────────
# Report 5 — Campaign Email Summary
# ──────────────────────────────────────────────────────────────────────────────

def report_campaign_email_summary():
    """Email volume and refund value per campaign."""
    print_header("🏷️  CAMPAIGN EMAIL SUMMARY", Colors.CYAN)
    start, end = _ask_date_range()

    rows = email_db.execute_query(
        """
        SELECT
            campaign,
            COUNT(*)                        AS total,
            COUNT(DISTINCT agent_name)      AS agents,
            SUM(email_type='CANCELATION REQ') AS cancels,
            SUM(email_type='FULL REFUND')    AS full_ref,
            SUM(email_type='PARTIAL REFUND') AS part_ref,
            SUM(refund > 0)                  AS ref_cnt,
            COALESCE(SUM(refund), 0)         AS ref_val
        FROM tbl_email
        WHERE DATE(created_2) BETWEEN %s AND %s
        GROUP BY campaign
        ORDER BY total DESC
        """,
        (start, end)
    )

    if not rows:
        print_warning("  No data for this period.")
        input("\nPress Enter to continue...")
        return

    print(f"\n  Period: {start}  →  {end}\n")
    print(f"  {'Campaign':<20} {'Total':<7} {'Agents':<7} {'Cancels':<8} {'FullRef':<8} {'PartRef':<8} {'RefVal':>10}")
    print("  " + "─" * 75)

    for r in rows:
        print(
            f"  {(r['campaign'] or 'UNKNOWN'):<20} "
            f"{_safe(r['total']):<7} {_safe(r['agents']):<7} "
            f"{_safe(r['cancels']):<8} {_safe(r['full_ref']):<8} "
            f"{_safe(r['part_ref']):<8} ${_safe(r['ref_val'],float):>9,.2f}"
        )

    if input("\n  Export to CSV? (y/N): ").strip().lower() == 'y':
        fn = _exports_dir() / f"campaign_email_{start}_{end}.csv"
        with open(fn, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Campaign', 'Total Emails', 'Agents', 'Cancellations',
                        'Full Refunds', 'Partial Refunds', 'Refund Count', 'Refund Value'])
            for r in rows:
                w.writerow([
                    r['campaign'] or 'UNKNOWN',
                    _safe(r['total']), _safe(r['agents']),
                    _safe(r['cancels']), _safe(r['full_ref']),
                    _safe(r['part_ref']), _safe(r['ref_cnt']),
                    f"{_safe(r['ref_val'],float):.2f}"
                ])
        print_success(f"  Exported: {fn}")

    input("\nPress Enter to continue...")


# ──────────────────────────────────────────────────────────────────────────────
# Main menu
# ──────────────────────────────────────────────────────────────────────────────

def email_channel_reports_menu():
    """Main menu for Email Channel Reports."""
    while True:
        print_header("📧 EMAIL CHANNEL REPORTS", Colors.MAGENTA)
        print("  Powered by pinktools (altriaca_email)\n")
        print("   1. 👤 Agent Email Performance")
        print("   2. 📋 Email Type Breakdown  (by day)")
        print("   3. 💰 Refund Value Report")
        print("   4. 📊 Email vs Call Volume  (per agent)")
        print("   5. 🏷️  Campaign Email Summary")
        print("   0. 🔙 Back")
        print("  " + "─" * 50)

        choice = input(f"\n{Colors.CYAN}  Choice: {Colors.RESET}").strip()

        if   choice == '1': report_agent_email_performance()
        elif choice == '2': report_email_type_breakdown()
        elif choice == '3': report_refund_value()
        elif choice == '4': report_email_vs_calls()
        elif choice == '5': report_campaign_email_summary()
        elif choice == '0': break
        else:
            print_error("Invalid option")
            input("\nPress Enter to continue...")
