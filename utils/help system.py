#!/usr/bin/env python3
"""
File: utils/help_system.py
Version: 2.1.0
Date: 2026-03-09
Description: Unified help system with search, keyboard shortcuts, and documentation
"""

from typing import List, Tuple, Dict, Any, Optional
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info

# =============================================================================
# HELP CONTENT DATABASE
# =============================================================================

HELP_CONTENT = {
    "Agent Management": {
        "description": "Tools for managing call center agents, viewing performance, and monitoring activity",
        "keywords": ["agent", "employee", "staff", "team", "representative", "rep", "csr", "performance", "monitoring"],
        "subsections": {
            "Agent Lookup": {
                "description": "Search and view detailed information about specific agents including contact info, skills, and current status",
                "keywords": ["search", "find", "details", "profile", "information", "contact"],
                "tips": "Use agent ID, name, extension, or email to search | Filter by team, skill, or status"
            },
            "Performance Dashboard": {
                "description": "View key performance metrics for all agents including call volume, handle time, and satisfaction scores",
                "keywords": ["kpi", "metrics", "stats", "statistics", "dashboard", "performance", "score"],
                "tips": "Metrics include call volume, average handle time (AHT), and customer satisfaction (CSAT) | Export data to CSV"
            },
            "Real-time Monitor": {
                "description": "Live view of agent status, current call duration, and activities in real-time",
                "keywords": ["live", "current", "status", "activity", "now", "realtime", "monitor"],
                "tips": "Shows current call duration, status (Available, Busy, Break, etc.), and current campaign"
            },
            "Outbound Dialer Monitor": {
                "description": "Monitor outbound calling campaigns, dialer effectiveness, and agent connect rates",
                "keywords": ["outbound", "dialer", "calling", "connect", "rate", "campaign"],
                "tips": "Tracks dialer effectiveness, agent connect rates, and call outcomes"
            },
            "Inbound Groups": {
                "description": "Manage inbound call groups, skill-based routing, and group membership",
                "keywords": ["inbound", "group", "queue", "routing", "skill", "membership"],
                "tips": "Configure skill-based routing rules and manage group membership | Set overflow parameters"
            },
            "Top Performers": {
                "description": "View rankings, leaderboards, and top performing agents by various metrics",
                "keywords": ["top", "best", "performers", "ranking", "leaderboard", "achievers"],
                "tips": "Filter by different time periods (today, week, month) and metrics (calls, sales, satisfaction)"
            },
            "Agent Notes": {
                "description": "Add, view, and manage notes and feedback for agents",
                "keywords": ["notes", "feedback", "comments", "review", "coaching"],
                "tips": "Add coaching notes, track performance issues, and document achievements"
            }
        }
    },
    "Campaign Analytics": {
        "description": "Analyze campaign performance, queue statistics, service levels, and historical trends",
        "keywords": ["campaign", "queue", "service level", "performance", "analytics", "statistics"],
        "subsections": {
            "Campaign Performance": {
                "description": "Detailed metrics for each campaign including calls handled, abandoned, and service level",
                "keywords": ["performance", "metrics", "calls", "handled", "abandoned", "service"],
                "tips": "Compare performance across different campaigns and time periods | View SL%, ASA, and abandonment rate"
            },
            "Queue Monitor": {
                "description": "Real-time queue statistics including current wait times, call volume, and agent status",
                "keywords": ["queue", "wait time", "volume", "real-time", "live", "monitor"],
                "tips": "Monitor SL% in real-time and adjust staffing accordingly | View calls waiting and longest wait time"
            },
            "Service Level Analysis": {
                "description": "Track and analyze service level agreements (SLA) compliance and trends",
                "keywords": ["service level", "sla", "compliance", "threshold", "target"],
                "tips": "View compliance with target answer times (e.g., 80/20) | Analyze by time of day and day of week"
            },
            "Campaign Trends": {
                "description": "Analyze historical trends and patterns in campaign data for forecasting",
                "keywords": ["trends", "patterns", "historical", "forecast", "seasonal"],
                "tips": "Identify peak hours, seasonal patterns, and growth trends | Use for capacity planning"
            },
            "Historical Comparisons": {
                "description": "Compare current campaign performance with historical data from previous periods",
                "keywords": ["compare", "historical", "previous", "vs", "versus", "year-over-year"],
                "tips": "Week-over-week, month-over-month, and year-over-year comparisons | Identify significant changes"
            }
        }
    },
    "Reports & Exports": {
        "description": "Generate, export, schedule, and distribute reports for analysis and stakeholders",
        "keywords": ["report", "export", "csv", "excel", "pdf", "email", "schedule"],
        "subsections": {
            "CSV/Excel Export": {
                "description": "Export data to CSV or Excel format for further analysis in external tools",
                "keywords": ["csv", "excel", "export", "spreadsheet", "data", "download"],
                "tips": "Choose from various data sets (agent, campaign, call details) and date ranges | Customize columns"
            },
            "Email Reports": {
                "description": "Schedule and send automated reports via email to stakeholders",
                "keywords": ["email", "send", "schedule", "automated", "distribution", "mail"],
                "tips": "Set up recurring daily, weekly, or monthly reports | Multiple recipient support | PDF or Excel format"
            },
            "Trend Analysis": {
                "description": "Analyze trends in key metrics like call volume, handle time, and abandonment rate",
                "keywords": ["trend", "analysis", "chart", "graph", "visualization", "metrics"],
                "tips": "Visualize data with line charts, bar graphs, and heat maps | Identify patterns and anomalies"
            },
            "Week-over-Week": {
                "description": "Compare performance metrics week over week to identify growth and patterns",
                "keywords": ["week", "weekly", "compare", "wow", "growth", "trend"],
                "tips": "Compare current week to previous week, same week last month, or same week last year"
            },
            "Call Volume Analysis": {
                "description": "Detailed analysis of call volume patterns by time, day, and interval",
                "keywords": ["volume", "calls", "traffic", "arrival", "pattern", "interval"],
                "tips": "Analyze by 15-minute, 30-minute, or hourly intervals | Forecast future volume based on historical data"
            },
            "End of Day Report": {
                "description": "Comprehensive end of day summary report with key metrics and highlights",
                "keywords": ["eod", "end of day", "summary", "daily", "close", "wrap-up"],
                "tips": "Automatically generated at configurable time | Includes key metrics, anomalies, and top performers"
            },
            "PDF Generation": {
                "description": "Generate professional PDF reports with charts and formatted tables",
                "keywords": ["pdf", "document", "print", "generate", "professional"],
                "tips": "Customizable templates | Include charts, graphs, and summary tables | Save or email directly"
            }
        }
    },
    "Alerts & Monitoring": {
        "description": "Configure and view system alerts, performance monitoring, and notifications",
        "keywords": ["alert", "monitor", "notification", "warning", "threshold", "detect"],
        "subsections": {
            "System Health": {
                "description": "Monitor system performance, database connectivity, and response times",
                "keywords": ["health", "system", "performance", "database", "connectivity", "status"],
                "tips": "Check database connection, query response times, and API availability | Get alerts for issues"
            },
            "Agent Behavior": {
                "description": "Detect unusual agent behavior patterns like extended breaks or unusual call patterns",
                "keywords": ["behavior", "pattern", "unusual", "anomaly", "break", "activity"],
                "tips": "Alerts for extended breaks, after-call work (ACW) time, or unusual call patterns"
            },
            "Threshold Alerts": {
                "description": "Set and monitor performance threshold alerts for key metrics",
                "keywords": ["threshold", "limit", "breach", "alert", "warning", "trigger"],
                "tips": "Get notified when metrics exceed defined limits (SL%, abandonment rate, wait time)"
            },
            "Anomaly Detection": {
                "description": "Machine learning-based detection of anomalies in call patterns and agent behavior",
                "keywords": ["anomaly", "ml", "machine learning", "detection", "outlier", "pattern"],
                "tips": "Automatically detects unusual patterns that may indicate issues or opportunities"
            }
        }
    },
    "Settings": {
        "description": "Configure system settings, user preferences, and application behavior",
        "keywords": ["settings", "preferences", "configure", "setup", "options", "language"],
        "subsections": {
            "Language": {
                "description": "Change the system interface language for localized experience",
                "keywords": ["language", "locale", "i18n", "translation", "spanish", "french"],
                "tips": "Supports English, Spanish, French, German, Arabic, and Chinese | Changes take effect immediately"
            },
            "Export Directory": {
                "description": "Set default directory for file exports like CSV, Excel, and PDF files",
                "keywords": ["export", "directory", "folder", "path", "save", "location"],
                "tips": "Use absolute paths for consistent access | Network drives supported | Create if doesn't exist"
            },
            "Campaign Hours": {
                "description": "Configure operating hours for campaigns including holidays and special schedules",
                "keywords": ["hours", "operating", "schedule", "business", "holiday", "time"],
                "tips": "Set different hours for different days of week | Configure holiday schedules | Affects reporting"
            },
            "Email Configuration": {
                "description": "Configure email server settings for sending reports and notifications",
                "keywords": ["email", "smtp", "mail", "server", "configuration", "send"],
                "tips": "SMTP server, port, authentication, and security settings | Test configuration before saving"
            },
            "Notification Preferences": {
                "description": "Set preferences for system notifications and alerts",
                "keywords": ["notification", "alert", "preferences", "settings", "popup"],
                "tips": "Choose which alerts to receive and how (popup, email, both) | Set quiet hours"
            }
        }
    },
    "Unified Search": {
        "description": "Search across campaigns, inbound groups, and other entities from a single interface",
        "keywords": ["search", "find", "lookup", "unified", "global", "quick"],
        "subsections": {
            "Campaign Search": {
                "description": "Search for campaigns by name, ID, or other attributes",
                "keywords": ["campaign", "search", "find", "lookup"],
                "tips": "Search by campaign name, ID, or description | Filter by status, date range"
            },
            "Inbound Group Search": {
                "description": "Search for inbound groups and queues",
                "keywords": ["inbound", "group", "queue", "search"],
                "tips": "Find groups by name, extension, or skills | View current queue status"
            }
        }
    },
    "Schedule Management": {
        "description": "Manage agent schedules, view adherence, and track shift assignments",
        "keywords": ["schedule", "shift", "adherence", "attendance", "calendar", "roster"],
        "subsections": {
            "Today's Schedule": {
                "description": "View all agents scheduled for today with their shift times and status",
                "keywords": ["today", "daily", "current", "now"],
                "tips": "Shows which agents are scheduled, their shift times, and current status | Add new shifts directly"
            },
            "Agent Schedule": {
                "description": "View and manage schedules for individual agents",
                "keywords": ["agent", "individual", "personal", "calendar"],
                "tips": "Select date ranges (7/14/30 days) | View upcoming shifts | Cancel or modify shifts"
            },
            "Adherence Report": {
                "description": "Compare scheduled shifts with actual login times to measure adherence",
                "keywords": ["adherence", "compliance", "late", "absent", "attendance"],
                "tips": "Shows on-time, late, and no-show agents | Calculates lateness in minutes | Compare scheduled vs actual"
            },
            "Shift Templates": {
                "description": "Create and manage shift templates for quick scheduling",
                "keywords": ["template", "pattern", "recurring", "standard"],
                "tips": "Create templates for common shifts (morning, afternoon, evening) | Assign colors for easy identification"
            }
        }
    },
    "Schedule Integration": {
        "description": "Integration between schedule management, forecasting, and predictive analytics",
        "keywords": ["schedule", "forecast", "predictive", "integration", "staffing", "prediction", "vs", "compare"],
        "subsections": {
            "Schedule Database": {
                "description": "Schedule database module that creates and manages schedule tables, stores shifts, templates, exceptions, and predictions in MySQL",
                "keywords": ["schedule_db", "database", "tables", "mysql", "storage"],
                "tips": "Creates actual database tables for schedule management | Provides menu-driven interface"
            },
            "Forecast Engine": {
                "description": "Generates call volume predictions using historical data and calculates staffing needs based on forecasts",
                "keywords": ["forecast", "prediction", "call volume", "staffing", "aht", "occupancy"],
                "tips": "Uses historical data to predict future call volumes | Calculates agents needed based on Erlang formulas"
            },
            "Schedule vs Predictions": {
                "description": "Compare scheduled agents with predicted needs to identify staffing gaps",
                "keywords": ["compare", "vs", "gap", "understaffed", "overstaffed", "optimal"],
                "tips": "Shows understaffed and overstaffed days | Helps optimize workforce planning"
            }
        }
    }
}

