#!/usr/bin/env python3
# =============================================================================
# File:         schedule.py
# Version:      3.0.1
# Date:         2026-03-06
# Description:  Agent schedule management with JSON backend
# Update:       Added debug line for schedule data file creation
# Location:     D:\Altria_Ops\agents\schedule.py
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info
from utils.formatter import format_datetime, sec_to_hms, time_ago
import json
from pathlib import Path
from collections import defaultdict
import sys
import os

# Import agent list functions
try:
    from agents.dashboard import get_all_agents, show_agent_list, get_agent_by_selection
    AGENT_FUNCTIONS_AVAILABLE = True
except ImportError:
    AGENT_FUNCTIONS_AVAILABLE = False

# =============================================================================
# JSON Data Management
# =============================================================================

SCHEDULE_DATA_FILE = Path(__file__).parent.parent / "data" / "schedule_data.json"

def ensure_schedule_file():
    """Ensure the schedule data file exists with default structure"""
    if not SCHEDULE_DATA_FILE.exists():
        # Create default schedule data
        default_data = {
            "templates": [
                {
                    "id": 1,
                    "name": "Morning",
                    "start": "08:00",
                    "end": "16:00",
                    "break": 30,
                    "description": "Morning shift 8am-4pm",
                    "color": "cyan"
                },
                {
                    "id": 2,
                    "name": "Afternoon",
                    "start": "14:00",
                    "end": "22:00",
                    "break": 30,
                    "description": "Afternoon shift 2pm-10pm",
                    "color": "yellow"
                },
                {
                    "id": 3,
                    "name": "Evening",
                    "start": "22:00",
                    "end": "06:00",
                    "break": 45,
                    "description": "Overnight shift 10pm-6am",
                    "color": "magenta"
                },
                {
                    "id": 4,
                    "name": "Standard",
                    "start": "09:00",
                    "end": "17:00",
                    "break": 30,
                    "description": "Standard business hours",
                    "color": "green"
                }
            ],
            "shifts": [],
            "last_updated": datetime.now().isoformat()
        }
        
        # Create directory if it doesn't exist
        SCHEDULE_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(SCHEDULE_DATA_FILE, 'w') as f:
            json.dump(default_data, f, indent=2)
        
        # Debug line showing where the file was created
        print_success(f"✅ Created default schedule data file at: {SCHEDULE_DATA_FILE}")
        return True
    
    return True

