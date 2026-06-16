# check_scoring.py
import os

file_path = "D:/Altria_Ops/quality/scoring.py"
print(f"Checking: {file_path}")
print(f"File exists: {os.path.exists(file_path)}")
print("\n" + "=" * 60)

if os.path.exists(file_path):
    # Try different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    content = None
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = f.readlines()
            print(f"✅ Successfully read with {encoding} encoding")
            content = ''.join(lines)
            break
        except UnicodeDecodeError:
            print(f"❌ Failed with {encoding} encoding")
            continue
    
    if content is None:
        # Last resort: read as binary and decode with errors ignored
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        content = raw_data.decode('utf-8', errors='ignore')
        lines = content.split('\n')
        print("✅ Read with binary fallback (ignoring errors)")
    
    print(f"\nFile size: {len(lines)} lines")
    print("=" * 60)
    
    # Search for status-related variables
    found_lines = []
    for i, line in enumerate(lines, 1):
        if any(x in line for x in ['STATUS', 'RESOLVED', 'SALE', 'YPSALE', 'PINQRY', 'COMPLETE']):
            if '=' in line and not line.strip().startswith('#'):
                found_lines.append((i, line.strip()))
    
    if found_lines:
        print("\n✅ Found potential status definitions:")
        for line_num, line in found_lines[:20]:  # Show first 20
            print(f"Line {line_num:4d}: {line}")
    else:
        print("\n❌ No status definitions found with simple search")
        
        # Let's look for array/list definitions
        print("\nLooking for list/array definitions:")
        list_count = 0
        for i, line in enumerate(lines, 1):
            if '[' in line and ']' in line and '=' in line:
                if not line.strip().startswith('#'):
                    print(f"Line {i:4d}: {line.strip()}")
                    list_count += 1
                    if list_count >= 20:
                        print("... (showing first 20 only)")
                        break
    
    # Specifically search for RESOLVED_STATUSES
    print("\n" + "=" * 60)
    print("🔍 Specifically searching for RESOLVED_STATUSES:")
    found = False
    for i, line in enumerate(lines, 1):
        if 'RESOLVED_STATUSES' in line:
            print(f"✅ Found at line {i}: {line.strip()}")
            # Show surrounding lines for context
            print("\nContext:")
            start = max(1, i-3)
            end = min(len(lines), i+3)
            for j in range(start, end+1):
                prefix = "→" if j == i else " "
                print(f"{prefix} {j:4d}: {lines[j-1].rstrip()}")
            found = True
            break
    
    if not found:
        print("❌ RESOLVED_STATUSES not found in file")
        
        # Check for similar patterns
        print("\nLooking for similar patterns:")
        patterns = ['SALE', 'YPSALE', 'PINQRY', 'COMPLETE', 'RESOLVED']
        for pattern in patterns:
            for i, line in enumerate(lines, 1):
                if pattern in line and '=' in line:
                    print(f"✅ Found {pattern} at line {i}: {line.strip()}")
                    break
            else:
                print(f"❌ {pattern} not found")
    
    # Also check for any QC or quality related statuses
    print("\n" + "=" * 60)
    print("📊 Checking for QC-related statuses:")
    qc_patterns = ['QC_', 'QUALITY_', 'SCORE_', 'GRADE_']
    for pattern in qc_patterns:
        for i, line in enumerate(lines, 1):
            if pattern in line and '=' in line:
                print(f"✅ Found {pattern} at line {i}: {line.strip()}")
                break
        else:
            print(f"❌ {pattern} not found")

else:
    print("❌ File not found!")

print("\n" + "=" * 60)