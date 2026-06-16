# config/campaign_hours.py - Campaign operating hours configuration

import os
import json
from datetime import datetime, time, timedelta
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning

# Configuration file path
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
CAMPAIGN_HOURS_FILE = os.path.join(CONFIG_DIR, 'campaign_hours.json')

# Default operating hours (24/7)
DEFAULT_HOURS = {
    'start': '00:00',
    'end': '23:59',
    'timezone': 'EST',
    'crosses_midnight': False
}

# Campaign-specific hours (defaults - will be merged with DB campaigns)
DEFAULT_CAMPAIGN_HOURS = {
    'Xshield': {
        'start': '22:00',  # 10 PM
        'end': '18:00',    # 6 PM (next day)
        'timezone': 'EST',
        'crosses_midnight': True
    },
    'XCHANGE': {
        'start': '09:00',
        'end': '19:00',
        'timezone': 'EST',
        'crosses_midnight': False
    },
    'TodosGamersCS': {
        'start': '08:00',
        'end': '20:00',
        'timezone': 'EST',
        'crosses_midnight': False
    },
    'UpliftDeals': {
        'start': '09:00',
        'end': '21:00',
        'timezone': 'EST',
        'crosses_midnight': False
    },
    'SAVVYCS': {
        'start': '08:00',
        'end': '20:00',
        'timezone': 'EST',
        'crosses_midnight': False
    },
    'K1': {
        'start': '09:00',
        'end': '17:00',
        'timezone': 'EST',
        'crosses_midnight': False
    },
    'Zappify': {
        'start': '08:00',
        'end': '22:00',
        'timezone': 'EST',
        'crosses_midnight': False
    },
    'YPDirect': {
        'start': '09:00',
        'end': '18:00',
        'timezone': 'EST',
        'crosses_midnight': False
    },
    'DignityBioLabs': {
        'start': '09:00',
        'end': '17:00',
        'timezone': 'EST',
        'crosses_midnight': False
    }
}

def get_all_campaigns_from_db():
    """Get all campaigns from vicidial_campaigns table"""
    try:
        query = "SELECT campaign_id FROM vicidial_campaigns WHERE active = 'Y' ORDER BY campaign_id"
        results = db.execute_query(query)
        return [row['campaign_id'] for row in results] if results else []
    except Exception as e:
        print_error(f"Error fetching campaigns from database: {e}")
        return []

def load_campaign_hours():
    """Load campaign hours from JSON file, create with defaults if not exists"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    
    # Get all campaigns from database
    db_campaigns = get_all_campaigns_from_db()
    
    if os.path.exists(CAMPAIGN_HOURS_FILE):
        try:
            with open(CAMPAIGN_HOURS_FILE, 'r') as f:
                config = json.load(f)
            
            # Remove any campaigns that no longer exist in database
            campaigns_to_remove = []
            for campaign in config:
                if campaign not in db_campaigns and campaign not in DEFAULT_CAMPAIGN_HOURS:
                    campaigns_to_remove.append(campaign)
            
            for campaign in campaigns_to_remove:
                del config[campaign]
            
            # Add any new campaigns from database that aren't in config
            for campaign in db_campaigns:
                if campaign not in config:
                    # Use default hours if available, otherwise use 24/7
                    if campaign in DEFAULT_CAMPAIGN_HOURS:
                        config[campaign] = DEFAULT_CAMPAIGN_HOURS[campaign].copy()
                    else:
                        config[campaign] = DEFAULT_HOURS.copy()
            
            save_campaign_hours(config)
            return config
            
        except Exception as e:
            print_error(f"Error loading campaign hours: {e}")
            return create_default_config(db_campaigns)
    else:
        return create_default_config(db_campaigns)

def create_default_config(db_campaigns):
    """Create default configuration based on database campaigns"""
    config = {}
    
    # Add all database campaigns with their default hours or 24/7
    for campaign in db_campaigns:
        if campaign in DEFAULT_CAMPAIGN_HOURS:
            config[campaign] = DEFAULT_CAMPAIGN_HOURS[campaign].copy()
        else:
            config[campaign] = DEFAULT_HOURS.copy()
    
    # Save the config
    save_campaign_hours(config)
    return config

def save_campaign_hours(hours_config):
    """Save campaign hours to JSON file"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CAMPAIGN_HOURS_FILE, 'w') as f:
            json.dump(hours_config, f, indent=2)
        return True
    except Exception as e:
        print_error(f"Error saving campaign hours: {e}")
        return False

def get_campaign_hours(campaign_id):
    """Get operating hours for a specific campaign"""
    hours_config = load_campaign_hours()
    return hours_config.get(campaign_id, DEFAULT_HOURS.copy())