# =============================================================================
# SCHEDULE INTEGRATION SETUP GUIDE
# =============================================================================

SCHEDULE_SETUP_GUIDE = """
📊 SCHEDULE INTEGRATION SETUP GUIDE
====================================

The schedule management system integrates with forecasting for optimal staffing.

## Step 1: Create Schedule Tables (Run Once)
   from agents.schedule_db import create_schedule_tables
   create_schedule_tables()

## Step 2: Add Shift Templates
   from agents.schedule_db import add_shift_template
   add_shift_template("Morning", "08:00", "16:00", 30, "standard", "Morning shift")
   add_shift_template("Afternoon", "14:00", "22:00", 30, "standard", "Afternoon shift")
   add_shift_template("Evening", "22:00", "06:00", 45, "overnight", "Overnight shift")

## Step 3: Assign Shifts to Agents
   Schedule Management → Option 1 (Today's Schedule) → Add shift

## Step 4: Generate Forecasts
   Reports → Predictive Analytics → Generate Forecast

## Step 5: Compare Schedules vs Predictions
   Schedule Management → Option 4 (Schedule vs Predictions)

The system will show understaffed/overstaffed days and help optimize workforce planning.
"""

# =============================================================================
# KEYBOARD SHORTCUTS
# =============================================================================

KEYBOARD_SHORTCUTS = {
    '0': 'Return to previous menu / Exit',
    'Ctrl+C': 'Graceful shutdown',
    'Enter': 'Continue after any operation',
    '/': 'Search in help menu (when available)',
    'q': 'Quit current operation / Go back',
    'r': 'Refresh current view',
    '?': 'Show help for current screen',
    'h': 'Open help menu',
    's': 'Search help (from help menu)',
    '1-9': 'Select menu options',
    'n': 'Next page (in paginated views)',
    'p': 'Previous page (in paginated views)',
    'Tab': 'Auto-complete commands',
    'Up/Down': 'Navigate command history',
    'F1': 'Show help',
    'F5': 'Refresh view',
    'Esc': 'Cancel current operation'
}

