-- create_schedule_tables.sql - Create schedule management tables

-- 1. SHIFT TEMPLATES TABLE (predefined shift types)
CREATE TABLE IF NOT EXISTS shift_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_name VARCHAR(50) NOT NULL UNIQUE,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    break_duration INT DEFAULT 30,
    break_start TIME,
    description TEXT,
    color VARCHAR(20) DEFAULT '#3498db',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 2. AGENT SHIFTS TABLE (actual scheduled shifts)
CREATE TABLE IF NOT EXISTS agent_shifts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_username VARCHAR(50) NOT NULL,
    shift_date DATE NOT NULL,
    template_id INT,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    break_duration INT DEFAULT 30,
    break_start TIME,
    shift_type ENUM('regular', 'overtime', 'training', 'meeting') DEFAULT 'regular',
    status ENUM('scheduled', 'confirmed', 'cancelled', 'completed') DEFAULT 'scheduled',
    notes TEXT,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_date (agent_username, shift_date),
    INDEX idx_date (shift_date),
    FOREIGN KEY (template_id) REFERENCES shift_templates(id) ON DELETE SET NULL
);

-- 3. TIME OFF / EXCEPTIONS TABLE
CREATE TABLE IF NOT EXISTS agent_exceptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_username VARCHAR(50) NOT NULL,
    exception_date DATE NOT NULL,
    exception_type ENUM('pto', 'sick', 'training', 'meeting', 'holiday', 'other') NOT NULL,
    start_time TIME,
    end_time TIME,
    is_full_day BOOLEAN DEFAULT TRUE,
    reason TEXT,
    approved BOOLEAN DEFAULT FALSE,
    approved_by VARCHAR(50),
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_exception (agent_username, exception_date)
);

-- 4. SCHEDULE AUDIT LOG
CREATE TABLE IF NOT EXISTS schedule_audit (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    agent_username VARCHAR(50),
    shift_id INT,
    old_data JSON,
    new_data JSON,
    changed_by VARCHAR(50),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default shift templates
INSERT INTO shift_templates (template_name, start_time, end_time, break_duration, break_start, description, color) VALUES
('Morning', '08:00', '16:00', 30, '12:00', 'Morning shift 8am-4pm', '#3498db'),
('Afternoon', '14:00', '22:00', 30, '18:00', 'Afternoon shift 2pm-10pm', '#e67e22'),
('Evening', '22:00', '06:00', 45, '02:00', 'Overnight shift 10pm-6am', '#9b59b6'),
('Standard', '09:00', '17:00', 30, '12:30', 'Standard business hours', '#2ecc71'),
('Early', '06:00', '14:00', 30, '10:00', 'Early morning shift', '#f1c40f'),
('Late', '12:00', '20:00', 30, '16:00', 'Late day shift', '#e74c3c')
ON DUPLICATE KEY UPDATE 
    start_time = VALUES(start_time),
    end_time = VALUES(end_time);

-- Show success message
SELECT 'Schedule tables created successfully!' as message;