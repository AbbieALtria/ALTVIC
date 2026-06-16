#!/usr/bin/env python3
# =============================================================================
# File:         forecast.py
# Version:      1.1.0
# Date:         2026-03-06
# Description:  Call volume forecasting and predictive analytics
# Location:     D:\Altria_Ops\reports\forecast.py
# Updates:      Added get_staffing_forecast function for API integration
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, sec_to_hms
import json
from pathlib import Path
from collections import defaultdict
import math
import statistics

# =============================================================================
# Configuration
# =============================================================================

FORECAST_CONFIG_FILE = Path(__file__).parent.parent / "config" / "forecast_config.json"

DEFAULT_FORECAST_CONFIG = {
    "forecast_settings": {
        "default_days_ahead": 30,
        "historical_months": 12,
        "confidence_level": 0.95,
        "seasonality": {
            "daily": True,
            "weekly": True,
            "monthly": True,
            "yearly": False
        }
    },
    "holiday_impacts": {
        "New Years Day": 0.6,
        "Memorial Day": 0.7,
        "Independence Day": 0.5,
        "Labor Day": 0.7,
        "Thanksgiving": 0.4,
        "Christmas": 0.3,
        "Day After Christmas": 0.5,
        "New Years Eve": 0.6
    },
    "day_of_week_multipliers": {
        "Monday": 1.2,
        "Tuesday": 1.1,
        "Wednesday": 1.0,
        "Thursday": 1.0,
        "Friday": 1.1,
        "Saturday": 0.6,
        "Sunday": 0.5
    },
    "hour_multipliers": {
        "0": 0.1, "1": 0.05, "2": 0.02, "3": 0.01, "4": 0.01, "5": 0.02,
        "6": 0.1, "7": 0.3, "8": 0.7, "9": 1.0, "10": 1.2, "11": 1.3,
        "12": 1.2, "13": 1.3, "14": 1.4, "15": 1.3, "16": 1.2, "17": 1.0,
        "18": 0.8, "19": 0.6, "20": 0.4, "21": 0.3, "22": 0.2, "23": 0.1
    }
}

# =============================================================================
# Config Management
# =============================================================================

def load_forecast_config():
    """Load forecast configuration"""
    if FORECAST_CONFIG_FILE.exists():
        try:
            with open(FORECAST_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key, value in DEFAULT_FORECAST_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            print_warning(f"Could not load forecast config: {e}")
    
    save_forecast_config(DEFAULT_FORECAST_CONFIG)
    return DEFAULT_FORECAST_CONFIG.copy()

def save_forecast_config(config):
    """Save forecast configuration"""
    try:
        FORECAST_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FORECAST_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print_error(f"Cannot save forecast config: {e}")
        return False

# =============================================================================
# Data Collection & Analysis
# =============================================================================

def get_historical_call_data(days_back=365, campaign=None):
    """Get historical call data for forecasting"""
    try:
        where_clause = "WHERE call_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)"
        params = [days_back]
        
        if campaign:
            where_clause += " AND campaign_id = %s"
            params.append(campaign)
        
        query = f"""
        SELECT 
            DATE(call_date) as date,
            DAYOFWEEK(call_date) as day_of_week,
            HOUR(call_date) as hour,
            COUNT(*) as call_count
        FROM vicidial_closer_log
        {where_clause}
        GROUP BY DATE(call_date), HOUR(call_date)
        ORDER BY date, hour
        """
        
        results = db.execute_query(query, params) or []
        
        # Organize by date
        daily_data = defaultdict(list)
        for row in results:
            date_str = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])
            daily_data[date_str].append({
                'hour': row['hour'],
                'calls': row['call_count']
            })
        
        return daily_data
    except Exception as e:
        print_error(f"Error getting historical data: {e}")
        return {}