# =============================================================================
# SEARCH FUNCTIONS
# =============================================================================

def search_help(search_term: str, min_relevance: int = 50) -> List[Tuple[str, str, str, Optional[str]]]:
    """
    Search help content for a specific term and return relevant results
    
    Args:
        search_term: Term to search for
        min_relevance: Minimum relevance score (not currently used, for future enhancement)
        
    Returns:
        List of tuples containing (result_type, title, description, section)
    """
    search_term = search_term.lower().strip()
    results = []
    
    if not search_term or len(search_term) < 2:
        return results
    
    # Search through all sections
    for section, section_data in HELP_CONTENT.items():
        # Search in section title
        if search_term in section.lower():
            results.append(('section', section, section_data['description'], None))
        
        # Search in section description
        if search_term in section_data['description'].lower():
            results.append(('section_desc', section, section_data['description'], None))
        
        # Search in section keywords
        for keyword in section_data.get('keywords', []):
            if search_term in keyword.lower():
                results.append(('section_keyword', section, section_data['description'], None))
                break
        
        # Search in subsections
        for sub_name, sub_data in section_data.get('subsections', {}).items():
            # Search in subsection title
            if search_term in sub_name.lower():
                results.append(('subsection', sub_name, sub_data['description'], section))
            
            # Search in subsection description
            if search_term in sub_data['description'].lower():
                results.append(('subsection_desc', sub_name, sub_data['description'], section))
            
            # Search in subsection keywords
            for keyword in sub_data.get('keywords', []):
                if search_term in keyword.lower():
                    results.append(('subsection_keyword', sub_name, sub_data['description'], section))
                    break
            
            # Search in tips
            if 'tips' in sub_data and search_term in sub_data['tips'].lower():
                results.append(('tip', sub_name, sub_data['tips'], section))
    
    # Search in keyboard shortcuts
    for key, desc in KEYBOARD_SHORTCUTS.items():
        if search_term in key.lower() or search_term in desc.lower():
            results.append(('shortcut', key, desc, None))
    
    # Remove duplicates
    seen = set()
    unique_results = []
    for rtype, title, desc, section in results:
        key = (rtype, title, desc)
        if key not in seen:
            seen.add(key)
            unique_results.append((rtype, title, desc, section))
    
    return unique_results[:50]  # Limit to 50 results


