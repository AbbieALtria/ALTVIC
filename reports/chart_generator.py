# reports/chart_generator.py - Generate charts using unified search pagination

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info

# Try to import matplotlib
try:
    import matplotlib
    matplotlib.use('TkAgg')  # Use interactive backend for showing charts
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from datetime import datetime, timedelta
import os

from core.database import db
from utils.formatter import sec_to_hms, format_datetime

# Import unified search functions
try:
    from utils.unified_search import (
        search_campaigns,
        search_ingroups,
        print_campaign_results,
        print_ingroup_results,
        show_paginated_results
    )
    UNIFIED_SEARCH_AVAILABLE = True
except ImportError as e:
    UNIFIED_SEARCH_AVAILABLE = False
    print_warning(f"⚠️ Unified search not available: {e}")

def ensure_charts_dir():
    """Ensure charts directory exists"""
    charts_dir = Path(__file__).parent / 'exports' / 'charts'
    charts_dir.mkdir(parents=True, exist_ok=True)
    return charts_dir

def get_all_campaign_sources():
    """Get campaigns from ALL sources - campaigns table AND inbound groups"""
    all_campaigns = []
    campaign_ids = set()  # Use set to avoid duplicates
    
    try:
        # Source 1: vicidial_campaigns table
        query1 = """
        SELECT 
            campaign_id, 
            campaign_name, 
            active,
            'campaign' as source
        FROM vicidial_campaigns 
        ORDER BY campaign_id
        """
        results1 = db.execute_query(query1)
        if results1:
            for r in results1:
                if r['campaign_id'] and r['campaign_id'].strip() not in campaign_ids:
                    campaign_ids.add(r['campaign_id'].strip())
                    all_campaigns.append({
                        'campaign_id': r['campaign_id'],
                        'campaign_name': r.get('campaign_name', ''),
                        'active': r.get('active', 'Y'),
                        'source': 'campaign'
                    })
        
        # Source 2: vicidial_inbound_groups (these are your missing campaigns!)
        query2 = """
        SELECT 
            group_id as campaign_id,
            group_name as campaign_name,
            active,
            'inbound_group' as source
        FROM vicidial_inbound_groups 
        WHERE active = 'Y'
        ORDER BY group_id
        """
        results2 = db.execute_query(query2)
        if results2:
            for r in results2:
                if r['campaign_id'] and r['campaign_id'].strip() not in campaign_ids:
                    campaign_ids.add(r['campaign_id'].strip())
                    all_campaigns.append({
                        'campaign_id': r['campaign_id'],
                        'campaign_name': r.get('campaign_name', ''),
                        'active': 'Y',
                        'source': 'inbound_group'
                    })
        
        # Source 3: vicidial_closer_log (campaigns that have had calls)
        query3 = """
        SELECT DISTINCT 
            campaign_id,
            '' as campaign_name,
            'Y' as active,
            'call_log' as source
        FROM vicidial_closer_log
        WHERE campaign_id IS NOT NULL 
          AND campaign_id != ''
        ORDER BY campaign_id
        LIMIT 200
        """
        results3 = db.execute_query(query3)
        if results3:
            for r in results3:
                if r['campaign_id'] and r['campaign_id'].strip() not in campaign_ids:
                    campaign_ids.add(r['campaign_id'].strip())
                    all_campaigns.append({
                        'campaign_id': r['campaign_id'],
                        'campaign_name': '',
                        'active': 'Y',
                        'source': 'call_log'
                    })
        
        # Sort by campaign_id
        all_campaigns.sort(key=lambda x: x['campaign_id'])
        
        print_info(f"📊 Found {len(all_campaigns)} total campaigns from all sources")
        print_info(f"   • Campaigns table: {len([c for c in all_campaigns if c['source'] == 'campaign'])}")
        print_info(f"   • Inbound groups: {len([c for c in all_campaigns if c['source'] == 'inbound_group'])}")
        print_info(f"   • Call log entries: {len([c for c in all_campaigns if c['source'] == 'call_log'])}")
        
        return all_campaigns
        
    except Exception as e:
        print_error(f"Error loading campaigns: {e}")
        return []

def select_campaign_with_search():
    """Select campaign using unified search pagination - SHOW ALL CAMPAIGNS"""
    print_header("🔍 SELECT CAMPAIGN FOR CHART", Colors.CYAN)
    
    # Get ALL campaigns from all sources
    campaigns = get_all_campaign_sources()
    
    if not campaigns:
        print_warning("No campaigns found")
        return None
    
    # Calculate total pages
    total_campaigns = len(campaigns)
    print_header(f"📋 ALL CAMPAIGNS & INBOUND GROUPS  |  Total: {total_campaigns}", Colors.CYAN)
    
    # Convert to format expected by show_paginated_results
    display_items = []
    for c in campaigns:
        display_items.append({
            'campaign_id': c['campaign_id'],
            'campaign_name': c['campaign_name'],
            'active': c['active']
        })
    
    # Show paginated results
    selected = show_paginated_results(display_items, item_type="campaigns", page=1, page_size=20)
    
    if selected:
        campaign_id = selected.get('campaign_id')
        print_color(f"✅ Selected: {campaign_id}", Colors.GREEN)
        return campaign_id
    
    return None  # User cancelled or pressed Enter for all

