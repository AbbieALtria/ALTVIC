# agents/schedule_db.py - Schedule database operations

from core.database import db
from datetime import datetime, timedelta
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info

def create_schedule_tables():
    """Create schedule tables if they don't exist"""
    try:
        # Check if tables exist
        check = db.execute_query("SHOW TABLES LIKE 'agent_shifts'")
        if not check:
            print("Creating schedule tables...")
            
            # Create agent_shifts table
            db.execute_query("""
                CREATE TABLE agent_shifts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    agent_username VARCHAR(50) NOT NULL,
                    shift_date DATE NOT NULL,
                    start_time TIME NOT NULL,
                    end_time TIME NOT NULL,
                    shift_type VARCHAR(20) DEFAULT 'standard',
                    break_duration INT DEFAULT 30,
                    approved BOOLEAN DEFAULT FALSE,
                    notes TEXT,
                    created_by VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_agent_date (agent_username, shift_date)
                )
            """)
            
            # Create schedule_exceptions table (PTO, training, etc.)
            db.execute_query("""
                CREATE TABLE schedule_exceptions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    agent_username VARCHAR(50) NOT NULL,
                    exception_date DATE NOT NULL,
                    exception_type VARCHAR(30) NOT NULL,
                    start_time TIME,
                    end_time TIME,
                    reason TEXT,
                    approved BOOLEAN DEFAULT FALSE,
                    created_by VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_agent_exception (agent_username, exception_date)
                )
            """)
            
            # Create shift_templates table for reusable templates
            db.execute_query("""
                CREATE TABLE shift_templates (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    template_name VARCHAR(50) NOT NULL,
                    start_time TIME NOT NULL,
                    end_time TIME NOT NULL,
                    break_duration INT DEFAULT 30,
                    shift_type VARCHAR(20) DEFAULT 'standard',
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_template (template_name)
                )
            """)
            
            # Create schedule_predictions table for forecast comparison
            db.execute_query("""
                CREATE TABLE schedule_predictions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    prediction_date DATE NOT NULL,
                    predicted_calls INT,
                    required_agents INT,
                    actual_scheduled INT,
                    gap INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_pred_date (prediction_date)
                )
            """)
            
            print_success("Schedule tables created successfully!")
            return True
    except Exception as e:
        print_error(f"Error creating tables: {e}")
        return False

