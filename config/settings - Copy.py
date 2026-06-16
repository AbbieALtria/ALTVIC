# config/settings.py - Configuration management (UPDATED)

import json
import os
from pathlib import Path
from datetime import datetime
from utils.colors import print_warning

CONFIG_FILE = Path(__file__).parent.parent / 'data' / 'config.json'
ALERTS_CONFIG_FILE = Path(__file__).parent / 'alerts_config.json'
AGENT_ALERTS_CONFIG_FILE = Path(__file__).parent / 'agent_alerts_config.json'
QUALITY_CONFIG_FILE = Path(__file__).parent / 'quality_config.json'
FORECAST_CONFIG_FILE = Path(__file__).parent / 'forecast_config.json'
SYSTEM_HEALTH_CONFIG_FILE = Path(__file__).parent / 'system_health_config.json'
SCHEDULE_CONFIG_FILE = Path(__file__).parent / 'schedule_config.json'

def load_config():
    """Load main configuration from file"""
    default_config = {
        'language': 'en',
        'export_dir': 'data/exports/',
        'email': {
            'enabled': False,
            'smtp_server': '',
            'smtp_port': 587,
            'username': '',
            'password': '',
            'recipients': []
        },
        'notifications': {
            'slack': {'enabled': False, 'webhook': ''},
            'teams': {'enabled': False, 'webhook': ''},
            'email': {'enabled': False, 'recipients': []}
        },
        'thresholds': {
            'break_time': 15,
            'calls_waiting': 10,
            'no_agents': 5,
            'inactive_time': 30
        },
        'reports': {
            'daily': True,
            'weekly': True,
            'monthly': False,
            'time': '08:00'
        },
        'favorite_campaigns': []
    }
    
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            save_config(default_config)
            return default_config
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config

def save_config(config):
    """Save main configuration to file"""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def update_config(key, value):
    """Update a specific config value"""
    config = load_config()
    config[key] = value
    return save_config(config)

# =============================================================================
# Module-specific config loaders
# =============================================================================

