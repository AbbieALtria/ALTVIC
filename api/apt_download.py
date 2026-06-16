#!/usr/bin/env python3
# =============================================================================
# File:         apt_download.py
# Version:      3.0.0
# Date:         2026-03-06
# Description:  APT (Adherence & Performance Tracking) with enhanced metrics
# Update:       Added PST conversion, Agents Not Available, After Hours, Leads, Ghost Calls
# Location:     D:/Altria_Ops/api/apt_download.py
# =============================================================================

import sys
import os
import csv
import json
from datetime import datetime, timedelta, time
from pathlib import Path
from decimal import Decimal

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info
from utils.formatter import sec_to_hms, format_datetime
import pytz

# Try to import PDF libraries
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    PDF_AVAILABLE = True
    print_info("✓ ReportLab loaded successfully")
except ImportError as e:
    PDF_AVAILABLE = False
    print_warning(f"ReportLab not installed: {e}")
    print("Install with: pip install reportlab")

# =============================================================================
# Configuration
# =============================================================================

EXCLUDED_STATUSES = [
    'NA',           # Not Available
    'AFTHRS',       # After Hours
    'DROP',         # Dropped
    'QUEUE',        # In Queue
    'CLOSER',       # Closer (internal)
    'DISPO',        # Disposition
]

# Status descriptions for reporting
STATUS_DESCRIPTIONS = {
    'NA': 'Not Available',
    'AFTHRS': 'After Hours',
    'DROP': 'Dropped',
    'QUEUE': 'In Queue',
    'CLOSER': 'Closer',
    'DISPO': 'Disposition',
    'OTHER': 'Other'
}

# Timezone settings
EST_TZ = pytz.timezone('America/New_York')
PST_TZ = pytz.timezone('America/Los_Angeles')
UTC_TZ = pytz.UTC

# =============================================================================
# Helper Functions
# =============================================================================

def safe_float(value):
    """Safely convert any value to float"""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def safe_int(value):
    """Safely convert any value to int"""
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

def get_est_time():
    """Get current time in EST"""
    utc_now = datetime.utcnow().replace(tzinfo=UTC_TZ)
    return utc_now.astimezone(EST_TZ)

def get_pst_time():
    """Get current time in PST"""
    utc_now = datetime.utcnow().replace(tzinfo=UTC_TZ)
    return utc_now.astimezone(PST_TZ)

def convert_est_to_pst(est_datetime):
    """Convert EST datetime to PST"""
    if est_datetime.tzinfo is None:
        est_datetime = EST_TZ.localize(est_datetime)
    return est_datetime.astimezone(PST_TZ)

def convert_to_est(pst_datetime):
    """Convert PST datetime to EST"""
    if pst_datetime.tzinfo is None:
        pst_datetime = PST_TZ.localize(pst_datetime)
    return pst_datetime.astimezone(EST_TZ)

def format_datetime_iso(dt):
    """Format datetime to ISO string"""
    if dt.tzinfo is None:
        dt = PST_TZ.localize(dt)
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def calculate_call_time(length_sec, alt_dial_sec=0):
    """
    Calculate actual call time: length_in_sec - alt_dial
    Formula: Call Time = Length in Seconds - Alt Dial Time
    """
    length = safe_float(length_sec)
    alt = safe_float(alt_dial_sec)
    return max(0, length - alt)

# =============================================================================
# New Metrics Functions
# =============================================================================

def get_agents_not_available():
    """Get count of agents in unavailable status (PAUSE, WRAP-UP, AWAY)"""
    try:
        query = """
        SELECT COUNT(*) as count
        FROM vicidial_live_agents
        WHERE status IN ('PAUSE', 'WRAPUP', 'AWAY', 'BREAK', 'LUNCH', 'TRAINING', 'MEETING')
        """
        result = db.execute_query(query)
        return result[0]['count'] if result else 0
    except Exception as e:
        print_warning(f"Could not fetch agents not available: {e}")
        return 0

def get_inbound_after_hours(start_date, end_date, target_tz):
    """Get count of after hours calls"""
    try:
        # Convert dates to datetime range
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        
        if target_tz:
            start_dt = target_tz.localize(start_dt)
            end_dt = target_tz.localize(end_dt)
        
        start_utc = start_dt.astimezone(UTC_TZ)
        end_utc = end_dt.astimezone(UTC_TZ)
        
        query = """
        SELECT COUNT(*) as count
        FROM vicidial_closer_log
        WHERE term_reason = 'AFTHRS'
          AND call_date BETWEEN %s AND %s
        """
        result = db.execute_query(query, (start_utc, end_utc))
        return result[0]['count'] if result else 0
    except Exception as e:
        print_warning(f"Could not fetch after hours calls: {e}")
        return 0

def get_leads_to_be_called():
    """Get count of leads waiting to be called"""
    try:
        query = """
        SELECT COUNT(*) as count
        FROM vicidial_hopper
        WHERE status = 'READY'
        """
        result = db.execute_query(query)
        return result[0]['count'] if result else 0
    except Exception as e:
        # Try alternative table if hopper doesn't exist
        try:
            query2 = """
            SELECT COUNT(*) as count
            FROM vicidial_list
            WHERE status = 'NEW'
            """
            result2 = db.execute_query(query2)
            return result2[0]['count'] if result2 else 0
        except:
            return 0

