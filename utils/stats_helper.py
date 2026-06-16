#!/usr/bin/env python3
"""
Help search module for Altria Ops
Provides search functionality across help content, commands, and documentation
"""

from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info

# Help content database
HELP_CONTENT = {
    'getting_started': {
        'description': 'Basic setup and first steps',
        'keywords': ['setup', 'install', 'first', 'begin', 'start'],
        'subsections': {
            'installation': {
                'description': 'Installing Altria Ops',
                'keywords': ['install', 'setup', 'dependencies'],
                'tips': 'Make sure you have Python 3.8+ installed'
            },
            'configuration': {
                'description': 'Configuring your environment',
                'keywords': ['config', 'settings', 'environment'],
                'tips': 'Use config.yaml for persistent settings'
            }
        }
    },
    'commands': {
        'description': 'Available commands and usage',
        'keywords': ['command', 'run', 'execute', 'cli'],
        'subsections': {
            'analyze': {
                'description': 'Run analysis on log files',
                'keywords': ['analyze', 'scan', 'check', 'inspect'],
                'tips': 'Use --verbose for detailed output'
            },
            'monitor': {
                'description': 'Monitor system in real-time',
                'keywords': ['monitor', 'watch', 'real-time', 'live'],
                'tips': 'Press Ctrl+C to stop monitoring'
            },
            'export': {
                'description': 'Export results to various formats',
                'keywords': ['export', 'save', 'csv', 'json', 'pdf'],
                'tips': 'Supported formats: CSV, JSON, PDF, HTML'
            }
        }
    },
    'troubleshooting': {
        'description': 'Common issues and solutions',
        'keywords': ['trouble', 'issue', 'error', 'fix', 'problem'],
        'subsections': {
            'connection_errors': {
                'description': 'Fix network and connection issues',
                'keywords': ['connection', 'network', 'timeout', 'unreachable'],
                'tips': 'Check firewall settings and proxy configuration'
            },
            'permission_denied': {
                'description': 'Resolve permission problems',
                'keywords': ['permission', 'access', 'denied', 'sudo'],
                'tips': 'Run with appropriate privileges or check file ownership'
            }
        }
    },
    'advanced': {
        'description': 'Advanced features and customization',
        'keywords': ['advanced', 'custom', 'plugin', 'extension'],
        'subsections': {
            'plugins': {
                'description': 'Extend functionality with plugins',
                'keywords': ['plugin', 'extension', 'addon', 'module'],
                'tips': 'Place plugins in the ~/.altria_ops/plugins directory'
            },
            'api': {
                'description': 'Use the Altria Ops API',
                'keywords': ['api', 'rest', 'endpoint', 'integration'],
                'tips': 'API documentation available at /docs when server is running'
            },
            'custom_commands': {
                'description': 'Create your own commands',
                'keywords': ['custom', 'command', 'script', 'automation'],
                'tips': 'Extend the Command class and register in config'
            }
        }
    }
}

KEYBOARD_SHORTCUTS = {
    'Ctrl+C': 'Stop current operation',
    'Ctrl+D': 'Exit application',
    'Ctrl+L': 'Clear screen',
    'Tab': 'Auto-complete commands',
    'Up/Down': 'Navigate command history',
    'F1': 'Show help',
    'F5': 'Refresh view',
    '/': 'Search in current view',
    'q': 'Quit current view',
    'h': 'Show help for current context',
    '?': 'Show keyboard shortcuts',
    'Esc': 'Cancel current operation',
    'Enter': 'Select current item'
}

def search_help(search_term, min_relevance=50):
    """
    Search help content and return relevant results
    
    Args:
        search_term (str): The term to search for
        min_relevance (int): Minimum relevance score (0-100) - currently unused
    
    Returns:
        List of tuples: (result_type, title, description, section)
            result_type: Type of result (section, section_desc, section_keyword, 
                        subsection, subsection_desc, subsection_keyword, tip, shortcut)
            title: Title of the result
            description: Description or content
            section: Parent section (None for sections and shortcuts)
    """
    search_term = search_term.lower().strip()
    results = []
    
    if not search_term or len(search_term) < 2:
        return results
    
    # Search through all sections
    for section, section_data in HELP_CONTENT.items():
        # Search in section title
        if search_term in section.lower():
            results.append(('section', section, section_data['description'], None))
        
        # Search in section description
        if search_term in section_data['description'].lower():
            results.append(('section_desc', section, section_data['description'], None))
        
        # Search in section keywords
        for keyword in section_data.get('keywords', []):
            if search_term in keyword.lower():
                results.append(('section_keyword', section, section_data['description'], None))
                break
        
        # Search in subsections
        for sub_name, sub_data in section_data.get('subsections', {}).items():
            # Search in subsection title
            if search_term in sub_name.lower():
                results.append(('subsection', sub_name, sub_data['description'], section))
            
            # Search in subsection description
            if search_term in sub_data['description'].lower():
                results.append(('subsection_desc', sub_name, sub_data['description'], section))
            
            # Search in subsection keywords
            for keyword in sub_data.get('keywords', []):
                if search_term in keyword.lower():
                    results.append(('subsection_keyword', sub_name, sub_data['description'], section))
                    break
            
            # Search in tips
            if 'tips' in sub_data and search_term in sub_data['tips'].lower():
                results.append(('tip', sub_name, sub_data['tips'], section))
    
    # Search in keyboard shortcuts
    for key, desc in KEYBOARD_SHORTCUTS.items():
        if search_term in key.lower() or search_term in desc.lower():
            results.append(('shortcut', key, desc, None))
    
    # Remove duplicates
    seen = set()
    unique_results = []
    for rtype, title, desc, section in results:
        key = (rtype, title, desc)
        if key not in seen:
            seen.add(key)
            unique_results.append((rtype, title, desc, section))
    
    return unique_results

