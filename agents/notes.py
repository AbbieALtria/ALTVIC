#!/usr/bin/env python3
# =============================================================================
# File:         notes.py
# Version:      1.0.0
# Date:         2026-02-28
# Description:  Agent Notes & Feedback system (File-based, no database changes)
# Location:     D:/Altria_Ops/agents/notes.py
# =============================================================================

import os
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning
from utils.formatter import format_datetime, time_ago
from agents.dashboard import get_all_agents, show_agent_list, get_agent_by_selection, get_agent_name

# Configuration
NOTES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'agent_notes')
os.makedirs(NOTES_DIR, exist_ok=True)

NOTES_INDEX_FILE = os.path.join(NOTES_DIR, 'notes_index.json')
NOTES_TYPES = ['general', 'coaching', 'warning', 'achievement', 'feedback']

def init_notes_system():
    """Initialize the notes system (creates directory and index file)"""
    try:
        os.makedirs(NOTES_DIR, exist_ok=True)
        
        # Create index file if it doesn't exist
        if not os.path.exists(NOTES_INDEX_FILE):
            with open(NOTES_INDEX_FILE, 'w') as f:
                json.dump({
                    'agents': {},
                    'last_id': 0,
                    'created_at': datetime.now().isoformat()
                }, f, indent=2)
            print_success(f"Notes system initialized at {NOTES_DIR}")
        return True
    except Exception as e:
        print_error(f"Failed to initialize notes system: {e}")
        return False

