# campaigns/__init__.py
from .performance import campaign_performance_menu
from .queue_monitor import queue_monitor_menu
from .trends import trends_menu

__all__ = ['campaign_performance_menu', 'queue_monitor_menu', 'trends_menu']