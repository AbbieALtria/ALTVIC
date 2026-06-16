#!/usr/bin/env python3
# =============================================================================
# File:         main.py
# Version:      7.6.0
# Release Date: 2026-03-30
# Description:  Main entry point for Altria Operations System - Call Center Analytics
# Updates:      Added 15. 📞 DID Inspector for DID management and monitoring
#               Added 12. 📋 Client QA Package to Quality Scoring menu
# Author:       Altria Ops Team
# =============================================================================

import sys
import os
import platform
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.database import db
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info, print_persistent_header
from utils.formatter import format_datetime
from config.settings import load_config, save_config
from utils.unified_search import unified_search_menu

# Optional direct imports for new modules
try:
    from agents.sales_dashboard import sales_dashboard_menu
except ImportError:
    sales_dashboard_menu = None

try:
    from metrics.queue_analyzer import queue_analyzer_menu
except ImportError:
    queue_analyzer_menu = None


class AltriaOps:
    def __init__(self):
        self.config = load_config()
        self.current_user = None
        self.language = self.config.get('language', 'en')
        self.version = "7.6.0"
        self.release_date = "2026-03-30"

    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_banner(self):
        """Print welcome banner with version and release date"""
        print_color("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                    ALTRIA OPERATIONS SYSTEM                   ║
    ║                       Call Center Analytics                   ║
    ║                    🤖 AI-Powered Quality Scoring              ║
    ║                       Full Audit Trail                        ║
    ║                   📜 Historical Report Viewer                 ║
    ║                   📞 DID Inspector                            ║
    ╚═══════════════════════════════════════════════════════════════╝
        """, Colors.CYAN)

        print(f"  {Colors.YELLOW}Version: {self.version}{Colors.RESET}     {Colors.GREEN}Released: {self.release_date}{Colors.RESET}")
        print()

        now = datetime.now()
        print(f"  {Colors.CYAN}Server Time:{Colors.RESET} {format_datetime(now)}")

        if hasattr(db, 'params') and db.params:
            print_color(f"  Connected to: {db.params['host']}", Colors.GREEN)
        else:
            print_color("  Not connected to database", Colors.RED)

        print(f"  {Colors.CYAN}User:{Colors.RESET} {self.current_user or 'Not Logged In'}")
        print()

    def print_menu(self):
        """Print main menu with clean number formatting - Added DID Inspector"""
        menu_options = {
            '1': ('Agent Management', self.agent_menu),
            '2': ('Campaign Analytics', self.campaign_menu),
            '3': ('Reports & Exports', self.reports_menu),
            '4': ('Alerts & Monitoring', self.alerts_menu),
            '5': ('Agent Behavior Alerts', self.agent_alerts_menu),
            '6': ('Call Quality Scoring', self.quality_menu),
            '7': ('Predictive Analytics', self.forecasting_menu),
            '8': ('📅 Schedule Management', self.schedule_menu),
            '9': ('Anomaly Detection', self.anomaly_menu),
            '10': ('Query Monitor', self.query_monitor_menu),
            '11': ('Settings', self.settings_menu),
            '12': ('Help', self.help_menu),
            '13': ('Unified Search', self.unified_search),
            '14': ('📥 APT Download (Campaign Data API)', self.apt_download_menu),
            '15': ('📞 DID Inspector', self.did_inspector_menu),
            '16': ('📧 Email Agent Mapping', self.email_mapping_menu),
            '0': ('Exit', self.exit_system)
        }

        print_persistent_header("MAIN MENU")
        print("  " + "─" * 70)

        items = list(menu_options.items())
        for i in range(0, len(items), 2):
            key1, (desc1, _) = items[i]
            num1 = f"{key1:>2}"

            if i + 1 < len(items):
                key2, (desc2, _) = items[i + 1]
                num2 = f"{key2:>2}"
                print(f"  {num1}. {desc1:<32} {num2}. {desc2}")
            else:
                print(f"  {num1}. {desc1}")

        print("  " + "─" * 70)

        return menu_options

    # =========================================================================
    # UNIFIED SEARCH
    # =========================================================================

    def unified_search(self):
        """Unified Search for campaigns and inbound groups"""
        try:
            unified_search_menu()
        except ImportError:
            print_error("Unified search module not found.")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error: {str(e)}")
            input("\nPress Enter to continue...")

    # =========================================================================
    # AGENT BEHAVIOR ALERTS
    # =========================================================================

    def agent_alerts_menu(self):
        """Agent Behavior Alerts Menu"""
        try:
            from alerts.agent_alerts import agent_alerts_menu
            agent_alerts_menu()
        except ImportError as e:
            print_error(f"Agent alerts module not found: {e}")
            print("\nPlease ensure the file exists at: alerts/agent_alerts.py")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # CALL QUALITY SCORING
    # =========================================================================

    def quality_menu(self):
        """Call Quality Scoring Menu with AI-powered reports and audit trail"""
        while True:
            print_header("🎯 CALL QUALITY SCORING", Colors.CYAN)
            print("  " + "─" * 60)
            print("   1. 📊 Quality Dashboard")
            print("   2. 👤 Agent Quality Report (Advanced)")
            print("   3. 🏆 Top Performers (Advanced)")
            print("   4. 📈 Coaching Opportunities (Advanced)")
            print("   5. 📋 VICIdial QC Dashboard")
            print("   6. 📋 SOP Compliance Analysis")
            print("   7. ✨ Add QC Evaluation")
            print("   8. 🤖 AI Assistant (Auto-Score)")
            print("   9. 📊 AI vs QA Calibration Report")
            print("  10. 📜 View Historical Reports")
            print("  11. ⚙️ Configure Quality Settings")
            print("  12. 📋 Client QA Package")
            print("   0. 🔙 Back to Main Menu")
            print("  " + "─" * 60)

            choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

            if choice == '1':
                try:
                    from quality.scoring import show_quality_dashboard
                    show_quality_dashboard()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("Quality dashboard module not found")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '2':
                try:
                    from quality.scoring import show_agent_quality_detail_advanced
                    show_agent_quality_detail_advanced()
                except ImportError as e:
                    print_error(f"Advanced agent report module not found: {e}")
                    print("\nPlease ensure the updated scoring.py exists with advanced functions")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '3':
                try:
                    from quality.scoring import show_top_performers_advanced
                    show_top_performers_advanced()
                except ImportError as e:
                    print_error(f"Advanced top performers module not found: {e}")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '4':
                try:
                    from quality.scoring import show_coaching_opportunities_advanced
                    show_coaching_opportunities_advanced()
                except ImportError as e:
                    print_error(f"Advanced coaching module not found: {e}")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '5':
                try:
                    from quality.vicidial_qc_reports import show_qc_dashboard
                    show_qc_dashboard()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("VICIdial QC Reports module not found")
                    print("\nPlease ensure the file exists at: quality/vicidial_qc_reports.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '6':
                try:
                    from quality.vicidial_qc_reports import show_sop_compliance_report
                    show_sop_compliance_report()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("SOP Compliance module not found")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '7':
                try:
                    from quality.add_evaluation import add_qc_evaluation
                    add_qc_evaluation()
                except ImportError as e:
                    print_error(f"Add QC Evaluation module not found: {e}")
                    print("\nPlease ensure the file exists at: quality/add_evaluation.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '8':
                try:
                    from quality.ai_assistant import show_ai_assistant
                    show_ai_assistant()
                except ImportError as e:
                    print_error(f"AI Assistant module not found: {e}")
                    print("\nPlease ensure the file exists at: quality/ai_assistant.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '9':
                try:
                    from quality.scoring import show_calibration_report
                    show_calibration_report()
                except ImportError as e:
                    print_error(f"Calibration report module not found: {e}")
                    print("\nPlease ensure the updated scoring.py exists with calibration functions")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '10':
                try:
                    from quality.report_viewer import report_viewer_menu
                    report_viewer_menu()
                except ImportError as e:
                    print_error(f"Report Viewer module not found: {e}")
                    print("\nPlease ensure the file exists at: quality/report_viewer.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '11':
                try:
                    from quality.scoring import configure_quality_settings
                    configure_quality_settings()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("Quality settings module not found")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '12':
                try:
                    from quality.client_qa_package import show_client_qa_package
                    show_client_qa_package()
                except ImportError as e:
                    print_error(f"Client QA Package module not found: {e}")
                    print("\nPlease ensure the file exists at: quality/client_qa_package.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '0':
                break
            else:
                print_error("Invalid option")
                input("\nPress Enter to continue...")

    # =========================================================================
    # APT DOWNLOAD MENU
    # =========================================================================

    def apt_download_menu(self):
        """APT Download Menu for Campaign Data API"""
        try:
            from api.apt_download import apt_download_menu
            apt_download_menu()
        except ImportError as e:
            print_error(f"APT Download module not found: {e}")
            print("\nPlease ensure the file exists at: api/apt_download.py")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # SCHEDULE MANAGEMENT
    # =========================================================================

    def schedule_menu(self):
        """Schedule Management Menu - Connected to Predictive Analytics"""
        try:
            from agents.schedule import schedule_menu
            schedule_menu()
        except ImportError as e:
            print_error(f"Schedule module not found: {e}")
            print("\nPlease ensure the file exists at: agents/schedule.py")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # SYSTEM HEALTH
    # =========================================================================

    def system_health_menu(self):
        """System Health Monitoring Menu"""
        try:
            from alerts.system_health import system_health_menu
            system_health_menu()
        except ImportError as e:
            print_error(f"System health module not found: {e}")
            print("\nPlease ensure the file exists at: alerts/system_health.py")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # PREDICTIVE ANALYTICS
    # =========================================================================

    def forecasting_menu(self):
        """Predictive Analytics Menu"""
        try:
            from forecasting.predictive import forecasting_menu
            forecasting_menu()
        except ImportError as e:
            print_error(f"Predictive Analytics module not found: {e}")
            print("\nPlease ensure the file exists at: forecasting/predictive.py")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # ANOMALY DETECTION
    # =========================================================================

    def anomaly_menu(self):
        """Anomaly Detection Menu"""
        try:
            from monitoring.analytics.anomaly_detection import anomaly_menu
            anomaly_menu()
        except ImportError as e:
            print_error(f"Anomaly Detection module not found: {e}")
            print("\nPlease ensure the file exists at: monitoring/analytics/anomaly_detection.py")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # QUERY MONITOR
    # =========================================================================

    def query_monitor_menu(self):
        """Query Monitor Menu"""
        try:
            from optimization.query_monitor import query_monitor_menu
            query_monitor_menu()
        except ImportError as e:
            print_error(f"Query Monitor module not found: {e}")
            print("\nPlease ensure the file exists at: optimization/query_monitor.py")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # FORECAST (Legacy)
    # =========================================================================

    def forecast_menu(self):
        """Forecasting Menu (Legacy - kept for backward compatibility)"""
        try:
            from reports.forecast import forecast_menu
            forecast_menu()
        except ImportError as e:
            print_error(f"Forecast module not found: {e}")
            print("\nPlease ensure the file exists at: reports/forecast.py")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # ALERTS & MONITORING
    # =========================================================================

    def alerts_menu(self):
        """Alerts & Monitoring Submenu"""
        try:
            from alerts.monitoring import alerts_menu
            alerts_menu()
        except ImportError as e:
            print_error(f"Alerts monitoring module not found: {e}")
            print("\nPlease ensure the file exists at: alerts/monitoring.py")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error in alerts module: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # AGENT MANAGEMENT - FIXED Option 8
    # =========================================================================

    def agent_menu(self):
        """Agent Management Submenu - Fixed Login History option"""
        while True:
            print_persistent_header("AGENT MANAGEMENT")
            print("  " + "─" * 60)
            print("   1. Agent Lookup & Details")
            print("   2. Agent Performance Dashboard")
            print("   3. Real-time Agent Monitor")
            print("   4. Outbound Dialer Monitor")
            print("   5. Inbound Groups Manager")
            print("   6. Agent Notes & Feedback")
            print("   7. Top Performers")
            print("   8. Agent Login/Logout History")
            print("   9. 💰 Sales Dashboard")
            print("   0. Back to Main Menu")
            print("  " + "─" * 60)

            choice = input(f"\n{Colors.CYAN}Select option: {Colors.RESET}").strip()

            if choice == '1':
                try:
                    from agents.lookup import agent_lookup_menu
                    agent_lookup_menu()
                except ImportError:
                    print_error("Agent lookup module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '2':
                try:
                    from agents.dashboard import agent_dashboard
                    agent_dashboard()
                except ImportError:
                    print_error("Agent dashboard module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '3':
                try:
                    from monitoring.agent_monitor import AgentMonitor
                    AgentMonitor().quick_view()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("Agent monitor module not found at monitoring/agent_monitor.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '4':
                try:
                    from agents.outbound_monitor import outbound_monitor_menu
                    outbound_monitor_menu()
                except ImportError:
                    print_error("Outbound monitor module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '5':
                try:
                    from agents.inbound_groups import inbound_groups_menu
                    inbound_groups_menu()
                except ImportError:
                    print_error("Inbound groups module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '6':
                try:
                    from agents.notes import notes_menu
                    notes_menu()
                except ImportError as e:
                    print_error(f"Agent Notes module not found: {e}")
                    print("\nPlease ensure the file exists at: agents/notes.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '7':
                try:
                    from agents.dashboard import show_top_performers
                    show_top_performers()
                except ImportError as e:
                    print_error(f"Cannot load Top Performers view: {e}")
                    print("Make sure dashboard.py is in the agents/ folder and contains 'show_top_performers'")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '8':
                # FIXED: Now properly prompts for agent and days
                try:
                    from agents.dashboard import agent_login_history
                    from agents.dashboard import show_agent_list, get_agent_by_selection
                    
                    print_header("🔐 AGENT LOGIN HISTORY", Colors.CYAN)
                    
                    # First, get list of agents
                    agents = show_agent_list()
                    if agents:
                        selected_agent = get_agent_by_selection(agents)
                        if selected_agent:
                            # Ask for number of days
                            days_input = input("Days to analyze (default 7): ").strip()
                            days = int(days_input) if days_input.isdigit() else 7
                            agent_login_history(selected_agent, days)
                        else:
                            print_warning("No agent selected")
                    else:
                        print_warning("No agents found")
                        
                    input("\nPress Enter to continue...")
                except ImportError as e:
                    print_error(f"Login history module not found: {e}")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '9':
                try:
                    from agents.sales_dashboard import sales_dashboard_menu
                    sales_dashboard_menu()
                except ImportError as e:
                    print_error(f"Sales Dashboard module not found: {e}")
                    print("\nPlease ensure the file exists at: agents/sales_dashboard.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '0':
                break
            else:
                print_error("Invalid option")
                input("\nPress Enter to continue...")

    # =========================================================================
    # CAMPAIGN ANALYTICS
    # =========================================================================

    def campaign_menu(self):
        """Campaign Analytics Submenu with clean numbering"""
        while True:
            print_persistent_header("CAMPAIGN ANALYTICS")
            print("  " + "─" * 60)
            print("   1. Campaign Performance Reports")
            print("   2. Queue Monitor (Live)")
            print("   3. Service Level Analysis")
            print("   4. Campaign Trends")
            print("   5. Historical Comparisons")
            print("   6. Campaign Comparison")
            print("   7. Hourly Campaign Stats")
            print("   8. 🔍 Queue Analysis")
            print("   0. Back to Main Menu")
            print("  " + "─" * 60)

            choice = input(f"\n{Colors.CYAN}Select option: {Colors.RESET}").strip()

            if choice == '1':
                try:
                    from campaigns.performance import campaign_performance_menu
                    campaign_performance_menu()
                except ImportError:
                    print_error("Campaign performance module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '2':
                try:
                    from campaigns.live_queue import queue_menu
                    queue_menu()
                except ImportError:
                    print_error("Queue monitor module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '3':
                try:
                    from campaigns.service_level import service_level_menu
                    service_level_menu()
                except ImportError:
                    print_warning("Service Level Analysis module coming soon!")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '4':
                try:
                    from campaigns.trends import trends_menu
                    trends_menu()
                except ImportError:
                    print_error("Campaign trends module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '5':
                try:
                    from campaigns.historical import historical_menu
                    historical_menu()
                except ImportError:
                    print_error("Historical comparisons module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '6':
                try:
                    from campaigns.performance import compare_campaigns
                    compare_campaigns()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("Campaign comparison module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '7':
                try:
                    from campaigns.performance import hourly_campaign_stats
                    hourly_campaign_stats()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("Hourly stats module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '8':
                try:
                    from metrics.queue_analyzer import queue_analyzer_menu
                    queue_analyzer_menu()
                except ImportError as e:
                    print_error(f"Queue Analyzer module not found: {e}")
                    print("\nPlease ensure the file exists at: metrics/queue_analyzer.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '0':
                break
            else:
                print_error("Invalid option")
                input("\nPress Enter to continue...")

    # =========================================================================
    # REPORTS & EXPORTS
    # =========================================================================

    def reports_menu(self):
        """Reports & Exports Submenu with clean numbering - Added Charts option (10)"""
        while True:
            print_persistent_header("REPORTS & EXPORTS")
            print("  " + "─" * 60)
            print("   1. Export to CSV/Excel")
            print("   2. Email Reports")
            print("   3. Trend Analysis")
            print("   4. Week-over-Week Comparison")
            print("   5. Call Volume Analysis")
            print("   6. Performance Over Time")
            print("   7. End of Day (EOD) Report")
            print("   8. Generate PDF Report")
            print("   9. Scheduled Reports")
            print("  10. 📊 Generate Charts")
            print("  11. 📧 Email Channel Reports")
            print("   0. Back to Main Menu")
            print("  " + "─" * 60)

            choice = input(f"\n{Colors.CYAN}Select option: {Colors.RESET}").strip()

            if choice == '1':
                try:
                    from reports.excel_exporter import export_menu
                    export_menu()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("Export module not found")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '2':
                try:
                    from reports.email_reports import email_reports_menu
                    email_reports_menu()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("Email reports module not found")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '3':
                try:
                    from reports.trend_analysis import trend_analysis_menu
                    trend_analysis_menu()
                except ImportError:
                    print_error("Trend analysis module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '4':
                try:
                    from reports.trend_analysis import show_week_over_week
                    show_week_over_week()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("Week-over-week module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '5':
                try:
                    from reports.call_volume import volume_analysis_menu
                    volume_analysis_menu()
                except ImportError as e:
                    print_error(f"Call Volume module not found: {e}")
                    print("\nPlease ensure the file exists at: reports/call_volume.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '6':
                try:
                    from reports.performance_over_time import performance_over_time_menu
                    performance_over_time_menu()
                except ImportError:
                    print_error("Performance over time module not found.")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '7':
                try:
                    from reports.eod_report import eod_report_menu
                    eod_report_menu()
                except ImportError as e:
                    print_error(f"EOD Report module not found: {e}")
                    print("\nPlease ensure the file exists at: reports/eod_report.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '8':
                try:
                    from reports.pdf_generator import pdf_menu
                    pdf_menu()
                except ImportError as e:
                    print_error(f"PDF Generator module not found: {e}")
                    print("\nPlease ensure the file exists at: reports/pdf_generator.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '9':
                try:
                    from reports.email_reports import scheduled_reports_menu
                    scheduled_reports_menu()
                    input("\nPress Enter to continue...")
                except ImportError:
                    print_error("Scheduled reports module not found")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    input("\nPress Enter to continue...")

            elif choice == '10':
                try:
                    from reports.chart_generator import charts_menu
                    charts_menu()
                except ImportError as e:
                    print_error(f"Chart generator module not found: {e}")
                    print("\n📊 To enable charts, install required packages:")
                    print("   pip install matplotlib pandas")
                    print("\nOr use the simple charts menu option below.")

                    simple_choice = input("\nOpen simple charts menu? (y/n): ").strip().lower()
                    if simple_choice == 'y':
                        self.simple_charts_menu()
                except Exception as e:
                    print_error(f"Error generating charts: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '11':
                try:
                    from reports.email_channel_reports import email_channel_reports_menu
                    email_channel_reports_menu()
                except ImportError as e:
                    print_error(f"Email Channel Reports module not found: {e}")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")

            elif choice == '0':
                break
            else:
                print_error("Invalid option")
                input("\nPress Enter to continue...")

    def simple_charts_menu(self):
        """Simple charts menu when chart_generator module is not available"""
        while True:
            print_header("📊 SIMPLE CHART GENERATOR", Colors.CYAN)
            print("  1. 📈 Daily Trend Chart")
            print("  2. 🔥 Hourly Heatmap")
            print("  3. 📁 Open Charts Folder")
            print("  0. 🔙 Back")
            print("-" * 60)

            chart_choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

            if chart_choice == '1':
                try:
                    try:
                        from reports.chart_generator import generate_daily_trend_chart
                    except ImportError:
                        print_error("Chart generator module not found")
                        print("\nPlease install matplotlib: pip install matplotlib pandas")
                        input("\nPress Enter to continue...")
                        continue

                    campaign = input("Enter campaign name (or press Enter for all): ").strip()
                    days = input("Days to analyze (default 30): ").strip()
                    days = int(days) if days.isdigit() else 30

                    print(f"\n📊 Generating daily trend chart...")
                    filename = generate_daily_trend_chart(campaign if campaign else None, days)

                    if filename:
                        print_success(f"✅ Chart saved to: {filename}")
                        open_file = input("\nOpen chart file? (y/n): ").strip().lower()
                        if open_file == 'y' and os.path.exists(filename):
                            os.startfile(filename)
                    else:
                        print_error("Failed to generate chart")

                except Exception as e:
                    print_error(f"Error: {str(e)}")

                input("\nPress Enter to continue...")

            elif chart_choice == '2':
                try:
                    try:
                        from reports.chart_generator import generate_hourly_heatmap
                    except ImportError:
                        print_error("Chart generator module not found")
                        print("\nPlease install matplotlib: pip install matplotlib pandas")
                        input("\nPress Enter to continue...")
                        continue

                    campaign = input("Enter campaign name (or press Enter for all): ").strip()
                    days = input("Days to analyze (default 30): ").strip()
                    days = int(days) if days.isdigit() else 30

                    print(f"\n🔥 Generating hourly heatmap...")
                    filename = generate_hourly_heatmap(campaign if campaign else None, days)

                    if filename:
                        print_success(f"✅ Heatmap saved to: {filename}")
                        open_file = input("\nOpen heatmap file? (y/n): ").strip().lower()
                        if open_file == 'y' and os.path.exists(filename):
                            os.startfile(filename)
                    else:
                        print_error("Failed to generate heatmap")

                except Exception as e:
                    print_error(f"Error: {str(e)}")

                input("\nPress Enter to continue...")

            elif chart_choice == '3':
                try:
                    try:
                        from reports.chart_generator import ensure_charts_dir
                        charts_dir = ensure_charts_dir()
                    except ImportError:
                        charts_dir = Path(__file__).parent / "charts"
                        charts_dir.mkdir(exist_ok=True)

                    print(f"\n📁 Opening: {charts_dir}")
                    try:
                        os.startfile(charts_dir)
                        print_success("✅ Folder opened")
                    except Exception:
                        print_error("Could not open folder")
                except Exception as e:
                    print_error(f"Error: {str(e)}")

                input("\nPress Enter to continue...")

            elif chart_choice == '0':
                break
            else:
                print_error("Invalid option")
                input("\nPress Enter to continue...")

    # =========================================================================
    # SETTINGS
    # =========================================================================

    def settings_menu(self):
        """Settings Submenu with clean numbering"""
        while True:
            print_persistent_header("SETTINGS")
            print("  " + "─" * 60)
            print("   1. Language Selection")
            print("   2. Email Configuration")
            print("   3. Notification Settings")
            print("   4. Export Directory")
            print("   5. User Preferences")
            print("   6. Campaign Operating Hours")
            print("   7. Save Configuration")
            print("   8. 🔧 Reconfigure Database Connection")
            print("   0. Back to Main Menu")
            print("  " + "─" * 60)

            choice = input(f"\n{Colors.CYAN}Select option: {Colors.RESET}").strip()

            if choice == '1':
                self.change_language()
            elif choice == '2':
                self.email_config_menu()
            elif choice == '3':
                self.notification_settings_menu()
            elif choice == '4':
                self.set_export_directory()
            elif choice == '5':
                self.user_preferences_menu()
            elif choice == '6':
                try:
                    from config.campaign_hours import manage_campaign_hours_menu
                    manage_campaign_hours_menu()
                except ImportError as e:
                    print_error(f"Campaign Hours module not found: {e}")
                    print("\nPlease ensure the file exists at: config/campaign_hours.py")
                    input("\nPress Enter to continue...")
                except Exception as e:
                    print_error(f"Error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    input("\nPress Enter to continue...")
            elif choice == '7':
                save_config(self.config)
                print_success("Configuration saved!")
                input("\nPress Enter to continue...")
            elif choice == '8':
                self.reconfigure_connection()
            elif choice == '0':
                break
            else:
                print_error("Invalid option")
                input("\nPress Enter to continue...")

    def reconfigure_connection(self):
        """Allow user to reconfigure database connection"""
        print_header(" RECONFIGURE DATABASE CONNECTION ", Colors.YELLOW)
        from core.connection import ConnectionManager
        conn_manager = ConnectionManager()
        if conn_manager.prompt_for_connection():
            print_success("Connection reconfigured successfully!")
            global db
            from core.database import Database
            db = Database()
        else:
            print_error("Failed to reconfigure connection")
        input("\nPress Enter to continue...")

    def email_config_menu(self):
        """Email configuration menu"""
        print_header(" EMAIL CONFIGURATION ", Colors.YELLOW)
        print("  " + "─" * 50)
        print("   1. Configure SMTP Settings")
        print("   2. Test Email Configuration")
        print("   3. Manage Recipients")
        print("   0. Back")
        print("  " + "─" * 50)

        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

        if choice == '1':
            print("\nSMTP Configuration - Coming Soon!")
        elif choice == '2':
            print("\nTest Email - Coming Soon!")
        elif choice == '3':
            print("\nManage Recipients - Coming Soon!")
        input("\nPress Enter to continue...")

    def notification_settings_menu(self):
        """Notification settings menu"""
        print_header(" NOTIFICATION SETTINGS ", Colors.YELLOW)
        print("  " + "─" * 50)
        print("   1. Slack Integration")
        print("   2. Microsoft Teams Integration")
        print("   3. Desktop Notifications")
        print("   0. Back")
        print("  " + "─" * 50)

        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

        if choice == '1':
            print("\nSlack Integration - Coming Soon!")
        elif choice == '2':
            print("\nTeams Integration - Coming Soon!")
        elif choice == '3':
            print("\nDesktop Notifications - Coming Soon!")
        input("\nPress Enter to continue...")

    def user_preferences_menu(self):
        """User preferences menu"""
        print_header(" USER PREFERENCES ", Colors.YELLOW)
        print("  " + "─" * 50)
        print("   1. Default Report Period")
        print("   2. Favorite Campaigns")
        print("   3. Dashboard Layout")
        print("   0. Back")
        print("  " + "─" * 50)

        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

        if choice == '1':
            print("\nDefault Report Period - Coming Soon!")
        elif choice == '2':
            print("\nFavorite Campaigns - Coming Soon!")
        elif choice == '3':
            print("\nDashboard Layout - Coming Soon!")
        input("\nPress Enter to continue...")

    def change_language(self):
        """Change system language with clean numbering"""
        print_persistent_header("LANGUAGE SELECTION")
        print("  " + "─" * 40)
        print("   1. English")
        print("   2. Spanish (Español)")
        print("   3. French (Français)")
        print("   4. German (Deutsch)")
        print("   5. Arabic (العربية)")
        print("   6. Chinese (中文)")
        print("  " + "─" * 40)
        print("   0. Back")

        choice = input(f"\n{Colors.CYAN}Select language: {Colors.RESET}").strip()

        languages = {
            '1': 'en',
            '2': 'es',
            '3': 'fr',
            '4': 'de',
            '5': 'ar',
            '6': 'zh'
        }

        language_names = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'ar': 'Arabic',
            'zh': 'Chinese'
        }

        if choice == '0':
            return
        elif choice in languages:
            self.config['language'] = languages[choice]
            self.language = languages[choice]
            lang_name = language_names[self.language]
            print_success(f"Language changed to {lang_name}")

            welcome_messages = {
                'ar': "  مرحباً بك في نظام عمليات ألتريا",
                'zh': "  欢迎使用阿尔特里亚运营系统",
                'en': "  Welcome to Altria Operations System",
                'es': "  Bienvenido al Sistema de Operaciones Altria",
                'fr': "  Bienvenue sur le Système d'Opérations Altria",
                'de': "  Willkommen beim Altria Betriebssystem"
            }
            print_color(welcome_messages.get(self.language, welcome_messages['en']), Colors.CYAN)
        else:
            print_error("Invalid choice")

        input("\nPress Enter to continue...")

    def set_export_directory(self):
        """Set export directory"""
        print_persistent_header("EXPORT DIRECTORY")
        print("  " + "─" * 40)
        current = self.config.get('export_dir', 'data/exports/')
        print(f"  Current: {current}")
        new_dir = input("  Enter new export directory: ").strip()
        if new_dir:
            if new_dir.startswith('~'):
                new_dir = str(Path.home() / new_dir[1:])
            self.config['export_dir'] = new_dir
            save_config(self.config)
            print_success("Export directory updated!")
        input("\nPress Enter to continue...")

    # =========================================================================
    # HELP SYSTEM
    # =========================================================================

    def help_menu(self):
        """Comprehensive help menu with search - Updated with Quality Scoring Help"""
        while True:
            print_persistent_header("📚 HELP & DOCUMENTATION")
            print("  " + "─" * 60)
            print("   1. 📖 Browse by Category")
            print("   2. 🔍 Search Help")
            print("   3. ⌨️ Keyboard Shortcuts")
            print("   4. 📞 Support Information")
            print("   5. 🎯 Quality Scoring Help")
            print("   6. ℹ️ About")
            print("   0. Back to Main Menu")
            print("  " + "─" * 60)

            choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()

            if choice == '1':
                self.browse_help_categories()
            elif choice == '2':
                self.help_search()
            elif choice == '3':
                self.show_keyboard_shortcuts()
            elif choice == '4':
                self.show_support_info()
            elif choice == '5':
                self.show_quality_help()
            elif choice == '6':
                self.show_about()
            elif choice == '0':
                break
            else:
                print_error("Invalid choice")
                input("\nPress Enter to continue...")

    def show_keyboard_shortcuts(self):
        """Display keyboard shortcuts"""
        print_header("⌨️ KEYBOARD SHORTCUTS", Colors.MAGENTA)

        shortcuts = {
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
        }

        print("\n📋 Available Keyboard Shortcuts:")
        print("=" * 70)
        print(f"{'Shortcut':<15} {'Description':<50}")
        print("-" * 70)

        for key, desc in sorted(shortcuts.items()):
            if key in ['Ctrl+C', 'Enter']:
                print(f"  {Colors.YELLOW}{key:<15}{Colors.RESET} {desc}")
            elif key.isdigit() or '-' in key:
                print(f"  {Colors.CYAN}{key:<15}{Colors.RESET} {desc}")
            else:
                print(f"  {Colors.GREEN}{key:<15}{Colors.RESET} {desc}")

        print("=" * 70)
        print("\n💡 Tips:")
        print("  • Shortcuts work in most menus and views")
        print("  • Press 'h' at any time to return to help")
        print("  • Use numbers to navigate menus quickly")

        input("\nPress Enter to continue...")

    def help_search(self):
        """Interactive help search"""
        try:
            from utils.help_system import search_help, display_search_results, get_section_details, get_subsection_details
        except ImportError as e:
            print_error(f"Help search module not found: {e}")
            print("\nUsing basic search instead...")
            self.basic_help_search()
            return

        print_header("🔍 SEARCH HELP", Colors.CYAN)
        print("  " + "─" * 60)
        print("\n💡 Tip: Try searching for: report, agent, campaign, export, pdf, alert, qc, quality, schedule, forecast, chart, sop, compliance, did")

        while True:
            print("\nEnter search term or 'q' to quit:")
            search_term = input(f"{Colors.CYAN}> {Colors.RESET}").strip()

            if not search_term:
                continue

            if search_term.lower() == 'q':
                break

            print(f"\n📊 Searching for: '{search_term}'")
            print("  " + "─" * 60)

            results = search_help(search_term)

            if results and display_search_results(results, search_term):
                choice = input(f"\n{Colors.CYAN}Enter number or press Enter to continue: {Colors.RESET}").strip()

                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(results[:20]):
                        result = results[idx]

                        if len(result) == 4:
                            rtype, title, desc, section = result
                        elif len(result) == 3:
                            rtype, title, desc = result
                            section = None
                        else:
                            print_error("Invalid result format")
                            continue

                        if rtype.startswith('section'):
                            self.show_help_section(title)
                        elif rtype.startswith('subsection') or rtype == 'tip':
                            if section:
                                self.show_help_subsection(section, title)
                            else:
                                print_error("Cannot find section for this result")
                        elif rtype == 'shortcut':
                            self.show_shortcut_details(title, desc)
            else:
                print("\nNo results found. Try a different search term.")

    def basic_help_search(self):
        """Basic fallback search when module not available"""
        print_header("🔍 BASIC SEARCH", Colors.YELLOW)
        print("\nHelp search module not available.")
        print("\nPlease try:")
        print("  1. Browse by category (option 1)")
        print("  2. Check keyboard shortcuts (option 3)")
        print("  3. Contact support (option 4)")
        input("\nPress Enter to continue...")

    def browse_help_categories(self):
        """Browse help by category"""
        try:
            from utils.help_system import HELP_CONTENT
        except ImportError:
            print_error("Help content not available")
            print("\nPlease use Keyboard Shortcuts or Support Information instead.")
            input("\nPress Enter to continue...")
            return

        categories = list(HELP_CONTENT.keys())

        while True:
            print_header("📖 HELP CATEGORIES", Colors.CYAN)

            for i, category in enumerate(categories, 1):
                print(f"  {i:2d}. {category}")

            print(f"\n  0. Back")
            print("-" * 50)

            choice = input(f"\n{Colors.CYAN}Choose category: {Colors.RESET}").strip()

            if choice == '0':
                break
            if choice.isdigit() and 1 <= int(choice) <= len(categories):
                self.show_help_section(categories[int(choice)-1])
            else:
                print_error("Invalid choice")

    def show_help_section(self, section_name):
        """Show details for a help section"""
        try:
            from utils.help_system import get_section_details
        except ImportError:
            print_error("Help module not available")
            return

        section = get_section_details(section_name)
        if not section:
            print_error(f"Section '{section_name}' not found")
            return

        print_header(f"📖 {section_name}", Colors.BLUE)
        print(f"\n{section['description']}")

        if 'subsections' in section:
            print(f"\n📋 Features in this section:")
            for sub_name, sub_data in section['subsections'].items():
                print(f"\n  • {sub_name}")
                print(f"    {sub_data['description']}")
                if 'tips' in sub_data:
                    print(f"    💡 {sub_data['tips']}")

        input("\nPress Enter to continue...")

    def show_help_subsection(self, section_name, subsection_name):
        """Show details for a help subsection"""
        try:
            from utils.help_system import get_subsection_details
        except ImportError:
            print_error("Help module not available")
            return

        subsection = get_subsection_details(section_name, subsection_name)
        if not subsection:
            print_error(f"Subsection '{subsection_name}' not found")
            return

        print_header(f"📘 {subsection_name}", Colors.GREEN)
        print(f"\n{subsection['description']}")

        if 'tips' in subsection:
            print(f"\n💡 Tips:")
            if isinstance(subsection['tips'], str):
                for tip in subsection['tips'].split('|'):
                    print(f"  • {tip.strip()}")
            else:
                print(f"  • {subsection['tips']}")

        input("\nPress Enter to continue...")

    def show_shortcut_details(self, shortcut, description):
        """Show details for a keyboard shortcut"""
        print_header(f"⌨️ KEYBOARD SHORTCUT: {shortcut}", Colors.MAGENTA)
        print(f"\n{description}")
        print("\nThis shortcut can be used in various menus throughout the system.")
        input("\nPress Enter to continue...")

    def show_quality_help(self):
        """Show help specifically for Quality Scoring"""
        print_header("📚 QUALITY SCORING HELP", Colors.CYAN)
        print("""
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                   CALL QUALITY SCORING - QUICK HELP                    │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  1. QUALITY DASHBOARD                                                  │
    │     Shows overall statistics: total evaluations, average scores,       │
    │     score distribution (Excellent/Good/Needs Improvement)              │
    │                                                                        │
    │  2. AGENT QUALITY REPORT                                               │
    │     Select an agent to see their performance history, trends,          │
    │     and detailed breakdown of scores by checkpoint                     │
    │                                                                        │
    │  3. TOP PERFORMERS                                                     │
    │     Leaderboard of best-performing agents with:                        │
    │     - Average score                                                    │
    │     - Score stability (consistency)                                    │
    │     - Number of evaluations                                            │
    │                                                                        │
    │  4. COACHING OPPORTUNITIES                                             │
    │     Identifies agents with average scores below 70%, with:             │
    │     - Priority levels (IMMEDIATE/URGENT/SCHEDULED)                     │
    │     - Score range                                                      │
    │     - Recommended actions                                              │
    │                                                                        │
    │  5. VICIdial QC DASHBOARD                                              │
    │     Link to VICIdial's native QC interface                             │
    │                                                                        │
    │  6. SOP COMPLIANCE ANALYSIS                                            │
    │     Shows average scores for all 9 SOP checkpoints:                    │
    │     - Green: Good (≥80%)                                               │
    │     - Yellow: Needs Review (60-79%)                                    │
    │     - Red: Needs Training (<60%)                                       │
    │                                                                        │
    │  7. ADD QC EVALUATION                                                  │
    │     Manual evaluation entry for calls (alternative to AI)              │
    │                                                                        │
    │  8. AI ASSISTANT (Auto-Score)                                          │
    │     ✨ MAIN FEATURE ✨                                                  │
    │     - Select campaign, date range, and call                            │
    │     - AI transcribes the call using Whisper                            │
    │     - Suggests scores for all 9 checkpoints                            │
    │     - Shows confidence level (0-100%)                                  │
    │     - QA can review, edit, and save                                    │
    │     - Generates professional PDF report                                │
    │                                                                        │
    │  9. AI vs QA CALIBRATION REPORT                                        │
    │     Compares AI-suggested scores with QA final scores:                 │
    │     - Green: Well-aligned (diff <5%)                                   │
    │     - Yellow: Monitor (diff 5-10%)                                     │
    │     - Red: Needs calibration (diff >10%)                               │
    │                                                                        │
    │ 10. VIEW HISTORICAL REPORTS                                            │
    │     Browse past QC evaluations with date and agent filters             │
    │                                                                        │
    │ 11. CONFIGURE QUALITY SETTINGS                                         │
    │     Adjust thresholds, score weights, and notification settings        │
    │                                                                        │
    │ 12. CLIENT QA PACKAGE                                                  │
    │     📋 Generate professional QA reports for clients:                   │
    │     - Comprehensive PDF report with executive summary                  │
    │     - 9 SOP checkpoint analysis                                        │
    │     - Agent performance heatmap                                        │
    │     - Trends over time charts                                          │
    │     - Top performers and coaching lists                                │
    │     - Professional formatting for client delivery                      │
    │                                                                        │
    └─────────────────────────────────────────────────────────────────────────┘

    💡 TIPS:
    • Use AI Assistant (Option 8) for fast, consistent evaluations
    • QA should review and adjust AI scores for calibration
    • Run Calibration Report (Option 9) weekly to monitor AI accuracy
    • Use Coaching Opportunities (Option 4) to identify training needs
    • View Historical Reports (Option 10) to review past evaluations
    • Use Client QA Package (Option 12) to generate client-ready reports

    🔧 COMMANDS:
    • [N] Next page - in call lists
    • [P] Previous page - in call lists
    • [0] Cancel / Back
    • Ctrl+C - Exit application
    """)
        input("\nPress Enter to continue...")

    def show_support_info(self):
        """Display support information with QC features"""
        print_header("📞 SUPPORT INFORMATION", Colors.CYAN)
        print(f"""
    Technical Support
    =================

    Email: support@altriaops.com
    Phone: (555) 123-4567
    Hours: 24/7 - 365 days

    Online Resources:
    • Documentation: http://docs.altriaops.com
    • Knowledge Base: http://kb.altriaops.com
    • Community Forum: http://forum.altriaops.com

    System Information:
    • Version: {self.version}
    • Last Updated: {self.release_date}
    • Database: MySQL/MariaDB
    • VICIdial Compatible: Yes

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                      QC SYSTEM STATUS                                  │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  • QC Scorecard: SOP_COMP (9 checkpoints, 100 points)                 │
    │  • AI Model: Whisper base (CPU)                                       │
    │  • Active Evaluations: Check with Option 1                            │
    │  • AI Confidence Range: 70-85% (well-calibrated)                      │
    │  • PDF Reports: Generated automatically with each evaluation          │
    │  • Audit Trail: Full tracking of AI and QA scores                     │
    │                                                                        │
    └─────────────────────────────────────────────────────────────────────────┘

    Quick Reference:
    • Option 1 - View overall quality stats
    • Option 8 - Run AI Assistant to auto-score calls
    • Option 6 - View SOP compliance by checkpoint
    • Option 9 - Check AI vs QA calibration
    • Option 10 - Browse historical reports
    • Option 11 - Configure thresholds
    • Option 12 - Generate Client QA Package reports

    For urgent issues, please call the support line.
        """)
        input("\nPress Enter to continue...")

    def show_about(self):
        """Show about information with all features"""
        print_header("ℹ️ ABOUT ALTRIA OPS", Colors.CYAN)
        print(f"""
    Altria Operations System
    Call Center Analytics Platform
    Version {self.version} (Released: {self.release_date})

    © 2026 Altria Technologies
    All rights reserved

    This system provides real-time analytics and monitoring for call center operations.

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                      🎯 QUALITY SCORING SYSTEM                         │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  1. Quality Dashboard      - Overall stats & score distribution       │
    │  2. Agent Quality Report   - Detailed agent performance with trends   │
    │  3. Top Performers         - Leaderboard with stability scores        │
    │  4. Coaching Opportunities - Identify agents needing training         │
    │  5. VICIdial QC Dashboard  - Link to VICIdial QC interface            │
    │  6. SOP Compliance         - Checkpoint analysis (9 standards)        │
    │  7. Add QC Evaluation      - Manual evaluation entry                  │
    │  8. AI Assistant           - Auto-score calls using Whisper AI        │
    │  9. Calibration Report     - Compare AI vs QA scores                  │
    │ 10. View Historical Reports - Browse past QC evaluations              │
    │ 11. Configure Settings     - Adjust thresholds & weights              │
    │ 12. Client QA Package      - Generate client-ready QA reports         │
    │                                                                        │
    └─────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         🤖 AI ASSISTANT FEATURES                        │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  • Automatic transcription using OpenAI Whisper                        │
    │  • AI-suggested scores for 9 SOP checkpoints                           │
    │  • Confidence scoring (0-100%)                                         │
    │  • Full audit trail (stores both AI and final scores)                  │
    │  • PDF report generation with professional formatting                  │
    │  • Duplicate prevention & evaluation archiving                         │
    │  • Agent selection by campaign and date range                          │
    │  • Pagination for large call lists (50 per page)                       │
    │                                                                        │
    └─────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                         📞 DID INSPECTOR                               │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                                        │
    │  • View all DIDs with status (Active/Inactive)                        │
    │  • Identify problematic DIDs (inactive or low call volume)            │
    │  • Search DIDs by number or description                                │
    │  • Group DIDs by inbound group                                         │
    │  • Call volume analysis for each DID (last 30 days)                   │
    │                                                                        │
    └─────────────────────────────────────────────────────────────────────────┘

    Built with Python, PyInstaller, OpenAI Whisper, and VICIdial
        """)
        input("\nPress Enter to continue...")

    # =========================================================================
    # DID INSPECTOR
    # =========================================================================

    def did_inspector_menu(self):
        """DID Inspector Menu"""
        try:
            from dids.did_inspector import did_inspector_menu
            did_inspector_menu()
        except ImportError as e:
            print_error(f"DID Inspector module not found: {e}")
            print("\nPlease make sure the file exists at: dids/did_inspector.py")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error loading DID Inspector: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # EMAIL AGENT MAPPING WIZARD
    # =========================================================================

    def email_mapping_menu(self):
        """Launch the pinktools ↔ VICIdial agent mapping wizard."""
        try:
            from core.agent_mapping_wizard import agent_mapping_wizard
            agent_mapping_wizard()
        except ImportError as e:
            print_error(f"Mapping wizard module not found: {e}")
            input("\nPress Enter to continue...")
        except Exception as e:
            print_error(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to continue...")

    # =========================================================================
    # EXIT SYSTEM
    # =========================================================================

    def exit_system(self):
        """Exit the system with localized message"""
        exit_messages = {
            'ar': ("\nشكراً لاستخدامك نظام عمليات ألتريا!", "مع السلامة!\n"),
            'zh': ("\n感谢使用阿尔特里亚运营系统!", "再见!\n"),
            'es': ("\n¡Gracias por usar Altria Operations System!", "¡Adiós!\n"),
            'fr': ("\nMerci d'avoir utilisé le Système d'Opérations Altria!", "Au revoir!\n"),
            'de': ("\nVielen Dank für die Nutzung des Altria Betriebssystems!", "Auf Wiedersehen!\n"),
            'en': ("\nThank you for using Altria Operations System!", "Goodbye!\n")
        }

        msg1, msg2 = exit_messages.get(self.language, exit_messages['en'])
        print_color(msg1, Colors.GREEN)
        print_color(msg2, Colors.CYAN)
        sys.exit(0)

    def run(self):
        """Main application loop"""
        while True:
            self.clear_screen()
            self.print_banner()
            menu_options = self.print_menu()

            choice = input(f"\n{Colors.CYAN}Enter your choice: {Colors.RESET}").strip()

            if choice in menu_options:
                menu_options[choice][1]()
            else:
                print_error("Invalid option")
                input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        app = AltriaOps()
        app.run()
    except KeyboardInterrupt:
        if 'app' in locals() and hasattr(app, 'language'):
            exit_messages = {
                'ar': "\n\nمع السلامة!",
                'zh': "\n\n再见!",
                'es': "\n\n¡Adiós!",
                'fr': "\n\nAu revoir!",
                'de': "\n\nAuf Wiedersehen!",
                'en': "\n\nGoodbye!"
            }
            print_color(exit_messages.get(app.language, exit_messages['en']), Colors.CYAN)
        else:
            print_color("\n\nGoodbye!", Colors.CYAN)
        sys.exit(0)
    except Exception as e:
        print_error(f"Fatal Error: {str(e)}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)