def is_within_operating_hours(campaign_id, call_datetime):
    """Check if a call datetime is within campaign operating hours"""
    hours = get_campaign_hours(campaign_id)
    
    start_str = hours.get('start', DEFAULT_HOURS['start'])
    end_str = hours.get('end', DEFAULT_HOURS['end'])
    crosses_midnight = hours.get('crosses_midnight', False)
    
    # Parse times
    start_time = datetime.strptime(start_str, '%H:%M').time()
    end_time = datetime.strptime(end_str, '%H:%M').time()
    call_time = call_datetime.time()
    
    if crosses_midnight:
        # Overnight campaign (e.g., 22:00 to 06:00 next day)
        if start_time <= end_time:
            # This shouldn't happen for overnight, but handle it
            return start_time <= call_time <= end_time
        else:
            # Time range crosses midnight
            return call_time >= start_time or call_time <= end_time
    else:
        # Normal same-day campaign
        return start_time <= call_time <= end_time

def filter_calls_by_operating_hours(campaign_id, calls_data, datetime_field='call_date'):
    """Filter a list of calls to only include those within operating hours"""
    hours = get_campaign_hours(campaign_id)
    start_str = hours.get('start', DEFAULT_HOURS['start'])
    end_str = hours.get('end', DEFAULT_HOURS['end'])
    crosses_midnight = hours.get('crosses_midnight', False)
    
    start_time = datetime.strptime(start_str, '%H:%M').time()
    end_time = datetime.strptime(end_str, '%H:%M').time()
    
    filtered = []
    outside_hours = []
    
    for call in calls_data:
        call_time = call[datetime_field].time()
        
        if crosses_midnight:
            if start_time <= end_time:
                # Shouldn't happen, but handle
                is_within = start_time <= call_time <= end_time
            else:
                is_within = call_time >= start_time or call_time <= end_time
        else:
            is_within = start_time <= call_time <= end_time
        
        if is_within:
            filtered.append(call)
        else:
            outside_hours.append(call)
    
    return filtered, outside_hours

def format_operating_hours(campaign_id):
    """Get formatted string of operating hours for display"""
    hours = get_campaign_hours(campaign_id)
    start = hours.get('start', '00:00')
    end = hours.get('end', '23:59')
    tz = hours.get('timezone', 'EST')
    
    if hours.get('crosses_midnight', False):
        return f"{start} to {end} (next day) {tz}"
    else:
        return f"{start} to {end} {tz}"

def get_operating_hours_for_query(campaign_id, date):
    """Get SQL conditions for operating hours filter"""
    hours = get_campaign_hours(campaign_id)
    start_str = hours.get('start', '00:00')
    end_str = hours.get('end', '23:59')
    crosses_midnight = hours.get('crosses_midnight', False)
    
    start_hour, start_min = map(int, start_str.split(':'))
    end_hour, end_min = map(int, end_str.split(':'))
    
    if crosses_midnight:
        # For overnight campaigns, we need to check both sides of midnight
        if start_hour <= end_hour:
            # This shouldn't happen, but handle
            return f"(HOUR(call_date) BETWEEN {start_hour} AND {end_hour} OR (HOUR(call_date) = {end_hour} AND MINUTE(call_date) <= {end_min}))"
        else:
            # Time crosses midnight
            return f"(HOUR(call_date) >= {start_hour} OR HOUR(call_date) <= {end_hour} OR (HOUR(call_date) = {end_hour} AND MINUTE(call_date) <= {end_min}))"
    else:
        # Normal hours
        if start_hour == end_hour:
            return f"(HOUR(call_date) = {start_hour} AND MINUTE(call_date) BETWEEN {start_min} AND {end_min})"
        else:
            return f"((HOUR(call_date) > {start_hour} OR (HOUR(call_date) = {start_hour} AND MINUTE(call_date) >= {start_min})) AND (HOUR(call_date) < {end_hour} OR (HOUR(call_date) = {end_hour} AND MINUTE(call_date) <= {end_min})))"

def get_date_range_with_hours(campaign_id, start_date, end_date):
    """Get date range adjusted for overnight campaigns"""
    hours = get_campaign_hours(campaign_id)
    crosses_midnight = hours.get('crosses_midnight', False)
    
    if crosses_midnight:
        # For overnight campaigns, we need to include the next day's early hours
        # For example, if querying Feb 14, include Feb 14 22:00-23:59 and Feb 15 00:00-06:00
        next_day = end_date + timedelta(days=1)
        return start_date, next_day
    else:
        return start_date, end_date

