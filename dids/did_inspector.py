#!/usr/bin/env python3
# =============================================================================
# File:         dids/did_inspector.py
# Version:      1.8.0
# Date:         2026-03-30
# Description:  DID Inspector with numbered selection and call volume
# Changes:      Updated show_dids_by_group to show each DID on its own line
#               Added color-coded DIDs (🟢 Active / 🔴 Inactive)
#               Added group summary with status icons (✅/⚠️/❌)
#               Fixed specific DID filter to show only selected DID
#               Added post-query filtering for specific DID selection
#               Improved summary display based on filter type
# =============================================================================

from core.database import db
from utils.colors import Colors, print_header, print_success, print_error, print_warning, print_color

def safe_str(value, default="-"):
    return str(value) if value is not None else default

def format_number(value):
    if value is None:
        return "0"
    try:
        return f"{int(value):,}"
    except:
        return str(value)


def did_inspector_menu():
    while True:
        print_header("📞 DID INSPECTOR", Colors.CYAN)
        print("  " + "─" * 75)
        print("   1. 📋 View All DIDs")
        print("   2. ⚠️  Problem DIDs Report")
        print("   3. 🔍 Search DID")
        print("   4. 📊 DIDs by Inbound Group")
        print("   5. 📈 Call Volume by Period")
        print("   0. 🔙 Back to Main Menu")
        print("  " + "─" * 75)

        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

        if choice == '1':
            show_all_dids()
        elif choice == '2':
            show_problem_dids()
        elif choice == '3':
            search_did()
        elif choice == '4':
            show_dids_by_group()
        elif choice == '5':
            show_call_volume_by_period()
        elif choice == '0':
            break
        else:
            print_error("Invalid option")

        input("\nPress Enter to continue...")


def show_all_dids():
    print_header("📋 ALL DIDs IN SYSTEM", Colors.CYAN)

    query = """
        SELECT 
            did_pattern AS DID,
            did_description AS Description,
            group_id AS InGroup,
            did_active AS Active,
            server_ip AS Server
        FROM vicidial_inbound_dids 
        ORDER BY did_active DESC, did_pattern;
    """

    results = db.execute_query(query) or []

    if not results:
        print_warning("No DIDs found.")
        return

    print(f"\nTotal DIDs: {len(results)}\n")
    print("─" * 95)
    print(f"{'No.':<4} {'DID':<16} {'Description':<32} {'In-Group':<20} {'Active':<8} {'Server':<15}")
    print("─" * 95)

    for i, row in enumerate(results, 1):
        color = Colors.GREEN if row.get('Active') == 'Y' else Colors.RED
        print_color(
            f"{i:<4} {safe_str(row.get('DID')):<16} "
            f"{safe_str(row.get('Description'))[:31]:<32} "
            f"{safe_str(row.get('InGroup')):<20} "
            f"{safe_str(row.get('Active')):<8} "
            f"{safe_str(row.get('Server')):<15}",
            color
        )
    print("─" * 95)


def show_problem_dids():
    print_header("⚠️ PROBLEM DIDs REPORT", Colors.YELLOW)

    query = """
        SELECT 
            d.did_pattern AS DID,
            d.did_description AS Description,
            d.group_id AS InGroup,
            d.did_active AS Active,
            COUNT(vcl.uniqueid) AS Calls30d
        FROM vicidial_inbound_dids d
        LEFT JOIN vicidial_closer_log vcl 
            ON vcl.call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            AND (vcl.campaign_id = d.group_id OR vcl.campaign_id LIKE 'xshield%%')
        GROUP BY d.did_pattern, d.did_description, d.group_id, d.did_active
        HAVING d.did_active = 'N' OR COUNT(vcl.uniqueid) < 10
        ORDER BY d.did_active, Calls30d;
    """

    results = db.execute_query(query) or []

    if not results:
        print_success("✅ No problematic DIDs found!")
        return

    print(f"\nFound {len(results)} problematic DIDs:\n")
    print("─" * 100)
    print(f"{'No.':<4} {'DID':<16} {'Description':<30} {'In-Group':<20} {'Active':<8} {'Calls 30d':<10} {'Issue'}")
    print("─" * 100)

    for i, row in enumerate(results, 1):
        if row['Active'] == 'N':
            issue = "❌ INACTIVE"
            color = Colors.RED
        else:
            issue = f"⚠️ Low Activity ({row['Calls30d']} calls)"
            color = Colors.YELLOW

        print_color(
            f"{i:<4} {safe_str(row.get('DID')):<16} "
            f"{safe_str(row.get('Description'))[:29]:<30} "
            f"{safe_str(row.get('InGroup')):<20} "
            f"{safe_str(row.get('Active')):<8} "
            f"{row.get('Calls30d', 0):<10} {issue}",
            color
        )


