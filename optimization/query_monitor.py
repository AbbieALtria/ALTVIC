#!/usr/bin/env python3
# =============================================================================
# File:         query_monitor.py
# Version:      1.0.0
# Date:         2026-02-28
# Description:  Database query performance monitoring and optimization
# Location:     D:/Altria_Ops/optimization/query_monitor.py
# =============================================================================

import sys
from pathlib import Path
from datetime import datetime, timedelta
import time
import json
from collections import defaultdict, deque
import threading

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning

# =============================================================================
# Query Monitor Class
# =============================================================================

class QueryMonitor:
    """Monitor and analyze database query performance"""
    
    def __init__(self, max_history=1000):
        self.max_history = max_history
        self.query_history = deque(maxlen=max_history)
        self.slow_queries = deque(maxlen=100)
        self.query_stats = defaultdict(lambda: {'count': 0, 'total_time': 0, 'max_time': 0})
        self.monitoring = False
        self.monitor_thread = None
        
    def log_query(self, query, params, duration, caller):
        """Log a query execution"""
        entry = {
            'timestamp': datetime.now(),
            'query': query[:200],  # Truncate long queries
            'params': str(params)[:100],
            'duration': duration,
            'caller': caller,
            'slow': duration > 1.0
        }
        
        self.query_history.append(entry)
        
        # Update stats
        self.query_stats[caller]['count'] += 1
        self.query_stats[caller]['total_time'] += duration
        self.query_stats[caller]['max_time'] = max(
            self.query_stats[caller]['max_time'], duration
        )
        
        # Track slow queries
        if duration > 1.0:
            self.slow_queries.append(entry)
            
            # Alert if very slow
            if duration > 5.0:
                print_warning(f"⚠️ VERY SLOW QUERY ({duration:.2f}s): {caller}")
    
    def get_slow_queries(self, min_duration=1.0, limit=20):
        """Get recent slow queries"""
        return [q for q in self.slow_queries if q['duration'] >= min_duration][:limit]
    
    def get_stats(self):
        """Get query statistics"""
        stats = []
        for caller, data in self.query_stats.items():
            avg_time = data['total_time'] / data['count'] if data['count'] > 0 else 0
            stats.append({
                'caller': caller,
                'count': data['count'],
                'total_time': data['total_time'],
                'avg_time': avg_time,
                'max_time': data['max_time'],
                'pct_of_total': 0  # Will calculate later
            })
        
        # Calculate percentages
        total_time = sum(s['total_time'] for s in stats)
        for s in stats:
            s['pct_of_total'] = (s['total_time'] / total_time * 100) if total_time > 0 else 0
        
        # Sort by total time (desc)
        stats.sort(key=lambda x: x['total_time'], reverse=True)
        
        return stats
    
    def start_monitoring(self):
        """Start background monitoring thread"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print_success("Query monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print_success("Query monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                # Check for long-running queries
                self._check_long_running()
                time.sleep(5)
            except:
                pass
    
    def _check_long_running(self):
        """Check for long-running queries in database"""
        try:
            query = """
            SELECT 
                id,
                user,
                host,
                db,
                command,
                time,
                state,
                info
            FROM information_schema.processlist
            WHERE command != 'Sleep'
              AND time > 30
            ORDER BY time DESC
            """
            
            long_queries = db.execute_query(query)
            
            for q in long_queries or []:
                print_warning(f"⚠️ Long-running query ({q['time']}s): {q['info'][:100]}")
                
        except Exception as e:
            # May not have permission to view processlist
            pass

# Global instance
monitor = QueryMonitor()

# =============================================================================
# Decorator for monitoring queries
# =============================================================================

def monitor_query(func):
    """Decorator to monitor query execution time"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        
        # Log the query
        caller = func.__name__
        if hasattr(func, '__self__'):
            caller = f"{func.__self__.__class__.__name__}.{caller}"
        
        # Try to get the actual query if available
        query = "Unknown"
        if len(args) > 0 and isinstance(args[0], str):
            query = args[0]
        
        monitor.log_query(query, args[1:] if len(args) > 1 else [], duration, caller)
        
        return result
    return wrapper

# Patch the database execute_query method
original_execute = db.execute_query

def monitored_execute_query(query, params=None):
    """Monitored version of execute_query"""
    start = time.time()
    try:
        result = original_execute(query, params)
        return result
    finally:
        duration = time.time() - start
        
        # Get caller info
        import inspect
        frame = inspect.currentframe().f_back
        caller = frame.f_code.co_name
        if 'self' in frame.f_locals:
            caller = f"{frame.f_locals['self'].__class__.__name__}.{caller}"
        
        monitor.log_query(query, params, duration, caller)

# Replace the execute_query method
db.execute_query = monitored_execute_query

# =============================================================================
# Display Functions
# =============================================================================