def manage_campaign_hours_menu():
    """Interactive menu to manage campaign operating hours"""
    
    while True:
        # Reload campaigns from database each time
        db_campaigns = get_all_campaigns_from_db()
        hours_config = load_campaign_hours()
        
        print_header("⏰ CAMPAIGN OPERATING HOURS", Colors.CYAN)
        print("\nCurrent Campaign Hours:")
        print("-" * 70)
        print(f"{'Campaign':<20} {'Hours':<30} {'Timezone':<10} {'Status':<10}")
        print("-" * 70)
        
        # Show all campaigns from database
        for campaign in sorted(db_campaigns):
            if campaign in hours_config:
                hours = hours_config[campaign]
                start = hours.get('start', '00:00')
                end = hours.get('end', '23:59')
                tz = hours.get('timezone', 'EST')
                overnight = " (next day)" if hours.get('crosses_midnight', False) else ""
                status = "✅ Configured"
                color = Colors.GREEN
            else:
                # Campaign exists but no config (shouldn't happen with new code)
                start = '00:00'
                end = '23:59'
                tz = 'EST'
                overnight = ""
                status = "⚠️ Default"
                color = Colors.YELLOW
            
            print_color(f"{campaign:<20} {start} - {end}{overnight:<20} {tz:<10} {status:<10}", color)
        
        # Show any campaigns in config that are NOT in database (orphaned)
        orphans = [c for c in hours_config if c not in db_campaigns]
        if orphans:
            print_color("\n⚠️ Orphaned Campaigns (not in database):", Colors.RED)
            for campaign in orphans:
                print_color(f"  • {campaign}", Colors.RED)
        
        print("-" * 70)
        print(f"\nTotal Active Campaigns in Database: {len(db_campaigns)}")
        print("\nOptions:")
        print("  1. ✏️ Edit Campaign Hours")
        print("  2. 🔄 Sync with Database")  # Changed from Add New Campaign
        print("  3. ❌ Remove Orphaned Campaigns")  # Changed from Delete Campaign
        print("  4. 🔄 Reset to Defaults")
        print("  0. 🔙 Back")
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            edit_campaign_hours(hours_config, db_campaigns)
        elif choice == '2':
            # Sync with database (reload from DB)
            print_success("Syncing with database...")
            load_campaign_hours()  # This will refresh the config
        elif choice == '3':
            remove_orphaned_campaigns(hours_config, db_campaigns)
        elif choice == '4':
            reset_to_defaults(db_campaigns)
        elif choice == '0':
            break

def edit_campaign_hours(hours_config, db_campaigns):
    """Edit hours for an existing campaign"""
    
    print("\nAvailable Campaigns:")
    for i, campaign in enumerate(sorted(db_campaigns), 1):
        print(f"  {i}. {campaign}")
    
    campaign = input("\nEnter campaign name or number: ").strip()
    
    # Check if input is a number
    if campaign.isdigit():
        idx = int(campaign) - 1
        if 0 <= idx < len(db_campaigns):
            campaign = sorted(db_campaigns)[idx]
        else:
            print_error("Invalid campaign number")
            return
    else:
        # Check if campaign exists in database
        if campaign not in db_campaigns:
            print_error(f"Campaign '{campaign}' not found in database")
            return
    
    current = hours_config.get(campaign, DEFAULT_HOURS.copy())
    print(f"\nEditing {campaign}")
    print(f"Current: {current.get('start')} - {current.get('end')} {current.get('timezone')}")
    
    start = input("Start time (HH:MM, 24h format) [Enter to keep]: ").strip()
    end = input("End time (HH:MM, 24h format) [Enter to keep]: ").strip()
    tz = input("Timezone [EST] [Enter to keep]: ").strip()
    
    if campaign not in hours_config:
        hours_config[campaign] = DEFAULT_HOURS.copy()
    
    if start:
        hours_config[campaign]['start'] = start
    if end:
        hours_config[campaign]['end'] = end
    if tz:
        hours_config[campaign]['timezone'] = tz
    
    # Auto-detect if crosses midnight
    if start or end:
        start_h = int(hours_config[campaign]['start'].split(':')[0])
        end_h = int(hours_config[campaign]['end'].split(':')[0])
        hours_config[campaign]['crosses_midnight'] = start_h > end_h
    
    save_campaign_hours(hours_config)
    print_success(f"Updated hours for {campaign}")

def remove_orphaned_campaigns(hours_config, db_campaigns):
    """Remove campaigns that no longer exist in database"""
    orphans = [c for c in hours_config if c not in db_campaigns]
    
    if not orphans:
        print_warning("No orphaned campaigns found")
        return
    
    print("\nOrphaned Campaigns:")
    for i, campaign in enumerate(orphans, 1):
        print(f"  {i}. {campaign}")
    
    if input(f"\nRemove all {len(orphans)} orphaned campaigns? (y/N): ").lower() == 'y':
        for campaign in orphans:
            del hours_config[campaign]
        save_campaign_hours(hours_config)
        print_success(f"Removed {len(orphans)} orphaned campaigns")

def reset_to_defaults(db_campaigns):
    """Reset all campaigns to default hours"""
    if input("\nReset ALL campaigns to default hours? (y/N): ").lower() == 'y':
        new_config = {}
        for campaign in db_campaigns:
            if campaign in DEFAULT_CAMPAIGN_HOURS:
                new_config[campaign] = DEFAULT_CAMPAIGN_HOURS[campaign].copy()
            else:
                new_config[campaign] = DEFAULT_HOURS.copy()
        
        save_campaign_hours(new_config)
        print_success("All campaigns reset to default hours!")

if __name__ == "__main__":
    manage_campaign_hours_menu()