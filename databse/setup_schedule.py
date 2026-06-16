#!/usr/bin/env python3
# =============================================================================
# File:         setup_schedule.py
# Description:  Set up database tables for schedule management
# Location:     D:\Altria_Ops\database\setup_schedule.py
# =============================================================================

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import db
from utils.colors import Colors, print_color, print_header, print_success, print_error, print_warning, print_info

def setup_schedule_tables():
    """Create schedule management tables"""
    print_header("📅 SCHEDULE DATABASE SETUP", Colors.CYAN)
    print("=" * 60)
    
    try:
        # Create shift_templates table
        print("Creating shift_templates table...")
        db.execute_query("""
            CREATE TABLE IF NOT EXISTS shift_templates (
                id INT AUTO_INCREMENT PRIMARY KEY,
                template_name VARCHAR(50) NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                break_duration INT DEFAULT 30,
                description TEXT,
                color VARCHAR(20) DEFAULT 'white',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_template_name (template_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print_success("✓ shift_templates table created")
        
        # Create agent_shifts table
        print("Creating agent_shifts table...")
        db.execute_query("""
            CREATE TABLE IF NOT EXISTS agent_shifts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                agent_username VARCHAR(20) NOT NULL,
                shift_date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                template_id INT,
                break_duration INT DEFAULT 30,
                status ENUM('scheduled', 'confirmed', 'cancelled', 'completed') DEFAULT 'scheduled',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
                created_by VARCHAR(20),
                FOREIGN KEY (template_id) REFERENCES shift_templates(id) ON DELETE SET NULL,
                INDEX idx_agent_date (agent_username, shift_date),
                INDEX idx_date (shift_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print_success("✓ agent_shifts table created")
        
        # Insert default shift templates
        print("\nAdding default shift templates...")
        
        default_templates = [
            ('morning', '08:00', '16:00', 30, 'Morning shift', 'cyan'),
            ('afternoon', '14:00', '22:00', 30, 'Afternoon shift', 'yellow'),
            ('evening', '22:00', '06:00', 45, 'Evening/Night shift', 'magenta'),
            ('standard', '09:00', '17:00', 30, 'Standard business hours', 'green'),
            ('early', '06:00', '14:00', 30, 'Early morning shift', 'blue'),
            ('late', '16:00', '00:00', 30, 'Late shift', 'red')
        ]
        
        for name, start, end, break_dur, desc, color in default_templates:
            try:
                db.execute_query("""
                    INSERT IGNORE INTO shift_templates 
                    (template_name, start_time, end_time, break_duration, description, color)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (name, start, end, break_dur, desc, color))
                print(f"  • Added template: {name}")
            except Exception as e:
                print_warning(f"  Could not add {name}: {e}")
        
        print_success("\n✅ Schedule database setup complete!")
        print("\nTables created:")
        print("  • shift_templates - Store shift patterns")
        print("  • agent_shifts - Store agent schedules")
        print("\nDefault templates added:")
        print("  • Morning (08:00-16:00)")
        print("  • Afternoon (14:00-22:00)")
        print("  • Evening (22:00-06:00)")
        print("  • Standard (09:00-17:00)")
        print("  • Early (06:00-14:00)")
        print("  • Late (16:00-00:00)")
        
        return True
        
    except Exception as e:
        print_error(f"\n❌ Setup failed: {e}")
        return False

if __name__ == "__main__":
    setup_schedule_tables()