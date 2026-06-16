# utils/colors.py - Color-coded output utilities with emoji fallback

import os
import sys
from datetime import datetime

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    GOLD = '\033[93m'
    SILVER = '\033[97m'
    BRONZE = '\033[33m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Global settings
_current_screen = "MAIN MENU"
_use_emoji = True  # Default to True, will be set by main.py

def set_use_emoji(use_emoji):
    """Enable or disable emoji usage"""
    global _use_emoji
    _use_emoji = use_emoji

def get_icon(icon_name):
    """Return emoji or ASCII fallback based on setting"""
    icons = {
        # Status icons
        'success': ('✅', '[OK]'),
        'error': ('❌', '[ERR]'),
        'warning': ('⚠️', '[WARN]'),
        'info': ('ℹ️', '[INFO]'),
        
        # Navigation
        'back': ('🔙', '<-'),
        'exit': ('🚪', '[EXIT]'),
        
        # Modules
        'settings': ('⚙️', '[SET]'),
        'search': ('🔎', '[SRCH]'),
        'agent': ('👥', '[AGT]'),
        'campaign': ('📊', '[CAMP]'),
        'report': ('📈', '[REP]'),
        'alert': ('⚠️', '[ALRT]'),
        'quality': ('🎯', ['QUAL']),
        'predict': ('📈', '[PRED]'),
        'anomaly': ('🔍', '[ANOM]'),
        'query': ('📊', '[QRY]'),
        'help': ('📚', '[HELP]'),
        
        # UI elements
        'folder': ('📁', '[DIR]'),
        'open_folder': ('📂', '[OPEN]'),
        'clock': ('⏰', '[TIME]'),
        'calendar': ('📅', '[DATE]'),
        'chart': ('📊', '[CHART]'),
        'trend': ('📈', '[TREND]'),
        'phone': ('📞', '[CALL]'),
        'note': ('📝', '[NOTE]'),
        'trophy': ('🏆', '[TOP]'),
        
        # Status indicators
        'online': ('🟢', '[ON]'),
        'offline': ('⚪', '[OFF]'),
        'pause': ('⏸️', '[PAUSE]'),
        'queue': ('⏱️', '[QUEUE]'),
        'call': ('📞', '[CALL]'),
        
        # Language flags
        'flag_en': ('🇬🇧', '[EN]'),
        'flag_es': ('🇪🇸', '[ES]'),
        'flag_fr': ('🇫🇷', '[FR]'),
        'flag_de': ('🇩🇪', '[DE]'),
        'flag_ar': ('🇸🇦', '[AR]'),
        'flag_zh': ('🇨🇳', '[ZH]'),
    }
    
    if icon_name in icons:
        emoji, ascii_fallback = icons[icon_name]
        return emoji if _use_emoji else ascii_fallback
    return '•'

def set_current_screen(screen_name):
    """Set the current screen name for the header"""
    global _current_screen
    _current_screen = screen_name

def print_persistent_header(screen_name=None):
    """Print the main banner and current screen header"""
    from utils.formatter import format_datetime
    
    # Clear screen first
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Print main banner
    print_color("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                    ALTRIA OPERATIONS SYSTEM                   ║
    ║                       Call Center Analytics                   ║
    ╚═══════════════════════════════════════════════════════════════╝
        """, Colors.CYAN)
    
    # Print server time
    now = datetime.now()
    print(f"  Server Time: {format_datetime(now)}")
    print(f"  User: Not Logged In")
    print()
    
    # Print current screen header if provided
    if screen_name:
        set_current_screen(screen_name)
        print_header(f" {screen_name} ", Colors.CYAN)
    elif _current_screen:
        print_header(f" {_current_screen} ", Colors.CYAN)

def print_color(text, color=Colors.RESET, bold=False, end='\n'):
    """Print colored text"""
    if bold:
        print(f"{Colors.BOLD}{color}{text}{Colors.RESET}", end=end)
    else:
        print(f"{color}{text}{Colors.RESET}", end=end)

def print_header(text, color=Colors.CYAN):
    """Print a formatted header"""
    print(f"\n{color}{'=' * 60}{Colors.RESET}")
    print(f"{color}{text.center(60)}{Colors.RESET}")
    print(f"{color}{'=' * 60}{Colors.RESET}")

def print_success(text):
    """Print success message"""
    icon = get_icon('success')
    print(f"{Colors.GREEN}{icon} {text}{Colors.RESET}")

def print_error(text):
    """Print error message"""
    icon = get_icon('error')
    print(f"{Colors.RED}{icon} {text}{Colors.RESET}")

def print_warning(text):
    """Print warning message"""
    icon = get_icon('warning')
    print(f"{Colors.YELLOW}{icon}  {text}{Colors.RESET}")

def print_info(text):
    """Print info message"""
    icon = get_icon('info')
    print(f"{Colors.BLUE}{icon}  {text}{Colors.RESET}")