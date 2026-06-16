#!/usr/bin/env python3
# =============================================================================
# File:         pdf_generator.py
# Version:      2.1.0
# Date:         2026-03-07
# Description:  PDF Report Generator with Ghost Call Support
# Location:     D:/Altria_Ops/reports/pdf_generator.py
# Updates:      Fixed exports directory path for PyInstaller
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info
from utils.formatter import sec_to_hms, format_datetime
import os
from pathlib import Path

# Try to import from eod_report for timezone functions
try:
    from reports.eod_report import get_timezone_info, print_timezone_banner, generate_eod_report
except ImportError as e:
    print_warning(f"EOD report module not available: {e}")
    
    # Fallback timezone function if eod_report not available
    def get_timezone_info():
        """Fallback timezone info"""
        from datetime import datetime
        return {
            'server': datetime.now(),
            'est': datetime.now(),
            'pst': datetime.now(),
            'est_date': datetime.now().date()
        }
    
    def print_timezone_banner():
        """Fallback banner"""
        pass

# =============================================================================
# PDF Generation Functions
# =============================================================================

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import reportlab
        return True
    except ImportError:
        print_error("PDF generation requires reportlab. Install with:")
        print("  pip install reportlab")
        return False

def ensure_exports_dir():
    """Ensure exports directory exists - FIXED for PyInstaller"""
    import sys
    import os
    from pathlib import Path
    
    try:
        # Check if running as PyInstaller bundle
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            # Use the directory where the executable is located
            base_dir = Path(os.path.dirname(sys.executable))
            exports_dir = base_dir / 'exports' / 'reports'
            exports_dir.mkdir(parents=True, exist_ok=True)
            return exports_dir
        else:
            # Running as script
            exports_dir = Path(__file__).parent / 'exports'
            exports_dir.mkdir(exist_ok=True)
            return exports_dir
            
    except Exception as e:
        print_warning(f"Could not create standard exports dir: {e}")
        
        # Ultimate fallback - user's temp directory
        import tempfile
        fallback_dir = Path(tempfile.gettempdir()) / 'Altria_Exports'
        fallback_dir.mkdir(exist_ok=True)
        return fallback_dir

def get_selected_campaigns():
    """Get list of campaigns to include in report using unified search style"""
    try:
        query = """
        SELECT DISTINCT campaign_id
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        ORDER BY campaign_id
        """
        campaigns = db.execute_query(query)
        campaign_list = [c['campaign_id'] for c in campaigns] if campaigns else []
        
        if not campaign_list:
            print_warning("No campaigns found with recent activity")
            return None
        
        print("\n📋 Available Campaigns:")
        print("-" * 80)
        
        # Display in columns
        col_width = 25
        cols = 3
        
        for i, camp in enumerate(campaign_list, 1):
            display = f"{i:3}. {camp}"
            if len(display) < col_width:
                display = display.ljust(col_width)
            print(display, end="")
            if i % cols == 0:
                print()
        
        if len(campaign_list) % cols != 0:
            print()
        
        print("-" * 80)
        print("Enter campaign numbers (comma-separated) or 'all':")
        choice = input("> ").strip().lower()
        
        if choice == 'all' or choice == '':
            return campaign_list
        else:
            selected = []
            for part in choice.split(','):
                part = part.strip()
                if '-' in part:
                    try:
                        start, end = map(int, part.split('-'))
                        for i in range(start, min(end, len(campaign_list)) + 1):
                            selected.append(campaign_list[i-1])
                    except:
                        pass
                elif part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(campaign_list):
                        selected.append(campaign_list[idx])
            return selected if selected else campaign_list
            
    except Exception as e:
        print_error(f"Error loading campaigns: {e}")
        return None

def get_selected_agents():
    """Get list of agents to include in report"""
    try:
        query = """
        SELECT user, full_name
        FROM vicidial_users
        WHERE active = 'Y'
        ORDER BY user
        LIMIT 100
        """
        agents = db.execute_query(query)
        agent_list = [a['user'] for a in agents] if agents else []
        
        if not agent_list:
            print_warning("No active agents found")
            return None
        
        print("\n📋 Available Agents:")
        print("-" * 80)
        
        # Display in columns
        col_width = 25
        cols = 3
        
        for i, agent in enumerate(agent_list, 1):
            display = f"{i:3}. {agent}"
            if len(display) < col_width:
                display = display.ljust(col_width)
            print(display, end="")
            if i % cols == 0:
                print()
        
        if len(agent_list) % cols != 0:
            print()
        
        print("-" * 80)
        print("Enter agent numbers (comma-separated) or 'all':")
        choice = input("> ").strip().lower()
        
        if choice == 'all' or choice == '':
            return agent_list
        else:
            selected = []
            for part in choice.split(','):
                part = part.strip()
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(agent_list):
                        selected.append(agent_list[idx])
            return selected if selected else agent_list
            
    except Exception as e:
        print_error(f"Error loading agents: {e}")
        return None

