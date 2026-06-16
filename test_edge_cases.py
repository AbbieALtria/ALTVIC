# test_edge_cases.py
from datetime import datetime, timedelta
from config.campaign_hours import is_within_operating_hours

print("Testing Edge Cases")
print("=" * 50)

# Test 1: Campaign not in config (should use 24/7)
print("\n📊 Test 1: Unknown campaign (should default to 24/7)")
test_dt = datetime(2026, 2, 14, 3, 0)
result = is_within_operating_hours('UNKNOWN_CAMPAIGN', test_dt)
print(f"  03:00 AM: {'✅ INSIDE' if result else '❌ OUTSIDE'} (should be INSIDE)")

# Test 2: Exact boundary times for Xshield
print("\n📊 Test 2: Xshield boundary times")
test_dt = datetime(2026, 2, 14, 22, 0)  # 22:00 exactly
result = is_within_operating_hours('Xshield', test_dt)
print(f"  22:00 exactly: {'✅ INSIDE' if result else '❌ OUTSIDE'} (should be INSIDE)")

test_dt = datetime(2026, 2, 15, 18, 0)  # 18:00 exactly
result = is_within_operating_hours('Xshield', test_dt)
print(f"  18:00 exactly: {'✅ INSIDE' if result else '❌ OUTSIDE'} (should be INSIDE)")

test_dt = datetime(2026, 2, 15, 18, 1)  # 18:01
result = is_within_operating_hours('Xshield', test_dt)
print(f"  18:01: {'✅ INSIDE' if result else '❌ OUTSIDE'} (should be OUTSIDE)")

# Test 3: Multi-day period for Xshield
print("\n📊 Test 3: Xshield multi-day period")
dates = [
    datetime(2026, 2, 14, 23, 0),  # Feb 14 23:00
    datetime(2026, 2, 15, 5, 0),   # Feb 15 05:00
    datetime(2026, 2, 15, 17, 0),  # Feb 15 17:00
    datetime(2026, 2, 16, 1, 0),   # Feb 16 01:00
]

for dt in dates:
    result = is_within_operating_hours('Xshield', dt)
    print(f"  {dt}: {'✅ INSIDE' if result else '❌ OUTSIDE'}")

print("\n✅ Edge cases test complete!")