def search_did():
    term = input("\nEnter DID or description to search: ").strip()
    if not term:
        return

    query = """
        SELECT 
            did_pattern AS DID,
            did_description AS Description,
            group_id AS InGroup,
            did_active AS Active
        FROM vicidial_inbound_dids 
        WHERE did_pattern LIKE %s OR did_description LIKE %s
        ORDER BY did_pattern;
    """

    results = db.execute_query(query, (f"%{term}%", f"%{term}%")) or []

    if not results:
        print_warning(f"No DID found matching '{term}'")
        return

    print(f"\nFound {len(results)} matching DIDs:")
    print("─" * 80)
    print(f"{'DID':<16} {'Description':<35} {'In-Group':<20} {'Active'}")
    print("─" * 80)

    for row in results:
        color = Colors.GREEN if row['Active'] == 'Y' else Colors.RED
        print_color(
            f"{safe_str(row.get('DID')):<16} "
            f"{safe_str(row.get('Description'))[:34]:<35} "
            f"{safe_str(row.get('InGroup')):<20} {row['Active']}",
            color
        )


def show_dids_by_group():
    """Show DIDs grouped by inbound group with each DID on its own line"""
    print_header("📊 DIDs BY INBOUND GROUP", Colors.CYAN)

    query = """
        SELECT 
            group_id AS InGroup,
            did_pattern AS DID,
            did_description AS Description,
            did_active AS Active
        FROM vicidial_inbound_dids 
        ORDER BY group_id, did_active DESC, did_pattern;
    """
    
    results = db.execute_query(query) or []

    if not results:
        print_warning("No DIDs found.")
        return

    current_group = None
    group_active = 0
    group_total = 0
    
    print("─" * 100)
    print(f"{'Inbound Group':<25} {'DID':<18} {'Description':<35} {'Status'}")
    print("─" * 100)
    
    for row in results:
        group = safe_str(row.get('InGroup'))
        did = safe_str(row.get('DID'))
        desc = safe_str(row.get('Description'))[:34]
        active = row.get('Active')
        
        # When group changes, print summary for previous group
        if group != current_group and current_group is not None:
            # Print summary line for previous group
            if group_total > 0:
                summary_color = Colors.GREEN if group_active == group_total else Colors.YELLOW if group_active > 0 else Colors.RED
                summary_icon = "✅" if group_active == group_total else "⚠️" if group_active > 0 else "❌"
                print_color(f"\n{summary_icon} Group Summary: {group_active}/{group_total} active DIDs", summary_color)
            print("─" * 100)
            current_group = group
            group_active = 0
            group_total = 0
        elif current_group is None:
            current_group = group
        
        # Color code the DID based on active status
        if active == 'Y':
            color = Colors.GREEN
            status = "🟢 ACTIVE"
            group_active += 1
        else:
            color = Colors.RED
            status = "🔴 INACTIVE"
        
        group_total += 1
        
        # Print group header when first DID of group appears
        if group_total == 1:
            print_color(f"\n📁 {group}", Colors.MAGENTA)
        
        print_color(
            f"   {did:<18} {desc:<35} {status}",
            color
        )
    
    # Print summary for last group
    if group_total > 0:
        summary_color = Colors.GREEN if group_active == group_total else Colors.YELLOW if group_active > 0 else Colors.RED
        summary_icon = "✅" if group_active == group_total else "⚠️" if group_active > 0 else "❌"
        print_color(f"\n{summary_icon} Group Summary: {group_active}/{group_total} active DIDs", summary_color)
    
    print("─" * 100)
    print("\n📌 Legend: 🟢 Active | 🔴 Inactive")
    print("   ✅ Fully Active | ⚠️ Partially Active | ❌ All Inactive")


