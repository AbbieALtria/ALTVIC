#!/usr/bin/env python3
# =============================================================================
# File:         sales_dashboard.py
# Version:      1.1.0
# Date:         2026-03-07
# Description:  Dedicated Sales Dashboard for outbound / lead generation campaigns
# Location:     D:/Altria_Ops/agents/sales_dashboard.py
# =============================================================================

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_color, print_header, print_error, print_warning, print_info
from utils.formatter import sec_to_hms

# =============================================================================
# Load Config
# =============================================================================

try:
    from config.settings import load_config
    CONFIG = load_config()
except:
    CONFIG = {}

CAMPAIGN_TYPES_FILE = Path(__file__).parent.parent / "config" / "campaign_types.json"

try:
    with open(CAMPAIGN_TYPES_FILE, "r") as f:
        CAMPAIGN_TYPES = json.load(f)
except:
    CAMPAIGN_TYPES = {"sales": [], "leads": []}


# =============================================================================
# Campaign Helpers
# =============================================================================

def get_sales_campaigns():
    sales = CAMPAIGN_TYPES.get("sales", [])
    leads = CAMPAIGN_TYPES.get("leads", [])
    return sorted(set(sales + leads))


def get_campaigns_with_data(campaign_list, days=30):

    if not campaign_list:
        return []

    placeholders = ",".join(["%s"] * len(campaign_list))

    query = f"""
    SELECT DISTINCT campaign_id
    FROM vicidial_closer_log
    WHERE campaign_id IN ({placeholders})
    AND call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
    """

    params = campaign_list + [days]

    try:
        rows = db.execute_query(query, params)
        return [r["campaign_id"] for r in rows] if rows else []
    except:
        return campaign_list


# =============================================================================
# Sales Metrics
# =============================================================================

def get_sales_metrics(campaign, start_date, end_date):

    query = """
    SELECT
        COUNT(*) as total_calls,

        SUM(CASE WHEN c.length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,

        SUM(CASE WHEN c.length_in_sec = 0 AND c.queue_seconds > 0 THEN 1 ELSE 0 END) as abandoned,

        SUM(CASE WHEN c.length_in_sec = 0 AND c.queue_seconds = 0 THEN 1 ELSE 0 END) as ghost_calls,

        SUM(CASE WHEN c.status IN ('SALE','YPSALE','UPSELL','CROSSSELL') THEN 1 ELSE 0 END) as sales,

        SUM(IFNULL(a.talk_sec,0)) as total_talk_sec,

        SUM(CASE WHEN c.status IN ('SALE','YPSALE','UPSELL','CROSSSELL')
                 THEN IFNULL(a.talk_sec,0)
                 ELSE 0 END) as sales_talk_sec,

        COUNT(DISTINCT a.user) as unique_agents

    FROM vicidial_closer_log c
    LEFT JOIN vicidial_agent_log a
        ON c.uniqueid = a.uniqueid

    WHERE c.campaign_id = %s
    AND c.call_date BETWEEN %s AND %s
    """

    try:
        rows = db.execute_query(query, (campaign, start_date, end_date))

        if rows and rows[0]["total_calls"] > 0:
            return rows[0]

    except Exception as e:
        print_error(f"Query error: {e}")

    return None


# =============================================================================
# KPI Calculation
# =============================================================================

def calculate_sales_kpi(metrics):

    total = metrics["total_calls"] or 0
    answered = metrics["answered"] or 0
    abandoned = metrics["abandoned"] or 0
    ghost = metrics["ghost_calls"] or 0
    sales = metrics["sales"] or 0
    talk = metrics["total_talk_sec"] or 0

    kpi = {}

    kpi["total_calls"] = total
    kpi["answered"] = answered
    kpi["abandoned"] = abandoned
    kpi["ghost_calls"] = ghost
    kpi["sales"] = sales
    kpi["talk_sec"] = talk
    kpi["unique_agents"] = metrics["unique_agents"] or 0

    kpi["answer_rate"] = (answered / total * 100) if total else 0
    kpi["abandon_rate"] = (abandoned / total * 100) if total else 0
    kpi["ghost_rate"] = (ghost / total * 100) if total else 0
    kpi["conversion_rate"] = (sales / answered * 100) if answered else 0

    kpi["dials_per_sale"] = (total / sales) if sales else float("inf")
    kpi["talk_per_sale"] = (talk / sales) if sales else 0

    avg_sale_value = CONFIG.get("sales", {}).get("avg_sale_value", 50)
    kpi["estimated_revenue"] = sales * avg_sale_value

    return kpi