def calculate_seasonal_patterns(historical_data):
    """Calculate seasonal patterns from historical data"""
    patterns = {
        'hourly': defaultdict(list),
        'daily': defaultdict(list),
        'monthly': defaultdict(list)
    }
    
    for date_str, hours in historical_data.items():
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            month = date.month
            day_of_week = date.weekday()  # 0=Monday, 6=Sunday
            
            # Aggregate daily totals
            daily_total = sum(h['calls'] for h in hours)
            patterns['daily'][day_of_week].append(daily_total)
            patterns['monthly'][month].append(daily_total)
            
            # Aggregate hourly patterns
            for h in hours:
                patterns['hourly'][h['hour']].append(h['calls'])
                
        except Exception:
            continue
    
    # Calculate averages
    averages = {
        'hourly': {hour: statistics.mean(vals) for hour, vals in patterns['hourly'].items() if vals},
        'daily': {day: statistics.mean(vals) for day, vals in patterns['daily'].items() if vals},
        'monthly': {month: statistics.mean(vals) for month, vals in patterns['monthly'].items() if vals}
    }
    
    return averages

def calculate_trend_factor(historical_data, months=3):
    """Calculate trend factor based on recent performance"""
    try:
        # Get last N months of daily totals
        recent_totals = []
        dates = sorted(historical_data.keys())[-90:]  # Last 90 days
        
        for date_str in dates:
            daily_total = sum(h['calls'] for h in historical_data[date_str])
            recent_totals.append((date_str, daily_total))
        
        if len(recent_totals) < 30:
            return 1.0
        
        # Simple linear regression to find trend
        x = list(range(len(recent_totals)))
        y = [t[1] for t in recent_totals]
        
        n = len(x)
        if n < 2:
            return 1.0
            
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_xx = sum(xi * xi for xi in x)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x) if (n * sum_xx - sum_x * sum_x) != 0 else 0
        
        # Calculate average to normalize slope
        avg_y = sum_y / n
        
        if avg_y == 0:
            return 1.0
            
        # Trend factor as percentage growth per day
        trend_pct = (slope / avg_y) * 100
        
        # Convert to multiplier for forecast
        return 1.0 + (trend_pct / 100)
        
    except Exception as e:
        print_error(f"Error calculating trend: {e}")
        return 1.0

# =============================================================================
# Forecasting Engine
# =============================================================================

def generate_forecast(days_ahead=30, campaign=None):
    """Generate call volume forecast"""
    config = load_forecast_config()
    
    # Get historical data
    hist_months = config["forecast_settings"]["historical_months"]
    historical_data = get_historical_call_data(days_back=hist_months*30, campaign=campaign)
    
    if not historical_data:
        print_error("Insufficient historical data for forecast")
        return None
    
    # Calculate patterns and trends
    patterns = calculate_seasonal_patterns(historical_data)
    trend_factor = calculate_trend_factor(historical_data)
    
    # Calculate base daily average
    all_daily_totals = []
    for date_str, hours in historical_data.items():
        all_daily_totals.append(sum(h['calls'] for h in hours))
    
    base_daily_avg = statistics.mean(all_daily_totals) if all_daily_totals else 0
    
    # Generate forecast
    forecast = []
    start_date = datetime.now().date()
    
    for day in range(days_ahead):
        forecast_date = start_date + timedelta(days=day)
        day_of_week = forecast_date.weekday()
        month = forecast_date.month
        
        # Get multipliers
        dow_multiplier = config["day_of_week_multipliers"].get(
            list(config["day_of_week_multipliers"].keys())[day_of_week], 1.0
        )
        monthly_avg = patterns['monthly'].get(month, base_daily_avg)
        
        # Calculate daily forecast
        daily_forecast = monthly_avg * dow_multiplier * trend_factor
        
        # Apply trend factor compounding
        daily_forecast *= (1 + (trend_factor - 1) * (day / 30))
        
        # Generate hourly breakdown
        hourly_forecast = []
        total_hourly = 0
        
        for hour in range(24):
            hour_mult = config["hour_multipliers"].get(str(hour), 0.1)
            hour_calls = daily_forecast * hour_mult
            hourly_forecast.append({
                'hour': hour,
                'calls': round(hour_calls)
            })
            total_hourly += hour_calls
        
        forecast.append({
            'date': forecast_date.strftime('%Y-%m-%d'),
            'day_name': forecast_date.strftime('%A'),
            'day_of_week': forecast_date.strftime('%A'),
            'predicted_calls': round(daily_forecast),
            'daily_forecast': round(daily_forecast),
            'hourly_breakdown': hourly_forecast,
            'confidence_low': round(daily_forecast * 0.85),
            'confidence_high': round(daily_forecast * 1.15),
            'confidence_interval': {
                'lower': round(daily_forecast * 0.85),
                'upper': round(daily_forecast * 1.15)
            }
        })
    
    return forecast