def show_call_volume_by_period():
    """Call Volume with nice numbered DID selection - Fixed specific DID filter"""
    print_header("📈 CALL VOLUME BY PERIOD", Colors.CYAN)
    print("   1. Today")
    print("   2. Yesterday")
    print("   3. Last 7 Days")
    print("   4. Last 30 Days")
    print("   5. Custom Date Range")
    print("   0. Back")

    choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
    if choice == '0':
        return

    if choice == '1':
        days = 0
        title = "TODAY"
    elif choice == '2':
        days = 1
        title = "YESTERDAY"
    elif choice == '3':
        days = 7
        title = "LAST 7 DAYS"
    elif choice == '4':
        days = 30
        title = "LAST 30 DAYS"
    elif choice == '5':
        from_date = input("From date (YYYY-MM-DD): ").strip()
        to_date = input("To date (YYYY-MM-DD): ").strip()
        show_custom_date_range(from_date, to_date)
        return
    else:
        print_error("Invalid choice")
        return

    # Filter selection
    print("\nFilter options:")
    print("   1. All DIDs")
    print("   2. Specific DID")
    print("   3. Specific Campaign")
    filter_choice = input(f"\n{Colors.CYAN}Filter choice: {Colors.RESET}").strip()

    where_clause = ""
    params = [days]
    selected_did = None

    if filter_choice == '2':
        print("\nAvailable DIDs (🟢 Active = Green | 🔴 Inactive = Red):")
        print("─" * 90)
        
        did_list_query = """
            SELECT did_pattern, did_description, group_id, did_active
            FROM vicidial_inbound_dids 
            ORDER BY did_active DESC, did_pattern;
        """
        
        did_results = db.execute_query(did_list_query) or []
        
        for i, row in enumerate(did_results, 1):
            color = Colors.GREEN if row.get('did_active') == 'Y' else Colors.RED
            status = "🟢" if row.get('did_active') == 'Y' else "🔴"
            print_color(
                f"{i:>3}. {safe_str(row.get('did_pattern')):<16} "
                f"{safe_str(row.get('did_description'))[:38]:<38} "
                f"{safe_str(row.get('group_id')):<18} {status}",
                color
            )
        
        print("─" * 90)

        while True:
            selection = input(f"\n{Colors.CYAN}Enter number of DID: {Colors.RESET}").strip()
            if selection.isdigit() and 1 <= int(selection) <= len(did_results):
                selected_did = did_results[int(selection)-1]['did_pattern']
                where_clause = "AND d.did_pattern = %s"
                params = [days, selected_did]
                break
            else:
                print_error("Invalid number. Please try again.")

    elif filter_choice == '3':
        campaign = input("Enter Campaign name (e.g. UpliftDeals): ").strip()
        where_clause = "AND (vcl.campaign_id = %s OR vcl.campaign_id LIKE %s)"
        params = [days, campaign, f"%{campaign}%"]
    elif filter_choice == '1':
        where_clause = ""
        params = [days]
    else:
        print_error("Invalid filter choice")
        return

    # Main query
    query = f"""
        SELECT 
            d.did_pattern AS did_pattern,
            d.did_description AS did_description,
            d.group_id AS group_id,
            d.did_active AS did_active,
            COUNT(vcl.uniqueid) AS total_calls,
            SUM(CASE WHEN vcl.length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered,
            ROUND(100.0 * SUM(CASE WHEN vcl.length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(vcl.uniqueid), 0), 2) AS answer_rate
        FROM vicidial_inbound_dids d
        LEFT JOIN vicidial_closer_log vcl 
            ON vcl.call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            AND (vcl.campaign_id = d.group_id OR vcl.campaign_id LIKE 'xshield%%')
        {where_clause}
        GROUP BY d.did_pattern, d.did_description, d.group_id, d.did_active
        ORDER BY total_calls DESC, d.did_pattern
    """

    try:
        results = db.execute_query(query, tuple(params)) or []
    except Exception as e:
        print_error(f"Database error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Filter results to only show the selected DID when specific DID was chosen
    if filter_choice == '2' and selected_did:
        results = [r for r in results if r.get('did_pattern') == selected_did]

    print_header(f"📊 {title} - CALLS PER DID", Colors.GREEN)
    print("─" * 115)
    print(f"{'DID':<16} {'Description':<32} {'In-Group':<20} {'Active':<8} {'Total Calls':<12} {'Answered':<10} {'Answer Rate %'}")
    print("─" * 115)

    total_calls = 0
    total_answered = 0

    for row in results:
        color = Colors.GREEN if row.get('did_active') == 'Y' else Colors.RED
        calls = row.get('total_calls', 0)
        answered = row.get('answered', 0)
        total_calls += calls
        total_answered += answered

        print_color(
            f"{safe_str(row.get('did_pattern')):<16} "
            f"{safe_str(row.get('did_description'))[:31]:<32} "
            f"{safe_str(row.get('group_id')):<20} "
            f"{safe_str(row.get('did_active')):<8} "
            f"{calls:<12} "
            f"{answered:<10} "
            f"{safe_str(row.get('answer_rate'), '0.00')}%",
            color
        )

    print("─" * 115)

    # Smart summary based on filter type
    if filter_choice == '1' and total_calls > 0:
        # All DIDs - show overall summary
        overall_rate = (total_answered / total_calls * 100)
        print(f"\n📊 Overall Summary for this period:")
        print(f" • Total Calls   : {format_number(total_calls)}")
        print(f" • Total Answered: {format_number(total_answered)}")
        print(f" • Answer Rate   : {overall_rate:.1f}%")
    elif filter_choice == '2' and selected_did and len(results) > 0:
        # Specific DID - show summary for that DID only
        row = results[0]
        print(f"\n📊 Summary for DID {row.get('did_pattern')}:")
        print(f" • Total Calls   : {format_number(row.get('total_calls', 0))}")
        print(f" • Total Answered: {format_number(row.get('answered', 0))}")
        print(f" • Answer Rate   : {safe_str(row.get('answer_rate'), '0.00')}%")
    elif filter_choice == '3' and total_calls > 0:
        # Campaign filter - show summary for filtered results
        overall_rate = (total_answered / total_calls * 100)
        print(f"\n📊 Summary for Campaign Filter:")
        print(f" • Total Calls   : {format_number(total_calls)}")
        print(f" • Total Answered: {format_number(total_answered)}")
        print(f" • Answer Rate   : {overall_rate:.1f}%")
    elif total_calls == 0 and len(results) > 0:
        print(f"\n📊 No calls found for this period.")
    elif len(results) == 0:
        print(f"\n📊 No data found for the selected filter.")
    else:
        print(f"\n📊 Showing {len(results)} DID(s) with {format_number(total_calls)} total calls.")


def show_custom_date_range(from_date, to_date):
    """Custom date range for DID calls with fixed specific DID filter"""
    try:
        # Validate dates
        try:
            from datetime import datetime
            datetime.strptime(from_date, '%Y-%m-%d')
            datetime.strptime(to_date, '%Y-%m-%d')
        except ValueError:
            print_error("Invalid date format. Please use YYYY-MM-DD")
            return
        
        print("\nFilter options:")
        print("   1. All DIDs")
        print("   2. Specific DID")
        print("   3. Specific Campaign")
        filter_choice = input(f"\n{Colors.CYAN}Filter choice: {Colors.RESET}").strip()

        where_clause = ""
        params = [from_date, to_date]
        selected_did = None

        if filter_choice == '2':
            print("\nAvailable DIDs (🟢 Active = Green | 🔴 Inactive = Red):")
            print("─" * 90)
            
            did_list_query = """
                SELECT did_pattern, did_description, group_id, did_active
                FROM vicidial_inbound_dids 
                ORDER BY did_active DESC, did_pattern;
            """
            
            did_results = db.execute_query(did_list_query) or []
            
            for i, row in enumerate(did_results, 1):
                color = Colors.GREEN if row.get('did_active') == 'Y' else Colors.RED
                status = "🟢" if row.get('did_active') == 'Y' else "🔴"
                print_color(
                    f"{i:>3}. {safe_str(row.get('did_pattern')):<16} "
                    f"{safe_str(row.get('did_description'))[:38]:<38} "
                    f"{safe_str(row.get('group_id')):<18} {status}",
                    color
                )
            
            print("─" * 90)

            while True:
                selection = input(f"\n{Colors.CYAN}Enter number of DID: {Colors.RESET}").strip()
                if selection.isdigit() and 1 <= int(selection) <= len(did_results):
                    selected_did = did_results[int(selection)-1]['did_pattern']
                    where_clause = "AND d.did_pattern = %s"
                    params = [from_date, to_date, selected_did]
                    break
                else:
                    print_error("Invalid number. Please try again.")

        elif filter_choice == '3':
            campaign = input("Enter Campaign name (e.g. UpliftDeals): ").strip()
            where_clause = "AND (vcl.campaign_id = %s OR vcl.campaign_id LIKE %s)"
            params = [from_date, to_date, campaign, f"%{campaign}%"]
        elif filter_choice == '1':
            where_clause = ""
            params = [from_date, to_date]
        else:
            print_error("Invalid filter choice")
            return

        # Main query for custom range
        query = f"""
            SELECT 
                d.did_pattern AS did_pattern,
                d.did_description AS did_description,
                d.group_id AS group_id,
                d.did_active AS did_active,
                COUNT(vcl.uniqueid) AS total_calls,
                SUM(CASE WHEN vcl.length_in_sec >= 5 THEN 1 ELSE 0 END) AS answered,
                ROUND(100.0 * SUM(CASE WHEN vcl.length_in_sec >= 5 THEN 1 ELSE 0 END) / NULLIF(COUNT(vcl.uniqueid), 0), 2) AS answer_rate
            FROM vicidial_inbound_dids d
            LEFT JOIN vicidial_closer_log vcl 
                ON vcl.call_date BETWEEN %s AND %s
                AND (vcl.campaign_id = d.group_id OR vcl.campaign_id LIKE 'xshield%%')
            {where_clause}
            GROUP BY d.did_pattern, d.did_description, d.group_id, d.did_active
            ORDER BY total_calls DESC, d.did_pattern
        """

        results = db.execute_query(query, tuple(params)) or []

        # Filter results for specific DID
        if filter_choice == '2' and selected_did:
            results = [r for r in results if r.get('did_pattern') == selected_did]

        print_header(f"📊 CUSTOM RANGE ({from_date} to {to_date})", Colors.GREEN)
        print("─" * 115)
        print(f"{'DID':<16} {'Description':<32} {'In-Group':<20} {'Active':<8} {'Total Calls':<12} {'Answered':<10} {'Answer Rate %'}")
        print("─" * 115)

        total_calls = 0
        total_answered = 0

        for row in results:
            color = Colors.GREEN if row.get('did_active') == 'Y' else Colors.RED
            calls = row.get('total_calls', 0)
            answered = row.get('answered', 0)
            total_calls += calls
            total_answered += answered

            print_color(
                f"{safe_str(row.get('did_pattern')):<16} "
                f"{safe_str(row.get('did_description'))[:31]:<32} "
                f"{safe_str(row.get('group_id')):<20} "
                f"{safe_str(row.get('did_active')):<8} "
                f"{calls:<12} "
                f"{answered:<10} "
                f"{safe_str(row.get('answer_rate'), '0.00')}%",
                color
            )

        print("─" * 115)

        # Smart summary based on filter type
        if filter_choice == '1' and total_calls > 0:
            overall_rate = (total_answered / total_calls * 100)
            print(f"\n📊 Overall Summary for this period:")
            print(f" • Total Calls   : {format_number(total_calls)}")
            print(f" • Total Answered: {format_number(total_answered)}")
            print(f" • Answer Rate   : {overall_rate:.1f}%")
        elif filter_choice == '2' and selected_did and len(results) > 0:
            row = results[0]
            print(f"\n📊 Summary for DID {row.get('did_pattern')}:")
            print(f" • Total Calls   : {format_number(row.get('total_calls', 0))}")
            print(f" • Total Answered: {format_number(row.get('answered', 0))}")
            print(f" • Answer Rate   : {safe_str(row.get('answer_rate'), '0.00')}%")
        elif filter_choice == '3' and total_calls > 0:
            overall_rate = (total_answered / total_calls * 100)
            print(f"\n📊 Summary for Campaign Filter:")
            print(f" • Total Calls   : {format_number(total_calls)}")
            print(f" • Total Answered: {format_number(total_answered)}")
            print(f" • Answer Rate   : {overall_rate:.1f}%")
        elif total_calls == 0 and len(results) > 0:
            print(f"\n📊 No calls found for this period.")
        elif len(results) == 0:
            print(f"\n📊 No data found for the selected filter.")
        else:
            print(f"\n📊 Showing {len(results)} DID(s) with {format_number(total_calls)} total calls.")
        
    except Exception as e:
        print_error(f"Error with date range: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    did_inspector_menu()