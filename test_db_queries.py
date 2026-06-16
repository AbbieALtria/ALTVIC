# test_db_queries.py - Save this in D:/Altria_Ops/ and run it
from datetime import datetime, timedelta
from core.database import db
from config.campaign_hours import get_operating_hours_for_query
from utils.stats_helper import CampaignStats

print("Testing Database Queries with Hour Filtering")
print("=" * 70)

# Test campaign
campaign = 'Xshield'
start_date = '2026-02-14'
end_date = '2026-02-15'

print(f"\n📊 Testing for {campaign} on {start_date} to {end_date}")

# Method 1: Using the helper class
print("\n🔍 Method 1: Using CampaignStats class")
stats = CampaignStats(campaign, respect_hours=True)
summary = stats.get_summary(start_date, end_date)

print(f"  Operating Hours: {summary['operating_hours']}")
print(f"  Total Calls (within hours): {summary['stats'].get('total_calls', 0)}")
print(f"  After Hours Calls: {summary['after_hours'].get('total_calls', 0)}")

# Method 2: Direct SQL with hour condition
print("\n🔍 Method 2: Direct SQL with hour condition")
hours_condition = get_operating_hours_for_query(campaign, datetime.strptime(start_date, '%Y-%m-%d'))

query = f"""
SELECT 
    COUNT(*) as total_calls,
    SUM(CASE WHEN HOUR(call_date) BETWEEN 0 AND 23 THEN 1 ELSE 0 END) as total_with_hours
FROM vicidial_closer_log
WHERE campaign_id = %s
  AND DATE(call_date) BETWEEN %s AND %s
  AND {hours_condition}
"""

results = db.execute_query(query, (campaign, start_date, end_date))
print(f"  SQL Condition: {hours_condition}")
print(f"  Result: {results[0]['total_calls']} calls" if results else "  No results")

# Compare with unfiltered
print("\n📊 Comparison (with and without hour filtering):")
from utils.stats_helper import compare_stats
comparison = compare_stats(campaign, start_date, end_date)

print(f"  All calls: {comparison['all_calls'].get('total_calls', 0)}")
print(f"  Within hours: {comparison['within_hours'].get('total_calls', 0)}")
print(f"  Outside hours: {comparison['outside_hours']['calls']}")

print("\n✅ Database test complete!")