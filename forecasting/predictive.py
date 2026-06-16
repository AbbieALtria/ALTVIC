#!/usr/bin/env python3
# =============================================================================
# File:         predictive.py
# Version:      2.0.0
# Date:         2026-03-05
# Description:  Enhanced Predictive Analytics with clear explanations
# Location:     D:/Altria_Ops/forecasting/predictive.py
# =============================================================================

import sys
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import json
import os
import math

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info
from utils.formatter import format_datetime, sec_to_hms
from config.settings import load_forecast_config, save_forecast_config

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    import pandas as pd
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print_warning("scikit-learn not installed. Install with: pip install scikit-learn pandas")

# =============================================================================
# Helper Functions
# =============================================================================

def calculate_mape(y_true, y_pred):
    """Calculate Mean Absolute Percentage Error"""
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    # Avoid division by zero
    mask = y_true != 0
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

def calculate_confidence_interval(predictions, confidence=0.95):
    """Calculate confidence interval for predictions"""
    std = np.std(predictions)
    z_score = 1.96  # 95% confidence interval
    margin = z_score * std
    return margin

def explain_feature(feature_name):
    """Provide human-readable explanation of features"""
    explanations = {
        'lag_1': 'Calls from yesterday',
        'lag_2': 'Calls from 2 days ago',
        'lag_7': 'Calls from same day last week',
        'lag_14': 'Calls from 2 weeks ago (same weekday)',
        'lag_21': 'Calls from 3 weeks ago (same weekday)',
        'lag_28': 'Calls from 4 weeks ago (same weekday)',
        'rolling_avg_7': 'Average calls over the last 7 days',
        'rolling_avg_14': 'Average calls over the last 14 days',
        'rolling_avg_30': 'Average calls over the last 30 days',
        'rolling_max_7': 'Peak calls in the last 7 days',
        'rolling_min_7': 'Lowest calls in the last 7 days',
        'rolling_std_7': 'How much call volume fluctuated last week',
        'day_of_week': 'Day of week (Monday=0, Sunday=6)',
        'month': 'Month of the year (seasonal patterns)',
        'week_of_year': 'Week number (annual patterns)',
        'is_weekend': 'Whether it\'s a weekend',
        'is_month_start': 'First 3 days of month (payday effect)',
        'is_month_end': 'Last 3 days of month',
        'dow_avg': 'Average for this day of week',
    }
    return explanations.get(feature_name, feature_name.replace('_', ' ').title())

# =============================================================================
# Data Preparation
# =============================================================================

def get_historical_volume(days=730):  # Increased to 2 years default
    """Get historical call volume data"""
    query = """
    SELECT 
        DATE(call_date) as date,
        DAYNAME(call_date) as day_name,
        COUNT(*) as calls,
        SUM(CASE WHEN length_in_sec >= 5 THEN 1 ELSE 0 END) as answered,
        SUM(CASE WHEN term_reason IN ('ABANDON', 'QUEUETIMEOUT', 'NOAGENT') THEN 1 ELSE 0 END) as abandoned
    FROM vicidial_closer_log
    WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
    GROUP BY DATE(call_date)
    ORDER BY date
    """
    
    data = db.execute_query(query, (days,))
    
    if ML_AVAILABLE and data:
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df['day_of_week'] = df['date'].dt.dayofweek
        df['month'] = df['date'].dt.month
        df['day_of_month'] = df['date'].dt.day
        df['week_of_year'] = df['date'].dt.isocalendar().week.astype(int)
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        df['is_month_start'] = (df['day_of_month'] <= 3).astype(int)
        df['is_month_end'] = (df['day_of_month'] >= 28).astype(int)
        
        return df
    return None

def is_holiday(date):
    """Check if date is a holiday (simplified)"""
    holidays = [
        '2026-01-01',  # New Year's
        '2026-01-19',  # MLK Day
        '2026-02-16',  # Presidents Day
        '2026-05-25',  # Memorial Day
        '2026-07-04',  # Independence Day
        '2026-09-07',  # Labor Day
        '2026-10-12',  # Columbus Day
        '2026-11-11',  # Veterans Day
        '2026-11-26',  # Thanksgiving
        '2026-12-25',  # Christmas
    ]
    return date.strftime('%Y-%m-%d') in holidays

# =============================================================================
# Forecasting Models
# =============================================================================

