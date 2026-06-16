#!/usr/bin/env python3
# =============================================================================
# File:         anomaly_detection.py
# Version:      1.0.0
# Date:         2026-02-28
# Description:  Real-time anomaly detection for call center metrics
# Location:     D:/Altria_Ops/monitoring/analytics/anomaly_detection.py
# =============================================================================

import sys
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import json
from collections import defaultdict, deque

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.database import db
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms

try:
    from scipy import stats
    import numpy as np
    STATS_AVAILABLE = True
except ImportError:
    STATS_AVAILABLE = False
    print_warning("scipy not installed. Install with: pip install scipy numpy")

# =============================================================================
# Anomaly Detection Classes
# =============================================================================

class AnomalyDetector:
    """Base class for anomaly detection"""
    
    def __init__(self, window_size=30, threshold=3):
        self.window_size = window_size
        self.threshold = threshold
        self.history = deque(maxlen=window_size)
        
    def add_value(self, value):
        """Add a new value to history"""
        self.history.append(value)
        
    def detect_zscore(self, value):
        """Detect anomaly using Z-score method"""
        if len(self.history) < 10:
            return False, 0
        
        arr = np.array(self.history)
        mean = np.mean(arr)
        std = np.std(arr)
        
        if std == 0:
            return False, 0
        
        zscore = abs((value - mean) / std)
        return zscore > self.threshold, zscore
    
    def detect_iqr(self, value):
        """Detect anomaly using IQR method"""
        if len(self.history) < 10:
            return False, 0
        
        arr = np.array(self.history)
        q1 = np.percentile(arr, 25)
        q3 = np.percentile(arr, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        return value < lower_bound or value > upper_bound, 0

class CallVolumeDetector(AnomalyDetector):
    """Detect anomalies in call volume"""
    
    def __init__(self):
        super().__init__(window_size=30, threshold=2.5)
        
    def check_current_hour(self):
        """Check if current hour is anomalous"""
        query = """
        SELECT 
            HOUR(call_date) as hour,
            COUNT(*) as calls
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
        GROUP BY HOUR(call_date)
        """
        
        result = db.execute_query(query)
        if not result:
            return None
        
        current_calls = result[0]['calls']
        
        # Get historical data for this hour
        hist_query = """
        SELECT 
            COUNT(*) as calls
        FROM vicidial_closer_log
        WHERE HOUR(call_date) = HOUR(NOW())
          AND call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
          AND DATE(call_date) != CURDATE()
        GROUP BY DATE(call_date)
        """
        
        historical = db.execute_query(hist_query)
        
        if historical and len(historical) >= 5:
            values = [h['calls'] for h in historical]
            self.history = deque(values[-30:])
            
            is_anomaly, zscore = self.detect_zscore(current_calls)
            
            if is_anomaly:
                mean_val = np.mean(list(self.history))
                return {
                    'type': 'call_volume_anomaly',
                    'current': current_calls,
                    'expected': int(mean_val),
                    'zscore': zscore,
                    'message': f"Unusual call volume: {current_calls} calls (expected ~{int(mean_val)})"
                }
        
        return None

class AgentBehaviorDetector(AnomalyDetector):
    """Detect anomalies in agent behavior"""
    
    def __init__(self):
        super().__init__(window_size=14, threshold=2.0)
        
    def check_agent_daily(self, agent):
        """Check if agent's daily performance is anomalous"""
        query = """
        SELECT 
            COUNT(*) as calls,
            SUM(talk_sec) as talk_time
        FROM vicidial_agent_log
        WHERE user = %s
          AND DATE(event_time) = CURDATE()
        """
        
        today = db.execute_query(query, (agent,))
        if not today or today[0]['calls'] == 0:
            return None
        
        current_calls = today[0]['calls']
        
        # Get historical data
        hist_query = """
        SELECT 
            COUNT(*) as calls
        FROM vicidial_agent_log
        WHERE user = %s
          AND event_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
          AND DATE(event_time) != CURDATE()
        GROUP BY DATE(event_time)
        ORDER BY DATE(event_time) DESC
        LIMIT 30
        """
        
        historical = db.execute_query(hist_query, (agent,))
        
        if historical and len(historical) >= 5:
            values = [h['calls'] for h in historical]
            self.history = deque(values)
            
            is_anomaly, zscore = self.detect_zscore(current_calls)
            
            if is_anomaly:
                mean_val = np.mean(list(self.history))
                direction = "higher" if current_calls > mean_val else "lower"
                return {
                    'type': 'agent_behavior_anomaly',
                    'agent': agent,
                    'current': current_calls,
                    'expected': int(mean_val),
                    'zscore': zscore,
                    'message': f"Agent {agent} has {direction} than usual call volume: {current_calls} vs avg {int(mean_val)}"
                }
        
        return None

class QueueAnomalyDetector(AnomalyDetector):
    """Detect anomalies in queue metrics"""
    
    def __init__(self):
        super().__init__(window_size=20, threshold=2.5)
        
    def check_queue_metrics(self):
        """Check for anomalous queue behavior"""
        # Current queue
        current_query = """
        SELECT 
            COUNT(*) as waiting,
            AVG(queue_seconds) as avg_wait
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 5 MINUTE)
          AND length_in_sec = 0
        """
        
        current = db.execute_query(current_query)
        if not current or current[0]['waiting'] == 0:
            return None
        
        waiting = current[0]['waiting']
        
        # Historical queue for this time
        hist_query = """
        SELECT 
            COUNT(*) as waiting
        FROM vicidial_closer_log
        WHERE HOUR(call_date) = HOUR(NOW())
          AND MINUTE(call_date) BETWEEN MINUTE(NOW())-10 AND MINUTE(NOW())+10
          AND call_date >= DATE_SUB(NOW(), INTERVAL 14 DAY)
          AND DATE(call_date) != CURDATE()
        GROUP BY DATE(call_date), HOUR(call_date)
        """
        
        historical = db.execute_query(hist_query)
        
        if historical and len(historical) >= 5:
            values = [h['waiting'] for h in historical]
            self.history = deque(values)
            
            is_anomaly, zscore = self.detect_zscore(waiting)
            
            if is_anomaly:
                mean_val = np.mean(list(self.history))
                return {
                    'type': 'queue_anomaly',
                    'waiting': waiting,
                    'expected': int(mean_val),
                    'zscore': zscore,
                    'message': f"Unusual queue length: {waiting} calls waiting (expected ~{int(mean_val)})"
                }
        
        return None

class AbandonRateDetector(AnomalyDetector):
    """Detect anomalies in abandon rates"""
    
    def __init__(self):
        super().__init__(window_size=14, threshold=2.0)
        
    def check_abandon_rate(self, campaign=None):
        """Check for anomalous abandon rates"""
        where_clause = ""
        params = []
        
        if campaign:
            where_clause = "AND campaign_id = %s"
            params.append(campaign)
        
        # Current hour abandon rate
        current_query = f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
        {where_clause}
        """
        
        current = db.execute_query(current_query, params)
        if not current or current[0]['total'] < 10:
            return None
        
        current_rate = (current[0]['abandoned'] / current[0]['total'] * 100) if current[0]['total'] > 0 else 0
        
        # Historical rates
        hist_query = f"""
        SELECT 
            HOUR(call_date) as hour,
            COUNT(*) as total,
            SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') 
                     OR (length_in_sec = 0 AND queue_seconds > 0) THEN 1 ELSE 0 END) as abandoned
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL 14 DAY)
          AND HOUR(call_date) = HOUR(NOW())
          AND DATE(call_date) != CURDATE()
        {where_clause}
        GROUP BY DATE(call_date)
        """
        
        historical = db.execute_query(hist_query, params * (len(params) if params else 1))
        
        if historical and len(historical) >= 5:
            rates = []
            for h in historical:
                if h['total'] > 0:
                    rates.append((h['abandoned'] / h['total'] * 100))
            
            if rates:
                self.history = deque(rates)
                is_anomaly, zscore = self.detect_zscore(current_rate)
                
                if is_anomaly:
                    mean_rate = np.mean(list(self.history))
                    direction = "higher" if current_rate > mean_rate else "lower"
                    campaign_str = f" for {campaign}" if campaign else ""
                    return {
                        'type': 'abandon_rate_anomaly',
                        'campaign': campaign,
                        'current_rate': round(current_rate, 1),
                        'expected_rate': round(mean_rate, 1),
                        'zscore': zscore,
                        'message': f"Abandon rate{campaign_str} is {direction} than usual: {current_rate:.1f}% vs {mean_rate:.1f}%"
                    }
        
        return None

# =============================================================================
# Anomaly Detection Runner
# =============================================================================

def detect_all_anomalies():
    """Run all anomaly detectors and return results"""
    anomalies = []
    
    # Check call volume
    volume_detector = CallVolumeDetector()
    result = volume_detector.check_current_hour()
    if result:
        anomalies.append(result)
    
    # Check queue
    queue_detector = QueueAnomalyDetector()
    result = queue_detector.check_queue_metrics()
    if result:
        anomalies.append(result)
    
    # Check abandon rates for top campaigns
    campaign_query = """
    SELECT campaign_id
    FROM vicidial_closer_log
    WHERE call_date >= DATE_SUB(NOW(), INTERVAL 1 DAY)
    GROUP BY campaign_id
    HAVING COUNT(*) > 50
    ORDER BY COUNT(*) DESC
    LIMIT 5
    """
    
    campaigns = db.execute_query(campaign_query)
    abandon_detector = AbandonRateDetector()
    
    for camp in campaigns or []:
        result = abandon_detector.check_abandon_rate(camp['campaign_id'])
        if result:
            anomalies.append(result)
    
    # Check overall abandon rate
    result = abandon_detector.check_abandon_rate()
    if result:
        anomalies.append(result)
    
    # Check agent behaviors for top agents
    agent_query = """
    SELECT user
    FROM vicidial_agent_log
    WHERE DATE(event_time) = CURDATE()
    GROUP BY user
    ORDER BY COUNT(*) DESC
    LIMIT 10
    """
    
    agents = db.execute_query(agent_query)
    agent_detector = AgentBehaviorDetector()
    
    for agent in agents or []:
        result = agent_detector.check_agent_daily(agent['user'])
        if result:
            anomalies.append(result)
    
    return anomalies

# =============================================================================
# Display Functions
# =============================================================================

def show_anomaly_dashboard():
    """Display real-time anomaly dashboard"""
    print_header("🔍 REAL-TIME ANOMALY DETECTION", Colors.CYAN)
    
    if not STATS_AVAILABLE:
        print_error("Required libraries not installed")
        print("\nInstall with: pip install scipy numpy")
        input("\nPress Enter to continue...")
        return
    
    print(f"\nScanning for anomalies...")
    anomalies = detect_all_anomalies()
    
    if not anomalies:
        print_success("\n✅ No anomalies detected - System operating normally")
    else:
        print(f"\n🚨 {len(anomalies)} ANOMALIES DETECTED")
        print("=" * 80)
        
        for i, a in enumerate(anomalies, 1):
            if a['type'] == 'call_volume_anomaly':
                color = Colors.RED if a['zscore'] > 3 else Colors.YELLOW
                print_color(f"\n{i}. 📊 CALL VOLUME ANOMALY", color)
                print(f"   {a['message']}")
                print(f"   Z-Score: {a['zscore']:.2f}")
                
            elif a['type'] == 'queue_anomaly':
                color = Colors.RED if a['zscore'] > 3 else Colors.YELLOW
                print_color(f"\n{i}. ⏱️ QUEUE ANOMALY", color)
                print(f"   {a['message']}")
                print(f"   Z-Score: {a['zscore']:.2f}")
                
            elif a['type'] == 'abandon_rate_anomaly':
                color = Colors.RED if a['zscore'] > 3 else Colors.YELLOW
                print_color(f"\n{i}. 📉 ABANDON RATE ANOMALY", color)
                print(f"   {a['message']}")
                print(f"   Z-Score: {a['zscore']:.2f}")
                
            elif a['type'] == 'agent_behavior_anomaly':
                color = Colors.RED if a['zscore'] > 3 else Colors.YELLOW
                print_color(f"\n{i}. 👤 AGENT BEHAVIOR ANOMALY", color)
                print(f"   {a['message']}")
                print(f"   Z-Score: {a['zscore']:.2f}")
    
    print("\n" + "=" * 80)
    input("\nPress Enter to continue...")

def show_anomaly_history():
    """Show historical anomalies"""
    print_header("📜 ANOMALY HISTORY", Colors.BLUE)
    
    # This would require storing anomalies in database
    print("\n🚧 Feature coming soon - storing anomalies in database")
    input("\nPress Enter to continue...")

def configure_anomaly_detection():
    """Configure anomaly detection settings"""
    print_header("⚙️ ANOMALY DETECTION CONFIGURATION", Colors.GREEN)
    
    print("\nCurrent settings:")
    print("  Z-Score threshold: 2.5 (higher = less sensitive)")
    print("  Window size: 30 days")
    print("  Check frequency: Real-time")
    
    print("\nEnter new threshold (2.0-4.0):")
    threshold = input("New threshold (or Enter to keep): ").strip()
    
    if threshold:
        try:
            t = float(threshold)
            if 2.0 <= t <= 4.0:
                print_success(f"Threshold updated to {t}")
            else:
                print_error("Threshold must be between 2.0 and 4.0")
        except:
            print_error("Invalid number")
    
    input("\nPress Enter to continue...")

# =============================================================================
# Main Menu
# =============================================================================

def anomaly_menu():
    """Main anomaly detection menu"""
    while True:
        print_header("🔍 ANOMALY DETECTION", Colors.MAGENTA)
        print("  1. 🚨 Real-time Anomaly Dashboard")
        print("  2. 📊 Run Full Scan Now")
        print("  3. 📜 View Anomaly History")
        print("  4. ⚙️ Configure Settings")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_anomaly_dashboard()
        elif choice == '2':
            show_anomaly_dashboard()  # Same function runs scan
        elif choice == '3':
            show_anomaly_history()
        elif choice == '4':
            configure_anomaly_detection()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    anomaly_menu()