# =============================================================================
# Staffing Calculator - Enhanced with API function
# =============================================================================

def calculate_staffing_needs(forecast, avg_handle_time=300, occupancy=0.85):
    """
    Calculate staffing needs based on forecast
    avg_handle_time in seconds
    occupancy target as decimal (0.85 = 85%)
    """
    staffing = []
    
    for day in forecast:
        daily_calls = day['daily_forecast']
        
        # Erlang-C simplified staffing calculation
        # Base formula: (calls * AHT) / (occupancy * 3600)
        workload_seconds = daily_calls * avg_handle_time
        workload_hours = workload_seconds / 3600
        
        # Calculate base agents needed
        base_agents = workload_hours / (occupancy * 8)  # Assuming 8-hour shifts
        
        # Round up to nearest integer
        agents_needed = math.ceil(base_agents)
        
        # Calculate service level estimate
        # Simplified: if we have enough agents, service level improves
        if agents_needed >= base_agents * 1.2:
            service_level = 0.95
        elif agents_needed >= base_agents:
            service_level = 0.85
        elif agents_needed >= base_agents * 0.8:
            service_level = 0.70
        else:
            service_level = 0.50
        
        staffing.append({
            'date': day['date'],
            'day_of_week': day['day_of_week'],
            'forecast_calls': daily_calls,
            'agents_needed': agents_needed,
            'service_level_estimate': f"{service_level*100:.0f}%",
            'workload_hours': round(workload_hours, 1)
        })
    
    return staffing

# =============================================================================
# NEW FUNCTION: get_staffing_forecast - For API/Module Integration
# =============================================================================

def get_staffing_forecast(days=14, campaign=None, avg_handle_time=300, occupancy=0.85):
    """
    Get staffing recommendations from the forecast model
    Returns structured data for API or module integration
    
    Args:
        days (int): Number of days to forecast
        campaign (str, optional): Specific campaign to forecast
        avg_handle_time (int): Average handle time in seconds
        occupancy (float): Target occupancy rate (0.0-1.0)
    
    Returns:
        list: List of daily staffing forecasts with metadata
    """
    try:
        print_info(f"Generating {days}-day staffing forecast...")
        
        # Run your existing forecast
        forecast_data = generate_forecast(days_ahead=days, campaign=campaign)
        
        if not forecast_data:
            print_error("Could not generate forecast data")
            return []
        
        # Calculate staffing for each day
        staffing = []
        for day in forecast_data:
            # Get predicted calls
            predicted_calls = day.get('predicted_calls', day.get('daily_forecast', 0))
            
            # Calculate agents needed using the staffing formula
            workload_seconds = predicted_calls * avg_handle_time
            workload_hours = workload_seconds / 3600
            agents_needed = math.ceil(workload_hours / (occupancy * 8))
            
            # Simple service level estimate based on staffing adequacy
            base_agents_needed = workload_hours / (0.85 * 8)
            if agents_needed >= base_agents_needed * 1.2:
                service_level = 0.95
            elif agents_needed >= base_agents_needed:
                service_level = 0.85
            elif agents_needed >= base_agents_needed * 0.8:
                service_level = 0.70
            else:
                service_level = 0.50
            
            staffing.append({
                'date': day.get('date'),
                'day_name': day.get('day_name', day.get('day_of_week')),
                'predicted_calls': predicted_calls,
                'agents_needed': agents_needed,
                'service_level': round(service_level * 100, 1),
                'workload_hours': round(workload_hours, 1),
                'confidence_low': day.get('confidence_low', day.get('confidence_interval', {}).get('lower', predicted_calls * 0.85)),
                'confidence_high': day.get('confidence_high', day.get('confidence_interval', {}).get('upper', predicted_calls * 1.15)),
                'avg_handle_time': avg_handle_time,
                'occupancy_target': occupancy
            })
        
        # Add summary statistics
        total_calls = sum(d['predicted_calls'] for d in staffing)
        avg_daily_calls = total_calls / len(staffing) if staffing else 0
        max_day = max(staffing, key=lambda x: x['predicted_calls']) if staffing else {}
        
        summary = {
            'total_calls': total_calls,
            'avg_daily_calls': round(avg_daily_calls),
            'max_day': max_day.get('date') if max_day else None,
            'max_calls': max_day.get('predicted_calls') if max_day else 0,
            'total_agents_needed': sum(d['agents_needed'] for d in staffing),
            'avg_daily_agents': round(sum(d['agents_needed'] for d in staffing) / len(staffing)) if staffing else 0,
            'forecast_days': len(staffing),
            'campaign': campaign or 'All Campaigns',
            'generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return {
            'staffing': staffing,
            'summary': summary
        }
        
    except Exception as e:
        print_error(f"Error in get_staffing_forecast: {e}")
        import traceback
        traceback.print_exc()
        return {
            'staffing': [],
            'summary': {
                'error': str(e),
                'forecast_days': 0
            }
        }

