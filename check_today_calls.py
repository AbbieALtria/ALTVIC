import pymysql
from datetime import datetime

# Database connection
conn = pymysql.connect(
    host='216.219.88.67',
    user='cron',
    password='1234',
    database='asterisk',
    cursorclass=pymysql.cursors.DictCursor
)

print("\n" + "="*80)
print("📊 REAL CALL COUNTS VS EVENT COUNTS".center(80))
print("="*80)

try:
    with conn.cursor() as cursor:
        # Query to see what's really happening
        sql = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as total_events,
            SUM(CASE WHEN a.talk_sec >= 5 THEN 1 ELSE 0 END) as real_calls,
            SUM(a.talk_sec) as total_talk_sec,
            MIN(a.event_time) as first_event,
            MAX(a.event_time) as last_event
        FROM vicidial_agent_log a
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE DATE(a.event_time) = CURDATE()
        GROUP BY a.user
        ORDER BY real_calls DESC
        LIMIT 20;
        """
        
        cursor.execute(sql)
        results = cursor.fetchall()
        
        if not results:
            print("\n❌ No data for today")
        else:
            print(f"\n{'User':<15} {'Name':<20} {'Events':<10} {'Real Calls':<12} {'Talk Time':<15} {'Events per Call'}")
            print("-"*90)
            
            for row in results:
                user = row['user']
                name = (row['full_name'] or 'Unknown')[:20]
                events = row['total_events']
                real_calls = row['real_calls'] or 0
                talk_sec = row['total_talk_sec'] or 0
                
                # Calculate events per real call
                if real_calls > 0:
                    events_per_call = events / real_calls
                    talk_per_call = talk_sec / real_calls
                else:
                    events_per_call = 0
                    talk_per_call = 0
                
                # Format talk time
                hours = talk_sec // 3600
                minutes = (talk_sec % 3600) // 60
                talk_time = f"{hours}h {minutes}m"
                
                # Color code based on events per call
                if events_per_call > 10:
                    color = "🔴"
                elif events_per_call > 5:
                    color = "🟡"
                else:
                    color = "🟢"
                
                print(f"{color} {user:<15} {name:<20} {events:<10} {real_calls:<12} {talk_time:<15} {events_per_call:.1f}x")
            
            # Summary
            print("\n" + "="*90)
            print("📈 INTERPRETATION:")
            print("  • 🟢 1-5 events per call = Normal (each call logged 1-5 times)")
            print("  • 🟡 5-10 events per call = High (lots of status changes)")
            print("  • 🔴 10+ events per call = Excessive (counting non-call events)")
            
finally:
    conn.close()