def load_schedule_data():
    """Load schedule data from JSON file"""
    try:
        ensure_schedule_file()
        
        with open(SCHEDULE_DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print_error(f"Error loading schedule data: {e}")
        return {
            "templates": [],
            "shifts": [],
            "last_updated": datetime.now().isoformat()
        }

def save_schedule_data(data):
    """Save schedule data to JSON file"""
    try:
        data["last_updated"] = datetime.now().isoformat()
        
        with open(SCHEDULE_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print_error(f"Error saving schedule data: {e}")
        return False

# =============================================================================
# Agent Selection Functions
# =============================================================================

def select_agent_interactive(prompt="Select agent"):
    """Interactive agent selection with list display"""
    if not AGENT_FUNCTIONS_AVAILABLE:
        print_warning("Agent functions not available, using simple input")
        return input("Enter agent username: ").strip()
    
    # Show agent list
    agents = show_agent_list()
    if not agents:
        return None
    
    # Get selection
    selected_agent = get_agent_by_selection(agents)
    return selected_agent

# =============================================================================
# Schedule Data Functions
# =============================================================================

def check_schedule_tables():
    """Check if schedule data exists (always True for JSON)"""
    return SCHEDULE_DATA_FILE.exists()

def get_shift_templates():
    """Get all shift templates from JSON"""
    data = load_schedule_data()
    return data.get("templates", [])

def get_agent_shifts(agent_username, start_date=None, end_date=None):
    """Get shifts for an agent from JSON"""
    data = load_schedule_data()
    shifts = data.get("shifts", [])
    
    # Filter by agent
    shifts = [s for s in shifts if s.get("agent_username") == agent_username]
    
    # Filter by date range if specified
    if start_date and end_date:
        if isinstance(start_date, datetime):
            start_date = start_date.date()
        if isinstance(end_date, datetime):
            end_date = end_date.date()
        
        filtered = []
        for s in shifts:
            try:
                shift_date = datetime.strptime(s["shift_date"], "%Y-%m-%d").date()
                if start_date <= shift_date <= end_date:
                    filtered.append(s)
            except:
                continue
        return filtered
    
    return shifts

def get_daily_shifts(date=None):
    """Get all shifts for a specific date from JSON"""
    if not date:
        date = datetime.now().date()
    
    data = load_schedule_data()
    shifts = data.get("shifts", [])
    
    # Format date for comparison
    if isinstance(date, datetime):
        date_str = date.strftime("%Y-%m-%d")
    else:
        date_str = str(date)
    
    # Filter by date
    daily_shifts = []
    for s in shifts:
        if s.get("shift_date") == date_str:
            # Add template info if available
            if s.get("template_id"):
                template = next((t for t in data.get("templates", []) if t["id"] == s["template_id"]), None)
                if template:
                    s["template_name"] = template["name"]
                    s["color"] = template["color"]
            daily_shifts.append(s)
    
    return daily_shifts

def add_agent_shift(agent_username, shift_date, start_time, end_time, template_id=None, break_duration=30):
    """Add a shift to JSON"""
    data = load_schedule_data()
    
    # Format shift date
    if isinstance(shift_date, datetime):
        shift_date_str = shift_date.strftime("%Y-%m-%d")
    else:
        shift_date_str = str(shift_date)
    
    # Generate new ID
    shifts = data.get("shifts", [])
    new_id = max([s.get("id", 0) for s in shifts], default=0) + 1
    
    # Create new shift
    new_shift = {
        "id": new_id,
        "agent_username": agent_username,
        "shift_date": shift_date_str,
        "start_time": start_time,
        "end_time": end_time,
        "template_id": template_id,
        "break_duration": break_duration,
        "status": "scheduled",
        "created_at": datetime.now().isoformat()
    }
    
    # Add template name if template_id provided
    if template_id:
        template = next((t for t in data.get("templates", []) if t["id"] == template_id), None)
        if template:
            new_shift["template_name"] = template["name"]
            new_shift["color"] = template.get("color", "white")
    
    shifts.append(new_shift)
    data["shifts"] = shifts
    
    if save_schedule_data(data):
        return new_id
    return None

def update_shift(shift_id, **kwargs):
    """Update a shift in JSON"""
    data = load_schedule_data()
    shifts = data.get("shifts", [])
    
    for shift in shifts:
        if shift["id"] == shift_id:
            for key, value in kwargs.items():
                shift[key] = value
            shift["updated_at"] = datetime.now().isoformat()
            break
    
    return save_schedule_data(data)

def cancel_shift(shift_id):
    """Cancel a shift in JSON"""
    return update_shift(shift_id, status="cancelled")

def create_shift_template(name, start, end, break_duration=30, description="", color=None):
    """Create a new shift template in JSON"""
    data = load_schedule_data()
    templates = data.get("templates", [])
    
    # Generate new ID
    new_id = max([t.get("id", 0) for t in templates], default=0) + 1
    
    # Assign color if not provided
    if not color:
        if 'morning' in name.lower():
            color = 'cyan'
        elif 'afternoon' in name.lower():
            color = 'yellow'
        elif 'evening' in name.lower() or 'night' in name.lower():
            color = 'magenta'
        else:
            color = 'white'
    
    new_template = {
        "id": new_id,
        "name": name,
        "start": start,
        "end": end,
        "break": break_duration,
        "description": description,
        "color": color,
        "created_at": datetime.now().isoformat()
    }
    
    templates.append(new_template)
    data["templates"] = templates
    
    return save_schedule_data(data)

def update_shift_template(template_id, **kwargs):
    """Update a shift template in JSON"""
    data = load_schedule_data()
    templates = data.get("templates", [])
    
    for template in templates:
        if template["id"] == template_id:
            for key, value in kwargs.items():
                template[key] = value
            template["updated_at"] = datetime.now().isoformat()
            break
    
    return save_schedule_data(data)

def delete_shift_template(template_id):
    """Delete a shift template from JSON"""
    data = load_schedule_data()
    templates = data.get("templates", [])
    
    # Check if template is in use
    shifts = data.get("shifts", [])
    in_use = any(s.get("template_id") == template_id for s in shifts)
    
    if in_use:
        print_warning(f"⚠️ Template is used by existing shifts. Cannot delete.")
        print_info("   You can either:")
        print_info("   1. Edit the template instead of deleting")
        print_info("   2. Cancel all shifts using this template first")
        return False
    
    # Remove template
    data["templates"] = [t for t in templates if t["id"] != template_id]
    
    return save_schedule_data(data)

# =============================================================================
# Display Functions
# =============================================================================

def show_daily_schedule():
    """Display today's schedule"""
    print_header("📅 TODAY'S SCHEDULE", Colors.CYAN)
    
    # Ensure data file exists
    ensure_schedule_file()
    
    date = datetime.now().date()
    print(f"\n📆 Date: {date}")
    print("=" * 80)
    
    # Get today's shifts
    shifts = get_daily_shifts(date)
    
    if not shifts:
        print_info("\n📭 No shifts scheduled for today")
        
        # Show upcoming days that have shifts
        data = load_schedule_data()
        all_shifts = data.get("shifts", [])
        
        # Group by date
        upcoming = {}
        for s in all_shifts:
            if s.get("status") != "cancelled" and s.get("shift_date", "") > str(date):
                upcoming[s["shift_date"]] = upcoming.get(s["shift_date"], 0) + 1
        
        if upcoming:
            print("\n📅 Upcoming scheduled days:")
            sorted_dates = sorted(upcoming.items())
            for date_str, count in sorted_dates[:5]:
                print(f"  • {date_str}: {count} agent(s)")
        
        # Option to add a shift
        print("\nOptions:")
        print("  1. Add a shift")
        print("  2. Back")
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        if choice == '1':
            add_shift_interactive()
    else:
        print(f"\n👥 Agents scheduled today: {len(shifts)}")
        print("-" * 100)
        print(f"{'#':<4} {'Agent':<12} {'Name':<20} {'Shift':<15} {'Time':<20} {'Status'}")
        print("-" * 100)
        
        for i, shift in enumerate(shifts, 1):
            # Get agent name
            name = "Unknown"
            if AGENT_FUNCTIONS_AVAILABLE:
                name_query = "SELECT full_name FROM vicidial_users WHERE user = %s"
                name_result = db.execute_query(name_query, (shift['agent_username'],))
                name = name_result[0]['full_name'] if name_result else 'Unknown'
            
            template = shift.get('template_name', 'Custom')
            time_range = f"{shift['start_time']} - {shift['end_time']}"
            
            # Color by shift type
            color_map = {
                'cyan': Colors.CYAN,
                'yellow': Colors.YELLOW,
                'magenta': Colors.MAGENTA,
                'green': Colors.GREEN,
                'red': Colors.RED,
                'blue': Colors.BLUE
            }
            color = color_map.get(shift.get('color', ''), Colors.RESET)
            
            status_color = Colors.GREEN if shift.get('status') == 'confirmed' else Colors.YELLOW
            
            print_color(f"{i:<4} {shift['agent_username']:<12} {name[:20]:<20} {template:<15} {time_range:<20} ", color, end='')
            print_color(f"{shift.get('status', 'scheduled')}", status_color)
    
    input("\nPress Enter to continue...")

def add_shift_interactive():
    """Interactive shift addition"""
    print_header("➕ ADD SHIFT", Colors.GREEN)
    
    # Select agent
    agent = select_agent_interactive("Select agent to schedule")
    if not agent:
        return
    
    # Get shift date
    date_input = input("Shift date (YYYY-MM-DD) or press Enter for tomorrow: ").strip()
    if date_input:
        try:
            shift_date = datetime.strptime(date_input, '%Y-%m-%d').date()
        except:
            print_error("Invalid date format")
            return
    else:
        shift_date = datetime.now().date() + timedelta(days=1)
    
    # Show templates
    templates = get_shift_templates()
    if templates:
        print("\n📋 Available templates:")
        for t in templates:
            color_map = {
                'cyan': Colors.CYAN,
                'yellow': Colors.YELLOW,
                'magenta': Colors.MAGENTA,
                'green': Colors.GREEN
            }
            color = color_map.get(t.get('color', ''), Colors.RESET)
            print_color(f"  {t['id']}. {t['name']}: {t['start']}-{t['end']} ({t['break']}min break)", color)
    
    use_template = input("\nUse template? (y/N): ").strip().lower() == 'y'
    
    template_id = None
    if use_template and templates:
        template_id_input = input("Enter template ID: ").strip()
        if template_id_input.isdigit():
            template_id = int(template_id_input)
            template = next((t for t in templates if t['id'] == template_id), None)
            if template:
                start_time = template['start']
                end_time = template['end']
                break_duration = template['break']
            else:
                print_error("Invalid template ID")
                return
        else:
            return
    else:
        # Manual entry
        start_time = input("Start time (HH:MM): ").strip()
        end_time = input("End time (HH:MM): ").strip()
        break_dur = input("Break duration (minutes) [30]: ").strip()
        break_duration = int(break_dur) if break_dur else 30
    
    # Add the shift
    shift_id = add_agent_shift(agent, shift_date, start_time, end_time, template_id, break_duration)
    if shift_id:
        print_success(f"✅ Shift added for {agent} on {shift_date} (ID: {shift_id})")
    else:
        print_error("Failed to add shift")

def show_agent_schedule():
    """Show schedule for specific agent with agent selection"""
    print_header("👤 AGENT SCHEDULE", Colors.MAGENTA)
    
    # Ensure data file exists
    ensure_schedule_file()
    
    # Use interactive agent selection
    agent = select_agent_interactive("Select agent to view schedule")
    
    if not agent:
        print_warning("No agent selected")
        input("\nPress Enter to continue...")
        return
    
    print_info(f"\n📋 Loading schedule for: {agent}")
    
    # Get agent's full name
    name_query = "SELECT full_name FROM vicidial_users WHERE user = %s"
    name_result = db.execute_query(name_query, (agent,))
    full_name = name_result[0]['full_name'] if name_result else 'Unknown'
    
    # Get date range
    print("\nSelect date range:")
    print("  1. Next 7 days")
    print("  2. Next 14 days")
    print("  3. Next 30 days")
    print("  4. This week")
    print("  5. Next week")
    print("  6. Custom range")
    
    range_choice = input("\nChoice (1-6): ").strip()
    
    today = datetime.now().date()
    
    if range_choice == '1':
        start_date = today
        end_date = today + timedelta(days=7)
    elif range_choice == '2':
        start_date = today
        end_date = today + timedelta(days=14)
    elif range_choice == '3':
        start_date = today
        end_date = today + timedelta(days=30)
    elif range_choice == '4':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif range_choice == '5':
        start_date = today + timedelta(days=(7 - today.weekday()))
        end_date = start_date + timedelta(days=6)
    elif range_choice == '6':
        start_input = input("Start date (YYYY-MM-DD): ").strip()
        end_input = input("End date (YYYY-MM-DD): ").strip()
        try:
            start_date = datetime.strptime(start_input, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_input, '%Y-%m-%d').date()
        except:
            print_error("Invalid date format")
            return
    else:
        start_date = today
        end_date = today + timedelta(days=7)
    
    shifts = get_agent_shifts(agent, start_date, end_date)
    
    print_header(f"📋 SCHEDULE: {agent} ({full_name})", Colors.CYAN)
    print(f"Period: {start_date} to {end_date}")
    print("=" * 90)
    
    if shifts:
        print(f"\n{'ID':<5} {'Date':<12} {'Day':<10} {'Shift':<15} {'Time':<20} {'Status'}")
        print("-" * 80)
        
        for shift in shifts:
            date = datetime.strptime(shift['shift_date'], '%Y-%m-%d').date()
            day_name = date.strftime('%A')
            template = shift.get('template_name', 'Custom')
            time_range = f"{shift['start_time']} - {shift['end_time']}"
            status = shift.get('status', 'scheduled')
            
            # Color by status
            if status == 'cancelled':
                color = Colors.RED
            elif status == 'confirmed':
                color = Colors.GREEN
            else:
                color = Colors.YELLOW
            
            print_color(f"{shift['id']:<5} {shift['shift_date']:<12} {day_name:<10} {template:<15} {time_range:<20} ", color, end='')
            print_color(f"{status}", color)
    else:
        print_info(f"\n📭 No shifts scheduled for {agent} in this period")
    
    # Get recent activity
    activity_query = """
    SELECT 
        DATE(event_time) as date,
        MIN(event_time) as first_login,
        MAX(event_time) as last_logout,
        COUNT(*) as status_changes
    FROM vicidial_agent_log
    WHERE user = %s
      AND event_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    GROUP BY DATE(event_time)
    ORDER BY date DESC
    """
    
    activity = db.execute_query(activity_query, (agent,))
    
    if activity:
        print(f"\n📊 RECENT ACTIVITY (Last 7 days):")
        print("-" * 70)
        print(f"{'Date':<12} {'First Login':<12} {'Last Logout':<12} {'Changes'}")
        print("-" * 70)
        
        for day in activity:
            date = day['date']
            first = day['first_login'].strftime('%H:%M') if day['first_login'] else '--'
            last = day['last_logout'].strftime('%H:%M') if day['last_logout'] else '--'
            print(f"{date:<12} {first:<12} {last:<12} {day['status_changes']:<7}")
    
    # Option to cancel a shift
    if shifts:
        print("\nOptions:")
        print("  1. Cancel a shift")
        print("  2. Back")
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        if choice == '1':
            shift_id = input("Enter shift ID to cancel: ").strip()
            if shift_id.isdigit() and cancel_shift(int(shift_id)):
                print_success("✅ Shift cancelled")
            else:
                print_error("Invalid shift ID or cancellation failed")
    
    input("\nPress Enter to continue...")

def show_adherence_report():
    """Show adherence report comparing scheduled vs actual"""
    print_header("📊 ADHERENCE REPORT", Colors.CYAN)
    
    # Ensure data file exists
    ensure_schedule_file()
    
    date_input = input("Enter date (YYYY-MM-DD) or press Enter for today: ").strip()
    if date_input:
        try:
            date = datetime.strptime(date_input, '%Y-%m-%d').date()
        except:
            print_error("Invalid date format")
            return
    else:
        date = datetime.now().date()
    
    # Get all scheduled agents for this date
    scheduled = get_daily_shifts(date)
    
    if not scheduled:
        print_warning(f"No shifts scheduled for {date}")
        input("\nPress Enter to continue...")
        return
    
    print_header(f"📊 ADHERENCE REPORT - {date}", Colors.MAGENTA)
    print("=" * 110)
    print(f"{'Agent':<12} {'Name':<20} {'Scheduled':<20} {'Actual':<20} {'Adherence'} {'Status'}")
    print("=" * 110)
    
    on_time = 0
    late = 0
    no_show = 0
    
    for shift in scheduled:
        agent = shift['agent_username']
        
        # Get agent name
        name = "Unknown"
        if AGENT_FUNCTIONS_AVAILABLE:
            name_query = "SELECT full_name FROM vicidial_users WHERE user = %s"
            name_result = db.execute_query(name_query, (agent,))
            name = name_result[0]['full_name'] if name_result else 'Unknown'
        
        scheduled_time = f"{shift['start_time']} - {shift['end_time']}"
        
        # Get actual login for this agent on this date
        login_query = """
        SELECT 
            MIN(event_time) as first_login,
            MAX(event_time) as last_logout,
            COUNT(*) as events
        FROM vicidial_agent_log
        WHERE user = %s
          AND DATE(event_time) = %s
        """
        
        login = db.execute_query(login_query, (agent, date))
        
        if login and login[0]['first_login']:
            first = login[0]['first_login']
            last = login[0]['last_logout']
            
            first_str = first.strftime('%H:%M') if first else '--'
            last_str = last.strftime('%H:%M') if last else '--'
            actual_time = f"{first_str} - {last_str}"
            
            # Calculate lateness
            if first:
                scheduled_start = datetime.strptime(f"{date} {shift['start_time']}", "%Y-%m-%d %H:%M")
                if first > scheduled_start:
                    late_minutes = int((first - scheduled_start).total_seconds() / 60)
                    adherence = f"Late by {late_minutes} min"
                    color = Colors.YELLOW
                    late += 1
                else:
                    adherence = "✅ On time"
                    color = Colors.GREEN
                    on_time += 1
                
                status = "Working"
            else:
                actual_time = "No activity"
                adherence = "❌ No show"
                color = Colors.RED
                no_show += 1
                status = "No show"
        else:
            actual_time = "No login"
            adherence = "❌ No show"
            color = Colors.RED
            no_show += 1
            status = "No show"
        
        print_color(f"{agent:<12} {name[:20]:<20} {scheduled_time:<20} {actual_time:<20} {adherence:<15} {status}", color)
    
    print("=" * 110)
    print(f"Summary: ✅ On time: {on_time} | ⚠️ Late: {late} | ❌ No show: {no_show}")
    
    input("\nPress Enter to continue...")

def manage_shift_templates():
    """Manage shift templates"""
    print_header("⏰ SHIFT TEMPLATES", Colors.GREEN)
    
    # Ensure data file exists
    ensure_schedule_file()
    
    while True:
        templates = get_shift_templates()
        
        if templates:
            print("\n📋 Current Templates:")
            print("-" * 90)
            print(f"{'ID':<5} {'Template':<20} {'Start':<8} {'End':<8} {'Break':<8} {'Color':<10} {'Description'}")
            print("-" * 90)
            
            for t in templates:
                # Map color name to actual color
                color_map = {
                    'cyan': Colors.CYAN,
                    'yellow': Colors.YELLOW,
                    'magenta': Colors.MAGENTA,
                    'green': Colors.GREEN,
                    'red': Colors.RED,
                    'blue': Colors.BLUE,
                    'white': Colors.RESET
                }
                color = color_map.get(t.get('color', ''), Colors.RESET)
                
                print_color(
                    f"{t['id']:<5} {t['name']:<20} {t['start']:<8} {t['end']:<8} "
                    f"{t['break']}min{' ':<5} {t.get('color', 'white'):<10} {t.get('description', '')[:30]}",
                    color
                )
        else:
            print_warning("No templates found")
        
        print("\nOptions:")
        print("  1. ➕ Create new template")
        print("  2. ✏️ Edit template")
        print("  3. 🗑️ Delete template")
        print("  0. 🔙 Back")
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            # Create new template
            print("\n📝 New Shift Template")
            print("-" * 40)
            
            name = input("Template name: ").strip()
            if not name:
                print_error("Name is required")
                input("\nPress Enter to continue...")
                continue
            
            start = input("Start time (HH:MM): ").strip()
            if not start:
                print_error("Start time is required")
                input("\nPress Enter to continue...")
                continue
            
            end = input("End time (HH:MM): ").strip()
            if not end:
                print_error("End time is required")
                input("\nPress Enter to continue...")
                continue
            
            break_dur = input("Break duration (minutes) [30]: ").strip()
            break_duration = int(break_dur) if break_dur else 30
            
            description = input("Description (optional): ").strip()
            
            print("\nAvailable colors: cyan, yellow, magenta, green, blue, red, white")
            color = input("Color [white]: ").strip().lower() or 'white'
            
            if create_shift_template(name, start, end, break_duration, description, color):
                print_success(f"✅ Template '{name}' created")
        
        elif choice == '2' and templates:
            # Edit template
            template_id = input("Enter template ID to edit: ").strip()
            if template_id.isdigit():
                template_id = int(template_id)
                template = next((t for t in templates if t['id'] == template_id), None)
                
                if template:
                    print(f"\n✏️ Editing: {template['name']}")
                    print("(Press Enter to keep current value)")
                    
                    new_name = input(f"Name [{template['name']}]: ").strip()
                    new_start = input(f"Start time [{template['start']}]: ").strip()
                    new_end = input(f"End time [{template['end']}]: ").strip()
                    new_break = input(f"Break duration [{template['break']}]: ").strip()
                    new_desc = input(f"Description [{template.get('description', '')}]: ").strip()
                    new_color = input(f"Color [{template.get('color', 'white')}]: ").strip().lower()
                    
                    updates = {}
                    if new_name:
                        updates['name'] = new_name
                    if new_start:
                        updates['start'] = new_start
                    if new_end:
                        updates['end'] = new_end
                    if new_break:
                        updates['break'] = int(new_break)
                    if new_desc:
                        updates['description'] = new_desc
                    if new_color:
                        updates['color'] = new_color
                    
                    if updates and update_shift_template(template_id, **updates):
                        print_success("✅ Template updated")
                    else:
                        print_info("No changes made")
                else:
                    print_error("Template not found")
        
        elif choice == '3' and templates:
            # Delete template
            template_id = input("Enter template ID to delete: ").strip()
            if template_id.isdigit():
                template_id = int(template_id)
                template = next((t for t in templates if t['id'] == template_id), None)
                
                if template:
                    print_warning(f"⚠️ Delete template: {template['name']}?")
                    confirm = input("This cannot be undone. Type 'yes' to confirm: ").strip().lower()
                    
                    if confirm == 'yes':
                        if delete_shift_template(template_id):
                            print_success("✅ Template deleted")
                        else:
                            print_error("Failed to delete template - it may be in use")
                else:
                    print_error("Template not found")
        
        elif choice == '0':
            break
        
        input("\nPress Enter to continue...")

# =============================================================================
# Main Menu
# =============================================================================

def schedule_menu():
    """Main schedule management menu"""
    while True:
        print_header("📅 SCHEDULE MANAGEMENT", Colors.CYAN)
        print("  1. 📋 Today's Schedule")
        print("  2. 👤 Agent Schedule")
        print("  3. 📊 Adherence Report")
        print("  4. ⏰ Shift Templates")
        print("  5. ⚙️ Configure Settings")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_daily_schedule()
        elif choice == '2':
            show_agent_schedule()
        elif choice == '3':
            show_adherence_report()
        elif choice == '4':
            manage_shift_templates()
        elif choice == '5':
            print_header("⚙️ SCHEDULE SETTINGS", Colors.YELLOW)
            print("\n🚧 Configuration - Coming Soon! 🚧")
            print("\nFuture features:")
            print("  • Auto-notifications for schedule changes")
            print("  • Email reminders")
            print("  • Shift swapping")
            print("  • Time-off requests")
            input("\nPress Enter to continue...")
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    schedule_menu()