# =============================================================================
# Display Functions
# =============================================================================

def show_forecast():
    """Display call volume forecast"""
    print_header("📈 CALL VOLUME FORECAST", Colors.CYAN)
    
    # Get parameters
    days = input("Forecast days ahead (default 30): ").strip()
    days_ahead = int(days) if days.isdigit() else 30
    
    campaign = input("Campaign (or press Enter for all): ").strip() or None
    
    print("\n📡 Generating forecast...")
    forecast = generate_forecast(days_ahead, campaign)
    
    if not forecast:
        print_error("Could not generate forecast")
        input("\nPress Enter to continue...")
        return
    
    # Display summary
    total_calls = sum(d['daily_forecast'] for d in forecast)
    avg_daily = total_calls / len(forecast)
    
    print_header(f"📊 FORECAST SUMMARY - Next {days_ahead} Days", Colors.MAGENTA)
    print(f"Total Forecast Calls: {total_calls}")
    print(f"Average Daily: {avg_daily:.0f}")
    print(f"Peak Day: {max(forecast, key=lambda x: x['daily_forecast'])['date']} ({max(d['daily_forecast'] for d in forecast)} calls)")
    print()
    
    # Display daily forecast
    print("📅 DAILY FORECAST:")
    print("-" * 80)
    print(f"{'Date':<12} {'Day':<10} {'Forecast':<12} {'Range':<15}")
    print("-" * 80)
    
    for day in forecast[:min(30, len(forecast))]:
        ci = day['confidence_interval']
        print(f"{day['date']:<12} {day['day_of_week']:<10} {day['daily_forecast']:<12} {ci['lower']}-{ci['upper']}")
    
    if len(forecast) > 30:
        print(f"\n... and {len(forecast)-30} more days")
    
    # Show staffing needs option
    print("\n" + "-" * 80)
    if input("Calculate staffing needs? (y/n): ").strip().lower() == 'y':
        aht = input("Average Handle Time (seconds) [300]: ").strip()
        aht = int(aht) if aht.isdigit() else 300
        
        occupancy = input("Target Occupancy (0.85 = 85%) [0.85]: ").strip()
        occupancy = float(occupancy) if occupancy else 0.85
        
        staffing = calculate_staffing_needs(forecast, aht, occupancy)
        
        print_header("👥 STAFFING REQUIREMENTS", Colors.GREEN)
        print("-" * 80)
        print(f"{'Date':<12} {'Day':<10} {'Calls':<8} {'Agents':<8} {'Service Level':<15}")
        print("-" * 80)
        
        for s in staffing[:min(14, len(staffing))]:
            print(f"{s['date']:<12} {s['day_of_week']:<10} {s['forecast_calls']:<8} {s['agents_needed']:<8} {s['service_level_estimate']:<15}")
    
    input("\nPress Enter to continue...")

