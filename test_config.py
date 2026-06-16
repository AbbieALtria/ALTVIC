# test_config.py - Save this in D:/Altria_Ops/ and run it
import os
from config.campaign_hours import load_campaign_hours, CAMPAIGN_HOURS_FILE

print("Testing Campaign Hours Configuration...")
print("-" * 50)

# Load config (this will create the file if it doesn't exist)
config = load_campaign_hours()

print(f"Config file location: {CAMPAIGN_HOURS_FILE}")
print(f"File exists: {os.path.exists(CAMPAIGN_HOURS_FILE)}")

print("\nLoaded Campaign Hours:")
for campaign, hours in config.items():
    overnight = " (overnight)" if hours.get('crosses_midnight') else ""
    print(f"  • {campaign}: {hours['start']} - {hours['end']}{overnight} {hours['timezone']}")

print("\n✅ Test complete!")