def load_notes_index():
    """Load the notes index file"""
    try:
        if os.path.exists(NOTES_INDEX_FILE):
            with open(NOTES_INDEX_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print_error(f"Error loading notes index: {e}")
    
    # Return default structure if file doesn't exist or is corrupted
    return {'agents': {}, 'last_id': 0}

def save_notes_index(index):
    """Save the notes index file"""
    try:
        with open(NOTES_INDEX_FILE, 'w') as f:
            json.dump(index, f, indent=2)
        return True
    except Exception as e:
        print_error(f"Error saving notes index: {e}")
        return False

def get_agent_notes_file(agent_username):
    """Get the notes file path for a specific agent"""
    # Sanitize username for filename
    safe_name = agent_username.replace('/', '_').replace('\\', '_').replace(' ', '_')
    return os.path.join(NOTES_DIR, f"{safe_name}_notes.json")

def load_agent_notes(agent_username):
    """Load notes for a specific agent"""
    notes_file = get_agent_notes_file(agent_username)
    
    if os.path.exists(notes_file):
        try:
            with open(notes_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print_error(f"Error loading notes for {agent_username}: {e}")
    
    # Return default structure
    return {
        'agent_username': agent_username,
        'notes': [],
        'stats': {
            'total_notes': 0,
            'last_note': None
        }
    }

def save_agent_notes(agent_username, notes_data):
    """Save notes for a specific agent"""
    try:
        notes_file = get_agent_notes_file(agent_username)
        with open(notes_file, 'w') as f:
            json.dump(notes_data, f, indent=2)
        return True
    except Exception as e:
        print_error(f"Error saving notes for {agent_username}: {e}")
        return False

def add_note(agent_username, note_text, note_type='general', created_by='system', is_important=False, is_private=False):
    """Add a new note for an agent"""
    try:
        # Load existing notes
        notes_data = load_agent_notes(agent_username)
        
        # Load index to get next ID
        index = load_notes_index()
        next_id = index.get('last_id', 0) + 1
        
        # Create new note
        now = datetime.now().isoformat()
        new_note = {
            'id': next_id,
            'agent_username': agent_username,
            'note_text': note_text,
            'note_type': note_type,
            'created_by': created_by,
            'created_at': now,
            'updated_at': now,
            'is_important': is_important,
            'is_private': is_private
        }
        
        # Add to notes list
        notes_data['notes'].insert(0, new_note)  # Add to beginning for newest first
        
        # Update stats
        notes_data['stats']['total_notes'] = len(notes_data['notes'])
        notes_data['stats']['last_note'] = now
        
        # Update agent in index
        if agent_username not in index['agents']:
            index['agents'][agent_username] = {
                'total_notes': 0,
                'last_note': None
            }
        
        index['agents'][agent_username]['total_notes'] = len(notes_data['notes'])
        index['agents'][agent_username]['last_note'] = now
        index['last_id'] = next_id
        
        # Save both files
        save_agent_notes(agent_username, notes_data)
        save_notes_index(index)
        
        return True, next_id
    except Exception as e:
        print_error(f"Error adding note: {e}")
        return False, None

def get_notes_for_agent(agent_username, include_private=False, note_type=None):
    """Get notes for a specific agent with optional filters"""
    notes_data = load_agent_notes(agent_username)
    
    notes = notes_data.get('notes', [])
    
    # Apply filters
    filtered = []
    for note in notes:
        # Filter private notes
        if note.get('is_private', False) and not include_private:
            continue
        
        # Filter by type
        if note_type and note.get('note_type') != note_type:
            continue
        
        filtered.append(note)
    
    return filtered

def delete_note(agent_username, note_id):
    """Delete a note by ID"""
    try:
        notes_data = load_agent_notes(agent_username)
        original_count = len(notes_data['notes'])
        
        # Filter out the note to delete
        notes_data['notes'] = [n for n in notes_data['notes'] if n.get('id') != note_id]
        
        if len(notes_data['notes']) < original_count:
            # Update stats
            notes_data['stats']['total_notes'] = len(notes_data['notes'])
            
            # Update index
            index = load_notes_index()
            if agent_username in index['agents']:
                index['agents'][agent_username]['total_notes'] = len(notes_data['notes'])
                if notes_data['notes']:
                    index['agents'][agent_username]['last_note'] = notes_data['notes'][0]['created_at']
                else:
                    index['agents'][agent_username]['last_note'] = None
            
            save_agent_notes(agent_username, notes_data)
            save_notes_index(index)
            return True
        return False
    except Exception as e:
        print_error(f"Error deleting note: {e}")
        return False

def get_all_agents_with_notes():
    """Get list of all agents that have notes"""
    index = load_notes_index()
    return index.get('agents', {})

def show_notes_menu():
    """Display the main notes menu"""
    while True:
        print_header("📝 AGENT NOTES & FEEDBACK", Colors.CYAN)
        print("  1. 📋 View All Agents with Notes")
        print("  2. 👤 View Notes for Specific Agent")
        print("  3. ➕ Add New Note")
        print("  4. 🗑️ Delete Note")
        print("  5. 🔍 Search Notes")
        print("  6. 📊 Notes Statistics")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_agents_with_notes()
        elif choice == '2':
            view_agent_notes()
        elif choice == '3':
            add_note_interactive()
        elif choice == '4':
            delete_note_interactive()
        elif choice == '5':
            search_notes()
        elif choice == '6':
            show_notes_statistics()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

def show_agents_with_notes():
    """Show all agents that have notes"""
    agents_with_notes = get_all_agents_with_notes()
    
    if not agents_with_notes:
        print_warning("No agents have notes yet")
        input("\nPress Enter to continue...")
        return
    
    print_header("📋 AGENTS WITH NOTES", Colors.GREEN)
    print(f"\n{'#':<4} {'Agent':<15} {'Name':<25} {'Notes':<8} {'Last Note'}")
    print("-" * 80)
    
    all_agents = {a['user']: a['name'] for a in get_all_agents()}
    
    for i, (agent, data) in enumerate(sorted(agents_with_notes.items()), 1):
        name = all_agents.get(agent, 'Unknown')[:25]
        last_note = time_ago(datetime.fromisoformat(data['last_note'])) if data['last_note'] else 'Never'
        
        # Color code by number of notes
        if data['total_notes'] > 10:
            color = Colors.GREEN
        elif data['total_notes'] > 5:
            color = Colors.YELLOW
        else:
            color = Colors.RESET
        
        print_color(f"{i:<4} {agent:<15} {name:<25} {data['total_notes']:<8} {last_note}", color)
    
    print("-" * 80)
    input("\nPress Enter to continue...")

def view_agent_notes():
    """View notes for a specific agent"""
    # Show agent list
    agents = show_agent_list()
    if not agents:
        input("\nPress Enter to continue...")
        return
    
    selected_agent = get_agent_by_selection(agents)
    if not selected_agent:
        return
    
    print("\nFilter options:")
    print("  1. All notes")
    print("  2. General only")
    print("  3. Coaching only")
    print("  4. Warnings only")
    print("  5. Achievements only")
    print("  6. Feedback only")
    print("  7. Important only")
    
    filter_choice = input("\nChoice (1-7): ").strip()
    
    note_type = None
    important_only = False
    include_private = False
    
    if filter_choice == '2':
        note_type = 'general'
    elif filter_choice == '3':
        note_type = 'coaching'
    elif filter_choice == '4':
        note_type = 'warning'
    elif filter_choice == '5':
        note_type = 'achievement'
    elif filter_choice == '6':
        note_type = 'feedback'
    elif filter_choice == '7':
        important_only = True
    
    # Ask about private notes
    if input("\nInclude private notes? (y/N): ").lower() == 'y':
        include_private = True
    
    notes = get_notes_for_agent(selected_agent, include_private, note_type)
    
    if important_only:
        notes = [n for n in notes if n.get('is_important', False)]
    
    agent_name = get_agent_name(selected_agent)
    
    print_header(f"📝 NOTES FOR: {selected_agent} ({agent_name})", Colors.MAGENTA)
    
    if not notes:
        print_warning(f"\nNo notes found for {selected_agent}")
        input("\nPress Enter to continue...")
        return
    
    print(f"\nTotal notes: {len(notes)}")
    print("=" * 100)
    
    for i, note in enumerate(notes, 1):
        # Color code by note type
        note_type_display = note.get('note_type', 'general').upper()
        if note.get('note_type') == 'warning':
            color = Colors.RED
            type_color = Colors.RED
        elif note.get('note_type') == 'achievement':
            color = Colors.GREEN
            type_color = Colors.GREEN
        elif note.get('note_type') == 'coaching':
            color = Colors.YELLOW
            type_color = Colors.YELLOW
        else:
            color = Colors.RESET
            type_color = Colors.BLUE
        
        # Important flag
        important_flag = "⭐ " if note.get('is_important', False) else ""
        
        # Private flag
        private_flag = "🔒 " if note.get('is_private', False) else ""
        
        created_at = datetime.fromisoformat(note['created_at']).strftime('%Y-%m-%d %H:%M')
        
        print_color(f"\n{important_flag}{private_flag}Note #{note['id']} [{type_color}{note_type_display}{Colors.RESET}]", color)
        print(f"  By: {note['created_by']} on {created_at}")
        print(f"  {note['note_text']}")
        print("-" * 100)
    
    input("\nPress Enter to continue...")

def add_note_interactive():
    """Interactively add a new note"""
    # Show agent list
    agents = show_agent_list()
    if not agents:
        input("\nPress Enter to continue...")
        return
    
    selected_agent = get_agent_by_selection(agents)
    if not selected_agent:
        return
    
    agent_name = get_agent_name(selected_agent)
    print(f"\nAdding note for: {selected_agent} ({agent_name})")
    
    print("\nNote type:")
    for i, note_type in enumerate(NOTES_TYPES, 1):
        print(f"  {i}. {note_type.capitalize()}")
    
    type_choice = input("\nSelect type (1-5) [1]: ").strip()
    
    try:
        type_idx = int(type_choice) - 1 if type_choice else 0
        note_type = NOTES_TYPES[type_idx] if 0 <= type_idx < len(NOTES_TYPES) else 'general'
    except:
        note_type = 'general'
    
    note_text = input("\nEnter note text: ").strip()
    if not note_text:
        print_error("Note text cannot be empty")
        input("\nPress Enter to continue...")
        return
    
    is_important = input("\nMark as important? (y/N): ").lower() == 'y'
    is_private = input("Mark as private? (y/N): ").lower() == 'y'
    created_by = input("Created by [system]: ").strip() or 'system'
    
    success, note_id = add_note(selected_agent, note_text, note_type, created_by, is_important, is_private)
    
    if success:
        print_success(f"Note #{note_id} added successfully!")
    else:
        print_error("Failed to add note")
    
    input("\nPress Enter to continue...")

def delete_note_interactive():
    """Interactively delete a note"""
    # Show agent list
    agents = show_agent_list()
    if not agents:
        input("\nPress Enter to continue...")
        return
    
    selected_agent = get_agent_by_selection(agents)
    if not selected_agent:
        return
    
    notes = get_notes_for_agent(selected_agent, include_private=True)
    
    if not notes:
        print_warning(f"\nNo notes found for {selected_agent}")
        input("\nPress Enter to continue...")
        return
    
    print_header(f"🗑️ DELETE NOTE - {selected_agent}", Colors.RED)
    print("\nSelect note to delete:")
    
    for i, note in enumerate(notes[:10], 1):  # Show last 10 notes
        created_at = datetime.fromisoformat(note['created_at']).strftime('%Y-%m-%d %H:%M')
        preview = note['note_text'][:50] + "..." if len(note['note_text']) > 50 else note['note_text']
        print(f"  {i}. [#{note['id']}] {created_at} - {preview}")
    
    if len(notes) > 10:
        print(f"  ... and {len(notes)-10} more")
    
    choice = input("\nEnter note number to delete (or 0 to cancel): ").strip()
    
    if choice == '0':
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(notes[:10]):
            note_id = notes[idx]['id']
            
            confirm = input(f"Are you sure you want to delete note #{note_id}? (y/N): ").lower()
            if confirm == 'y':
                if delete_note(selected_agent, note_id):
                    print_success(f"Note #{note_id} deleted successfully!")
                else:
                    print_error(f"Failed to delete note #{note_id}")
    except:
        print_error("Invalid selection")
    
    input("\nPress Enter to continue...")

def search_notes():
    """Search through all notes"""
    search_term = input("\nEnter search term: ").strip()
    
    if not search_term or len(search_term) < 3:
        print_warning("Please enter at least 3 characters")
        input("\nPress Enter to continue...")
        return
    
    print_header(f"🔍 SEARCH RESULTS FOR: '{search_term}'", Colors.CYAN)
    
    results = []
    index = load_notes_index()
    
    for agent_username in index.get('agents', {}):
        notes = get_notes_for_agent(agent_username, include_private=True)
        for note in notes:
            if search_term.lower() in note['note_text'].lower():
                results.append({
                    'agent': agent_username,
                    'note': note
                })
    
    if not results:
        print_warning(f"\nNo notes found containing '{search_term}'")
        input("\nPress Enter to continue...")
        return
    
    print(f"\nFound {len(results)} matching notes:")
    print("=" * 100)
    
    for i, result in enumerate(results[:20], 1):
        note = result['note']
        agent = result['agent']
        created_at = datetime.fromisoformat(note['created_at']).strftime('%Y-%m-%d %H:%M')
        
        # Highlight search term
        text = note['note_text']
        highlighted = text.replace(search_term, f"{Colors.YELLOW}{search_term}{Colors.RESET}")
        
        print(f"\n{i}. {Colors.GREEN}{agent}{Colors.RESET} - {created_at}")
        print(f"   {highlighted[:100]}{'...' if len(text) > 100 else ''}")
    
    if len(results) > 20:
        print(f"\n... and {len(results)-20} more matches")
    
    input("\nPress Enter to continue...")

def show_notes_statistics():
    """Show statistics about the notes system"""
    index = load_notes_index()
    agents_with_notes = index.get('agents', {})
    
    total_notes = sum(data['total_notes'] for data in agents_with_notes.values())
    total_agents = len(agents_with_notes)
    
    # Count by type
    type_counts = {t: 0 for t in NOTES_TYPES}
    
    for agent in agents_with_notes:
        notes = get_notes_for_agent(agent, include_private=True)
        for note in notes:
            note_type = note.get('note_type', 'general')
            if note_type in type_counts:
                type_counts[note_type] += 1
    
    print_header("📊 NOTES STATISTICS", Colors.BLUE)
    print(f"\n📈 OVERALL STATS:")
    print(f"  • Total Notes: {total_notes}")
    print(f"  • Agents with Notes: {total_agents}")
    print(f"  • Average Notes per Agent: {total_notes/total_agents:.1f}" if total_agents > 0 else "  • Average Notes per Agent: 0")
    
    print(f"\n📝 NOTES BY TYPE:")
    for note_type, count in type_counts.items():
        percentage = (count/total_notes*100) if total_notes > 0 else 0
        
        if note_type == 'warning':
            color = Colors.RED
        elif note_type == 'achievement':
            color = Colors.GREEN
        elif note_type == 'coaching':
            color = Colors.YELLOW
        else:
            color = Colors.BLUE
        
        print_color(f"  • {note_type.capitalize()}: {count} ({percentage:.1f}%)", color)
    
    # Most active agents
    if agents_with_notes:
        top_agents = sorted(agents_with_notes.items(), key=lambda x: x[1]['total_notes'], reverse=True)[:5]
        
        print(f"\n🏆 TOP 5 AGENTS BY NOTES:")
        for agent, data in top_agents:
            name = get_agent_name(agent)[:20]
            print(f"  • {agent} ({name}): {data['total_notes']} notes")
    
    # Storage info
    notes_files = list(Path(NOTES_DIR).glob('*_notes.json'))
    total_size = sum(f.stat().st_size for f in notes_files) / 1024  # KB
    
    print(f"\n💾 STORAGE:")
    print(f"  • Location: {NOTES_DIR}")
    print(f"  • Files: {len(notes_files)}")
    print(f"  • Total Size: {total_size:.1f} KB")
    
    input("\nPress Enter to continue...")

def notes_menu():
    """Main entry point for notes system"""
    # Initialize on first use
    init_notes_system()
    show_notes_menu()

if __name__ == "__main__":
    notes_menu()