class CallVolumeForecaster:
    """Machine learning model for call volume forecasting with explanations"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.features = None
        self.feature_importance = {}
        self.config = load_forecast_config()
        self.history = None
        self.daily_average = 0
        
    def prepare_features(self, df):
        """Prepare features for training with more options"""
        # Create feature matrix
        features = pd.DataFrame()
        
        # Time-based features
        features['day_of_week'] = df['day_of_week']
        features['month'] = df['month']
        features['day_of_month'] = df['day_of_month']
        features['week_of_year'] = df['week_of_year']
        features['is_weekend'] = df['is_weekend']
        features['is_month_start'] = df['is_month_start']
        features['is_month_end'] = df['is_month_end']
        
        # Holiday indicator
        features['is_holiday'] = df['date'].apply(is_holiday).astype(int)
        
        # Lag features (previous days)
        for lag in [1, 2, 3, 7, 14, 21, 28]:
            features[f'lag_{lag}'] = df['calls'].shift(lag)
        
        # Rolling averages
        for window in [7, 14, 30]:
            features[f'rolling_avg_{window}'] = df['calls'].rolling(window=window).mean().shift(1)
            features[f'rolling_max_{window}'] = df['calls'].rolling(window=window).max().shift(1)
            features[f'rolling_min_{window}'] = df['calls'].rolling(window=window).min().shift(1)
            features[f'rolling_std_{window}'] = df['calls'].rolling(window=window).std().shift(1)
        
        # Day of week averages
        dow_avg = df.groupby('day_of_week')['calls'].transform('mean')
        features['dow_avg'] = dow_avg.shift(1)
        
        # Fill NaN values
        features = features.bfill().fillna(0)
        
        return features
    
    def train(self, days=730):
        """Train the forecasting model with detailed metrics"""
        if not ML_AVAILABLE:
            print_error("Machine learning libraries not available")
            return False
        
        print(f"\n📊 Training forecast model on last {days} days of data...")
        print("   This analyzes historical patterns to predict future call volumes.")
        
        # Get historical data
        df = get_historical_volume(days)
        if df is None or len(df) < 60:
            print_error("Insufficient historical data")
            return False
        
        self.history = df
        self.daily_average = df['calls'].mean()
        
        # Prepare features
        X = self.prepare_features(df)
        y = df['calls'].values
        
        # Remove rows with NaN in target
        valid_idx = ~np.isnan(y)
        X = X[valid_idx]
        y = y[valid_idx]
        
        if len(X) < 30:
            print_error("Insufficient training data after preprocessing")
            return False
        
        # Split into train/test (80/20)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train model
        self.model = RandomForestRegressor(
            n_estimators=200,
            max_depth=15,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        train_pred = self.model.predict(X_train_scaled)
        test_pred = self.model.predict(X_test_scaled)
        
        train_mae = mean_absolute_error(y_train, train_pred)
        test_mae = mean_absolute_error(y_test, test_pred)
        
        train_rmse = np.sqrt(mean_squared_error(y_train, train_pred))
        test_rmse = np.sqrt(mean_squared_error(y_test, test_pred))
        
        train_mape = calculate_mape(y_train, train_pred)
        test_mape = calculate_mape(y_test, test_pred)
        
        # Store feature names for importance
        self.features = X.columns.tolist()
        
        # Calculate feature importance
        if hasattr(self.model, 'feature_importances_'):
            for feat, imp in zip(self.features, self.model.feature_importances_):
                self.feature_importance[feat] = imp
        
        print_success(f"✅ Model trained successfully!")
        print(f"\n📈 Model Performance Metrics:")
        print(f"   These metrics tell you how accurate the model is:")
        print(f"   • MAE (Mean Absolute Error): Average prediction error in calls")
        print(f"   • RMSE (Root Mean Square Error): Penalizes large errors more")
        print(f"   • MAPE (Mean Absolute Percentage Error): Error as percentage")
        print("-" * 60)
        print(f"  {'Metric':<20} {'Training':<15} {'Testing':<15} {'Interpretation'}")
        print("-" * 60)
        print(f"  MAE (calls)      : {train_mae:<15.1f} {test_mae:<15.1f} "
              f"Testing error is {test_mae/train_mae:.1f}x training error")
        print(f"  RMSE (calls)     : {train_rmse:<15.1f} {test_rmse:<15.1f} "
              f"Larger errors are {test_rmse/train_rmse:.1f}x more common")
        print(f"  MAPE (%)         : {train_mape:<15.1f} {test_mape:<15.1f} "
              f"Average error is {test_mape:.1f}% of actual call volume")
        
        # Feature importance with explanations
        print(f"\n🔍 Top Features Influencing the Forecast:")
        print(f"   These factors most strongly affect call volume predictions:")
        print("-" * 80)
        importances = sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        for feat, imp in importances:
            bar_length = int(imp * 50)
            bar = "█" * bar_length
            print(f"  {feat:<20} {imp:>6.3f} {bar:<20} {explain_feature(feat)}")
        
        return True
    
    def predict_next_days(self, days=14, confidence=0.95):
        """Predict call volume for next N days with confidence intervals"""
        if self.model is None:
            print_error("Model not trained yet")
            return None
        
        # Get recent data for features
        df = get_historical_volume(90)
        if df is None:
            return None
        
        last_date = df['date'].max()
        predictions = []
        
        # Calculate daily average for comparison
        daily_avg = df['calls'].mean()
        
        for i in range(1, days + 1):
            pred_date = last_date + timedelta(days=i)
            
            # Create feature row for prediction
            feat = pd.DataFrame({
                'day_of_week': [pred_date.weekday()],
                'month': [pred_date.month],
                'day_of_month': [pred_date.day],
                'week_of_year': [pred_date.isocalendar().week],
                'is_weekend': [1 if pred_date.weekday() >= 5 else 0],
                'is_month_start': [1 if pred_date.day <= 3 else 0],
                'is_month_end': [1 if pred_date.day >= 28 else 0],
                'is_holiday': [1 if is_holiday(pred_date) else 0]
            })
            
            # Add lag features from recent data
            for lag in [1, 2, 3, 7, 14, 21, 28]:
                lag_date = pred_date - timedelta(days=lag)
                lag_data = df[df['date'] == lag_date]
                feat[f'lag_{lag}'] = lag_data['calls'].values[0] if len(lag_data) > 0 else daily_avg
            
            # Add rolling averages
            for window in [7, 14, 30]:
                window_data = df[df['date'] >= pred_date - timedelta(days=window)]
                feat[f'rolling_avg_{window}'] = window_data['calls'].mean() if len(window_data) > 0 else daily_avg
                feat[f'rolling_max_{window}'] = window_data['calls'].max() if len(window_data) > 0 else daily_avg
                feat[f'rolling_min_{window}'] = window_data['calls'].min() if len(window_data) > 0 else daily_avg
                feat[f'rolling_std_{window}'] = window_data['calls'].std() if len(window_data) > 0 else 0
            
            # Add day of week average
            dow_data = df[df['day_of_week'] == pred_date.weekday()]
            feat['dow_avg'] = dow_data['calls'].mean() if len(dow_data) > 0 else daily_avg
            
            # Ensure feature order matches training
            feat = feat[self.features]
            
            # Scale and predict
            feat_scaled = self.scaler.transform(feat)
            
            # Get prediction and confidence interval
            predictions_list = []
            for estimator in self.model.estimators_:
                predictions_list.append(estimator.predict(feat_scaled)[0])
            
            pred = np.mean(predictions_list)
            margin = calculate_confidence_interval(predictions_list, confidence)
            
            predictions.append({
                'date': pred_date.strftime('%Y-%m-%d'),
                'day': pred_date.strftime('%A'),
                'predicted_calls': int(max(0, pred)),
                'lower_bound': int(max(0, pred - margin)),
                'upper_bound': int(pred + margin),
                'vs_avg': ((pred - daily_avg) / daily_avg * 100) if daily_avg > 0 else 0
            })
        
        return predictions
    
    def predict_by_hour(self, date, total_predicted):
        """Distribute daily prediction across hours with explanations"""
        hourly_pattern = self.get_hourly_pattern(90)
        
        if hourly_pattern is None:
            # Fallback to typical call center distribution
            print_info("   Using standard call center distribution pattern")
            hours = list(range(24))
            weights = [0.02, 0.01, 0.01, 0.01, 0.01, 0.02,
                      0.05, 0.08, 0.10, 0.08, 0.07, 0.06,
                      0.06, 0.07, 0.08, 0.07, 0.06, 0.05,
                      0.04, 0.03, 0.02, 0.02, 0.01, 0.01]
        else:
            # Use actual pattern from data
            day_of_week = pd.to_datetime(date).dayofweek + 1
            day_data = hourly_pattern[hourly_pattern['day_of_week'] == day_of_week]
            if len(day_data) > 0:
                total = day_data['calls'].sum()
                day_data = day_data.copy()
                day_data.loc[:, 'weight'] = day_data['calls'] / total if total > 0 else 1/24
                weights = []
                hours = []
                for _, row in day_data.iterrows():
                    hours.append(int(row['hour']))
                    weights.append(row['weight'])
            else:
                hours = list(range(24))
                weights = [1/24] * 24
        
        hourly_pred = []
        for h, w in zip(hours, weights):
            hourly_pred.append({
                'hour': h,
                'predicted_calls': int(total_predicted * w)
            })
        
        return sorted(hourly_pred, key=lambda x: x['hour'])
    
    def get_hourly_pattern(self, days=90):
        """Get hourly call patterns"""
        query = """
        SELECT 
            HOUR(call_date) as hour,
            DAYOFWEEK(call_date) as day_of_week,
            COUNT(*) as calls
        FROM vicidial_closer_log
        WHERE call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY HOUR(call_date), DAYOFWEEK(call_date)
        ORDER BY day_of_week, hour
        """
        
        data = db.execute_query(query, (days,))
        
        if ML_AVAILABLE and data:
            df = pd.DataFrame(data)
            return df
        return None

# =============================================================================
# Staffing Calculator
# =============================================================================

def calculate_staffing_needs(predicted_calls, avg_calls_per_agent=15, service_level_target=80):
    """
    Calculate number of agents needed based on forecast
    
    Formula: 
        Base Agents = ceil(predicted_calls / avg_calls_per_agent)
        Then adjust for service level target
    """
    base_agents = math.ceil(predicted_calls / avg_calls_per_agent)
    
    # Adjust for service level (more agents needed for higher service levels)
    if service_level_target >= 90:
        multiplier = 1.3
    elif service_level_target >= 80:
        multiplier = 1.15
    elif service_level_target >= 70:
        multiplier = 1.0
    else:
        multiplier = 0.9
    
    adjusted = math.ceil(base_agents * multiplier)
    
    # Calculate confidence ranges
    low_agents = max(5, math.ceil(predicted_calls * 0.9 / avg_calls_per_agent))
    high_agents = math.ceil(predicted_calls * 1.1 / avg_calls_per_agent)
    
    return {
        'base_agents': base_agents,
        'recommended': adjusted,
        'range': (low_agents, high_agents),
        'confidence': '±10% volume variance'
    }

def explain_staffing_calculation(predicted_calls):
    """Provide explanation of staffing calculation"""
    explanation = f"""
   Staffing Calculation Explanation:
   • Based on {predicted_calls} predicted calls
   • Assuming 15 calls per agent per shift (industry standard)
   • Base calculation: {predicted_calls} ÷ 15 = {predicted_calls/15:.1f} agents
   • Adjusted for service level target (80%): +15% = {math.ceil(predicted_calls/15 * 1.15)} agents
   • Range accounts for ±10% volume variance
    """
    return explanation

# =============================================================================
# Display Functions
# =============================================================================

def show_forecast():
    """Show forecast dashboard with explanations"""
    print_header("📈 CALL VOLUME FORECAST", Colors.CYAN)
    
    print("""
    What This Forecast Does:
    • Analyzes historical call patterns to predict future volume
    • Uses machine learning to identify weekly, monthly, and seasonal trends
    • Provides confidence intervals to show prediction reliability
    • Helps with staffing decisions and resource planning
    """)
    
    if not ML_AVAILABLE:
        print_error("Required libraries not installed")
        print("\nInstall with:")
        print("  pip install scikit-learn pandas numpy")
        input("\nPress Enter to continue...")
        return
    
    forecaster = CallVolumeForecaster()
    
    # Train model
    if not forecaster.train(days=730):  # Use 2 years for better accuracy
        print_error("Could not train model")
        input("\nPress Enter to continue...")
        return
    
    # Get predictions
    predictions = forecaster.predict_next_days(14)
    
    if not predictions:
        print_error("Could not generate predictions")
        input("\nPress Enter to continue...")
        return
    
    # Display predictions with explanations
    print(f"\n📊 14-DAY FORECAST (with 95% confidence intervals)")
    print("   The model is 95% confident that actual calls will fall within the range")
    print("=" * 100)
    print(f"{'Date':<12} {'Day':<10} {'Predicted':<10} {'Range':<18} {'vs Avg':<10} {'Status'}")
    print("-" * 100)
    
    for pred in predictions:
        date = pred['date']
        day = pred['day'][:3]
        calls = pred['predicted_calls']
        low = pred['lower_bound']
        high = pred['upper_bound']
        vs_avg = pred['vs_avg']
        
        # Determine status based on vs_avg
        if vs_avg > 30:
            status = "🔴 HIGH"
            color = Colors.RED
        elif vs_avg > 15:
            status = "🟡 ABOVE AVG"
            color = Colors.YELLOW
        elif vs_avg > -15:
            status = "🟢 NORMAL"
            color = Colors.GREEN
        elif vs_avg > -30:
            status = "🔵 BELOW AVG"
            color = Colors.BLUE
        else:
            status = "🔵 LOW"
            color = Colors.BLUE
        
        print_color(f"{date:<12} {day:<10} {calls:<10} {low}-{high:<14} {vs_avg:>+6.1f}%   {status}", color)
    
    print("=" * 100)
    
    # Explanation of statuses
    print("\n📊 Status Legend:")
    print("  🔴 HIGH       - More than 30% above average - Prepare for peak volume")
    print("  🟡 ABOVE AVG  - 15-30% above average - Slightly busier than normal")
    print("  🟢 NORMAL     - Within 15% of average - Typical day")
    print("  🔵 BELOW AVG  - 15-30% below average - Quieter than normal")
    print("  🔵 LOW        - More than 30% below average - Very quiet")
    
    # Show hourly breakdown for tomorrow
    print(f"\n⏰ HOURLY FORECAST - Tomorrow ({predictions[0]['date']})")
    print("   This shows when calls are expected throughout the day")
    print("   Helps with shift scheduling and break planning")
    print("-" * 70)
    
    hourly = forecaster.predict_by_hour(predictions[0]['date'], predictions[0]['predicted_calls'])
    
    # Get current actuals for comparison
    today = datetime.now().date()
    actual_query = """
    SELECT HOUR(call_date) as hour, COUNT(*) as actual
    FROM vicidial_closer_log
    WHERE DATE(call_date) = %s
    GROUP BY HOUR(call_date)
    """
    actuals = db.execute_query(actual_query, (today,))
    actual_dict = {a['hour']: a['actual'] for a in actuals or []}
    
    print(f"{'Hour':<8} {'Predicted':<12} {'Actual':<10} {'Diff':<10} {'Accuracy'}")
    print("-" * 60)
    
    peak_hour = max(hourly, key=lambda x: x['predicted_calls'])
    
    for h in hourly:
        hour = h['hour']
        pred = h['predicted_calls']
        actual = actual_dict.get(hour, 0)
        diff = pred - actual
        
        if diff > 0:
            diff_symbol = "▲"
            diff_color = Colors.GREEN
        elif diff < 0:
            diff_symbol = "▼"
            diff_color = Colors.RED
        else:
            diff_symbol = " "
            diff_color = Colors.RESET
        
        # Calculate accuracy (if actual > 0)
        if actual > 0:
            accuracy = max(0, 100 - abs(diff) / actual * 100)
            accuracy_display = f"{accuracy:.0f}%"
        else:
            accuracy_display = "N/A"
        
        # Highlight peak hour
        if hour == peak_hour['hour']:
            print(f"★ ", end='')
        else:
            print("  ", end='')
        
        print_color(f"{hour:02d}:00   {pred:<12} {actual:<10} {diff_symbol} {abs(diff):<3}      {accuracy_display}", diff_color)
    
    print("-" * 60)
    print(f"★ Peak hour: {peak_hour['hour']:02d}:00 ({peak_hour['predicted_calls']} predicted calls)")
    
    # Staffing recommendations
    print(f"\n👥 STAFFING RECOMMENDATIONS")
    print("   Based on predicted call volume and industry standards")
    print("-" * 70)
    
    total_agents_needed = 0
    for pred in predictions[:7]:
        calls = pred['predicted_calls']
        staffing = calculate_staffing_needs(calls)
        total_agents_needed += staffing['recommended']
        
        # Determine urgency
        if staffing['recommended'] > staffing['base_agents'] * 1.2:
            urgency = "🔴 HIGH NEED"
            color = Colors.RED
        elif staffing['recommended'] > staffing['base_agents']:
            urgency = "🟡 MODERATE"
            color = Colors.YELLOW
        else:
            urgency = "🟢 NORMAL"
            color = Colors.GREEN
        
        print_color(f"  {pred['date']} ({pred['day'][:3]}): {staffing['recommended']} agents needed "
                   f"(range: {staffing['range'][0]}-{staffing['range'][1]}) {urgency}", color)
    
    print("\n" + explain_staffing_calculation(predictions[0]['predicted_calls']))
    
    # Weekly summary
    print(f"\n📅 WEEKLY STAFFING SUMMARY")
    print("-" * 70)
    avg_daily = total_agents_needed / 7
    peak_day = max(predictions[:7], key=lambda x: x['predicted_calls'])
    low_day = min(predictions[:7], key=lambda x: x['predicted_calls'])
    
    print(f"  • Total agents needed this week: {total_agents_needed}")
    print(f"  • Average daily agents: {avg_daily:.0f}")
    print(f"  • Peak day: {peak_day['date']} ({peak_day['day']}) - {peak_day['predicted_calls']} calls")
    print(f"  • Lightest day: {low_day['date']} ({low_day['day']}) - {low_day['predicted_calls']} calls")
    print(f"  • Consider scheduling meetings/training on {low_day['date']}")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    if peak_day['predicted_calls'] > forecaster.daily_average * 1.3:
        print(f"  • {peak_day['date']} will be very busy - ensure full staff, minimize breaks")
        print(f"  • Consider having backup agents on call")
    
    if low_day['predicted_calls'] < forecaster.daily_average * 0.7:
        print(f"  • {low_day['date']} will be quiet - good for training, meetings, or maintenance")
    
    input("\nPress Enter to continue...")

def show_trend_analysis():
    """Show trend analysis with ML and explanations"""
    print_header("📈 TREND ANALYSIS", Colors.MAGENTA)
    
    print("""
    What This Analysis Shows:
    • Long-term patterns in your call volume
    • Day-of-week and seasonal trends
    • Growth or decline over time
    • Helps identify when you're busiest
    """)
    
    if not ML_AVAILABLE:
        print_error("Required libraries not installed")
        input("\nPress Enter to continue...")
        return
    
    # Get data
    df = get_historical_volume(730)  # 2 years
    if df is None:
        print_error("No data available")
        input("\nPress Enter to continue...")
        return
    
    print(f"\n📊 LONG-TERM TRENDS (Last 2 Years)")
    print("=" * 80)
    
    # Year-over-year growth
    df_year1 = df[df['date'] < df['date'].max() - timedelta(days=365)]
    df_year2 = df[df['date'] >= df['date'].max() - timedelta(days=365)]
    
    year1_avg = df_year1['calls'].mean() if len(df_year1) > 0 else 0
    year2_avg = df_year2['calls'].mean() if len(df_year2) > 0 else 0
    
    if year1_avg > 0:
        growth = ((year2_avg - year1_avg) / year1_avg * 100)
        
        if growth > 10:
            trend = "📈 STRONG GROWTH"
            color = Colors.GREEN
            explanation = "Your call volume is increasing significantly. Consider hiring more staff."
        elif growth > 0:
            trend = "📈 SLIGHT GROWTH"
            color = Colors.GREEN
            explanation = "Call volume is slowly increasing."
        elif growth < -10:
            trend = "📉 STRONG DECLINE"
            color = Colors.RED
            explanation = "Call volume is dropping. Consider cross-training agents."
        elif growth < 0:
            trend = "📉 SLIGHT DECLINE"
            color = Colors.RED
            explanation = "Call volume is slightly decreasing."
        else:
            trend = "📊 STABLE"
            color = Colors.YELLOW
            explanation = "Call volume is steady."
        
        print_color(f"Year-over-year trend: {trend} ({growth:+.1f}%)", color)
        print(f"  {explanation}")
        print(f"  • Avg daily (year 1): {year1_avg:.0f} calls")
        print(f"  • Avg daily (year 2):  {year2_avg:.0f} calls")
    
    # Day of week patterns
    print(f"\n📅 DAY OF WEEK PATTERNS")
    print("   This helps you plan staffing by day")
    print("-" * 60)
    
    dow_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    for dow in range(7):
        dow_data = df[df['day_of_week'] == dow]
        if len(dow_data) > 0:
            avg_calls = dow_data['calls'].mean()
            pct_of_avg = (avg_calls / df['calls'].mean() * 100)
            
            if pct_of_avg > 110:
                color = Colors.RED
                desc = "Busiest day"
            elif pct_of_avg > 100:
                color = Colors.YELLOW
                desc = "Above average"
            elif pct_of_avg > 90:
                color = Colors.BLUE
                desc = "Below average"
            else:
                color = Colors.BLUE
                desc = "Quietest day"
            
            print_color(f"  {dow_names[dow]:<10}: {avg_calls:6.0f} calls ({pct_of_avg:5.1f}% of avg) - {desc}", color)
    
    # Monthly patterns
    print(f"\n📆 MONTHLY PATTERNS")
    print("   Seasonal trends throughout the year")
    print("-" * 60)
    
    monthly_data = []
    for month in range(1, 13):
        month_data = df[df['month'] == month]
        if len(month_data) > 0:
            avg_calls = month_data['calls'].mean()
            month_name = datetime(2000, month, 1).strftime('%B')
            monthly_data.append((month_name, avg_calls))
    
    # Find peak and low months
    if monthly_data:
        peak_month = max(monthly_data, key=lambda x: x[1])
        low_month = min(monthly_data, key=lambda x: x[1])
        print(f"  • Peak month: {peak_month[0]} ({peak_month[1]:.0f} calls/day)")
        print(f"  • Lowest month: {low_month[0]} ({low_month[1]:.0f} calls/day)")
        print(f"  • Seasonal variation: {(peak_month[1]/low_month[1]-1)*100:.0f}%")
    
    # Busiest hours
    print(f"\n⏰ BUSIEST HOURS")
    print("   When calls peak during the day")
    print("-" * 40)
    
    hourly_data = []
    for hour in range(24):
        hour_data = df[df['date'].dt.hour == hour]  # Approximate
        if len(hour_data) > 0:
            hourly_data.append((hour, hour_data['calls'].mean()))
    
    if hourly_data:
        hourly_data.sort(key=lambda x: -x[1])
        for hour, avg in hourly_data[:3]:
            print(f"  • {hour:02d}:00 - {avg:.0f} avg calls (peak period)")
    
    input("\nPress Enter to continue...")

# =============================================================================
# Configuration
# =============================================================================

def configure_forecast():
    """Configure forecast settings"""
    config = load_forecast_config()
    
    print_header("⚙️ FORECAST CONFIGURATION", Colors.GREEN)
    
    print("\nCurrent settings:")
    print(f"  Default days ahead: {config['forecast_settings']['default_days_ahead']}")
    print(f"  Historical months: {config['forecast_settings']['historical_months']}")
    print(f"  Confidence level: {config['forecast_settings']['confidence_level']}")
    
    print("\nEnter new values (press Enter to keep current):")
    
    days = input(f"Default forecast days [{config['forecast_settings']['default_days_ahead']}]: ").strip()
    if days:
        try:
            config['forecast_settings']['default_days_ahead'] = int(days)
        except:
            print_warning("Invalid number")
    
    months = input(f"Historical months to use [{config['forecast_settings']['historical_months']}]: ").strip()
    if months:
        try:
            config['forecast_settings']['historical_months'] = int(months)
        except:
            print_warning("Invalid number")
    
    save_forecast_config(config)
    print_success("Forecast settings updated!")

# =============================================================================
# Main Menu
# =============================================================================

def forecasting_menu():
    """Main forecasting menu"""
    while True:
        print_header("📈 FORECASTING & PREDICTIVE ANALYTICS", Colors.CYAN)
        print("  1. 📊 Call Volume Forecast (Next 14 Days)")
        print("  2. 📈 Trend Analysis")
        print("  3. 🔄 Retrain Model")
        print("  4. ⚙️ Configure Forecast Settings")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_forecast()
        elif choice == '2':
            show_trend_analysis()
        elif choice == '3':
            forecaster = CallVolumeForecaster()
            forecaster.train(days=730)
            input("\nPress Enter to continue...")
        elif choice == '4':
            configure_forecast()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    forecasting_menu()