#!/usr/bin/env python3
# =============================================================================
# File:         unified_search.py
# Version:      2.4.0
# Date:         2026-02-28
# Description:  Unified Search (menu-driven) for Campaigns and Inbound Groups
# Update:       Compact table output + optional full listing (no forced 20 limit)
# Author:       Altria Ops Team
# =============================================================================

from __future__ import annotations

import math
import shutil
from core.database import db
from utils.colors import Colors, print_color, print_header, print_warning


def _like(term: str) -> str:
    term = (term or "").strip()
    return f"%{term}%"


# =============================================================================
# Pagination (compact navigation line)
# =============================================================================

def show_paginated_results(items, item_type="campaigns", page=1, page_size=25):
    """
    Display paginated results with compact navigation.
    Returns the selected item dict or None.
    """
    total_items = len(items or [])
    if total_items <= 0:
        return None

    total_pages = max(1, math.ceil(total_items / page_size))

    while True:
        start = (page - 1) * page_size
        end = min(start + page_size, total_items)

        print_header(f"{item_type.upper()}  |  Page {page}/{total_pages}  |  Total: {total_items}", Colors.CYAN)
        print("-" * 90)

        for i in range(start, end):
            idx = i + 1
            item = items[i]

            if item_type == "campaigns":
                cid = item.get("campaign_id", "")
                cname = item.get("campaign_name", "")
                active = item.get("active", "")
                print(f"{idx:>3}. {cid:<18} {cname:<30} [{active}]")
            else:
                gid = item.get("group_id", "")
                gname = item.get("group_name", "")
                active = item.get("active", "")
                print(f"{idx:>3}. {gid:<18} {gname:<34} [{active}]")

        print("-" * 90)
        print(f"Showing {start+1}-{end}/{total_items}")

        nav = ["[#]=select"]
        if page > 1:
            nav.append("p=prev")
        if page < total_pages:
            nav.append("n=next")
        nav.append("q=back")
        print("   ".join(nav))

        choice = input(f"{Colors.CYAN}Choice: {Colors.RESET}").strip().lower()

        if choice == "q":
            return None
        elif choice == "n" and page < total_pages:
            page += 1
        elif choice == "p" and page > 1:
            page -= 1
        elif choice.isdigit():
            sel = int(choice) - 1
            if 0 <= sel < total_items:
                return items[sel]
            print_warning("Invalid selection.")
        else:
            print_warning("Invalid option.")


# =============================================================================
# Fetch all
# =============================================================================

def get_all_campaigns(active_filter="ALL", limit=1000):
    where_active = ""
    params = []
    if active_filter in ("Y", "N"):
        where_active = "WHERE active = %s"
        params.append(active_filter)

    query = f"""
        SELECT campaign_id, campaign_name, active
        FROM vicidial_campaigns
        {where_active}
        ORDER BY (active='Y') DESC, campaign_id
        LIMIT {int(limit)}
    """
    return db.execute_query(query, params) or []


def get_all_ingroups(active_filter="ALL", limit=1000):
    where_active = ""
    params = []
    if active_filter in ("Y", "N"):
        where_active = "WHERE active = %s"
        params.append(active_filter)

    query = f"""
        SELECT group_id, group_name, active
        FROM vicidial_inbound_groups
        {where_active}
        ORDER BY (active='Y') DESC, group_id
        LIMIT {int(limit)}
    """
    return db.execute_query(query, params) or []


# =============================================================================
# Search
# =============================================================================

def search_campaigns(term: str, active_filter="ALL", limit=50):
    term_like = _like(term)

    where_active = ""
    params = [term_like, term_like]
    if active_filter in ("Y", "N"):
        where_active = " AND active = %s "
        params.append(active_filter)

    query = f"""
        SELECT campaign_id, campaign_name, active
        FROM vicidial_campaigns
        WHERE (campaign_id LIKE %s OR campaign_name LIKE %s)
        {where_active}
        ORDER BY (active='Y') DESC, campaign_id
        LIMIT {int(limit)}
    """
    return db.execute_query(query, params) or []


def search_ingroups(term: str, active_filter="ALL", limit=50):
    term_like = _like(term)

    where_active = ""
    params = [term_like, term_like]
    if active_filter in ("Y", "N"):
        where_active = " AND active = %s "
        params.append(active_filter)

    query = f"""
        SELECT group_id, group_name, active
        FROM vicidial_inbound_groups
        WHERE (group_id LIKE %s OR group_name LIKE %s)
        {where_active}
        ORDER BY (active='Y') DESC, group_id
        LIMIT {int(limit)}
    """
    return db.execute_query(query, params) or []


# =============================================================================
# Print Helpers (COMPACT TABLE)
# =============================================================================

