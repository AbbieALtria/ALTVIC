#!/usr/bin/env python3
# core/agent_mapping_wizard.py - Interactive wizard to link pinktools agents → VICIdial usernames

from core.email_database import email_db
from core.email_integration import (
    ensure_mapping_table, get_all_mappings,
    add_mapping, list_unmapped_agents
)
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info
from datetime import date, timedelta


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_all_pinktools_agents():
    """Return every distinct agent_name ever seen in tbl_email, with their email count."""
    rows = email_db.execute_query(
        """
        SELECT agent_name, COUNT(*) AS total
        FROM tbl_email
        WHERE agent_name IS NOT NULL AND agent_name != ''
        GROUP BY agent_name
        ORDER BY total DESC
        """
    )
    return rows or []


def _get_recent_pinktools_agents(days=30):
    """Agents active in the last N days."""
    rows = email_db.execute_query(
        """
        SELECT agent_name, COUNT(*) AS total
        FROM tbl_email
        WHERE agent_name IS NOT NULL AND agent_name != ''
          AND created_2 >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY agent_name
        ORDER BY total DESC
        """,
        (days,)
    )
    return rows or []


def _check_email_db():
    """Quick connectivity check — returns True/False."""
    return email_db.test_connection()


# ──────────────────────────────────────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────────────────────────────────────

def _print_mapping_table(mapping: dict):
    if not mapping:
        print_warning("  No mappings saved yet.")
        return
    print(f"\n  {'#':<4} {'Pinktools Agent':<28} {'VICIdial Username'}")
    print("  " + "─" * 55)
    for i, (pt, al) in enumerate(sorted(mapping.items()), 1):
        print(f"  {i:<4} {pt:<28} {al}")
    print("  " + "─" * 55)


# ──────────────────────────────────────────────────────────────────────────────
# Sub-screens
# ──────────────────────────────────────────────────────────────────────────────

def _screen_link_agents():
    """Show all pinktools agents and let the user type a VICIdial username for each."""
    ensure_mapping_table()
    mapping = get_all_mappings()

    all_agents = _get_all_pinktools_agents()
    if not all_agents:
        print_warning("No agents found in tbl_email. Is the email DB connected?")
        input("\nPress Enter to continue...")
        return

    print_header("🔗 LINK AGENTS  (pinktools → VICIdial)", Colors.CYAN)
    print_info("Type the VICIdial username for each agent, or press Enter to skip.")
    print_info("To remove an existing link type '-' and press Enter.")
    print()

    changed = 0
    for row in all_agents:
        name  = row['agent_name']
        total = row['total']
        linked = mapping.get(name, '')

        status = f"{Colors.GREEN}→ {linked}{Colors.RESET}" if linked else f"{Colors.YELLOW}⚠ Unlinked{Colors.RESET}"
        prompt_line = (
            f"  [{total:>4} emails]  {name:<26}  {status}\n"
            f"  VICIdial username (Enter to skip): "
        )
        print(prompt_line, end='')

        try:
            answer = input().strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if answer == '-':
            # Remove mapping
            email_db.execute_query(
                "UPDATE tbl_agent_map SET active = 0 WHERE pinktools_agent_name = %s",
                (name,)
            )
            print_color(f"    ✖ Unlinked '{name}'", Colors.YELLOW)
            changed += 1
        elif answer:
            add_mapping(name, answer)
            print_color(f"    ✔ Mapped '{name}' → '{answer}'", Colors.GREEN)
            changed += 1

    if changed:
        print_success(f"\n{changed} mapping(s) saved.")
    else:
        print_info("\nNo changes made.")

    input("\nPress Enter to continue...")


def _screen_view_mappings():
    """Show current mapping table."""
    ensure_mapping_table()
    mapping = get_all_mappings()
    print_header("📋 CURRENT AGENT MAPPINGS", Colors.CYAN)
    _print_mapping_table(mapping)
    input("\nPress Enter to continue...")