def display_search_results(results, search_term):
    """
    Display search results in a formatted way
    
    Args:
        results (list): List of result tuples from search_help
        search_term (str): The original search term
    
    Returns:
        bool: True if results were displayed, False if no results
    """
    if not results:
        print_warning(f"No results found for '{search_term}'")
        print_info("Try:")
        print("  • Using different words")
        print("  • Checking spelling")
        print("  • Searching for related terms")
        return False
    
    print_color(f"\n✅ Found {len(results)} results for '{search_term}':", Colors.GREEN)
    print("  " + "─" * 80)
    
    for i, (rtype, title, desc, section) in enumerate(results[:20], 1):
        # Determine icon based on result type
        if rtype.startswith('section'):
            icon = "📑"
            type_text = "SECTION"
            color = Colors.BLUE
            location = f"[{title}]"
        elif rtype.startswith('subsection'):
            icon = "📘"
            type_text = "FEATURE"
            color = Colors.GREEN
            location = f"[{section} → {title}]"
        elif rtype == 'tip':
            icon = "💡"
            type_text = "TIP"
            color = Colors.YELLOW
            location = f"[{section}]"
        elif rtype == 'shortcut':
            icon = "⌨️"
            type_text = "SHORTCUT"
            color = Colors.MAGENTA
            location = ""
        else:
            icon = "📌"
            type_text = "RESULT"
            color = Colors.RESET
            location = ""
        
        # Print result
        print_color(f"\n  {i:2d}. {icon} {type_text}", color)
        if location:
            print(f"      {location}")
        print(f"      {desc[:100]}{'...' if len(desc) > 100 else ''}")
    
    if len(results) > 20:
        print_info(f"\n  ... and {len(results) - 20} more results")
    
    print("\n  " + "─" * 80)
    return True

def get_section_details(section):
    """
    Get details for a specific section
    
    Args:
        section (str): Section name
    
    Returns:
        dict: Section details or default dict if not found
    """
    if section in HELP_CONTENT:
        return HELP_CONTENT[section]
    return {"description": "Section not found"}

def get_subsection_details(section, sub):
    """
    Get details for a specific subsection
    
    Args:
        section (str): Parent section name
        sub (str): Subsection name
    
    Returns:
        dict: Subsection details or default dict if not found
    """
    if section in HELP_CONTENT and sub in HELP_CONTENT[section].get('subsections', {}):
        return HELP_CONTENT[section]['subsections'][sub]
    return {"description": "Subsection not found"}

def get_all_sections():
    """
    Get a list of all available sections
    
    Returns:
        list: Section names
    """
    return list(HELP_CONTENT.keys())

def get_all_subsections(section):
    """
    Get a list of all subsections for a given section
    
    Args:
        section (str): Section name
    
    Returns:
        list: Subsection names or empty list if section not found
    """
    if section in HELP_CONTENT:
        return list(HELP_CONTENT[section].get('subsections', {}).keys())
    return []

def get_keyboard_shortcuts():
    """
    Get all keyboard shortcuts
    
    Returns:
        dict: Keyboard shortcuts and descriptions
    """
    return KEYBOARD_SHORTCUTS

def display_keyboard_shortcuts():
    """
    Display all keyboard shortcuts in a formatted way
    """
    print_header("⌨️  Keyboard Shortcuts")
    print("  " + "─" * 60)
    
    for key, desc in KEYBOARD_SHORTCUTS.items():
        print_color(f"  {key:15}", Colors.CYAN, end="")
        print(f" - {desc}")
    
    print("  " + "─" * 60)

if __name__ == "__main__":
    # Simple test when run directly
    print_header("Help Search Module Test")
    
    # Test search
    test_terms = ["install", "monitor", "shortcut", "xyz"]
    
    for term in test_terms:
        print_color(f"\nSearching for: '{term}'", Colors.YELLOW)
        results = search_help(term)
        display_search_results(results, term)
    
    # Test keyboard shortcuts display
    display_keyboard_shortcuts()
    
    # Test section access
    print_color("\nGetting section details:", Colors.YELLOW)
    section = "commands"
    details = get_section_details(section)
    print(f"  {section}: {details['description']}")
    
    subsection = "analyze"
    sub_details = get_subsection_details(section, subsection)
    print(f"  {section} → {subsection}: {sub_details['description']}")
    if 'tips' in sub_details:
        print(f"    Tip: {sub_details['tips']}")