# =============================================================================
# Dashboard Display
# =============================================================================

def show_sales_dashboard():

    print_header("💰 SALES DASHBOARD", Colors.GREEN)

    print("\nSelect period:")
    print("1. Today")
    print("2. Yesterday")
    print("3. Last 7 Days")
    print("4. Last 30 Days")

    choice = input("\nChoice: ").strip()

    now = datetime.now()

    if choice == "1":
        start = datetime.combine(now.date(), datetime.min.time())
        end = datetime.combine(now.date(), datetime.max.time())
        period = "TODAY"

    elif choice == "2":
        d = now.date() - timedelta(days=1)
        start = datetime.combine(d, datetime.min.time())
        end = datetime.combine(d, datetime.max.time())
        period = "YESTERDAY"

    elif choice == "3":
        start = now - timedelta(days=7)
        end = now
        period = "LAST 7 DAYS"

    else:
        start = now - timedelta(days=30)
        end = now
        period = "LAST 30 DAYS"

    sales_campaigns = get_sales_campaigns()

    if not sales_campaigns:
        print_warning("No sales campaigns configured")
        return

    campaigns = get_campaigns_with_data(sales_campaigns)

    print(f"\n📊 Analyzing {len(campaigns)} campaigns for {period}")

    all_metrics = []

    for campaign in campaigns:

        metrics = get_sales_metrics(campaign, start, end)

        if metrics:

            kpi = calculate_sales_kpi(metrics)

            all_metrics.append({
                "campaign": campaign,
                "kpi": kpi
            })

    if not all_metrics:
        print_warning("No data found")
        return

    all_metrics.sort(key=lambda x: x["kpi"]["sales"], reverse=True)

    print("\n")
    print(f"{'Campaign':<20}{'Calls':<10}{'Sales':<10}{'Conv%':<10}{'Dials/Sale':<12}{'Revenue':<12}")
    print("-"*80)

    total_calls = 0
    total_sales = 0
    total_rev = 0

    for item in all_metrics:

        c = item["campaign"]
        k = item["kpi"]

        total_calls += k["total_calls"]
        total_sales += k["sales"]
        total_rev += k["estimated_revenue"]

        dials = "∞" if k["dials_per_sale"] == float("inf") else f"{k['dials_per_sale']:.0f}"

        print(f"{c:<20}{k['total_calls']:<10}{k['sales']:<10}{k['conversion_rate']:.1f}%{'':<5}{dials:<12}${k['estimated_revenue']:<10.0f}")

    print("-"*80)

    overall_conv = (total_sales / total_calls * 100) if total_calls else 0

    print(f"{'TOTAL':<20}{total_calls:<10}{total_sales:<10}{overall_conv:.1f}%{'':<5}{'':<12}${total_rev:<10.0f}")

    print("-"*80)

    input("\nPress Enter to continue...")


# =============================================================================
# Menu
# =============================================================================

def sales_dashboard_menu():

    while True:

        print_header("💰 SALES DASHBOARD MENU", Colors.GREEN)

        print("1. Sales Overview Dashboard")
        print("2. Campaign Detail (Coming Soon)")
        print("3. Compare Campaigns (Coming Soon)")
        print("0. Back")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            show_sales_dashboard()

        elif choice == "0":
            break

        else:
            print_error("Invalid choice")


if __name__ == "__main__":
    sales_dashboard_menu()