def add_shift_template(template_name, start_time, end_time, break_duration=30, shift_type='standard', description=''):
    """Add a shift template"""
    try:
        db.execute_query("""
            INSERT INTO shift_templates (template_name, start_time, end_time, break_duration, shift_type, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (template_name, start_time, end_time, break_duration, shift_type, description))
        print_success(f"Template '{template_name}' added successfully!")
        return True
    except Exception as e:
        print_error(f"Error adding template: {e}")
        return False

def get_shift_templates():
    """Get all shift templates"""
    try:
        return db.execute_query("SELECT * FROM shift_templates ORDER BY template_name")
    except Exception as e:
        print_error(f"Error getting templates: {e}")
        return []

def delete_shift_template(template_id):
    """Delete a shift template"""
    try:
        db.execute_query("DELETE FROM shift_templates WHERE id = %s", (template_id,))
        print_success("Template deleted successfully!")
        return True
    except Exception as e:
        print_error(f"Error deleting template: {e}")
        return False

def add_agent_shift(agent_username, shift_date, start_time, end_time, shift_type='standard', break_duration=30, notes='', created_by='system'):
    """Add a shift for an agent"""
    try:
        # Check for existing shift
        existing = db.execute_query("""
            SELECT id FROM agent_shifts 
            WHERE agent_username = %s AND shift_date = %s
        """, (agent_username, shift_date))
        
        if existing:
            print_warning(f"Agent {agent_username} already has a shift on {shift_date}")
            overwrite = input("Overwrite? (y/n): ").strip().lower()
            if overwrite == 'y':
                db.execute_query("""
                    UPDATE agent_shifts 
                    SET start_time = %s, end_time = %s, shift_type = %s, 
                        break_duration = %s, notes = %s, created_by = %s
                    WHERE agent_username = %s AND shift_date = %s
                """, (start_time, end_time, shift_type, break_duration, notes, created_by, agent_username, shift_date))
                print_success("Shift updated successfully!")
            return True
        
        # Insert new shift
        db.execute_query("""
            INSERT INTO agent_shifts 
            (agent_username, shift_date, start_time, end_time, shift_type, break_duration, notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (agent_username, shift_date, start_time, end_time, shift_type, break_duration, notes, created_by))
        print_success(f"Shift added for {agent_username} on {shift_date}")
        return True
    except Exception as e:
        print_error(f"Error adding shift: {e}")
        return False

def get_agent_shifts(agent_username=None, start_date=None, end_date=None):
    """Get agent shifts with optional filters"""
    try:
        query = "SELECT * FROM agent_shifts WHERE 1=1"
        params = []
        
        if agent_username:
            query += " AND agent_username = %s"
            params.append(agent_username)
        
        if start_date:
            query += " AND shift_date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND shift_date <= %s"
            params.append(end_date)
        
        query += " ORDER BY shift_date, start_time"
        
        return db.execute_query(query, params)
    except Exception as e:
        print_error(f"Error getting shifts: {e}")
        return []

def get_daily_schedule(shift_date=None):
    """Get schedule for a specific day"""
    if not shift_date:
        shift_date = datetime.now().date()
    
    try:
        return db.execute_query("""
            SELECT * FROM agent_shifts 
            WHERE shift_date = %s 
            ORDER BY start_time, agent_username
        """, (shift_date,))
    except Exception as e:
        print_error(f"Error getting daily schedule: {e}")
        return []

def delete_agent_shift(shift_id):
    """Delete an agent shift"""
    try:
        db.execute_query("DELETE FROM agent_shifts WHERE id = %s", (shift_id,))
        print_success("Shift deleted successfully!")
        return True
    except Exception as e:
        print_error(f"Error deleting shift: {e}")
        return False

def add_schedule_exception(agent_username, exception_date, exception_type, reason='', start_time=None, end_time=None):
    """Add a schedule exception (PTO, training, etc.)"""
    try:
        db.execute_query("""
            INSERT INTO schedule_exceptions 
            (agent_username, exception_date, exception_type, start_time, end_time, reason)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (agent_username, exception_date, exception_type, start_time, end_time, reason))
        print_success(f"Exception added for {agent_username} on {exception_date}")
        return True
    except Exception as e:
        print_error(f"Error adding exception: {e}")
        return False

def get_schedule_exceptions(agent_username=None, start_date=None, end_date=None):
    """Get schedule exceptions"""
    try:
        query = "SELECT * FROM schedule_exceptions WHERE 1=1"
        params = []
        
        if agent_username:
            query += " AND agent_username = %s"
            params.append(agent_username)
        
        if start_date:
            query += " AND exception_date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND exception_date <= %s"
            params.append(end_date)
        
        query += " ORDER BY exception_date"
        
        return db.execute_query(query, params)
    except Exception as e:
        print_error(f"Error getting exceptions: {e}")
        return []

def save_prediction_comparison(prediction_date, predicted_calls, required_agents, actual_scheduled):
    """Save prediction comparison data"""
    try:
        gap = required_agents - actual_scheduled if required_agents and actual_scheduled else 0
        
        db.execute_query("""
            INSERT INTO schedule_predictions 
            (prediction_date, predicted_calls, required_agents, actual_scheduled, gap)
            VALUES (%s, %s, %s, %s, %s)
        """, (prediction_date, predicted_calls, required_agents, actual_scheduled, gap))
        return True
    except Exception as e:
        print_error(f"Error saving prediction comparison: {e}")
        return False

def get_prediction_comparisons(start_date=None, end_date=None):
    """Get prediction comparison data"""
    try:
        query = "SELECT * FROM schedule_predictions WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND prediction_date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND prediction_date <= %s"
            params.append(end_date)
        
        query += " ORDER BY prediction_date"
        
        return db.execute_query(query, params)
    except Exception as e:
        print_error(f"Error getting predictions: {e}")
        return []

# =============================================================================
# Schedule Menu Functions
# =============================================================================

def show_daily_schedule():
    """Display today's schedule"""
    from datetime import datetime
    
    date_str = input("Enter date (YYYY-MM-DD) or press Enter for today: ").strip()
    if date_str:
        try:
            schedule_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            print_error("Invalid date format")
            return
    else:
        schedule_date = datetime.now().date()
    
    shifts = get_daily_schedule(schedule_date)
    
    print_header(f"📋 SCHEDULE FOR {schedule_date}", Colors.CYAN)
    
    if not shifts:
        print_warning(f"No shifts scheduled for {schedule_date}")
        input("\nPress Enter to continue...")
        return
    
    print(f"\n{'Agent':<20} {'Start':<8} {'End':<8} {'Type':<12} {'Break':<6}")
    print("-" * 60)
    
    for shift in shifts:
        print(f"{shift['agent_username']:<20} {shift['start_time']:<8} {shift['end_time']:<8} "
              f"{shift['shift_type']:<12} {shift['break_duration']}min")
    
    # Check for exceptions
    exceptions = get_schedule_exceptions(start_date=schedule_date, end_date=schedule_date)
    if exceptions:
        print("\n📌 EXCEPTIONS:")
        for ex in exceptions:
            print(f"  {ex['agent_username']}: {ex['exception_type']} - {ex['reason']}")
    
    input("\nPress Enter to continue...")

def show_agent_schedule():
    """Show schedule for specific agent"""
    agent = input("Enter agent username: ").strip()
    if not agent:
        return
    
    days = input("Number of days to show (default 7): ").strip()
    days = int(days) if days.isdigit() else 7
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    shifts = get_agent_shifts(agent, start_date, end_date)
    
    print_header(f"📅 SCHEDULE FOR {agent}", Colors.CYAN)
    print(f"Period: {start_date} to {end_date}\n")
    
    if not shifts:
        print_warning(f"No shifts found for {agent} in this period")
    else:
        print(f"{'Date':<12} {'Start':<8} {'End':<8} {'Type':<12}")
        print("-" * 50)
        for shift in shifts:
            print(f"{shift['shift_date']:<12} {shift['start_time']:<8} {shift['end_time']:<8} {shift['shift_type']:<12}")
    
    input("\nPress Enter to continue...")

def show_adherence_report():
    """Show schedule adherence report"""
    from datetime import datetime, timedelta
    from agents.performance import get_agent_login_history
    
    date_str = input("Enter date for adherence report (YYYY-MM-DD): ").strip()
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        print_error("Invalid date format")
        return
    
    # Get scheduled shifts for the day
    scheduled = get_daily_schedule(report_date)
    
    if not scheduled:
        print_warning(f"No schedules found for {report_date}")
        return
    
    print_header(f"📊 SCHEDULE ADHERENCE - {report_date}", Colors.CYAN)
    
    total_agents = len(scheduled)
    adhered = 0
    late = 0
    absent = 0
    
    print(f"\n{'Agent':<20} {'Scheduled':<15} {'Actual Login':<15} {'Status':<12}")
    print("-" * 70)
    
    for shift in scheduled:
        # Get actual login for this agent on this day
        logins = get_agent_login_history(shift['agent_username'], report_date, report_date)
        
        scheduled_time = shift['start_time']
        status = "❌ ABSENT"
        
        if logins:
            login_time = logins[0].get('login_time', '')
            if login_time:
                # Compare times
                login_hour = login_time.hour if hasattr(login_time, 'hour') else 0
                login_min = login_time.minute if hasattr(login_time, 'minute') else 0
                
                scheduled_hour = int(str(scheduled_time).split(':')[0])
                scheduled_min = int(str(scheduled_time).split(':')[1])
                
                if login_hour < scheduled_hour or (login_hour == scheduled_hour and login_min <= scheduled_min + 5):
                    status = "✅ ON TIME"
                    adhered += 1
                elif login_hour == scheduled_hour and login_min <= scheduled_min + 15:
                    status = "⚠️ LATE (<15 min)"
                    late += 1
                else:
                    status = "❌ LATE (>15 min)"
                    late += 1
            else:
                status = "❌ NO LOGIN DATA"
        else:
            status = "❌ ABSENT"
            absent += 1
        
        print(f"{shift['agent_username']:<20} {shift['start_time']:<15} {login_time if logins else 'No login':<15} {status}")
    
    print("\n" + "=" * 70)
    print(f"SUMMARY:")
    print(f"  Total Scheduled: {total_agents}")
    print(f"  ✅ On Time: {adhered} ({adhered/total_agents*100:.1f}%)")
    print(f"  ⚠️ Late: {late} ({late/total_agents*100:.1f}%)")
    print(f"  ❌ Absent: {absent} ({absent/total_agents*100:.1f}%)")
    
    input("\nPress Enter to continue...")

def manage_shift_templates():
    """Manage shift templates"""
    while True:
        templates = get_shift_templates()
        
        print_header("⏰ SHIFT TEMPLATES", Colors.GREEN)
        
        if templates:
            print(f"\n{'ID':<5} {'Template':<20} {'Start':<8} {'End':<8} {'Break':<8}")
            print("-" * 60)
            for t in templates:
                print(f"{t['id']:<5} {t['template_name']:<20} {t['start_time']:<8} {t['end_time']:<8} {t['break_duration']}min")
        
        print("\nOptions:")
        print("  1. Add Template")
        print("  2. Delete Template")
        print("  0. Back")
        print("-" * 40)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            name = input("Template name: ").strip()
            start = input("Start time (HH:MM): ").strip()
            end = input("End time (HH:MM): ").strip()
            break_dur = input("Break duration (minutes) [30]: ").strip()
            break_dur = int(break_dur) if break_dur.isdigit() else 30
            
            add_shift_template(name, start, end, break_dur)
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            if not templates:
                print_warning("No templates to delete")
                input("\nPress Enter to continue...")
                continue
            
            tid = input("Enter template ID to delete: ").strip()
            if tid.isdigit():
                delete_shift_template(int(tid))
            input("\nPress Enter to continue...")
        
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

# =============================================================================
# Main Schedule Menu
# =============================================================================

def schedule_menu():
    """Main schedule management menu"""
    while True:
        print_header("📅 SCHEDULE MANAGEMENT", Colors.CYAN)
        print("  1. 📋 Today's Schedule")
        print("  2. 👤 Agent Schedule")
        print("  3. 📊 Adherence Report")
        print("  4. 📈 Schedule vs Predictions")  # NEW
        print("  5. ⏰ Shift Templates")
        print("  6. ⚙️ Configure Settings")
        print("  0. 🔙 Back")
        print("-" * 60)
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_daily_schedule()
        elif choice == '2':
            show_agent_schedule()
        elif choice == '3':
            show_adherence_report()
        elif choice == '4':  # NEW
            try:
                from agents.schedule_predictive import show_schedule_gaps
                show_schedule_gaps()
            except ImportError:
                print_error("Schedule predictive module not found")
                print_info("Creating schedule_predictive.py...")
                # Create basic version if missing
                with open('agents/schedule_predictive.py', 'w') as f:
                    f.write('''
def show_schedule_gaps():
    """Show schedule vs prediction gaps"""
    from utils.colors import print_header, print_warning
    from datetime import datetime
    
    print_header("📈 SCHEDULE VS PREDICTIONS", "cyan")
    print_warning("This feature requires forecast data.")
    print("\\nTo use this feature, first run forecasting to generate predictions.")
    input("\\nPress Enter to continue...")
''')
                print_success("Created basic schedule_predictive.py")
                print_info("Please run forecasting first to generate predictions.")
                input("\nPress Enter to continue...")
            except Exception as e:
                print_error(f"Error: {e}")
                input("\nPress Enter to continue...")
        elif choice == '5':
            manage_shift_templates()
        elif choice == '6':
            configure_schedule_settings()
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")
            input("\nPress Enter to continue...")

def configure_schedule_settings():
    """Configure schedule settings"""
    print_header("⚙️ SCHEDULE SETTINGS", Colors.YELLOW)
    print("Coming soon!")
    input("\nPress Enter to continue...")

if __name__ == "__main__":
    # Test the module
    create_schedule_tables()
    schedule_menu()