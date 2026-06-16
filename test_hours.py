# test_hours.py - Save this in D:/Altria_Ops/ and run it
from datetime import datetime, time
from config.campaign_hours import is_within_operating_hours, get_campaign_hours
from utils.stats_helper import CampaignStats

print("Testing Campaign Operating Hours Logic")
print("=" * 60)

# Test Xshield (overnight campaign: 22:00 to 18:00 next day)
print("\n📊 Testing XSHIELD (22:00 - 18:00 next day EST)")
print("-" * 50)

test_times = [
    ("2026-02-14 09:00:00", "Morning (should be OUTSIDE - after hours end)"),
    ("2026-02-14 15:00:00", "Afternoon (should be OUTSIDE)"),
    ("2026-02-14 21:00:00", "Evening (should be OUTSIDE - before hours start)"),
    ("2026-02-14 22:30:00", "Night (should be INSIDE - after start)"),
    ("2026-02-15 02:00:00", "Early morning (should be INSIDE)"),
    ("2026-02-15 06:00:00", "Early morning (should be INSIDE - at end)"),
    ("2026-02-15 07:00:00", "Morning (should be OUTSIDE - after end)")
]

for dt_str, description in test_times:
    test_dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    result = is_within_operating_hours('Xshield', test_dt)
    status = "✅ INSIDE" if result else "❌ OUTSIDE"
    print(f"{dt_str} - {description:<40} {status}")

# Test XCHANGE (normal hours: 09:00 - 19:00)
print("\n📊 Testing XCHANGE (09:00 - 19:00 EST)")
print("-" * 50)

test_times = [
    ("2026-02-14 08:00:00", "Before start (should be OUTSIDE)"),
    ("2026-02-14 09:00:00", "At start (should be INSIDE)"),
    ("2026-02-14 14:30:00", "Mid-day (should be INSIDE)"),
    ("2026-02-14 19:00:00", "At end (should be INSIDE)"),
    ("2026-02-14 20:00:00", "After end (should be OUTSIDE)")
]

for dt_str, description in test_times:
    test_dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    result = is_within_operating_hours('XCHANGE', test_dt)
    status = "✅ INSIDE" if result else "❌ OUTSIDE"
    print(f"{dt_str} - {description:<30} {status}")

print("\n✅ Logic test complete!")