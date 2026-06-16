import pymysql
from datetime import datetime, timedelta

# Database connection
conn = pymysql.connect(
    host='216.219.88.67',
    user='cron',
    password='1234',
    database='asterisk',
    cursorclass=pymysql.cursors.DictCursor
)

agent = '1101'  # Alfred Lucero

print("="*80)
print(f"📊 DETAILED ANALYSIS FOR AGENT: {agent} (Alfred Lucero)".center(80))
print("="*80)

try:
    with conn.cursor() as cursor:
        # 1. Check what campaigns this agent works on
        cursor.execute("""
            SELECT DISTINCT campaign_id 
            FROM vicidial_agent_log 
            WHERE user = %s 
            LIMIT 10
        """, (agent,))
        campaigns = cursor.fetchall()
        print(f"\n📋 Campaigns: {', '.join([c['campaign_id'] for c in campaigns])}")
        
        # 2. Break down today's events by status
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count,
                SUM(talk_sec) as total_talk,
                AVG(talk_sec) as avg_talk
            FROM vicidial_agent_log 
            WHERE user = %s AND DATE(event_time) = CURDATE()
            GROUP BY status
            ORDER BY count DESC
        """, (agent,))
        
        events = cursor.fetchall()
        print(f"\n📋 TODAY'S OUTBOUND ACTIVITY BREAKDOWN:")
        print("=" * 70)
        print(f"{'Status':<12} {'Count':<8} {'Total Talk':<15} {'Avg Talk':<10} {'Interpretation'}")
        print("-" * 70)
        
        total_calls = 0
        for e in events:
            status = e['status'] or 'UNKNOWN'
            count = e['count']
            total_talk = e['total_talk'] or 0
            avg_talk = e['avg_talk'] or 0
            
            total_calls += count
            
            # Format talk time
            talk_str = f"{total_talk//60}m {total_talk%60}s" if total_talk > 0 else "0"
            avg_str = f"{avg_talk:.0f}s" if avg_talk > 0 else "-"
            
            # Interpret the status
            if status == 'YPVM':
                interp = "Left voicemail"
            elif status == 'YPNA':
                interp = "No answer"
            elif status == 'YPNI':
                interp = "Not interested"
            elif status == 'YPCBCK':
                interp = "Callback scheduled"
            elif status == 'YPSALE':
                interp = "SALE! 🎉"
            else:
                interp = "Other"
            
            print(f"{status:<12} {count:<8} {talk_str:<15} {avg_str:<10} {interp}")
        
        # 3. Calculate real conversations (sales)
        cursor.execute("""
            SELECT 
                COUNT(*) as sale_count
            FROM vicidial_agent_log 
            WHERE user = %s AND DATE(event_time) = CURDATE()
              AND status = 'YPSALE'
        """, (agent,))
        
        sales = cursor.fetchone()
        sale_count = sales['sale_count'] if sales else 0
        
        print("\n" + "=" * 70)
        print(f"📊 SUMMARY FOR AGENT {agent}")
        print("=" * 70)
        print(f"  • Total outbound attempts: {total_calls}")
        print(f"  • Voicemails left: {next((e['count'] for e in events if e['status'] == 'YPVM'), 0)}")
        print(f"  • No answers: {next((e['count'] for e in events if e['status'] == 'YPNA'), 0)}")
        print(f"  • Not interested: {next((e['count'] for e in events if e['status'] == 'YPNI'), 0)}")
        print(f"  • Callbacks scheduled: {next((e['count'] for e in events if e['status'] == 'YPCBCK'), 0)}")
        print(f"  • 🎯 SALES MADE: {sale_count}")
        
        # 4. Calculate conversion rates
        if total_calls > 0:
            print(f"\n📈 CONVERSION RATES:")
            print(f"  • Voicemail rate: {next((e['count'] for e in events if e['status'] == 'YPVM'), 0)/total_calls*100:.1f}%")
            print(f"  • No answer rate: {next((e['count'] for e in events if e['status'] == 'YPNA'), 0)/total_calls*100:.1f}%")
            print(f"  • Rejection rate: {next((e['count'] for e in events if e['status'] == 'YPNI'), 0)/total_calls*100:.1f}%")
            print(f"  • Callback rate: {next((e['count'] for e in events if e['status'] == 'YPCBCK'), 0)/total_calls*100:.1f}%")
            print(f"  • Sales conversion: {sale_count/total_calls*100:.2f}%")
        
        # 5. Time analysis
        cursor.execute("""
            SELECT 
                HOUR(event_time) as hour,
                COUNT(*) as calls
            FROM vicidial_agent_log 
            WHERE user = %s AND DATE(event_time) = CURDATE()
            GROUP BY HOUR(event_time)
            ORDER BY hour
        """, (agent,))
        
        hourly = cursor.fetchall()
        print(f"\n⏰ HOURLY CALL ATTEMPTS:")
        max_calls = max([h['calls'] for h in hourly]) if hourly else 1
        for h in hourly:
            bar_length = int((h['calls'] / max_calls) * 30)
            bar = "█" * bar_length
            print(f"  {h['hour']:02d}:00 {bar} {h['calls']} calls")
        
        # 6. Recommendation
        print("\n" + "=" * 70)
        print("💡 RECOMMENDATIONS")
        print("=" * 70)
        if sale_count == 0:
            print("  • No sales today -可能需要 coaching on closing techniques")
            print("  • High voicemail rate - review voicemail script")
            print("  • Consider call timing - many no-answers")
        elif sale_count < 3:
            print("  • Low conversion rate - focus on objection handling")
        else:
            print("  • Good sales numbers - keep it up!")
        
finally:
    conn.close()