def display_search_results(results: List[Tuple[str, str, str, Optional[str]]], search_term: str) -> bool:
    """
    Display search results with formatting and numbering
    
    Args:
        results: List of search result tuples
        search_term: Original search term
        
    Returns:
        True if display was successful, False if no results
    """
    if not results:
        print_warning(f"No results found for '{search_term}'")
        print_info("Try:")
        print("  • Using different words")
        print("  • Checking spelling")
        print("  • Searching for related terms")
        return False
    
    print_color(f"\n✅ Found {len(results)} results for '{search_term}':", Colors.GREEN)
    print("  " + "─" * 80)
    
    for i, result in enumerate(results[:20], 1):
        # Handle different result formats
        if len(result) == 4:
            rtype, title, desc, section = result
        elif len(result) == 3:
            rtype, title, desc = result
            section = None
        else:
            continue
        
        # Determine icon and color based on result type
        if rtype.startswith('section'):
            icon = "📑"
            type_text = "SECTION"
            color = Colors.BLUE
            location = f"[{title}]" if not section else f"[{section}]"
        elif rtype.startswith('subsection'):
            icon = "📘"
            type_text = "FEATURE"
            color = Colors.GREEN
            location = f"[{section} → {title}]" if section else f"[{title}]"
        elif rtype == 'tip':
            icon = "💡"
            type_text = "TIP"
            color = Colors.YELLOW
            location = f"[{section}]" if section else ""
        elif rtype == 'shortcut':
            icon = "⌨️"
            type_text = "SHORTCUT"
            color = Colors.MAGENTA
            location = ""
        else:
            icon = "📌"
            type_text = "RESULT"
            color = Colors.RESET
            location = ""
        
        # Print result with color
        print_color(f"\n  {i:2d}. {icon} {type_text}", color)
        if location:
            print(f"      {location}")
        print(f"      {title}")
        
        # Truncate description if too long
        if len(desc) > 100:
            print(f"      {desc[:100]}...")
        else:
            print(f"      {desc}")
    
    if len(results) > 20:
        print_info(f"\n  ... and {len(results) - 20} more results")
    
    print("\n  " + "─" * 80)
    print(f"  Showing top {min(20, len(results))} of {len(results)} results")
    
    return True


