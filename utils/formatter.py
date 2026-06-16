# utils/formatter.py - Date/time formatting utilities

from datetime import datetime

def format_datetime(dt):
    """Format datetime object to string"""
    if not dt:
        return "Never"
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except:
            return dt
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def format_date(dt):
    """Format date only"""
    if not dt:
        return "Never"
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, '%Y-%m-%d')
        except:
            return dt
    return dt.strftime('%Y-%m-%d')

def format_time(dt):
    """Format time only"""
    if not dt:
        return "Never"
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, '%H:%M:%S')
        except:
            return dt
    return dt.strftime('%H:%M:%S')

def sec_to_hms(seconds):
    """Convert seconds to HH:MM:SS format"""
    if seconds is None or seconds <= 0:
        return "0:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    else:
        return f"{m}:{s:02d}"

def time_ago(dt):
    """Get human readable time ago"""
    if not dt:
        return "Never"
    
    if isinstance(dt, str):
        dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
    
    now = datetime.now()
    diff = now - dt
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"