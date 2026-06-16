#!/usr/bin/env python3
# =============================================================================
# File:         system_health.py
# Version:      1.0.0
# Date:         2026-02-27
# Description:  System health monitoring for servers and services
# Location:     D:\Altria_Ops\alerts\system_health.py
# =============================================================================

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
import json
from pathlib import Path
import subprocess
import platform
import psutil
import os
import socket

# =============================================================================
# Configuration
# =============================================================================

SYSTEM_HEALTH_CONFIG_FILE = Path(__file__).parent.parent / "config" / "system_health_config.json"

DEFAULT_HEALTH_CONFIG = {
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

# =============================================================================
# Config Management
# =============================================================================

def load_health_config():
    """Load system health configuration"""
    if SYSTEM_HEALTH_CONFIG_FILE.exists():
        try:
            with open(SYSTEM_HEALTH_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key, value in DEFAULT_HEALTH_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            print_warning(f"Could not load health config: {e}")
    
    save_health_config(DEFAULT_HEALTH_CONFIG)
    return DEFAULT_HEALTH_CONFIG.copy()

def save_health_config(config):
    """Save system health configuration"""
    try:
        SYSTEM_HEALTH_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SYSTEM_HEALTH_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print_error(f"Cannot save health config: {e}")
        return False

# =============================================================================
# Health Check Functions
# =============================================================================

def check_database_health():
    """Check database connectivity and performance"""
    config = load_health_config()
    db_config = config["health_checks"]["database"]
    
    if not db_config["enabled"]:
        return None
    
    try:
        import time
        start = time.time()
        
        # Simple query to test connection
        result = db.execute_query("SELECT 1 as test")
        
        elapsed_ms = (time.time() - start) * 1000
        
        status = "healthy"
        if elapsed_ms > db_config["critical_threshold_ms"]:
            status = "critical"
        elif elapsed_ms > db_config["warning_threshold_ms"]:
            status = "warning"
        
        return {
            "check": "database",
            "status": status,
            "response_time_ms": round(elapsed_ms, 2),
            "connected": True,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "check": "database",
            "status": "critical",
            "error": str(e),
            "connected": False,
            "timestamp": datetime.now().isoformat()
        }

def check_system_resources():
    """Check CPU, memory, and load averages"""
    config = load_health_config()
    thresholds = config["alert_thresholds"]
    
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Load average
        load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
        load_1min = load_avg[0]
        
        # Determine status
        cpu_status = "healthy"
        if cpu_percent > thresholds["cpu_critical"]:
            cpu_status = "critical"
        elif cpu_percent > thresholds["cpu_warning"]:
            cpu_status = "warning"
        
        memory_status = "healthy"
        if memory_percent > thresholds["memory_critical"]:
            memory_status = "critical"
        elif memory_percent > thresholds["memory_warning"]:
            memory_status = "warning"
        
        load_status = "healthy"
        if load_1min > thresholds["load_critical"]:
            load_status = "critical"
        elif load_1min > thresholds["load_warning"]:
            load_status = "warning"
        
        overall_status = "healthy"
        if "critical" in [cpu_status, memory_status, load_status]:
            overall_status = "critical"
        elif "warning" in [cpu_status, memory_status, load_status]:
            overall_status = "warning"
        
        return {
            "check": "system_resources",
            "status": overall_status,
            "cpu": {
                "percent": cpu_percent,
                "status": cpu_status
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent": memory_percent,
                "status": memory_status
            },
            "load": {
                "1min": round(load_1min, 2),
                "5min": round(load_avg[1], 2),
                "15min": round(load_avg[2], 2),
                "status": load_status
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "check": "system_resources",
            "status": "unknown",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def check_disk_space():
    """Check disk space on configured paths"""
    config = load_health_config()
    disk_config = config["health_checks"]["disk_space"]
    
    if not disk_config["enabled"]:
        return None
    
    results = []
    overall_status = "healthy"
    
    for path in disk_config["paths"]:
        try:
            if platform.system() == "Windows":
                # Windows path checking
                if os.path.exists(path):
                    usage = psutil.disk_usage(path)
                    free_gb = usage.free / (1024**3)
                else:
                    free_gb = 999  # Path doesn't exist, assume OK
            else:
                # Unix path checking
                stat = os.statvfs(path)
                free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            
            status = "healthy"
            if free_gb < disk_config["critical_threshold_gb"]:
                status = "critical"
                overall_status = "critical"
            elif free_gb < disk_config["warning_threshold_gb"]:
                status = "warning"
                if overall_status != "critical":
                    overall_status = "warning"
            
            results.append({
                "path": path,
                "free_gb": round(free_gb, 2),
                "status": status
            })
        except Exception as e:
            results.append({
                "path": path,
                "error": str(e),
                "status": "unknown"
            })
    
    return {
        "check": "disk_space",
        "status": overall_status,
        "disks": results,
        "timestamp": datetime.now().isoformat()
    }

def check_services():
    """Check if required services are running"""
    config = load_health_config()
    services_config = config["health_checks"]["services"]
    
    if not services_config["enabled"]:
        return None
    
    results = []
    overall_status = "healthy"
    
    for service in services_config["services"]:
        try:
            if platform.system() == "Windows":
                # Windows service check
                result = subprocess.run(
                    f'sc query "{service}"',
                    shell=True,
                    capture_output=True,
                    text=True
                )
                running = "RUNNING" in result.stdout
            else:
                # Unix service check
                result = subprocess.run(
                    f'systemctl is-active {service}',
                    shell=True,
                    capture_output=True,
                    text=True
                )
                running = result.returncode == 0
            
            status = "healthy" if running else "critical"
            if not running:
                overall_status = "critical"
            
            results.append({
                "service": service,
                "running": running,
                "status": status
            })
        except Exception as e:
            results.append({
                "service": service,
                "error": str(e),
                "status": "unknown"
            })
    
    return {
        "check": "services",
        "status": overall_status,
        "services": results,
        "timestamp": datetime.now().isoformat()
    }

def check_backups():
    """Check backup age and existence"""
    config = load_health_config()
    backup_config = config["health_checks"]["backup"]
    
    if not backup_config["enabled"]:
        return None
    
    results = []
    overall_status = "healthy"
    max_age = backup_config["max_age_hours"]
    
    for path in backup_config["backup_paths"]:
        try:
            if os.path.exists(path):
                # Get newest file in directory
                files = [f for f in Path(path).glob('*') if f.is_file()]
                if files:
                    newest = max(files, key=lambda x: x.stat().st_mtime)
                    age_hours = (datetime.now().timestamp() - newest.stat().st_mtime) / 3600
                    
                    status = "healthy"
                    if age_hours > max_age * 2:
                        status = "critical"
                        overall_status = "critical"
                    elif age_hours > max_age:
                        status = "warning"
                        if overall_status != "critical":
                            overall_status = "warning"
                    
                    results.append({
                        "path": path,
                        "newest_backup": newest.name,
                        "age_hours": round(age_hours, 1),
                        "status": status
                    })
                else:
                    results.append({
                        "path": path,
                        "error": "No backup files found",
                        "status": "warning"
                    })
                    if overall_status != "critical":
                        overall_status = "warning"
            else:
                results.append({
                    "path": path,
                    "error": "Path does not exist",
                    "status": "unknown"
                })
        except Exception as e:
            results.append({
                "path": path,
                "error": str(e),
                "status": "unknown"
            })
    
    return {
        "check": "backups",
        "status": overall_status,
        "backups": results,
        "timestamp": datetime.now().isoformat()
    }

def run_all_health_checks():
    """Run all enabled health checks"""
    results = []
    
    checks = [
        check_database_health,
        check_system_resources,
        check_disk_space,
        check_services,
        check_backups
    ]
    
    for check in checks:
        try:
            result = check()
            if result:
                results.append(result)
        except Exception as e:
            results.append({
                "check": check.__name__,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    return results

# =============================================================================
# Display Functions
# =============================================================================

def show_system_health():
    """Display system health dashboard"""
    print_header("🖥️ SYSTEM HEALTH DASHBOARD", Colors.CYAN)
    print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    print("\nRunning health checks...")
    results = run_all_health_checks()
    
    # Overall status
    critical = any(r['status'] == 'critical' for r in results)
    warning = any(r['status'] == 'warning' for r in results)
    
    if critical:
        overall_color = Colors.RED
        overall_status = "🔴 CRITICAL"
    elif warning:
        overall_color = Colors.YELLOW
        overall_status = "🟡 WARNING"
    else:
        overall_color = Colors.GREEN
        overall_status = "✅ HEALTHY"
    
    print_color(f"\nOverall System Status: {overall_status}", overall_color)
    print("=" * 80)
    
    for result in results:
        check = result['check'].replace('_', ' ').title()
        
        if result['status'] == 'critical':
            color = Colors.RED
            symbol = "🔴"
        elif result['status'] == 'warning':
            color = Colors.YELLOW
            symbol = "🟡"
        elif result['status'] == 'healthy':
            color = Colors.GREEN
            symbol = "✅"
        else:
            color = Colors.BLUE
            symbol = "❓"
        
        print_color(f"\n{symbol} {check}", color)
        print("-" * 40)
        
        # Database check
        if result['check'] == 'database':
            if 'response_time_ms' in result:
                print(f"  Response Time: {result['response_time_ms']}ms")
            if 'error' in result:
                print(f"  Error: {result['error']}")
        
        # System resources
        elif result['check'] == 'system_resources':
            if 'cpu' in result:
                cpu_color = Colors.RED if result['cpu']['status'] == 'critical' else Colors.YELLOW if result['cpu']['status'] == 'warning' else Colors.GREEN
                print_color(f"  CPU: {result['cpu']['percent']}%", cpu_color)
            
            if 'memory' in result:
                mem_color = Colors.RED if result['memory']['status'] == 'critical' else Colors.YELLOW if result['memory']['status'] == 'warning' else Colors.GREEN
                print_color(f"  Memory: {result['memory']['percent']}% ({result['memory']['used_gb']}GB/{result['memory']['total_gb']}GB)", mem_color)
            
            if 'load' in result:
                load_color = Colors.RED if result['load']['status'] == 'critical' else Colors.YELLOW if result['load']['status'] == 'warning' else Colors.GREEN
                print_color(f"  Load (1min): {result['load']['1min']}", load_color)
        
        # Disk space
        elif result['check'] == 'disk_space':
            for disk in result['disks']:
                if disk['status'] == 'critical':
                    disk_color = Colors.RED
                elif disk['status'] == 'warning':
                    disk_color = Colors.YELLOW
                else:
                    disk_color = Colors.GREEN
                
                if 'free_gb' in disk:
                    print_color(f"  {disk['path']}: {disk['free_gb']}GB free", disk_color)
                else:
                    print(f"  {disk['path']}: {disk.get('error', 'Unknown')}")
        
        # Services
        elif result['check'] == 'services':
            for svc in result['services']:
                if svc['status'] == 'critical':
                    svc_color = Colors.RED
                    status_text = "❌ STOPPED"
                elif svc['status'] == 'healthy':
                    svc_color = Colors.GREEN
                    status_text = "✅ RUNNING"
                else:
                    svc_color = Colors.YELLOW
                    status_text = "❓ UNKNOWN"
                
                print_color(f"  {svc['service']}: {status_text}", svc_color)
        
        # Backups
        elif result['check'] == 'backups':
            for backup in result['backups']:
                if backup['status'] == 'critical':
                    b_color = Colors.RED
                elif backup['status'] == 'warning':
                    b_color = Colors.YELLOW
                else:
                    b_color = Colors.GREEN
                
                if 'age_hours' in backup:
                    print_color(f"  {backup['path']}: {backup['age_hours']} hours old", b_color)
                else:
                    print(f"  {backup['path']}: {backup.get('error', 'Unknown')}")
    
    print("\n" + "=" * 80)
    input("\nPress Enter to continue...")

def configure_health_checks():
    """Configure health check settings"""
    config = load_health_config()
    
    while True:
        print_header("⚙️ HEALTH CHECK CONFIGURATION", Colors.GREEN)
        
        checks = config["health_checks"]
        thresholds = config["alert_thresholds"]
        
        print("\n📊 HEALTH CHECKS:")
        for i, (check, settings) in enumerate(checks.items(), 1):
            enabled = "✅" if settings.get("enabled", True) else "❌"
            print(f"  {i}. {enabled} {check.replace('_', ' ').title()}")
        
        print("\n📈 ALERT THRESHOLDS:")
        print(f"  CPU Warning: {thresholds['cpu_warning']}% | Critical: {thresholds['cpu_critical']}%")
        print(f"  Memory Warning: {thresholds['memory_warning']}% | Critical: {thresholds['memory_critical']}%")
        print(f"  Load Warning: {thresholds['load_warning']} | Critical: {thresholds['load_critical']}")
        
        print("\n0. Save and Exit")
        print("-" * 60)
        
        choice = input("\nEnter number to toggle (or 0 to exit): ").strip()
        
        if choice == '0':
            if save_health_config(config):
                print_success("Configuration saved!")
            break
        elif choice.isdigit() and 1 <= int(choice) <= len(checks):
            check_name = list(checks.keys())[int(choice)-1]
            checks[check_name]["enabled"] = not checks[check_name].get("enabled", True)
            print_success(f"Toggled {check_name}")
        else:
            print_error("Invalid choice")
        
        input("\nPress Enter to continue...")

# =============================================================================
# Main Menu
# =============================================================================

def system_health_menu():
    """Main system health menu"""
    while True:
        print_header("🖥️ SYSTEM HEALTH MONITORING", Colors.CYAN)
        print("  1. 📊 Run Health Check")
        print("  2. 📈 View Dashboard")
        print("  3. ⚙️ Configure Health Checks")
        print("  4. 📜 Health History")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_system_health()
        elif choice == '2':
            show_system_health()  # Same for now
        elif choice == '3':
            configure_health_checks()
        elif choice == '4':
            print("\n🚧 Health History - Coming Soon! 🚧")
            input("\nPress Enter to continue...")
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    system_health_menu()