def get_ghost_calls(start_date, end_date, target_tz):
    """Get count of ghost calls (0 seconds, no agent)"""
    try:
        # Convert dates to datetime range
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        
        if target_tz:
            start_dt = target_tz.localize(start_dt)
            end_dt = target_tz.localize(end_dt)
        
        start_utc = start_dt.astimezone(UTC_TZ)
        end_utc = end_dt.astimezone(UTC_TZ)
        
        query = """
        SELECT COUNT(*) as count
        FROM vicidial_closer_log c
        LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
        WHERE c.length_in_sec = 0
          AND a.uniqueid IS NULL
          AND c.call_date BETWEEN %s AND %s
        """
        result = db.execute_query(query, (start_utc, end_utc))
        return result[0]['count'] if result else 0
    except Exception as e:
        print_warning(f"Could not fetch ghost calls: {e}")
        return 0

# =============================================================================
# PDF Export Class
# =============================================================================

class APTPDFGenerator:
    def __init__(self, title="APT Report"):
        self.title = title
        self.elements = []
        self.styles = getSampleStyleSheet()
        self.setup_styles()
        
    def setup_styles(self):
        """Setup custom styles for the PDF"""
        # Title style
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER,
            spaceAfter=30,
            spaceBefore=30
        )
        
        # Subtitle style
        self.subtitle_style = ParagraphStyle(
            'CustomSubTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#34495e'),
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        # Section header style
        self.section_style = ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=colors.HexColor('#2980b9'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        # Normal text style
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=6
        )
        
        # Footer style
        self.footer_style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
    
    def add_title(self, title, subtitle=None):
        """Add title to the report"""
        self.elements.append(Paragraph(title, self.title_style))
        if subtitle:
            self.elements.append(Paragraph(subtitle, self.subtitle_style))
        self.elements.append(Spacer(1, 0.2*inch))
    
    def add_section(self, title):
        """Add a section header"""
        self.elements.append(Paragraph(title, self.section_style))
        self.elements.append(Spacer(1, 0.1*inch))
    
    def add_text(self, text, style='normal'):
        """Add normal text"""
        if style == 'normal':
            self.elements.append(Paragraph(text, self.normal_style))
        else:
            self.elements.append(Paragraph(text, self.styles[style]))
    
    def add_spacer(self, height=0.2):
        """Add vertical space"""
        self.elements.append(Spacer(1, height*inch))
    
    def add_metric_row(self, label, value, color=None):
        """Add a metric row with optional color"""
        if color:
            text = f'<font color="{color}"><b>{label}:</b> {value}</font>'
        else:
            text = f'<b>{label}:</b> {value}'
        self.elements.append(Paragraph(text, self.normal_style))
    
    def add_table(self, data, col_widths=None, header_row=True):
        """Add a table to the report"""
        if not data or len(data) < 2:
            return
        
        # Create table
        table = Table(data, colWidths=col_widths)
        
        # Style the table
        style = [
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ]
        
        # Alternate row colors
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8f9fa')))
        
        table.setStyle(TableStyle(style))
        self.elements.append(table)
        self.elements.append(Spacer(1, 0.2*inch))
    
    def add_horizontal_line(self):
        """Add a horizontal line"""
        self.elements.append(Spacer(1, 0.1*inch))
        self.elements.append(Paragraph('─' * 80, self.normal_style))
        self.elements.append(Spacer(1, 0.1*inch))
    
    def add_footer(self, text):
        """Add footer text"""
        self.elements.append(Spacer(1, 0.3*inch))
        self.elements.append(Paragraph(text, self.footer_style))
    
    def save(self, filename):
        """Save the PDF to file"""
        try:
            print_info(f"   Creating PDF: {filename}")
            doc = SimpleDocTemplate(
                str(filename),
                pagesize=landscape(letter),
                rightMargin=0.5*inch,
                leftMargin=0.5*inch,
                topMargin=0.5*inch,
                bottomMargin=0.5*inch
            )
            doc.build(self.elements)
            return True
        except Exception as e:
            print_error(f"Error saving PDF: {e}")
            return False

# =============================================================================
# Campaign Selection
# =============================================================================

def get_campaign_list():
    """Get list of all campaigns"""
    try:
        query = """
        SELECT DISTINCT campaign_id
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        ORDER BY campaign_id
        """
        results = db.execute_query(query)
        return [r['campaign_id'] for r in results] if results else []
    except Exception as e:
        print_error(f"Error getting campaign list: {e}")
        return []

def select_multiple_campaigns():
    """Interactive multi-campaign selection"""
    campaigns = get_campaign_list()
    
    if not campaigns:
        print_warning("No campaigns found")
        return None
    
    print_header("📋 SELECT CAMPAIGNS", Colors.CYAN)
    print("\nSelect campaigns to download (use numbers or ranges):")
    print("-" * 60)
    
    # Display in columns
    col_width = 25
    cols = 3
    
    for i, camp in enumerate(campaigns, 1):
        display = f"{i:3}. {camp}"
        if len(display) < col_width:
            display = display.ljust(col_width)
        print(display, end="")
        if i % cols == 0:
            print()
    
    if len(campaigns) % cols != 0:
        print()
    
    print("-" * 60)
    print("\nOptions:")
    print("  • Enter numbers: 1,3,5")
    print("  • Enter ranges: 1-10")
    print("  • 'all' for all campaigns")
    print("  • 'q' to quit")
    
    choice = input("\nSelection: ").strip().lower()
    
    if choice == 'q':
        return None
    elif choice == 'all':
        return campaigns
    
    selected = []
    for part in choice.split(','):
        part = part.strip()
        if '-' in part:
            start, end = map(int, part.split('-'))
            for i in range(start, min(end, len(campaigns)) + 1):
                if 1 <= i <= len(campaigns):
                    selected.append(campaigns[i-1])
        elif part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(campaigns):
                selected.append(campaigns[idx])
    
    return selected if selected else None

