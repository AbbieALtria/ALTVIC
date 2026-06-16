# utils/help_system.py - Help content and search system for Altria Ops

HELP_CONTENT = {
    "Agent Management": {
        "description": "Manage agents, view performance, monitor real-time activity, and track login history.",
        "subsections": {
            "Agent Lookup & Details": {
                "description": "Search for any agent by name or user ID. View extension, status, campaign assignments, and contact details.",
                "tips": "Type part of the agent name to search | Press Enter with no input to list all agents"
            },
            "Agent Performance Dashboard": {
                "description": "View individual or team-wide performance metrics including calls handled, talk time, and dispositions.",
                "tips": "Filter by campaign or date range | Export results to CSV"
            },
            "Real-time Agent Monitor": {
                "description": "Live view of all agents currently logged in, their status (READY/INCALL/PAUSE), and current call duration.",
                "tips": "Refreshes automatically | Color-coded by status"
            },
            "Outbound Dialer Monitor": {
                "description": "Monitor outbound campaign dialing ratios, drop rates, and agent availability in real-time.",
                "tips": "Use this to detect over-dialing or under-dialing conditions"
            },
            "Inbound Groups Manager": {
                "description": "View and manage inbound queue groups, assigned agents, and service level statistics.",
                "tips": "Shows current queue depth and wait times"
            },
            "Agent Notes & Feedback": {
                "description": "Add, view, and manage performance notes and coaching feedback for agents.",
                "tips": "Notes are timestamped and tied to the logged-in user"
            },
            "Top Performers": {
                "description": "Leaderboard ranking agents by calls handled, talk time, or quality scores.",
                "tips": "Adjust the date range to compare weekly or monthly performance"
            },
            "Agent Login/Logout History": {
                "description": "View full login and logout history for any agent over a selected number of days.",
                "tips": "Select the agent first, then choose the number of days (default 7)"
            },
            "Sales Dashboard": {
                "description": "Track sales conversions, revenue metrics, and agent sales performance.",
                "tips": "Requires sales disposition codes to be configured in VICIdial"
            }
        }
    },
    "Campaign Analytics": {
        "description": "Analyze campaign performance, monitor live queues, and compare historical trends.",
        "subsections": {
            "Campaign Performance Reports": {
                "description": "Detailed breakdown of calls, dispositions, talk time, and conversion rates per campaign.",
                "tips": "Filter by date range | Compare multiple campaigns side by side"
            },
            "Queue Monitor (Live)": {
                "description": "Real-time view of active queues showing calls waiting, agents available, and average wait time.",
                "tips": "Auto-refreshes every 30 seconds"
            },
            "Service Level Analysis": {
                "description": "Measure how well campaigns are meeting service level agreements (SLA) for answer speed.",
                "tips": "Service level threshold is configurable in Settings"
            },
            "Campaign Trends": {
                "description": "Line charts and tables showing call volume and performance trends over time.",
                "tips": "Select weekly or monthly view for different granularity"
            },
            "Historical Comparisons": {
                "description": "Compare current period performance against past periods for any campaign.",
                "tips": "Use to identify seasonal patterns or measure improvement"
            },
            "Campaign Comparison": {
                "description": "Side-by-side comparison of two or more campaigns across key metrics.",
                "tips": "Useful for benchmarking new campaigns against established ones"
            },
            "Hourly Campaign Stats": {
                "description": "Breakdown of call volume, dispositions, and agent activity by hour of day.",
                "tips": "Use to optimize staffing schedules based on call patterns"
            },
            "Queue Analysis": {
                "description": "Deep analysis of queue behavior including abandonment rates and wait time distribution.",
                "tips": "Identify peak abandon windows to improve scheduling"
            }
        }
    },
    "Reports & Exports": {
        "description": "Generate, export, and schedule reports in CSV, Excel, and PDF formats.",
        "subsections": {
            "Export to CSV/Excel": {
                "description": "Export call records, agent performance, or disposition data to CSV or Excel.",
                "tips": "Choose date range and campaign before exporting | Large exports may take a moment"
            },
            "Email Reports": {
                "description": "Send generated reports to configured recipients via email.",
                "tips": "SMTP must be configured in Settings > Email Configuration"
            },
            "Trend Analysis": {
                "description": "Multi-period trend analysis showing performance direction across campaigns and agents.",
                "tips": "Use 30-day view for meaningful trend lines"
            },
            "Week-over-Week Comparison": {
                "description": "Automatically compares current week vs. prior week across all key metrics.",
                "tips": "Green = improvement, Red = decline from prior week"
            },
            "Call Volume Analysis": {
                "description": "Analyze daily, weekly, and monthly call volumes with peak identification.",
                "tips": "Filter by campaign or view all campaigns combined"
            },
            "Performance Over Time": {
                "description": "Track agent and campaign performance metrics across a custom date range.",
                "tips": "Useful for monthly performance reviews"
            },
            "End of Day (EOD) Report": {
                "description": "Comprehensive daily summary report including calls, dispositions, agent stats, and quality scores.",
                "tips": "Can be scheduled to auto-generate and email at end of shift"
            },
            "Generate PDF Report": {
                "description": "Create a formatted PDF report for any campaign or agent for any date range.",
                "tips": "PDFs are saved to the exports folder and can be emailed"
            },
            "Scheduled Reports": {
                "description": "Set up automatic report generation and delivery on a recurring schedule.",
                "tips": "Configure email recipients in Settings > Email Configuration first"
            },
            "Generate Charts": {
                "description": "Create visual charts including daily trend lines and hourly heatmaps.",
                "tips": "Requires matplotlib: pip install matplotlib pandas"
            },
            "Email Channel Reports": {
                "description": "Reports specific to email channel activity, response times, and agent handling.",
                "tips": "Requires Email DB connection to be active"
            }
        }
    },
    "Call Quality Scoring": {
        "description": "AI-powered and manual QC scoring, calibration reports, and client QA packages.",
        "subsections": {
            "Quality Dashboard": {
                "description": "Overview of all evaluations: total count, average score, and score distribution (Excellent/Good/Needs Improvement).",
                "tips": "Scores are color-coded: Green ≥80%, Yellow 60-79%, Red <60%"
            },
            "Agent Quality Report": {
                "description": "Detailed quality history for a selected agent including score trends and checkpoint breakdown.",
                "tips": "Select the agent by number from the list"
            },
            "Top Performers": {
                "description": "Quality leaderboard ranked by average score, including consistency rating.",
                "tips": "Consistency score penalizes high variance — stable good scores rank higher"
            },
            "Coaching Opportunities": {
                "description": "Lists agents with average scores below 70% with priority levels: IMMEDIATE, URGENT, SCHEDULED.",
                "tips": "IMMEDIATE = score <50%, URGENT = 50-60%, SCHEDULED = 60-70%"
            },
            "VICIdial QC Dashboard": {
                "description": "Access VICIdial's native QC reporting interface.",
                "tips": "Requires VICIdial admin credentials"
            },
            "SOP Compliance Analysis": {
                "description": "Average scores for all 9 SOP checkpoints across all evaluated agents.",
                "tips": "Red checkpoints indicate training gaps that need addressing"
            },
            "Add QC Evaluation": {
                "description": "Manually enter QC scores for a call without using the AI assistant.",
                "tips": "Use when AI transcription is not available or not needed"
            },
            "AI Assistant (Auto-Score)": {
                "description": "Select a call, and AI will transcribe it with Whisper and suggest scores for all 9 checkpoints.",
                "tips": "QA reviews and adjusts AI scores before saving | Confidence score shows AI certainty"
            },
            "AI vs QA Calibration Report": {
                "description": "Compares AI-suggested scores against final QA scores to measure AI accuracy.",
                "tips": "Run weekly — if difference >10% consistently, retrain or adjust AI weights"
            },
            "View Historical Reports": {
                "description": "Browse and filter past QC evaluation reports by agent, date, or campaign.",
                "tips": "Reports include both AI scores and final QA-adjusted scores"
            },
            "Configure Quality Settings": {
                "description": "Adjust scoring thresholds, checkpoint weights, and notification triggers.",
                "tips": "Changes take effect immediately for new evaluations"
            },
            "Client QA Package": {
                "description": "Generate a professional, client-ready PDF QA report with executive summary, heatmaps, and trends.",
                "tips": "Select date range and campaign before generating | Takes 30-60 seconds to build"
            }
        }
    },
    "Alerts & Monitoring": {
        "description": "Configure and manage alerts for call center thresholds and system health.",
        "subsections": {
            "Alert Configuration": {
                "description": "Set thresholds for alerts such as high abandon rate, low service level, or agent idle time.",
                "tips": "Alerts can be delivered via email, Slack, or desktop notification"
            },
            "Active Alerts": {
                "description": "View currently triggered alerts that have not been acknowledged.",
                "tips": "Acknowledge alerts to clear them from the active list"
            },
            "Alert History": {
                "description": "Review past alerts with timestamps and resolution status.",
                "tips": "Use to identify recurring issues"
            }
        }
    },
    "Agent Behavior Alerts": {
        "description": "Automated alerts for unusual agent behavior such as excessive pause time or low call volume.",
        "subsections": {
            "Behavior Thresholds": {
                "description": "Configure thresholds that trigger behavior alerts per agent or campaign.",
                "tips": "Set realistic baselines before enabling alerts"
            },
            "Active Behavior Alerts": {
                "description": "View agents currently flagged for behavior issues.",
                "tips": "Click through to view the specific agent metrics that triggered the alert"
            }
        }
    },
    "Predictive Analytics": {
        "description": "Forecast future call volumes, staffing needs, and campaign performance.",
        "subsections": {
            "Volume Forecast": {
                "description": "Predict call volume for the next 7, 14, or 30 days based on historical patterns.",
                "tips": "Accuracy improves with more historical data (90+ days recommended)"
            },
            "Staffing Recommendations": {
                "description": "Suggested agent headcount by hour based on forecast volume and target service level.",
                "tips": "Adjust target service level in config to change staffing suggestions"
            }
        }
    },
    "Schedule Management": {
        "description": "Manage agent schedules, shift assignments, and adherence tracking.",
        "subsections": {
            "View Schedules": {
                "description": "View current shift schedules for all agents or filter by team.",
                "tips": "Schedules import from VICIdial or can be entered manually"
            },
            "Adherence Tracking": {
                "description": "Compare actual login times against scheduled times to measure adherence.",
                "tips": "Adherence % = (time logged in and active / scheduled time) × 100"
            }
        }
    },
    "Settings": {
        "description": "Configure system preferences, database connection, email, and campaign operating hours.",
        "subsections": {
            "Database Connection": {
                "description": "Reconfigure the MySQL/MariaDB connection to VICIdial.",
                "tips": "Use option 8 in Settings to update host, user, password, or port"
            },
            "Campaign Operating Hours": {
                "description": "Set the operating hours for each campaign to correctly calculate availability and SLA.",
                "tips": "Hours are used by reports and forecasting — keep them up to date"
            },
            "Export Directory": {
                "description": "Set the default folder where exported files (CSV, Excel, PDF) are saved.",
                "tips": "Use an absolute path to avoid confusion across sessions"
            }
        }
    },
    "DID Inspector": {
        "description": "View, search, and analyze Direct Inward Dial (DID) numbers and their call volume.",
        "subsections": {
            "View All DIDs": {
                "description": "List all DID numbers with status (Active/Inactive) and assigned inbound group.",
                "tips": "Sort by call volume to quickly identify low-activity DIDs"
            },
            "Problematic DIDs": {
                "description": "Highlights DIDs that are inactive or have unusually low call volume in the last 30 days.",
                "tips": "Investigate before deactivating — low volume may be intentional"
            },
            "Search DIDs": {
                "description": "Search by DID number or description to quickly locate a specific line.",
                "tips": "Partial matches are supported"
            }
        }
    }
}


