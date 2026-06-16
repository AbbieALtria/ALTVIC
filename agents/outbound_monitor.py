# agents/outbound_monitor.py - Real-time outbound dialer monitoring

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms, time_ago

def get_outbound_agents():
    """Get agents currently on outbound calls"""
    print_header("📞 OUTBOUND DIALER - LIVE MONITOR", Colors.CYAN)
    
    try:
        # First, let's get all outbound campaigns - FIXED: escaped % signs with %%
        outbound_campaigns_query = """
        SELECT campaign_id 
        FROM vicidial_campaigns 
        WHERE campaign_allow_inbound = 'N' 
           OR campaign_id LIKE '%%outbound%%' 
           OR campaign_id LIKE '%%dial%%'
        """
        
        outbound_campaigns = db.execute_query(outbound_campaigns_query)
        campaign_list = [c['campaign_id'] for c in outbound_campaigns] if outbound_campaigns else []
        
        # Add known outbound campaigns
        known_outbound = ['YPDirect', 'Hotpro', 'BabiTrump', 'K1', 'Boxco', 'Aiven']
        for campaign in known_outbound:
            if campaign not in campaign_list:
                campaign_list.append(campaign)
        
        if not campaign_list:
            print_warning("No outbound campaigns found")
            return {}
        
        print(f"\n🔍 Searching {len(campaign_list)} outbound campaigns")
        
        # Method 1: Check live_agents for outbound campaigns
        live_agents = []
        for campaign in campaign_list:
            live_query = """
            SELECT 
                l.user,
                l.status,
                l.campaign_id,
                l.last_call_time,
                l.last_state_change,
                l.closer_campaigns,
                u.full_name,
                TIMESTAMPDIFF(SECOND, l.last_state_change, NOW()) as seconds_in_status
            FROM vicidial_live_agents l
            LEFT JOIN vicidial_users u ON l.user = u.user
            WHERE l.status = 'INCALL'
              AND l.campaign_id = %s
            """
            
            result = db.execute_query(live_query, (campaign,))
            if result:
                live_agents.extend(result)
        
        # Method 2: Check active calls
        active_calls = []
        for campaign in campaign_list:
            calls_query = """
            SELECT 
                v.uniqueid,
                v.callerid,
                v.campaign_id,
                v.call_date,
                v.length_in_sec,
                a.user,
                u.full_name
            FROM vicidial_closer_log v
            JOIN vicidial_agent_log a ON v.uniqueid = a.uniqueid
            LEFT JOIN vicidial_users u ON a.user = u.user
            WHERE v.call_date >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
              AND v.length_in_sec < 5
              AND v.campaign_id = %s
            ORDER BY v.call_date DESC
            """
            
            result = db.execute_query(calls_query, (campaign,))
            if result:
                active_calls.extend(result)
        
        # Combine results
        outbound_agents = {}
        
        for agent in live_agents:
            outbound_agents[agent['user']] = {
                'user': agent['user'],
                'name': agent['full_name'] or 'Unknown',
                'campaign': agent['campaign_id'],
                'status': agent['status'],
                'duration': agent['seconds_in_status'] or 0,
                'source': 'live'
            }
        
        for call in active_calls:
            if call['user'] and call['user'] not in outbound_agents:
                outbound_agents[call['user']] = {
                    'user': call['user'],
                    'name': call['full_name'] or 'Unknown',
                    'campaign': call['campaign_id'],
                    'status': 'INCALL',
                    'duration': call['length_in_sec'] or 0,
                    'source': 'active',
                    'callerid': call['callerid']
                }
        
        # Display results
        if outbound_agents:
            print(f"\n🟢 CURRENTLY ON OUTBOUND CALLS: {len(outbound_agents)}")
            print("-" * 90)
            print(f"{'Agent':<15} {'Name':<20} {'Campaign':<15} {'Status':<10} {'Duration':<12}")
            print("-" * 90)
            
            for user, data in outbound_agents.items():
                # Color code by campaign
                if 'YPDirect' in data['campaign'] or 'YP' in data['campaign']:
                    color = Colors.BLUE
                elif 'Hot' in data['campaign']:
                    color = Colors.RED
                elif 'K1' in data['campaign']:
                    color = Colors.GREEN
                elif 'Babi' in data['campaign']:
                    color = Colors.MAGENTA
                else:
                    color = Colors.RESET
                
                duration_str = sec_to_hms(data['duration'])
                
                print_color(f"{data['user']:<15} {data['name']:<20} {data['campaign']:<15} {data['status']:<10} {duration_str:<12}", color)
                
                # Show caller ID if available
                if data.get('callerid'):
                    print_color(f"  └─ 📞 Calling: {data['callerid']}", Colors.YELLOW)
            
            # Group by campaign
            print(f"\n📊 OUTBOUND SUMMARY BY CAMPAIGN:")
            print("-" * 50)
            
            campaign_counts = {}
            for data in outbound_agents.values():
                camp = data['campaign']
                campaign_counts[camp] = campaign_counts.get(camp, 0) + 1
            
            for camp, count in campaign_counts.items():
                bar = "█" * count
                print(f"  {camp:<15} {bar} {count}")
            
        else:
            print("\n📭 No outbound agents currently on calls")
        
        # Get recent outbound activity
        print(f"\n📋 RECENT OUTBOUND ACTIVITY (Last 30 min):")
        print("-" * 90)
        
        recent_calls = []
        for campaign in campaign_list[:5]:  # Limit to 5 campaigns to avoid too many queries
            recent_query = """
            SELECT 
                a.user,
                u.full_name,
                c.campaign_id,
                c.call_date,
                c.length_in_sec,
                c.phone_number
            FROM vicidial_agent_log a
            JOIN vicidial_closer_log c ON a.uniqueid = c.uniqueid
            LEFT JOIN vicidial_users u ON a.user = u.user
            WHERE c.call_date >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
              AND c.campaign_id = %s
            ORDER BY c.call_date DESC
            LIMIT 10
            """
            
            result = db.execute_query(recent_query, (campaign,))
            if result:
                recent_calls.extend(result)
        
        # Sort by date
        recent_calls.sort(key=lambda x: x['call_date'], reverse=True)
        recent_calls = recent_calls[:20]  # Keep only top 20
        
        if recent_calls:
            print(f"{'Time':<20} {'Agent':<15} {'Name':<20} {'Campaign':<15} {'Duration':<10}")
            print("-" * 90)
            
            for call in recent_calls:
                if hasattr(call['call_date'], 'strftime'):
                    time_str = call['call_date'].strftime('%H:%M:%S')
                else:
                    time_str = str(call['call_date'])[11:19]
                duration = sec_to_hms(call['length_in_sec'] or 0)
                name = call['full_name'] or 'Unknown'
                print(f"  {time_str:<20} {call['user']:<15} {name:<20} {call['campaign_id']:<15} {duration:<10}")
        else:
            print("  No recent outbound activity")
        
        return outbound_agents
        
    except Exception as e:
        print_error(f"Error monitoring outbound agents: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

def get_outbound_campaigns():
    """List all outbound campaigns"""
    print_header("📋 OUTBOUND CAMPAIGNS", Colors.BLUE)
    
    try:
        # FIXED: escaped % signs with %%
        query = """
        SELECT 
            campaign_id,
            campaign_name,
            active,
            campaign_allow_inbound,
            dial_method
        FROM vicidial_campaigns
        WHERE campaign_allow_inbound = 'N'
           OR campaign_id LIKE '%%outbound%%'
           OR campaign_id LIKE '%%dial%%'
        ORDER BY campaign_id
        """
        
        campaigns = db.execute_query(query)
        campaign_list = list(campaigns) if campaigns else []
        
        # Add known outbound campaigns if not in results
        known_outbound = ['YPDirect', 'Hotpro', 'BabiTrump', 'K1', 'Boxco', 'Aiven']
        existing_ids = [c['campaign_id'] for c in campaign_list]
        
        for known in known_outbound:
            if known not in existing_ids:
                campaign_list.append({
                    'campaign_id': known,
                    'campaign_name': f'{known} Campaign',
                    'active': 'Y',
                    'campaign_allow_inbound': 'N',
                    'dial_method': 'MANUAL'
                })
        
        if campaign_list:
            print(f"\n{'Campaign':<20} {'Name':<30} {'Active':<8} {'Dial Method':<15}")
            print("-" * 80)
            
            for camp in campaign_list:
                active = "✅" if camp.get('active') == 'Y' else "❌"
                dial_method = camp.get('dial_method') or 'Unknown'
                name = camp.get('campaign_name', 'N/A')
                if name and len(name) > 30:
                    name = name[:27] + '...'
                print(f"  {camp['campaign_id']:<20} {name:<30} {active:<8} {dial_method:<15}")
            
            print(f"\n📊 Total Outbound Campaigns: {len(campaign_list)}")
        else:
            print("  No outbound campaigns found")
            
    except Exception as e:
        print_error(f"Error getting outbound campaigns: {str(e)}")

def outbound_team_summary():
    """Summary of outbound team activity"""
    print_header("📊 OUTBOUND TEAM SUMMARY", Colors.GREEN)
    
    try:
        # Today's outbound stats - simpler query first
        today_query = """
        SELECT 
            COUNT(DISTINCT a.user) as active_agents,
            COUNT(*) as total_calls,
            SUM(a.talk_sec) as total_talk,
            AVG(a.talk_sec) as avg_talk
        FROM vicidial_agent_log a
        WHERE DATE(a.event_time) = CURDATE()
        """
        
        today = db.execute_query(today_query)
        
        if today and today[0]['total_calls'] > 0:
            data = today[0]
            print(f"\n📈 TODAY'S OVERALL ACTIVITY:")
            print("-" * 50)
            print(f"  • Active Agents: {data['active_agents']}")
            print(f"  • Total Calls: {data['total_calls']}")
            print(f"  • Total Talk Time: {sec_to_hms(data['total_talk'])}")
            print(f"  • Average Call: {sec_to_hms(data['avg_talk'])}")
        
        # This week's stats
        week_query = """
        SELECT 
            COUNT(DISTINCT user) as active_agents,
            COUNT(*) as total_calls,
            SUM(talk_sec) as total_talk,
            AVG(talk_sec) as avg_talk
        FROM vicidial_agent_log
        WHERE event_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """
        
        week = db.execute_query(week_query)
        
        if week and week[0]['total_calls'] > 0:
            data = week[0]
            print(f"\n📊 THIS WEEK'S OVERALL ACTIVITY:")
            print("-" * 50)
            print(f"  • Active Agents: {data['active_agents']}")
            print(f"  • Total Calls: {data['total_calls']}")
            print(f"  • Total Talk Time: {sec_to_hms(data['total_talk'])}")
            print(f"  • Average Call: {sec_to_hms(data['avg_talk'])}")
            
    except Exception as e:
        print_error(f"Error getting outbound summary: {str(e)}")

def outbound_monitor_menu():
    """Main outbound monitor menu"""
    while True:
        print_header("📞 OUTBOUND DIALER MONITOR", Colors.CYAN)
        print("  1. 👁️ Live Outbound Agents")
        print("  2. 📋 List Outbound Campaigns")
        print("  3. 📊 Outbound Team Summary")
        print("  4. 🔄 Auto-Refresh (5 sec)")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Select option: {Colors.RESET}").strip()
        
        if choice == '1':
            get_outbound_agents()
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            get_outbound_campaigns()
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            outbound_team_summary()
            input("\nPress Enter to continue...")
        
        elif choice == '4':
            print("\n🔄 Auto-refresh mode (Press Ctrl+C to stop)")
            try:
                while True:
                    get_outbound_agents()
                    print(f"\n🔄 Refreshing... ({datetime.now().strftime('%H:%M:%S')})")
                    import time
                    time.sleep(5)
            except KeyboardInterrupt:
                print("\n\n✅ Auto-refresh stopped")
        
        elif choice == '0':
            break
        
        else:
            print_error("Invalid option")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    outbound_monitor_menu()