def show_query_stats():
    """Display query performance statistics"""
    print_header("📊 QUERY PERFORMANCE STATISTICS", Colors.CYAN)
    
    stats = monitor.get_stats()
    
    if not stats:
        print_warning("No query data available yet")
        input("\nPress Enter to continue...")
        return
    
    total_queries = sum(s['count'] for s in stats)
    total_time = sum(s['total_time'] for s in stats)
    
    print(f"\n📈 SUMMARY")
    print("=" * 80)
    print(f"  Total Queries: {total_queries}")
    print(f"  Total Time:    {total_time:.2f}s")
    print(f"  Avg Query:     {total_time/total_queries:.3f}s" if total_queries > 0 else "")
    print(f"  Slow Queries:  {len(monitor.slow_queries)}")
    
    print(f"\n📊 QUERY BREAKDOWN")
    print("=" * 100)
    print(f"{'Caller':<30} {'Count':<8} {'Total Time':<12} {'Avg Time':<10} {'Max Time':<10} {'%'}")
    print("-" * 100)
    
    for s in stats[:20]:
        if s['total_time'] > 0.1:  # Only show significant queries
            color = Colors.RED if s['avg_time'] > 1.0 else Colors.YELLOW if s['avg_time'] > 0.5 else Colors.GREEN
            print_color(
                f"{s['caller'][:30]:<30} {s['count']:<8} {s['total_time']:>8.2f}s{' ':<4} "
                f"{s['avg_time']:>6.3f}s{' ':<4} {s['max_time']:>6.3f}s{' ':<4} {s['pct_of_total']:>5.1f}%",
                color
            )
    
    print("=" * 100)
    input("\nPress Enter to continue...")

def show_slow_queries():
    """Display recent slow queries"""
    print_header("🐢 SLOW QUERIES", Colors.YELLOW)
    
    slow = monitor.get_slow_queries()
    
    if not slow:
        print_success("No slow queries detected")
        input("\nPress Enter to continue...")
        return
    
    print(f"\nFound {len(slow)} slow queries")
    print("=" * 100)
    
    for i, q in enumerate(slow, 1):
        print(f"\n{i}. ⚠️ {q['duration']:.2f}s - {q['caller']}")
        print(f"   Time: {q['timestamp'].strftime('%H:%M:%S')}")
        print(f"   Query: {q['query']}")
        if q['params'] and q['params'] != '()':
            print(f"   Params: {q['params']}")
    
    print("\n" + "=" * 100)
    input("\nPress Enter to continue...")

def show_index_recommendations():
    """Analyze slow queries and recommend indexes"""
    print_header("🔍 INDEX RECOMMENDATIONS", Colors.MAGENTA)
    
    slow = monitor.get_slow_queries(min_duration=0.5)
    
    if not slow:
        print_success("No queries needing optimization")
        input("\nPress Enter to continue...")
        return
    
    # Analyze queries for missing indexes
    tables = {}
    
    for q in slow:
        # Simple parsing to extract table names
        query_lower = q['query'].lower()
        
        # Find FROM clause
        if 'from' in query_lower:
            parts = query_lower.split('from')
            if len(parts) > 1:
                table_part = parts[1].split()[0].strip('`')
                if table_part not in tables:
                    tables[table_part] = {
                        'count': 0,
                        'total_time': 0,
                        'conditions': set()
                    }
                
                tables[table_part]['count'] += 1
                tables[table_part]['total_time'] += q['duration']
                
                # Try to extract WHERE conditions
                if 'where' in query_lower:
                    where_part = query_lower.split('where')[1].split('order')[0].split('group')[0]
                    for word in where_part.split():
                        if '=' in word:
                            col = word.split('=')[0].strip()
                            tables[table_part]['conditions'].add(col)
    
    print(f"\n📋 INDEX RECOMMENDATIONS")
    print("=" * 80)
    
    for table, data in tables.items():
        if data['count'] >= 3:  # Only if queried multiple times
            print(f"\n📊 Table: {table}")
            print(f"  Slow queries: {data['count']}")
            print(f"  Total time:   {data['total_time']:.2f}s")
            
            if data['conditions']:
                print(f"  Consider indexes on: {', '.join(data['conditions'])}")
                
                # Generate CREATE INDEX statements
                for col in data['conditions']:
                    idx_name = f"idx_{table}_{col}"
                    print(f"    CREATE INDEX {idx_name} ON {table}({col});")
    
    print("\n" + "=" * 80)
    print("💡 Run these CREATE INDEX statements to improve performance")
    input("\nPress Enter to continue...")

def start_monitoring():
    """Start query monitoring"""
    monitor.start_monitoring()
    input("\nPress Enter to continue...")

def stop_monitoring():
    """Stop query monitoring"""
    monitor.stop_monitoring()
    input("\nPress Enter to continue...")

# =============================================================================
# Main Menu
# =============================================================================

def query_monitor_menu():
    """Main query monitoring menu"""
    while True:
        print_header("📊 QUERY MONITOR & OPTIMIZATION", Colors.CYAN)
        print("  1. 📈 Query Performance Stats")
        print("  2. 🐢 View Slow Queries")
        print("  3. 🔍 Index Recommendations")
        print("  4. ▶️ Start Background Monitoring")
        print("  5. ⏹️ Stop Background Monitoring")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_query_stats()
        elif choice == '2':
            show_slow_queries()
        elif choice == '3':
            show_index_recommendations()
        elif choice == '4':
            start_monitoring()
        elif choice == '5':
            stop_monitoring()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    query_monitor_menu()