def print_campaign_results(rows, limit=20):
    total = len(rows or [])
    print_color(f"\nCAMPAIGNS ({total} found)", Colors.YELLOW)
    if not rows:
        print("  (none)")
        return

    show = rows if limit is None else rows[:limit]
    for i, c in enumerate(show, 1):
        cid = c.get("campaign_id", "")
        cname = c.get("campaign_name", "")
        active = c.get("active", "")
        print(f"  {i:>2}. {cid:<18} | {cname:<28} | Active: {active}")

    if limit is not None and total > limit:
        print_warning(f"Showing {limit} of {total}.")


def print_ingroup_results(rows, limit=None):
    """
    Professional compact table for inbound groups:
      No. | ID | Name | Status (A/N)

    limit=None => show ALL
    """
    import shutil

    total = len(rows or [])
    print_color(f"\nINBOUND GROUPS ({total} found)", Colors.YELLOW)
    if not rows:
        print("  (none)")
        return

    width = shutil.get_terminal_size((140, 30)).columns
    no_w = 4
    id_w = 18
    status_w = 6
    sep = " | "

    # remaining width for Name
    name_w = max(20, width - (no_w + id_w + status_w + len(sep) * 3))
    line_w = min(width, 170)

    header = (
        f"{'No.':<{no_w}}{sep}"
        f"{'ID':<{id_w}}{sep}"
        f"{'Name':<{name_w}}{sep}"
        f"{'Status':<{status_w}}"
    )

    print("-" * line_w)
    print(header)
    print("-" * line_w)

    show = rows if limit is None else rows[:limit]
    for i, r in enumerate(show, 1):
        gid = (r.get("group_id") or "").strip()
        gname = (r.get("group_name") or "").strip()
        active = (r.get("active") or "").strip().upper()

        status = "A" if active == "Y" else "N"

        if len(gname) > name_w:
            gname = gname[: max(0, name_w - 1)] + "…"

        print(
            f"{i:<{no_w}}{sep}"
            f"{gid:<{id_w}}{sep}"
            f"{gname:<{name_w}}{sep}"
            f"{status:<{status_w}}"
        )

    print("-" * line_w)

    if limit is not None and total > limit:
        print_warning(f"Showing {limit} of {total}.")


# =============================================================================
# Unified Search Menu (kept simple / stable)
# =============================================================================

def unified_search_menu(return_result=False):
    """
    Menu-driven search:
      - campaigns / inbound groups / both
      - active filter
      - keyword search OR browse all with pagination
    """
    while True:
        print_header("UNIFIED SEARCH", Colors.CYAN)
        print("Search in:")
        print("  1) Campaigns")
        print("  2) Inbound Groups")
        print("  3) All (Campaigns + Inbound Groups)")
        print("  0) Back")

        scope = input(f"{Colors.CYAN}Select (0-3): {Colors.RESET}").strip()
        if scope == "0":
            return None
        if scope not in ("1", "2", "3"):
            print_warning("Invalid selection.")
            continue

        print("\nActive Filter:")
        print("  1) All")
        print("  2) Active only (Y)")
        print("  3) Inactive only (N)")
        f = input(f"{Colors.CYAN}Select (1-3): {Colors.RESET}").strip()

        active_filter = "ALL"
        if f == "2":
            active_filter = "Y"
        elif f == "3":
            active_filter = "N"

        term = input("\nEnter keyword (or press Enter to browse all): ").strip()

        # Browse mode
        if term == "":
            if scope == "1":
                items = get_all_campaigns(active_filter=active_filter, limit=1000)
                selected = show_paginated_results(items, item_type="campaigns", page=1, page_size=25)
                if return_result and selected:
                    return selected.get("campaign_id")
            elif scope == "2":
                items = get_all_ingroups(active_filter=active_filter, limit=1000)
                selected = show_paginated_results(items, item_type="inbound groups", page=1, page_size=25)
                if return_result and selected:
                    return selected.get("group_id")
            else:
                print_warning("Browse for 'All' is not enabled. Use search keyword.")
            input("\nPress Enter to continue...")
            continue

        # Search mode
        if scope == "1":
            rows = search_campaigns(term, active_filter=active_filter, limit=200)
            print_campaign_results(rows, limit=None)
        elif scope == "2":
            rows = search_ingroups(term, active_filter=active_filter, limit=200)
            print_ingroup_results(rows, limit=None)
        else:
            c = search_campaigns(term, active_filter=active_filter, limit=200)
            g = search_ingroups(term, active_filter=active_filter, limit=200)
            print_campaign_results(c, limit=None)
            print_ingroup_results(g, limit=None)

        input("\nPress Enter to continue...")