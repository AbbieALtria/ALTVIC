# utils/campaign_selector.py - Universal campaign selector that shows ALL campaigns

from core.database import db
from utils.colors import Colors, print_color, print_header, print_error, print_warning
from utils.unified_search import (
    search_campaigns, 
    search_ingroups,
    print_campaign_results,
    print_ingroup_results
)
import math

def get_all_campaigns():
    """Get ALL campaigns using unified search - NO hardcoding"""
    try:
        # Use unified search to get campaigns with empty search term (returns all)
        campaigns = search_campaigns("", active_filter="ALL", limit=1000)
        if campaigns:
            return [c['campaign_id'] for c in campaigns]
    except Exception:
        pass
    
    # Fallback to direct query if unified search fails
    try:
        query = "SELECT campaign_id FROM vicidial_campaigns ORDER BY campaign_id"
        results = db.execute_query(query)
        if results:
            return [r['campaign_id'] for r in results]
    except Exception:
        pass
    
    return []

def get_all_inbound_groups():
    """Get ALL inbound groups using unified search - NO hardcoding"""
    try:
        # Use unified search to get groups with empty search term (returns all)
        groups = search_ingroups("", active_filter="ALL", limit=1000)
        if groups:
            return [g['group_id'] for g in groups]
    except Exception:
        pass
    
    # Fallback to direct query if unified search fails
    try:
        query = "SELECT group_id FROM vicidial_inbound_groups ORDER BY group_id"
        results = db.execute_query(query)
        if results:
            return [r['group_id'] for r in results]
    except Exception:
        pass
    
    return []

def search_items(search_type, term, active_filter="ALL", limit=50):
    """Search for campaigns or inbound groups using unified search"""
    if search_type == "campaigns":
        return search_campaigns(term, active_filter, limit)
    elif search_type == "ingroups":
        return search_ingroups(term, active_filter, limit)
    else:
        return []

def display_items_paginated(items, item_type="campaigns", page=1, page_size=20):
    """Display paginated results with navigation"""
    total_items = len(items)
    total_pages = math.ceil(total_items / page_size)
    start = (page - 1) * page_size
    end = min(start + page_size, total_items)
    
    while True:
        # Use the unified search print functions
        if item_type == "campaigns":
            print_campaign_results(items[start:end])
        else:
            print_ingroup_results(items[start:end])
        
        print(f"\nShowing {start+1}-{end} of {total_items} items")
        
        # Navigation options
        print("\nOptions:")
        print("  • Enter NUMBER to select an item")
        if page < total_pages:
            print("  • 'n' for next page")
        if page > 1:
            print("  • 'p' for previous page")
        print("  • 'q' to quit")
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip().lower()
        
        if choice == 'q':
            return None
        elif choice == 'n' and page < total_pages:
            page += 1
            start = (page - 1) * page_size
            end = min(start + page_size, total_items)
        elif choice == 'p' and page > 1:
            page -= 1
            start = (page - 1) * page_size
            end = min(start + page_size, total_items)
        elif choice.isdigit():
            idx = int(choice) - 1
            if start <= idx < end:
                return items[idx]
            else:
                print_error(f"Please enter a number between {start+1} and {end}")
        else:
            print_warning("Invalid option")

def select_campaign(prompt="Select campaign (or press Enter for all):"):
    """Universal campaign selector using unified search"""
    
    # Get ALL campaigns
    campaigns = get_all_campaigns()
    
    if not campaigns:
        print_error("No campaigns found in database")
        return None
    
    # Convert to format expected by display
    campaign_items = [{'campaign_id': c, 'campaign_name': '', 'active': ''} for c in campaigns]
    
    page = 1
    page_size = 20
    
    while True:
        selected = display_items_paginated(campaign_items, "campaigns", page, page_size)
        
        if selected is None:  # User quit
            return None
        elif selected:
            return selected.get('campaign_id')
        
        # If we get here, user might have entered something that wasn't handled
        print_error("Invalid selection")
        continue

def select_inbound_group(prompt="Select inbound group (or press Enter for all):"):
    """Universal inbound group selector using unified search"""
    
    # Get ALL inbound groups
    groups = get_all_inbound_groups()
    
    if not groups:
        print_error("No inbound groups found in database")
        return None
    
    # Convert to format expected by display
    group_items = [{'group_id': g, 'group_name': '', 'active': ''} for g in groups]
    
    page = 1
    page_size = 20
    
    while True:
        selected = display_items_paginated(group_items, "ingroups", page, page_size)
        
        if selected is None:  # User quit
            return None
        elif selected:
            return selected.get('group_id')
        
        # If we get here, user might have entered something that wasn't handled
        print_error("Invalid selection")
        continue