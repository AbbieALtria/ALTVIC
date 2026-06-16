# test_queue.py - Test queue monitor directly
import sys
sys.path.insert(0, "D:\\Altria_Ops")

from campaigns.queue_monitor import get_live_queue_stats

print("=" * 60)
print("TESTING QUEUE MONITOR DIRECTLY")
print("=" * 60)

get_live_queue_stats()
