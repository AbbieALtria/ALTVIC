from datetime import datetime, timedelta
from core.database import db

print("\nData Availability Check (last few days)")
print("-" * 50)

for days in [0, 1, 2, 3, 7, 14, 30]:
    date = datetime.now().date() - timedelta(days=days)
    try:
        agent_result = db.execute_query(
            "SELECT COUNT(*) as c FROM vicidial_agent_log WHERE DATE(event_time) = %s",
            (date,)
        )
        calls_result = db.execute_query(
            "SELECT COUNT(*) as c FROM vicidial_closer_log WHERE DATE(call_date) = %s",
            (date,)
        )

        agent_count = agent_result[0]['c'] if agent_result else 0
        calls_count = calls_result[0]['c'] if calls_result else 0

        print(f"{date}:  Agent Log: {agent_count:6,}   Closer Log: {calls_count:6,}")
    except Exception as e:
        print(f"{date}:  ERROR: {e}")