def _screen_edit_single():
    """Edit or delete one mapping by pinktools name."""
    ensure_mapping_table()
    mapping = get_all_mappings()

    if not mapping:
        print_warning("No mappings yet. Use 'Link Agents' first.")
        input("\nPress Enter to continue...")
        return

    print_header("✏️  EDIT / DELETE A MAPPING", Colors.CYAN)
    _print_mapping_table(mapping)

    keys = sorted(mapping.keys())
    print("\nEnter the pinktools agent name (or row number):")
    answer = input(f"{Colors.CYAN}> {Colors.RESET}").strip()

    # Accept row number
    if answer.isdigit():
        idx = int(answer) - 1
        if 0 <= idx < len(keys):
            name = keys[idx]
        else:
            print_error("Row number out of range.")
            input("\nPress Enter to continue...")
            return
    else:
        name = answer

    if name not in mapping:
        print_error(f"'{name}' not found in mappings.")
        input("\nPress Enter to continue...")
        return

    print(f"\n  Current: {name}  →  {mapping[name]}")
    print("  Enter new VICIdial username (or '-' to delete, Enter to cancel):")
    new_val = input(f"{Colors.CYAN}> {Colors.RESET}").strip()

    if not new_val:
        print_info("Cancelled.")
    elif new_val == '-':
        email_db.execute_query(
            "UPDATE tbl_agent_map SET active = 0 WHERE pinktools_agent_name = %s",
            (name,)
        )
        print_color(f"✖ Unlinked '{name}'", Colors.YELLOW)
    else:
        add_mapping(name, new_val)
        print_success(f"✔ Updated '{name}' → '{new_val}'")

    input("\nPress Enter to continue...")


def _screen_unmapped_today():
    """Show agents who worked today but have no mapping."""
    ensure_mapping_table()
    today = date.today()
    names = list_unmapped_agents(today)

    print_header(f"⚠  UNMAPPED AGENTS — {today}", Colors.YELLOW)
    if not names:
        print_success("  All agents are mapped. Nothing to fix.")
    else:
        print_color(f"  {len(names)} unlinked agent(s):\n", Colors.YELLOW)
        for n in names:
            print(f"    • {n}")
        print()
        print_info("Use option 1 (Link Agents) to assign VICIdial usernames.")

    input("\nPress Enter to continue...")


def _screen_connection_test():
    """Test pinktools DB connection and show basic stats."""
    print_header("🔌 EMAIL DATABASE CONNECTION TEST", Colors.CYAN)

    ok = _check_email_db()
    if not ok:
        print_error("  Cannot connect to altriaca_email database.")
        print_info("  Check EMAIL_DB_HOST / EMAIL_DB_USER / EMAIL_DB_PASSWORD in .env")
        input("\nPress Enter to continue...")
        return

    print_success("  Connected to altriaca_email ✔")

    # Quick stats
    stats = email_db.execute_query(
        """
        SELECT
            COUNT(*)                           AS total_rows,
            COUNT(DISTINCT agent_name)         AS agents,
            COUNT(DISTINCT campaign)           AS campaigns,
            MIN(DATE(created_2))               AS earliest,
            MAX(DATE(created_2))               AS latest
        FROM tbl_email
        """
    )
    if stats and stats[0]['total_rows']:
        s = stats[0]
        print(f"\n  Total email records : {s['total_rows']:,}")
        print(f"  Distinct agents     : {s['agents']}")
        print(f"  Distinct campaigns  : {s['campaigns']}")
        print(f"  Date range          : {s['earliest']}  →  {s['latest']}")

    # Mapping stats
    ensure_mapping_table()
    mapping = get_all_mappings()
    all_agents = _get_all_pinktools_agents()
    unmapped = [a['agent_name'] for a in all_agents if a['agent_name'] not in mapping]
    print(f"\n  Agent mappings      : {len(mapping)} linked, {len(unmapped)} unlinked")

    input("\nPress Enter to continue...")


# ──────────────────────────────────────────────────────────────────────────────
# Main wizard entry point
# ──────────────────────────────────────────────────────────────────────────────

def agent_mapping_wizard():
    """Main menu for the agent mapping wizard."""
    while True:
        print_header("📧 EMAIL AGENT MAPPING WIZARD", Colors.MAGENTA)
        print("  Pinktools (email) ←→ VICIdial (calls) agent linker\n")
        print("   1. 🔗 Link Agents  (walk through all pinktools agents)")
        print("   2. 📋 View Current Mappings")
        print("   3. ✏️  Edit / Delete a Single Mapping")
        print("   4. ⚠️  Show Unlinked Agents (today)")
        print("   5. 🔌 Test Email DB Connection")
        print("   0. 🔙 Back")
        print("  " + "─" * 50)

        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

        if choice == '1':
            _screen_link_agents()
        elif choice == '2':
            _screen_view_mappings()
        elif choice == '3':
            _screen_edit_single()
        elif choice == '4':
            _screen_unmapped_today()
        elif choice == '5':
            _screen_connection_test()
        elif choice == '0':
            break
        else:
            print_error("Invalid option")
            input("\nPress Enter to continue...")