def generate_and_show_chart(campaign=None, days=30):
    """Generate chart and show it on screen, return the figure"""
    if not MATPLOTLIB_AVAILABLE or not NUMPY_AVAILABLE:
        print_error("Required libraries not installed. Run: pip install matplotlib numpy")
        return None, None
    
    try:
        # Build query
        where_clause = "WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)"
        params = [days]
        
        if campaign:
            where_clause += " AND campaign_id = %s"
            params.append(campaign)
        
        query = f"""
        SELECT 
            DATE(call_date) as date,
            COUNT(*) as calls
        FROM vicidial_closer_log
        {where_clause}
        GROUP BY DATE(call_date)
        ORDER BY date
        """
        
        results = db.execute_query(query, params)
        
        if not results:
            print_warning("No data available for the selected period")
            return None, None
        
        # Extract data
        dates = [r['date'] for r in results]
        calls = [r['calls'] for r in results]
        
        # Create chart
        plt.figure(figsize=(12, 6))
        plt.plot(dates, calls, marker='o', linestyle='-', linewidth=2, markersize=4, color='#3498db')
        
        # Formatting
        title = f'Daily Call Volume Trend'
        if campaign:
            title += f' - {campaign}'
        else:
            title += ' - All Campaigns'
        plt.title(title, fontsize=16, fontweight='bold')
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Number of Calls', fontsize=12)
        plt.grid(True, alpha=0.3)
        
        # Format x-axis dates
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days//10)))
        plt.xticks(rotation=45)
        
        # Add trend line
        if len(calls) > 1:
            z = np.polyfit(range(len(calls)), calls, 1)
            p = np.poly1d(z)
            plt.plot(dates, p(range(len(calls))), "r--", alpha=0.7, label='Trend Line')
            plt.legend()
        
        plt.tight_layout()
        
        # Show the chart
        plt.show(block=False)
        plt.pause(0.1)  # Small pause to ensure window appears
        
        print_success("✅ Chart displayed on screen")
        
        return plt.gcf(), {
            'dates': dates,
            'calls': calls,
            'title': title,
            'campaign': campaign,
            'days': days
        }
        
    except Exception as e:
        print_error(f"Error generating chart: {e}")
        return None, None

def save_chart(fig, campaign=None, days=30):
    """Save the chart to a file"""
    if not fig:
        return False
    
    charts_dir = ensure_charts_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    camp_part = f"_{campaign}" if campaign else "_all"
    filename = charts_dir / f"daily_trend{camp_part}_{timestamp}.png"
    
    try:
        fig.savefig(filename, dpi=150, bbox_inches='tight')
        print_success(f"✅ Chart saved to: {filename}")
        
        # Ask if they want to open the folder
        open_choice = input("\n📂 Open the folder containing the chart? (y/N): ").strip().lower()
        if open_choice == 'y':
            if os.name == 'nt':  # Windows
                os.startfile(charts_dir)
            else:  # Linux/Mac
                import subprocess
                subprocess.run(['xdg-open', str(charts_dir)])
        
        return True
    except Exception as e:
        print_error(f"Error saving chart: {e}")
        return False

def open_charts_folder():
    """Open the charts folder"""
    charts_dir = ensure_charts_dir()
    print(f"\n📁 Opening: {charts_dir}")
    try:
        if os.name == 'nt':  # Windows
            os.startfile(charts_dir)
        else:  # Linux/Mac
            import subprocess
            subprocess.run(['xdg-open', str(charts_dir)])
        print_success("✅ Folder opened")
        return True
    except Exception as e:
        print_error(f"Could not open folder: {e}")
        return False

def charts_menu():
    """Main charts menu"""
    if not MATPLOTLIB_AVAILABLE:
        print_header("📊 CHART GENERATOR", Colors.CYAN)
        print("=" * 70)
        print_error("❌ matplotlib is not installed!")
        print_info("\n📦 Required packages:")
        print("   pip install matplotlib numpy")
        print("\nAfter installation, restart the application.")
        print("=" * 70)
        input("\nPress Enter to continue...")
        return
    
    while True:
        print_header("📊 CHART GENERATOR", Colors.CYAN)
        print("  1. 📈 Daily Trend Chart")
        print("  2. 📁 Open Charts Folder")
        print("  0. 🔙 Back")
        print("-" * 70)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            print("\n📈 DAILY TREND CHART")
            print("=" * 50)
            
            # Get ALL campaigns from all sources
            campaign = select_campaign_with_search()
            
            if campaign is None:
                print_info("Selected: ALL CAMPAIGNS")
            else:
                print_info(f"Selected: {campaign}")
            
            days = input("Days to analyze (default 30): ").strip()
            days = int(days) if days.isdigit() else 30
            
            print(f"\n📊 Generating chart...")
            
            # Generate and show the chart
            fig, chart_data = generate_and_show_chart(campaign, days)
            
            if fig:
                print("\n" + "-" * 70)
                print("Chart Statistics:")
                if chart_data and chart_data.get('calls'):
                    total_calls = sum(chart_data['calls'])
                    avg_calls = total_calls / len(chart_data['calls'])
                    print(f"  • Total Calls: {total_calls}")
                    print(f"  • Daily Average: {avg_calls:.1f}")
                    print(f"  • Peak Day: {max(chart_data['calls'])} calls")
                
                print("\n" + "-" * 70)
                save_choice = input("💾 Would you like to save this chart? (y/N): ").strip().lower()
                
                if save_choice == 'y':
                    save_chart(fig, campaign, days)
                
                # Close the figure to free memory
                plt.close(fig)
            else:
                print_error("Failed to generate chart - no data available")
            
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            open_charts_folder()
            input("\nPress Enter to continue...")
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    charts_menu()