def load_alerts_config():
    """Load alerts configuration"""
    default_config = {
        "thresholds": {
            "agent_pause_time": 15,
            "queue_abandon_rate": 15,
            "service_level": 80,
            "call_volume_spike": 50,
            "agent_idle_time": 30,
            "campaign_health": 60
        },
        "notification": {
            "email_enabled": False,
            "email_recipients": [],
            "slack_enabled": False,
            "slack_webhook": "",
            "dashboard_alerts": True
        },
        "alert_history": []
    }
    
    try:
        if ALERTS_CONFIG_FILE.exists():
            with open(ALERTS_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            save_alerts_config(default_config)
            return default_config
    except Exception as e:
        print_warning(f"Error loading alerts config: {e}")
        return default_config

def save_alerts_config(config):
    """Save alerts configuration"""
    try:
        with open(ALERTS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print_warning(f"Error saving alerts config: {e}")
        return False

def load_agent_alerts_config():
    """Load agent alerts configuration"""
    default_config = {
        "thresholds": {
            "acw_warning_minutes": 5,
            "acw_critical_minutes": 10,
            "short_call_seconds": 30,
            "short_call_consecutive": 3,
            "idle_ready_minutes": 30,
            "transfers_per_hour": 10,
            "pause_warning_minutes": 15,
            "pause_critical_minutes": 30,
            "wrap_up_warning_minutes": 3,
            "wrap_up_critical_minutes": 8
        },
        "enabled_alerts": {
            "acw_alert": True,
            "short_calls_alert": True,
            "idle_alert": True,
            "transfer_alert": True,
            "pause_alert": True,
            "wrap_up_alert": True
        },
        "alert_history": [],
        "notification": {
            "email_enabled": False,
            "email_recipients": [],
            "slack_enabled": False,
            "slack_webhook": ""
        }
    }
    
    try:
        if AGENT_ALERTS_CONFIG_FILE.exists():
            with open(AGENT_ALERTS_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            save_agent_alerts_config(default_config)
            return default_config
    except Exception as e:
        print_warning(f"Error loading agent alerts config: {e}")
        return default_config

def save_agent_alerts_config(config):
    """Save agent alerts configuration"""
    try:
        with open(AGENT_ALERTS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print_warning(f"Error saving agent alerts config: {e}")
        return False

def load_quality_config():
    """Load quality scoring configuration"""
    default_config = {
        "weights": {
            "hold_time": 0.15,
            "call_duration": 0.20,
            "resolution_rate": 0.25,
            "repeat_calls": 0.30,
            "transfers": 0.10
        },
        "ranges": {
            "ideal_call_min": 120,
            "ideal_call_max": 600,
            "hold_time_max": 30,
            "repeat_window_hours": 24
        },
        "quality_tiers": {
            "excellent": 90,
            "good": 80,
            "average": 70,
            "needs_work": 60,
            "poor": 0
        },
        "scoring_periods": {
            "daily": 1,
            "weekly": 7,
            "monthly": 30,
            "quarterly": 90
        },
        "agent_scores": {},
        "coaching_threshold": 70
    }
    
    try:
        if QUALITY_CONFIG_FILE.exists():
            with open(QUALITY_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            save_quality_config(default_config)
            return default_config
    except Exception as e:
        print_warning(f"Error loading quality config: {e}")
        return default_config

def save_quality_config(config):
    """Save quality scoring configuration"""
    try:
        with open(QUALITY_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print_warning(f"Error saving quality config: {e}")
        return False

def load_forecast_config():
    """Load forecasting configuration"""
    default_config = {
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
    
    try:
        if FORECAST_CONFIG_FILE.exists():
            with open(FORECAST_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            save_forecast_config(default_config)
            return default_config
    except Exception as e:
        print_warning(f"Error loading forecast config: {e}")
        return default_config

def save_forecast_config(config):
    """Save forecasting configuration"""
    try:
        with open(FORECAST_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print_warning(f"Error saving forecast config: {e}")
        return False

def load_system_health_config():
    """Load system health configuration"""
    default_config = {
        "health_checks": {
            "database": {
                "enabled": True,
                "timeout_seconds": 5,
                "warning_threshold_ms": 200,
                "critical_threshold_ms": 500
            },
            "disk_space": {
                "enabled": True,
                "warning_threshold_gb": 10,
                "critical_threshold_gb": 5,
                "paths": ["/", "/var/lib/mysql", "/var/log"]
            },
            "services": {
                "enabled": True,
                "services": ["asterisk", "httpd", "mariadb", "vici-dial"]
            },
            "backup": {
                "enabled": True,
                "max_age_hours": 24,
                "backup_paths": ["/var/spool/asterisk/monitor", "/etc/asterisk", "/var/lib/mysql"]
            },
            "certificates": {
                "enabled": True,
                "warning_days": 30,
                "critical_days": 7,
                "cert_paths": ["/etc/ssl/certs", "/etc/asterisk/keys"]
            }
        },
        "alert_thresholds": {
            "cpu_warning": 80,
            "cpu_critical": 95,
            "memory_warning": 85,
            "memory_critical": 95,
            "load_warning": 5,
            "load_critical": 10
        },
        "notification_channels": {
            "dashboard": True,
            "email": False,
            "slack": False,
            "sms": False
        }
    }
    
    try:
        if SYSTEM_HEALTH_CONFIG_FILE.exists():
            with open(SYSTEM_HEALTH_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            save_system_health_config(default_config)
            return default_config
    except Exception as e:
        print_warning(f"Error loading system health config: {e}")
        return default_config

def save_system_health_config(config):
    """Save system health configuration"""
    try:
        with open(SYSTEM_HEALTH_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print_warning(f"Error saving system health config: {e}")
        return False

def load_schedule_config():
    """Load schedule adherence configuration"""
    default_config = {
        "shift_templates": {
            "morning": {"start": "08:00", "end": "16:00", "break_duration": 30},
            "afternoon": {"start": "14:00", "end": "22:00", "break_duration": 30},
            "evening": {"start": "22:00", "end": "06:00", "break_duration": 45},
            "standard": {"start": "09:00", "end": "17:00", "break_duration": 30}
        },
        "adherence_thresholds": {
            "late_minutes": 5,
            "early_departure_minutes": 5,
            "extended_break_minutes": 10,
            "max_breaks_per_day": 2
        },
        "grace_periods": {
            "login_grace": 5,
            "break_grace": 2,
            "lunch_grace": 5
        },
        "overtime_rules": {
            "daily_overtime_threshold": 8,
            "weekly_overtime_threshold": 40,
            "require_approval": True
        }
    }
    
    try:
        if SCHEDULE_CONFIG_FILE.exists():
            with open(SCHEDULE_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            save_schedule_config(default_config)
            return default_config
    except Exception as e:
        print_warning(f"Error loading schedule config: {e}")
        return default_config

def save_schedule_config(config):
    """Save schedule adherence configuration"""
    try:
        with open(SCHEDULE_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print_warning(f"Error saving schedule config: {e}")
        return False

# =============================================================================
# Schedule Data Storage (actual schedule data, not configuration)
# =============================================================================

SCHEDULE_DATA_FILE = Path(__file__).parent / 'schedule_data.json'

def load_schedule_data():
    """Load schedule data from JSON file (not database)"""
    default_data = {
        "shifts": [],  # Store agent shifts here
        "templates": [  # Default templates
            {"id": 1, "name": "morning", "start": "08:00", "end": "16:00", "break": 30, "color": "cyan"},
            {"id": 2, "name": "afternoon", "start": "14:00", "end": "22:00", "break": 30, "color": "yellow"},
            {"id": 3, "name": "evening", "start": "22:00", "end": "06:00", "break": 45, "color": "magenta"},
            {"id": 4, "name": "standard", "start": "09:00", "end": "17:00", "break": 30, "color": "green"},
            {"id": 5, "name": "early", "start": "06:00", "end": "14:00", "break": 30, "color": "blue"},
            {"id": 6, "name": "late", "start": "16:00", "end": "00:00", "break": 30, "color": "red"}
        ],
        "last_updated": None
    }
    
    try:
        if SCHEDULE_DATA_FILE.exists():
            with open(SCHEDULE_DATA_FILE, 'r') as f:
                data = json.load(f)
                if "templates" not in data or not data["templates"]:
                    data["templates"] = default_data["templates"]
                if "shifts" not in data:
                    data["shifts"] = []
                return data
        else:
            save_schedule_data(default_data)
            return default_data
    except Exception as e:
        print_warning(f"Error loading schedule data: {e}")
        return default_data

def save_schedule_data(data):
    """Save schedule data to JSON file"""
    try:
        SCHEDULE_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SCHEDULE_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        print_warning(f"Error saving schedule data: {e}")
        return False

# =============================================================================
# Campaign Type Classification (NEW - added March 2025)
# =============================================================================

def load_campaign_types():
    """Load campaign type classifications"""
    CAMPAIGN_TYPES_FILE = Path(__file__).parent / "campaign_types.json"
    
    default_types = {
        "sales": [],
        "support": [],
        "leads": [],
        "other": [],
        "classifications": {
            "default_type": "other",
            "auto_classify": True,
            "last_updated": datetime.now().strftime('%Y-%m-%d')
        }
    }
    
    try:
        if CAMPAIGN_TYPES_FILE.exists():
            with open(CAMPAIGN_TYPES_FILE, 'r') as f:
                config = json.load(f)
                # Merge missing keys from defaults
                for key in default_types:
                    if key not in config:
                        config[key] = default_types[key]
                # Also merge missing sub-keys in classifications
                for subkey, subvalue in default_types["classifications"].items():
                    if subkey not in config["classifications"]:
                        config["classifications"][subkey] = subvalue
                return config
        else:
            save_campaign_types(default_types)
            return default_types
    except Exception as e:
        print_warning(f"Error loading campaign types: {e}")
        return default_types

def save_campaign_types(config):
    """Save campaign type classifications"""
    CAMPAIGN_TYPES_FILE = Path(__file__).parent / "campaign_types.json"
    try:
        with open(CAMPAIGN_TYPES_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print_warning(f"Error saving campaign types: {e}")
        return False

def get_campaigns_by_type(campaign_type):
    """Get all campaigns of a specific type"""
    types_config = load_campaign_types()
    # Normalize input (in case someone passes "Sales" or "SALES")
    campaign_type = campaign_type.lower().strip()
    return types_config.get(campaign_type, [])