# =============================================================================
# Date Selection with Timezone
# =============================================================================

def select_date_with_timezone():
    """Select date with timezone options"""
    print_header("📅 SELECT DATE", Colors.GREEN)
    
    est_now = get_est_time()
    pst_now = get_pst_time()
    
    print(f"\nCurrent Times:")
    print(f"  EST: {est_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  PST: {pst_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("-" * 50)
    
    print("Select date for download:")
    print("  1. Today (EST)")
    print("  2. Yesterday (EST)")
    print("  3. Specific date (EST)")
    print("  4. Date range (EST)")
    print("  5. Today (PST)")
    print("  6. Yesterday (PST)")
    print("  7. Specific date (PST)")
    print("  8. Date range (PST)")
    
    choice = input("\nChoice (1-8): ").strip()
    
    target_tz = EST_TZ
    date_desc = "EST"
    
    if choice in ['5', '6', '7', '8']:
        target_tz = PST_TZ
        date_desc = "PST"
        choice = str(int(choice) - 4)  # Normalize to 1-4
    
    if choice == '1':  # Today
        start_date = datetime.now().astimezone(target_tz).date()
        end_date = start_date
        date_range = f"{start_date}"
        
    elif choice == '2':  # Yesterday
        start_date = (datetime.now().astimezone(target_tz) - timedelta(days=1)).date()
        end_date = start_date
        date_range = f"{start_date}"
        
    elif choice == '3':  # Specific date
        date_str = input(f"Enter date ({date_desc} YYYY-MM-DD): ").strip()
        try:
            start_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            end_date = start_date
            date_range = f"{start_date}"
        except:
            print_error("Invalid date format")
            return None, None, None, None
            
    elif choice == '4':  # Date range
        start_str = input(f"Start date ({date_desc} YYYY-MM-DD): ").strip()
        end_str = input(f"End date ({date_desc} YYYY-MM-DD): ").strip()
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            date_range = f"{start_date} to {end_date}"
        except:
            print_error("Invalid date format")
            return None, None, None, None
    else:
        print_error("Invalid choice")
        return None, None, None, None
    
    return start_date, end_date, target_tz, date_range

# =============================================================================
# Data Download and Processing
# =============================================================================

def download_campaign_data(campaigns, start_date, end_date, target_tz):
    """
    Download campaign data with proper timezone handling
    """
    print_info(f"\n📥 Downloading data for {len(campaigns)} campaigns...")
    
    # Convert dates to datetime range
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    
    # Localize to target timezone
    if target_tz:
        start_dt = target_tz.localize(start_dt)
        end_dt = target_tz.localize(end_dt)
    
    # Convert to UTC for database query
    start_utc = start_dt.astimezone(UTC_TZ)
    end_utc = end_dt.astimezone(UTC_TZ)
    
    print(f"  Timezone: {target_tz.zone}")
    print(f"  Selected: {start_dt.strftime('%Y-%m-%d %H:%M:%S %Z')} to {end_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  UTC:      {start_utc.strftime('%Y-%m-%d %H:%M:%S')} to {end_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Build query with campaign filter
    placeholders = ','.join(['%s'] * len(campaigns))
    
    query = f"""
    SELECT 
        c.call_date,
        c.campaign_id,
        c.uniqueid,
        c.phone_number,
        c.length_in_sec,
        c.queue_seconds,
        c.term_reason,
        c.status as call_status,
        a.user as agent,
        u.full_name as agent_name,
        a.talk_sec,
        a.dispo_sec,
        a.status as agent_status,
        a.pause_sec,
        a.wait_sec,
        a.campaign_id as agent_campaign,
        c.call_date as call_time_utc
    FROM vicidial_closer_log c
    LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
    LEFT JOIN vicidial_users u ON a.user = u.user
    WHERE c.campaign_id IN ({placeholders})
      AND c.call_date BETWEEN %s AND %s
    ORDER BY c.call_date DESC
    """
    
    params = campaigns + [start_utc, end_utc]
    
    try:
        results = db.execute_query(query, params)
        print_success(f"✅ Downloaded {len(results)} records")
        return results
    except Exception as e:
        print_error(f"Error downloading data: {e}")
        return []

def process_data_with_timezone(data, start_date, end_date, target_tz):
    """
    Process downloaded data with timezone conversion and filtering
    Returns: (processed_data, removed_stats)
    """
    if not data:
        return [], {'before': 0, 'after': 0, 'status': 0, 'by_type': {}}
    
    print_info("\n🔄 Processing data with timezone conversion...")
    
    processed = []
    removed_before = 0
    removed_after = 0
    removed_status = 0
    removed_by_type = {
        'NA': 0, 'AFTHRS': 0, 'DROP': 0, 'QUEUE': 0, 'CLOSER': 0, 'DISPO': 0, 'OTHER': 0
    }
    
    for row in data:
        # Convert call_date from UTC to target timezone
        call_date_utc = row['call_date']
        if call_date_utc.tzinfo is None:
            call_date_utc = UTC_TZ.localize(call_date_utc)
        
        call_date_tz = call_date_utc.astimezone(target_tz)
        call_date_local = call_date_tz.date()
        
        # Also convert to PST for display
        call_date_pst = call_date_utc.astimezone(PST_TZ)
        
        # Filter by date in target timezone
        if call_date_local < start_date:
            removed_before += 1
            continue
        if call_date_local > end_date:
            removed_after += 1
            continue
        
        # Track excluded statuses before filtering
        term_reason = row['term_reason']
        if term_reason in EXCLUDED_STATUSES:
            removed_by_type[term_reason] = removed_by_type.get(term_reason, 0) + 1
            removed_status += 1
            continue
        
        if row['agent_status'] and row['agent_status'] in EXCLUDED_STATUSES:
            removed_by_type[row['agent_status']] = removed_by_type.get(row['agent_status'], 0) + 1
            removed_status += 1
            continue
        
        # Calculate call time (length - alt_dial)
        alt_dial = safe_float(row.get('dispo_sec', 0))
        call_time_sec = calculate_call_time(row['length_in_sec'], alt_dial)
        
        # Create processed record with both timezones
        processed_row = {
            'call_date_utc': call_date_utc.strftime('%Y-%m-%d %H:%M:%S'),
            'call_date_tz': call_date_tz.strftime('%Y-%m-%d %H:%M:%S'),
            'call_date_pst': call_date_pst.strftime('%Y-%m-%d %H:%M:%S'),
            'call_date_local': call_date_local.strftime('%Y-%m-%d'),
            'timezone': target_tz.zone,
            'campaign_id': row['campaign_id'],
            'uniqueid': row['uniqueid'],
            'phone_number': row['phone_number'],
            'length_sec': safe_int(row['length_in_sec']),
            'queue_sec': safe_int(row['queue_seconds']),
            'talk_sec': safe_int(row['talk_sec']),
            'dispo_sec': safe_int(row['dispo_sec']),
            'call_time_sec': call_time_sec,  # Formula applied
            'call_time_hms': sec_to_hms(call_time_sec),
            'term_reason': row['term_reason'],
            'call_status': row['call_status'],
            'agent': row['agent'],
            'agent_name': row['agent_name'] or 'Unknown',
            'agent_status': row['agent_status'],
        }
        
        processed.append(processed_row)
    
    # Print processing statistics
    print(f"\n📊 PROCESSING STATISTICS:")
    print(f"  • Total records downloaded: {len(data)}")
    print(f"  • Removed (before date range): {removed_before}")
    print(f"  • Removed (after date range): {removed_after}")
    print(f"  • Removed by status:")
    for status, count in removed_by_type.items():
        if count > 0:
            status_desc = STATUS_DESCRIPTIONS.get(status, status)
            print(f"      - {status_desc}: {count}")
    print(f"  • TOTAL REMOVED: {removed_before + removed_after + removed_status}")
    print_color(f"  • RETAINED FOR ANALYSIS: {len(processed)}", Colors.GREEN)
    
    removed_stats = {
        'before': removed_before,
        'after': removed_after,
        'status': removed_status,
        'by_type': removed_by_type
    }
    
    return processed, removed_stats

# =============================================================================
# Report Generation - Updated with new metrics
# =============================================================================

def generate_apt_report(processed_data, campaigns, start_date, end_date, target_tz, 
                        removed_stats=None):
    """Generate APT report with statistics and show excluded calls"""
    
    print_header("📊 APT (Adherence & Performance Tracking) REPORT", Colors.MAGENTA)
    
    # Get current times in both timezones
    est_now = get_est_time()
    pst_now = get_pst_time()
    
    print(f"\n🕒 Report Generated (EST): {est_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"🕒 Report Generated (PST): {pst_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print("-" * 70)
    
    print(f"\n📋 Report Parameters:")
    print(f"  • Target Timezone: {target_tz.zone}")
    print(f"  • Date Range: {start_date} to {end_date}")
    print(f"  • Campaigns: {', '.join(campaigns[:5])}{'...' if len(campaigns) > 5 else ''}")
    print(f"  • Total Campaigns: {len(campaigns)}")
    print(f"  • Total Records: {len(processed_data)}")
    
    # Show excluded calls if any
    if removed_stats and (removed_stats['before'] > 0 or removed_stats['after'] > 0 or removed_stats['status'] > 0):
        print(f"\n🚫 EXCLUDED CALLS:")
        print("-" * 60)
        if removed_stats['before'] > 0:
            print(f"  • Before date range: {removed_stats['before']} calls")
        if removed_stats['after'] > 0:
            print(f"  • After date range: {removed_stats['after']} calls")
        if removed_stats['status'] > 0:
            print(f"  • Excluded statuses: {removed_stats['status']} calls")
            for status, count in removed_stats['by_type'].items():
                if count > 0:
                    status_desc = STATUS_DESCRIPTIONS.get(status, status)
                    print(f"      - {status_desc}: {count}")
        total_excluded = removed_stats['before'] + removed_stats['after'] + removed_stats['status']
        print(f"\n  • TOTAL EXCLUDED: {total_excluded} calls")
        print_color(f"  • RETAINED FOR ANALYSIS: {len(processed_data)} calls", Colors.GREEN)
        print("-" * 60)
    
    if not processed_data:
        print_warning("No data to analyze")
        return
    
    # Get new metrics
    agents_not_available = get_agents_not_available()
    inbound_after_hours = get_inbound_after_hours(start_date, end_date, target_tz)
    leads_to_be_called = get_leads_to_be_called()
    ghost_calls = get_ghost_calls(start_date, end_date, target_tz)
    
    # Calculate statistics
    total_calls = len(processed_data)
    total_talk_sec = sum(row['talk_sec'] for row in processed_data)
    total_call_time_sec = sum(row['call_time_sec'] for row in processed_data)
    avg_talk = total_talk_sec / total_calls if total_calls > 0 else 0
    avg_call_time = total_call_time_sec / total_calls if total_calls > 0 else 0
    
    # Answer rate
    answered = sum(1 for row in processed_data if row['length_sec'] >= 5)
    answer_rate = (answered / total_calls * 100) if total_calls > 0 else 0
    
    # Abandon rate
    abandoned = sum(1 for row in processed_data if row['term_reason'] in ['ABANDON', 'QUEUETIMEOUT', 'NOAGENT'])
    abandon_rate = (abandoned / total_calls * 100) if total_calls > 0 else 0
    
    print(f"\n📈 SUMMARY STATISTICS:")
    print(f"  • Total Calls Analyzed: {total_calls}")
    print(f"  • Answered: {answered} ({answer_rate:.1f}%)")
    print(f"  • Abandoned: {abandoned} ({abandon_rate:.1f}%)")
    print(f"  • Total Talk Time: {sec_to_hms(total_talk_sec)}")
    print(f"  • Total Call Time (after formula): {sec_to_hms(total_call_time_sec)}")
    print(f"  • Avg Talk Time: {sec_to_hms(avg_talk)}")
    print(f"  • Avg Call Time: {sec_to_hms(avg_call_time)}")
    
    # New metrics section
    print(f"\n📊 ADDITIONAL METRICS:")
    print("-" * 60)
    print(f"  • Agents Not Available: {agents_not_available}")
    print(f"  • Inbound After Hours: {inbound_after_hours}")
    print(f"  • Leads to be Called: {leads_to_be_called}")
    print(f"  • Ghost Calls (0 sec, no agent): {ghost_calls}")
    
    # Campaign breakdown
    campaign_stats = {}
    for row in processed_data:
        camp = row['campaign_id']
        if camp not in campaign_stats:
            campaign_stats[camp] = {'calls': 0, 'talk': 0, 'call_time': 0}
        campaign_stats[camp]['calls'] += 1
        campaign_stats[camp]['talk'] += row['talk_sec']
        campaign_stats[camp]['call_time'] += row['call_time_sec']
    
    print(f"\n📋 CAMPAIGN BREAKDOWN:")
    print("-" * 80)
    print(f"{'Campaign':<20} {'Calls':<8} {'Talk Time':<15} {'Call Time':<15} {'Avg Call':<10}")
    print("-" * 80)
    
    for camp, stats in sorted(campaign_stats.items(), key=lambda x: -x[1]['calls']):
        avg_call = stats['call_time'] / stats['calls'] if stats['calls'] > 0 else 0
        print(f"{camp:<20} {stats['calls']:<8} {sec_to_hms(stats['talk']):<15} "
              f"{sec_to_hms(stats['call_time']):<15} {sec_to_hms(avg_call):<10}")
    
    # Timezone distribution (using PST for display)
    print(f"\n🌍 TIMEZONE DISTRIBUTION (PST):")
    tz_counts = {}
    for row in processed_data:
        # Parse the PST time we stored
        pst_time_str = row.get('call_date_pst', row['call_date_tz'])
        hour = int(pst_time_str.split()[1].split(':')[0]) if ' ' in pst_time_str else 0
        period = '00-06' if hour < 6 else '06-12' if hour < 12 else '12-18' if hour < 18 else '18-24'
        tz_counts[period] = tz_counts.get(period, 0) + 1
    
    total_calls = len(processed_data)
    for period in ['00-06', '06-12', '12-18', '18-24']:
        count = tz_counts.get(period, 0)
        pct = (count / total_calls * 100) if total_calls > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"  {period}: {count:4} calls ({pct:5.1f}%) {bar}")

# =============================================================================
# PDF Export with File Details and Debug
# =============================================================================

def export_to_pdf(processed_data, campaigns, start_date, end_date, target_tz, filename, removed_stats=None):
    """Export APT report to PDF with file details and debug output"""
    if not PDF_AVAILABLE:
        print_error("ReportLab is not installed. PDF export unavailable.")
        print("Install with: pip install reportlab")
        return False
    
    if not processed_data:
        print_warning("No data to export")
        return False
    
    print_info(f"\n📑 Generating PDF...")
    print_info(f"   Target file: {filename}")
    
    try:
        pdf = APTPDFGenerator("APT Report")
        
        # Title
        pdf.add_title(
            "Adherence & Performance Tracking (APT) Report",
            f"Period: {start_date} to {end_date} ({target_tz.zone})"
        )
        
        # Timezone info
        est_now = get_est_time()
        pst_now = get_pst_time()
        pdf.add_text(f"Generated (EST): {est_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        pdf.add_text(f"Generated (PST): {pst_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        pdf.add_spacer(0.1)
        
        # Parameters
        pdf.add_section("📋 Report Parameters")
        pdf.add_text(f"Target Timezone: {target_tz.zone}")
        pdf.add_text(f"Date Range: {start_date} to {end_date}")
        pdf.add_text(f"Campaigns: {len(campaigns)} selected")
        pdf.add_text(f"Total Records: {len(processed_data)}")
        pdf.add_spacer(0.1)
        
        # Show excluded calls in PDF
        if removed_stats and (removed_stats['before'] > 0 or removed_stats['after'] > 0 or removed_stats['status'] > 0):
            pdf.add_section("🚫 Excluded Calls")
            if removed_stats['before'] > 0:
                pdf.add_text(f"• Before date range: {removed_stats['before']} calls")
            if removed_stats['after'] > 0:
                pdf.add_text(f"• After date range: {removed_stats['after']} calls")
            if removed_stats['status'] > 0:
                pdf.add_text(f"• Excluded statuses: {removed_stats['status']} calls")
                for status, count in removed_stats['by_type'].items():
                    if count > 0:
                        status_desc = STATUS_DESCRIPTIONS.get(status, status)
                        pdf.add_text(f"  - {status_desc}: {count}")
            total_excluded = removed_stats['before'] + removed_stats['after'] + removed_stats['status']
            pdf.add_text(f"\n• TOTAL EXCLUDED: {total_excluded}")
            pdf.add_text(f"• RETAINED FOR ANALYSIS: {len(processed_data)}")
            pdf.add_spacer(0.1)
        
        # Get new metrics
        agents_not_available = get_agents_not_available()
        inbound_after_hours = get_inbound_after_hours(start_date, end_date, target_tz)
        leads_to_be_called = get_leads_to_be_called()
        ghost_calls = get_ghost_calls(start_date, end_date, target_tz)
        
        # Summary Statistics
        pdf.add_section("📈 Summary Statistics")
        
        total_calls = len(processed_data)
        total_talk_sec = sum(row['talk_sec'] for row in processed_data)
        total_call_time_sec = sum(row['call_time_sec'] for row in processed_data)
        avg_talk = total_talk_sec / total_calls if total_calls > 0 else 0
        avg_call_time = total_call_time_sec / total_calls if total_calls > 0 else 0
        
        answered = sum(1 for row in processed_data if row['length_sec'] >= 5)
        answer_rate = (answered / total_calls * 100) if total_calls > 0 else 0
        
        abandoned = sum(1 for row in processed_data if row['term_reason'] in ['ABANDON', 'QUEUETIMEOUT', 'NOAGENT'])
        abandon_rate = (abandoned / total_calls * 100) if total_calls > 0 else 0
        
        # Color code metrics
        ans_color = '#27ae60' if answer_rate >= 80 else '#e67e22' if answer_rate >= 60 else '#e74c3c'
        abd_color = '#27ae60' if abandon_rate <= 5 else '#e67e22' if abandon_rate <= 10 else '#e74c3c'
        
        pdf.add_metric_row("Total Calls Analyzed", f"{total_calls}")
        pdf.add_metric_row("Answered", f"{answered} ({answer_rate:.1f}%)", ans_color)
        pdf.add_metric_row("Abandoned", f"{abandoned} ({abandon_rate:.1f}%)", abd_color)
        pdf.add_metric_row("Total Talk Time", sec_to_hms(total_talk_sec))
        pdf.add_metric_row("Total Call Time (after formula)", sec_to_hms(total_call_time_sec))
        pdf.add_metric_row("Avg Talk Time", sec_to_hms(avg_talk))
        pdf.add_metric_row("Avg Call Time", sec_to_hms(avg_call_time))
        pdf.add_spacer(0.1)
        
        # Additional Metrics Section
        pdf.add_section("📊 Additional Metrics")
        pdf.add_metric_row("Agents Not Available", f"{agents_not_available}")
        pdf.add_metric_row("Inbound After Hours", f"{inbound_after_hours}")
        pdf.add_metric_row("Leads to be Called", f"{leads_to_be_called}")
        pdf.add_metric_row("Ghost Calls (0 sec, no agent)", f"{ghost_calls}")
        pdf.add_spacer(0.1)
        
        # Campaign Breakdown Table
        pdf.add_section("📋 Campaign Breakdown")
        
        # Calculate campaign statistics
        campaign_stats = {}
        for row in processed_data:
            camp = row['campaign_id']
            if camp not in campaign_stats:
                campaign_stats[camp] = {'calls': 0, 'talk': 0, 'call_time': 0}
            campaign_stats[camp]['calls'] += 1
            campaign_stats[camp]['talk'] += row['talk_sec']
            campaign_stats[camp]['call_time'] += row['call_time_sec']
        
        if campaign_stats:
            table_data = [['Campaign', 'Calls', 'Talk Time', 'Call Time', 'Avg Call']]
            for camp, stats in sorted(campaign_stats.items(), key=lambda x: -x[1]['calls'])[:15]:
                avg_call = stats['call_time'] / stats['calls'] if stats['calls'] > 0 else 0
                table_data.append([
                    camp,
                    str(stats['calls']),
                    sec_to_hms(stats['talk']),
                    sec_to_hms(stats['call_time']),
                    sec_to_hms(avg_call)
                ])
            
            pdf.add_table(table_data, col_widths=[1.2*inch, 0.6*inch, 1.2*inch, 1.2*inch, 0.8*inch])
        
        # Timezone Distribution (PST)
        pdf.add_section("🌍 Timezone Distribution (PST)")
        tz_counts = {}
        for row in processed_data:
            pst_time_str = row.get('call_date_pst', row['call_date_tz'])
            hour = int(pst_time_str.split()[1].split(':')[0]) if ' ' in pst_time_str else 0
            period = '00-06' if hour < 6 else '06-12' if hour < 12 else '12-18' if hour < 18 else '18-24'
            tz_counts[period] = tz_counts.get(period, 0) + 1
        
        total_calls = len(processed_data)
        for period in ['00-06', '06-12', '12-18', '18-24']:
            count = tz_counts.get(period, 0)
            pct = (count / total_calls * 100) if total_calls > 0 else 0
            pdf.add_text(f"{period}: {count} calls ({pct:.1f}%)")
        
        # Footer
        pdf.add_footer(f"Generated by Altria Ops APT Tool | Formula: Call Time = Length - Alt Dial")
        
        # Save PDF
        print_info(f"   Building PDF document...")
        if pdf.save(filename):
            # Verify file was created
            if os.path.exists(filename):
                # Get absolute path
                abs_path = os.path.abspath(filename)
                file_size = os.path.getsize(filename)
                
                print()
                print_success(f"✅ PDF successfully created!")
                print_info(f"   📁 Location: {abs_path}")
                print_info(f"   📄 Filename: {Path(filename).name}")
                print_info(f"   📊 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
                
                return True
            else:
                print_error(f"❌ PDF file not found after save: {filename}")
                return False
        else:
            print_error("❌ PDF export failed - save returned False")
            return False
            
    except Exception as e:
        print_error(f"❌ PDF export error: {e}")
        import traceback
        traceback.print_exc()
        return False

# =============================================================================
# CSV Export with File Details
# =============================================================================

def export_to_csv(processed_data, filename):
    """Export processed data to CSV with file details"""
    if not processed_data:
        print_warning("No data to export")
        return False
    
    try:
        print_info(f"\n📄 Generating CSV...")
        print_info(f"   Target file: {filename}")
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'Call Date (UTC)', 'Call Date (Local)', 'Call Date (PST)', 'Timezone',
                'Campaign', 'Unique ID', 'Phone Number',
                'Length (sec)', 'Queue (sec)', 'Talk (sec)', 'Dispo (sec)',
                'Call Time (sec)', 'Call Time (HMS)', 'Formula Used',
                'Term Reason', 'Call Status', 'Agent', 'Agent Name', 'Agent Status'
            ])
            
            # Write data
            for row in processed_data:
                writer.writerow([
                    row['call_date_utc'],
                    row['call_date_tz'],
                    row.get('call_date_pst', row['call_date_tz']),
                    row['timezone'],
                    row['campaign_id'],
                    row['uniqueid'],
                    row['phone_number'],
                    row['length_sec'],
                    row['queue_sec'],
                    row['talk_sec'],
                    row['dispo_sec'],
                    row['call_time_sec'],
                    row['call_time_hms'],
                    'length_sec - dispo_sec',
                    row['term_reason'],
                    row['call_status'],
                    row['agent'],
                    row['agent_name'],
                    row['agent_status']
                ])
        
        # Verify file was created
        if os.path.exists(filename):
            abs_path = os.path.abspath(filename)
            file_size = os.path.getsize(filename)
            
            print()
            print_success(f"✅ CSV successfully created!")
            print_info(f"   📁 Location: {abs_path}")
            print_info(f"   📄 Filename: {Path(filename).name}")
            print_info(f"   📊 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
            return True
        else:
            print_error(f"❌ CSV file not found after save: {filename}")
            return False
        
    except Exception as e:
        print_error(f"❌ CSV export failed: {e}")
        return False

# =============================================================================
# Excel Export with File Details
# =============================================================================

def export_to_excel(processed_data, filename):
    """Export to Excel with formatting and file details"""
    try:
        import pandas as pd
    except ImportError:
        print_error("Excel export requires pandas. Install: pip install pandas openpyxl")
        return False
    
    if not processed_data:
        print_warning("No data to export")
        return False
    
    try:
        print_info(f"\n📊 Generating Excel...")
        print_info(f"   Target file: {filename}")
        
        df = pd.DataFrame(processed_data)
        
        # Select and rename columns for Excel
        excel_data = df[[
            'call_date_utc', 'call_date_tz', 'call_date_pst', 'campaign_id',
            'phone_number', 'call_time_sec', 'call_time_hms',
            'talk_sec', 'dispo_sec', 'term_reason', 'agent', 'agent_name'
        ]].copy()
        
        excel_data.columns = [
            'Call Date (UTC)', 'Call Date (Local)', 'Call Date (PST)', 'Campaign',
            'Phone Number', 'Call Time (sec)', 'Call Time',
            'Talk (sec)', 'Dispo (sec)', 'Term Reason', 'Agent', 'Agent Name'
        ]
        
        excel_data.to_excel(filename, index=False, sheet_name='APT Data')
        
        # Verify file was created
        if os.path.exists(filename):
            abs_path = os.path.abspath(filename)
            file_size = os.path.getsize(filename)
            
            print()
            print_success(f"✅ Excel successfully created!")
            print_info(f"   📁 Location: {abs_path}")
            print_info(f"   📄 Filename: {Path(filename).name}")
            print_info(f"   📊 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
            return True
        else:
            print_error(f"❌ Excel file not found after save: {filename}")
            return False
        
    except Exception as e:
        print_error(f"❌ Excel export failed: {e}")
        return False

# =============================================================================
# Main APT Function - User-Friendly Version with Pauses
# =============================================================================

def apt_download_menu():
    """Main APT download and processing menu - User-friendly version with pauses"""
    
    print_header("📥 APT (Adherence & Performance Tracking) DOWNLOAD API", Colors.CYAN)
    print("=" * 70)
    print("                API DOWNLOAD TOOL")
    print("=" * 70)
    print("This tool downloads campaign data via API with proper timezone handling")
    print("and applies the APT formula: Call Time = Length - Alt Dial")
    print("-" * 70)
    
    # Step 1: Select campaigns
    campaigns = select_multiple_campaigns()
    if not campaigns:
        return
    
    # Step 2: Select date with timezone
    start_date, end_date, target_tz, date_range = select_date_with_timezone()
    if not start_date:
        return
    
    print(f"\n📋 Selected Options:")
    print(f"  • Campaigns: {len(campaigns)} selected")
    print(f"  • Date: {date_range}")
    print(f"  • Timezone: {target_tz.zone}")
    
    confirm = input("\nProceed with download? (y/N): ").strip().lower()
    if confirm != 'y':
        print_warning("Download cancelled")
        return
    
    # Step 3: Download data
    raw_data = download_campaign_data(campaigns, start_date, end_date, target_tz)
    
    if not raw_data:
        print_error("No data downloaded")
        input("\nPress Enter to continue...")
        return
    
    # Step 4: Process data with timezone filtering
    processed_data, removed_stats = process_data_with_timezone(raw_data, start_date, end_date, target_tz)
    
    # Step 5: Generate and show report on screen
    generate_apt_report(processed_data, campaigns, start_date, end_date, target_tz, removed_stats)
    
    # Step 6: Ask if they want to download the report
    print("\n" + "─" * 70)
    print("📥 DOWNLOAD OPTIONS")
    print("Would you like to download this report?")
    print("  1. Yes, download now")
    print("  2. No, thanks")
    
    download_choice = input("\nChoice (1-2): ").strip()
    
    if download_choice != '1':
        print_info("Download skipped")
        input("\nPress Enter to continue...")
        return
    
    # Step 7: Choose format
    print("\n" + "─" * 70)
    print("📄 SELECT FORMAT")
    print("Choose the file format you want to download:")
    print("  1. CSV (Comma Separated Values - for Excel)")
    print("  2. Excel (XLSX - formatted spreadsheet)")
    print("  3. PDF (Portable Document Format - report)")
    print("  4. All formats (CSV, Excel, and PDF)")
    
    format_choice = input("\nChoice (1-4): ").strip()
    
    # Step 8: Automatically save to Downloads folder
    downloads_path = Path.home() / "Downloads"
    
    # Create filename with timestamp and campaign info
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    campaign_info = campaigns[0] if len(campaigns) == 1 else f"{len(campaigns)}campaigns"
    base_filename = f"APT_Report_{campaign_info}_{timestamp}"
    
    print(f"\n📁 Saving to your Downloads folder: {downloads_path}")
    print(f"📄 Base filename: {base_filename}.*")
    print("-" * 70)
    
    # Step 9: Save files based on format choice
    saved_files = []
    
    if format_choice in ['1', '4']:  # CSV
        csv_path = downloads_path / f"{base_filename}.csv"
        if export_to_csv(processed_data, str(csv_path)):
            saved_files.append(str(csv_path))
    
    if format_choice in ['2', '4']:  # Excel
        excel_path = downloads_path / f"{base_filename}.xlsx"
        if export_to_excel(processed_data, str(excel_path)):
            saved_files.append(str(excel_path))
    
    if format_choice in ['3', '4']:  # PDF
        pdf_path = downloads_path / f"{base_filename}.pdf"
        if PDF_AVAILABLE:
            if export_to_pdf(processed_data, campaigns, start_date, end_date, target_tz, str(pdf_path), removed_stats):
                saved_files.append(str(pdf_path))
        else:
            print_error("PDF export not available. Please install reportlab: pip install reportlab")
    
    # Step 10: Show summary of saved files with pauses
    if saved_files:
        print("\n" + "=" * 70)
        print_color("✅ DOWNLOAD COMPLETE!", Colors.GREEN)
        print("=" * 70)
        print(f"\n📁 Files saved to: {downloads_path}")
        print("\n📄 Files created:")
        for i, file in enumerate(saved_files, 1):
            print(f"   {i}. {Path(file).name}")
        
        # PAUSE SO USER CAN SEE THE MESSAGE
        print("\n" + "-" * 70)
        input("Press Enter to open the Downloads folder...")
        
        # Try to open the Downloads folder
        try:
            if os.name == 'nt':  # Windows
                os.startfile(downloads_path)
                print(f"\n📂 Opened Downloads folder for you!")
        except:
            pass
        
        # Another pause after opening
        print("\n" + "-" * 70)
        input("Press Enter to return to menu...")
        
    else:
        print_error("No files were saved")
        input("\nPress Enter to continue...")

# =============================================================================
# Standalone execution
# =============================================================================

if __name__ == "__main__":
    apt_download_menu()