def generate_eod_pdf():
    """Generate PDF for EOD report with ghost call support"""
    if not check_dependencies():
        input("\nPress Enter to continue...")
        return
    
    import reportlab
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    
    print_header("📄 EOD REPORT TO PDF", Colors.CYAN)
    
    # Get date
    print("\nSelect date for EOD report:")
    date_input = input("Enter date (YYYY-MM-DD) or Enter for yesterday: ").strip()
    
    try:
        if date_input:
            target_date = datetime.strptime(date_input, '%Y-%m-%d').date()
        else:
            # Get yesterday from timezone info
            tz = get_timezone_info()
            target_date = tz['est_date'] - timedelta(days=1)
            print(f"Using yesterday: {target_date}")
    except ValueError:
        print_error("Invalid date format. Using yesterday.")
        tz = get_timezone_info()
        target_date = tz['est_date'] - timedelta(days=1)
    
    # Get campaigns
    campaigns = get_selected_campaigns()
    if not campaigns:
        return
    
    # Generate report data using updated eod_report function
    print(f"\n📊 Generating report for {target_date}...")
    
    try:
        # Try to use eod_report's generate function
        report_data = generate_eod_report(target_date, campaigns)
    except Exception as e:
        print_error(f"Could not generate report data: {e}")
        import traceback
        traceback.print_exc()
        return
    
    if not report_data:
        print_warning("No data available for selected date")
        input("\nPress Enter to continue...")
        return
    
    # Create PDF
    exports_dir = ensure_exports_dir()
    filename = exports_dir / f"eod_report_{target_date}.pdf"
    
    doc = SimpleDocTemplate(
        str(filename),
        pagesize=landscape(letter),
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )
    
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # Center alignment
        textColor=colors.HexColor('#2c3e50')
    )
    story.append(Paragraph(f"End of Day Report: {target_date}", title_style))
    story.append(Spacer(1, 12))
    
    # Timezone info
    tz_info = get_timezone_info()
    time_text = f"Generated: {tz_info['server'].strftime('%Y-%m-%d %H:%M:%S')} (Server) | EST: {tz_info['est'].strftime('%Y-%m-%d %H:%M:%S')}"
    story.append(Paragraph(time_text, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Ghost Call Summary
    story.append(Paragraph("Ghost Call Summary", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    ghost_data = [
        ["Metric", "Value"],
        ["Total Calls", str(report_data['total_calls'])],
        ["Valid Calls", str(report_data['valid_calls'])],
        ["Ghost Calls", f"{report_data['ghost_calls']} ({report_data['ghost_pct']:.1f}%)"],
    ]
    
    ghost_table = Table(ghost_data, colWidths=[200, 200])
    ghost_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#95a5a6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(ghost_table)
    story.append(Spacer(1, 20))
    
    # Overall Statistics
    story.append(Paragraph("Overall Statistics (Valid Calls Only)", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    # Color code metrics
    ans_color = colors.HexColor('#27ae60') if report_data['ans_rate'] >= 80 else colors.HexColor('#e67e22') if report_data['ans_rate'] >= 60 else colors.HexColor('#e74c3c')
    abd_color = colors.HexColor('#27ae60') if report_data['abd_rate'] <= 5 else colors.HexColor('#e67e22') if report_data['abd_rate'] <= 10 else colors.HexColor('#e74c3c')
    sl_color = colors.HexColor('#27ae60') if report_data['sl_pct'] >= 80 else colors.HexColor('#e67e22') if report_data['sl_pct'] >= 60 else colors.HexColor('#e74c3c')
    
    data = [
        ["Metric", "Value"],
        ["Valid Calls", str(report_data['valid_calls'])],
        ["Answered", f"{report_data['answered']} ({report_data['ans_rate']:.1f}%)"],
        ["Abandoned", f"{report_data['abandoned']} ({report_data['abd_rate']:.1f}%)"],
        ["Service Level (≤20s)", f"{report_data['sl_pct']:.1f}%"],
        ["Avg Talk Time", sec_to_hms(report_data['avg_talk'])],
        ["Avg Queue Time", f"{report_data['avg_queue']:.0f}s"],
        ["Total Talk Time", sec_to_hms(report_data['total_talk_sec'])],
    ]
    
    table = Table(data, colWidths=[200, 300])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        # Color code specific rows
        ('TEXTCOLOR', (1, 2), (1, 2), ans_color),  # Answer rate
        ('TEXTCOLOR', (1, 3), (1, 3), abd_color),  # Abandon rate
        ('TEXTCOLOR', (1, 4), (1, 4), sl_color),   # Service level
    ]))
    story.append(table)
    story.append(Spacer(1, 20))
    
    # Campaign Breakdown
    if report_data['by_campaign']:
        story.append(Paragraph("Campaign Breakdown", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        camp_data = [["Campaign", "Total", "Valid", "Ghost", "Ghost%", "Ans%", "Abd%", "SL%"]]
        for camp in report_data['by_campaign'][:15]:  # Limit to 15 campaigns for readability
            # Color code ghost rate
            ghost_pct = camp['ghost_pct']
            if ghost_pct > 20:
                ghost_color = colors.red
            elif ghost_pct > 10:
                ghost_color = colors.orange
            else:
                ghost_color = colors.green
            
            camp_data.append([
                camp['campaign_id'],
                str(camp['calls']),
                str(camp['valid_calls']),
                str(camp['ghost_calls']),
                f"{camp['ghost_pct']:.1f}%",
                f"{camp['ans_pct']:.0f}%",
                f"{camp['abd_pct']:.0f}%",
                f"{camp.get('sl_pct', 0):.0f}%"
            ])
        
        table = Table(camp_data, colWidths=[100, 50, 50, 50, 60, 60, 60, 60])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
        ]))
        
        # Color code ghost rates
        for i, camp in enumerate(report_data['by_campaign'][:15], 1):
            ghost_pct = camp['ghost_pct']
            if ghost_pct > 20:
                table.setStyle(TableStyle([('TEXTCOLOR', (4, i), (4, i), colors.red)]))
            elif ghost_pct > 10:
                table.setStyle(TableStyle([('TEXTCOLOR', (4, i), (4, i), colors.orange)]))
            else:
                table.setStyle(TableStyle([('TEXTCOLOR', (4, i), (4, i), colors.green)]))
        
        story.append(table)
        story.append(Spacer(1, 20))
    
    # Hourly Breakdown
    if report_data['hourly']:
        story.append(Paragraph("Hourly Breakdown", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        hourly_data = [["Hour", "Total", "Valid", "Ghost", "Answered", "Ans%"]]
        for h in report_data['hourly']:
            hourly_data.append([
                f"{h['hour']:02d}:00",
                str(h['calls']),
                str(h['valid_calls'] or 0),
                str(h['ghost_calls'] or 0),
                str(h['answered'] or 0),
                f"{h['ans_pct']:.0f}%"
            ])
        
        table = Table(hourly_data, colWidths=[60, 50, 50, 50, 60, 60])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))
    
    # Top Agents
    if report_data['agents']:
        story.append(Paragraph("Top Agents (Valid Calls Only)", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        agent_data = [["Agent", "Name", "Valid", "Ghost", "Talk Time", "Avg Call"]]
        for agent in report_data['agents'][:15]:  # Top 15 agents
            ghost_pct = (agent['ghost_calls'] / (agent['valid_calls'] + agent['ghost_calls']) * 100) if (agent['valid_calls'] + agent['ghost_calls']) > 0 else 0
            agent_data.append([
                agent['user'],
                agent.get('full_name', 'Unknown')[:15],
                str(agent['valid_calls']),
                str(agent['ghost_calls']),
                sec_to_hms(agent['total_talk'] or 0),
                sec_to_hms(agent['avg_talk'] or 0)
            ])
        
        table = Table(agent_data, colWidths=[70, 100, 50, 50, 80, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
        ]))
        
        # Highlight top 3
        for i in range(1, min(4, len(agent_data))):
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f1c40f')),
                ('TEXTCOLOR', (0, i), (-1, i), colors.HexColor('#2c3e50')),
            ]))
        
        story.append(table)
    
    # Summary footer
    story.append(Spacer(1, 30))
    summary_text = f"Summary: {report_data['total_calls']} total | {report_data['ghost_calls']} ghost ({report_data['ghost_pct']:.1f}%) | {report_data['ans_rate']:.1f}% answer | {report_data['abd_rate']:.1f}% abandon"
    story.append(Paragraph(summary_text, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    print_success(f"✅ PDF generated: {filename}")
    
    # Ask if user wants to open the folder
    open_choice = input("\nOpen exports folder? (y/N): ").strip().lower()
    if open_choice == 'y':
        os.startfile(exports_dir)
    
    input("\nPress Enter to continue...")

def generate_campaign_pdf():
    """Generate PDF for campaign report"""
    print_header("📋 CAMPAIGN REPORT TO PDF", Colors.CYAN)
    print("\n🚧 Campaign PDF generation coming soon!")
    input("\nPress Enter to continue...")

def generate_agent_pdf():
    """Generate PDF for agent report"""
    print_header("👤 AGENT REPORT TO PDF", Colors.CYAN)
    print("\n🚧 Agent PDF generation coming soon!")
    input("\nPress Enter to continue...")

def open_exports_folder():
    """Open the exports folder"""
    exports_dir = ensure_exports_dir()
    print_header("📁 EXPORTS FOLDER", Colors.CYAN)
    print(f"\nOpening: {exports_dir}")
    
    try:
        os.startfile(exports_dir)
        print_success("✅ Folder opened")
    except Exception as e:
        print_error(f"Could not open folder: {e}")
    
    input("\nPress Enter to continue...")

# =============================================================================
# Main Menu
# =============================================================================

def pdf_menu():
    """Main PDF generator menu"""
    while True:
        print_header("📄 PDF REPORT GENERATOR", Colors.CYAN)
        print("  1. 📊 EOD Report to PDF")
        print("  2. 📋 Campaign Report to PDF")
        print("  3. 👤 Agent Report to PDF")
        print("  4. 📁 Open Exports Folder")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            generate_eod_pdf()
        elif choice == '2':
            generate_campaign_pdf()
        elif choice == '3':
            generate_agent_pdf()
        elif choice == '4':
            open_exports_folder()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    pdf_menu()