def get_section_details(section: str) -> Optional[Dict[str, Any]]:
    """Get details for a specific section"""
    if section in HELP_CONTENT:
        return HELP_CONTENT[section]
    return None


def get_subsection_details(section: str, sub: str) -> Optional[Dict[str, str]]:
    """Get details for a specific subsection"""
    if section in HELP_CONTENT and "subsections" in HELP_CONTENT[section]:
        if sub in HELP_CONTENT[section]["subsections"]:
            return HELP_CONTENT[section]["subsections"][sub]
    return None


def get_keyboard_shortcuts() -> Dict[str, str]:
    """Get all keyboard shortcuts"""
    return KEYBOARD_SHORTCUTS.copy()


def display_keyboard_shortcuts() -> None:
    """Display all keyboard shortcuts in a formatted table"""
    shortcuts = get_keyboard_shortcuts()
    
    print_header("Keyboard Shortcuts")
    print()
    
    # Calculate column widths
    key_width = max(len(key) for key in shortcuts.keys()) + 2
    desc_width = 60
    
    # Print header
    print_color(f"{'Key':<{key_width}} {'Description':<{desc_width}}", Colors.CYAN)
    print_color("─" * (key_width + desc_width + 1), Colors.CYAN)
    
    # Print shortcuts
    for key, description in sorted(shortcuts.items()):
        # Special formatting for certain keys
        if key in ['Ctrl+C', 'Enter']:
            print_color(f"{key:<{key_width}} {description:<{desc_width}}", Colors.YELLOW)
        elif key.isdigit() or '-' in key:
            print_color(f"{key:<{key_width}} {description:<{desc_width}}", Colors.CYAN)
        else:
            print_color(f"{key:<{key_width}} {description:<{desc_width}}", Colors.GREEN)
    
    print()


def get_shortcut_description(key: str) -> Optional[str]:
    """Get description for a specific keyboard shortcut"""
    return KEYBOARD_SHORTCUTS.get(key)


def is_valid_shortcut(key: str) -> bool:
    """Check if a key combination is a valid shortcut"""
    return key in KEYBOARD_SHORTCUTS


def get_all_sections() -> List[str]:
    """Get a list of all available sections"""
    return list(HELP_CONTENT.keys())


def get_all_subsections(section: str) -> List[str]:
    """Get a list of all subsections for a given section"""
    if section in HELP_CONTENT:
        return list(HELP_CONTENT[section].get('subsections', {}).keys())
    return []


def display_schedule_setup_guide() -> None:
    """Display the schedule integration setup guide"""
    print_header("📊 SCHEDULE INTEGRATION SETUP GUIDE", Colors.GREEN)
    print(SCHEDULE_SETUP_GUIDE)

# =============================================================================
# MAIN FUNCTION (for testing)
# =============================================================================

if __name__ == "__main__":
    # Simple test when run directly
    print_header("Help System Test")
    
    # Test search for schedule-related terms
    test_terms = ["schedule", "forecast", "predictive", "integration", "staffing"]
    
    for term in test_terms:
        print_color(f"\nSearching for: '{term}'", Colors.YELLOW)
        results = search_help(term)
        display_search_results(results, term)
    
    # Display the setup guide
    display_schedule_setup_guide()
    
    # Test keyboard shortcuts display
    display_keyboard_shortcuts()
    
    # Test section access
    print_color("\nGetting section details:", Colors.YELLOW)
    section = "Schedule Integration"
    details = get_section_details(section)
    if details:
        print(f"  {section}: {details['description']}")
    
    subsection = "Schedule Database"
    sub_details = get_subsection_details(section, subsection)
    if sub_details:
        print(f"  {section} → {subsection}: {sub_details['description']}")
        if 'tips' in sub_details:
            print(f"    Tip: {sub_details['tips']}")