def show_campaign_forecast():
    """Show forecast for specific campaign"""
    campaign = input("Enter campaign name: ").strip()
    if not campaign:
        return
    
    days = input("Forecast days ahead (default 14): ").strip()
    days_ahead = int(days) if days.isdigit() else 14
    
    forecast = generate_forecast(days_ahead, campaign)
    
    if forecast:
        print_header(f"📈 FORECAST: {campaign}", Colors.CYAN)
        print(f"{'Date':<12} {'Day':<10} {'Forecast':<10} {'Range':<15}")
        print("-" * 50)
        
        for day in forecast:
            ci = day['confidence_interval']
            print(f"{day['date']:<12} {day['day_of_week']:<10} {day['daily_forecast']:<10} {ci['lower']}-{ci['upper']}")
    
    input("\nPress Enter to continue...")

def configure_forecast():
    """Configure forecast settings"""
    config = load_forecast_config()
    
    while True:
        print_header("⚙️ FORECAST CONFIGURATION", Colors.GREEN)
        
        settings = config["forecast_settings"]
        print(f"\n📊 FORECAST SETTINGS:")
        print(f"  1. Default Days Ahead:  {settings['default_days_ahead']}")
        print(f"  2. Historical Months:   {settings['historical_months']}")
        print(f"  3. Confidence Level:    {settings['confidence_level']}")
        
        print(f"\n📅 SEASONALITY:")
        print(f"  4. Daily Patterns:      {'✅' if settings['seasonality']['daily'] else '❌'}")
        print(f"  5. Weekly Patterns:     {'✅' if settings['seasonality']['weekly'] else '❌'}")
        print(f"  6. Monthly Patterns:    {'✅' if settings['seasonality']['monthly'] else '❌'}")
        
        print("\n0. Save and Exit")
        print("-" * 60)
        
        choice = input("\nEnter number to modify (or 0 to exit): ").strip()
        
        if choice == '0':
            if save_forecast_config(config):
                print_success("Configuration saved!")
            break
        elif choice == '1':
            new_val = input(f"Default days ahead [{settings['default_days_ahead']}]: ").strip()
            if new_val.isdigit():
                settings['default_days_ahead'] = int(new_val)
        elif choice == '2':
            new_val = input(f"Historical months [{settings['historical_months']}]: ").strip()
            if new_val.isdigit():
                settings['historical_months'] = int(new_val)
        elif choice == '3':
            new_val = input(f"Confidence level [{settings['confidence_level']}]: ").strip()
            if new_val:
                settings['confidence_level'] = float(new_val)
        elif choice in ['4', '5', '6']:
            key = ['daily', 'weekly', 'monthly'][int(choice)-4]
            settings['seasonality'][key] = not settings['seasonality'][key]
        else:
            print_error("Invalid choice")
        
        input("\nPress Enter to continue...")

# =============================================================================
# Main Menu
# =============================================================================

def forecast_menu():
    """Main forecast menu"""
    while True:
        print_header("📈 CALL FORECASTING", Colors.MAGENTA)
        print("  1. 📊 Generate Forecast")
        print("  2. 🎯 Campaign-Specific Forecast")
        print("  3. 👥 Staffing Calculator")
        print("  4. ⚙️ Configure Settings")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_forecast()
        elif choice == '2':
            show_campaign_forecast()
        elif choice == '3':
            # Quick staffing calc
            print_header("👥 STAFFING CALCULATOR", Colors.GREEN)
            calls = input("Daily call volume: ").strip()
            if calls.isdigit():
                aht = input("Average handle time (seconds) [300]: ").strip()
                aht = int(aht) if aht.isdigit() else 300
                
                workload = int(calls) * aht / 3600
                agents = math.ceil(workload / (0.85 * 8))
                
                print(f"\n📊 Results:")
                print(f"  Workload: {workload:.1f} hours")
                print(f"  Agents needed: {agents}")
                
                # Show example of using the new API function
                print("\n💡 For programmatic access, use:")
                print("    from reports.forecast import get_staffing_forecast")
                print("    staffing_data = get_staffing_forecast(days=14)")
                
            input("\nPress Enter to continue...")
        elif choice == '4':
            configure_forecast()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    forecast_menu()