def search_help(query):
    """Search HELP_CONTENT for matching sections, subsections, and tips."""
    query_lower = query.lower()
    results = []

    for section_name, section_data in HELP_CONTENT.items():
        # Match section name
        if query_lower in section_name.lower() or query_lower in section_data.get('description', '').lower():
            results.append(('section', section_name, section_data.get('description', ''), section_name))

        # Match subsections
        for sub_name, sub_data in section_data.get('subsections', {}).items():
            sub_desc = sub_data.get('description', '')
            sub_tips = sub_data.get('tips', '')
            if (query_lower in sub_name.lower() or
                    query_lower in sub_desc.lower() or
                    query_lower in sub_tips.lower()):
                results.append(('subsection', sub_name, sub_desc, section_name))

    return results


def display_search_results(results, query):
    """Print search results and return True if any found."""
    if not results:
        return False

    display = results[:20]
    print(f"\n  Found {len(results)} result(s) for '{query}':\n")
    print(f"  {'#':<4} {'Type':<12} {'Name':<35} {'Section'}")
    print("  " + "-" * 75)

    for i, result in enumerate(display, 1):
        rtype = result[0]
        name = result[1]
        section = result[3] if len(result) > 3 else ''
        type_label = 'Section' if rtype.startswith('section') else 'Feature'
        print(f"  {i:<4} {type_label:<12} {name:<35} {section}")

    return True


def get_section_details(section_name):
    """Return full section data dict or None."""
    return HELP_CONTENT.get(section_name)


def get_subsection_details(section_name, subsection_name):
    """Return subsection data dict or None."""
    section = HELP_CONTENT.get(section_name, {})
    return section.get('subsections', {}).get(subsection_name)
