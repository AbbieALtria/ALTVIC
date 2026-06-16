# check_qc_reports.py
import os

file_path = "D:/Altria_Ops/quality/vicidial_qc_reports.py"
print(f"Checking: {file_path}")
print(f"File exists: {os.path.exists(file_path)}")
print("\n" + "=" * 60)

if os.path.exists(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"File size: {len(lines)} lines")
    print("=" * 60)
    
    # Search for status-related variables
    found_lines = []
    for i, line in enumerate(lines, 1):
        if any(x in line for x in ['STATUS', 'SALE', 'YPSALE', 'PINQRY', 'COMPLETE', 'RESOLVED']):
            if '=' in line and not line.strip().startswith('#'):
                found_lines.append((i, line.strip()))
    
    if found_lines:
        print("\n✅ Found potential status definitions in vicidial_qc_reports.py:")
        for line_num, line in found_lines[:20]:
            print(f"Line {line_num:4d}: {line}")
    else:
        print("\n❌ No status definitions found")
        
        # Look for SQL queries that might reference statuses
        print("\nLooking for SQL queries with status references:")
        for i, line in enumerate(lines, 1):
            if 'SELECT' in line and any(x in line for x in ['status', 'SALE', 'YPSALE']):
                print(f"Line {i:4d}: {line.strip()}")
                # Show the next few lines to see the full query
                for j in range(1, 5):
                    if i+j <= len(lines):
                        next_line = lines[i+j-1].strip()
                        if next_line and not next_line.startswith('#'):
                            print(f"      {next_line}")
                print()
    
    # Also check for any configuration or constants
    print("\n" + "=" * 60)
    print("Looking for configuration or constant definitions:")
    for i, line in enumerate(lines, 1):
        if any(x in line for x in ['CONFIG', 'SETTINGS', 'PARAMS']):
            if '=' in line and not line.strip().startswith('#'):
                print(f"Line {i:4d}: {line.strip()}")
    
    # Check for any function that might handle statuses
    print("\n" + "=" * 60)
    print("Looking for functions that might handle statuses:")
    for i, line in enumerate(lines, 1):
        if 'def ' in line and any(x in line for x in ['status', 'qc', 'quality']):
            print(f"Line {i:4d}: {line.strip()}")
    
else:
    print("❌ File not found!")

print("\n" + "=" * 60)