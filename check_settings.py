# check_settings.py
import os

file_path = "D:/Altria_Ops/config/settings.py"
print(f"Checking: {file_path}")
print("=" * 60)

if os.path.exists(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"File size: {len(lines)} lines")
    print("=" * 60)
    
    # Look for any status-related settings
    print("\n🔍 Looking for status-related settings:")
    found = False
    for i, line in enumerate(lines, 1):
        if any(x in line for x in ['SALE', 'YPSALE', 'PINQRY', 'COMPLETE', 'STATUS', 'RESOLVED']):
            if '=' in line and not line.strip().startswith('#'):
                print(f"Line {i:4d}: {line.strip()}")
                found = True
                # Show surrounding lines for context
                start = max(1, i-2)
                end = min(len(lines), i+2)
                for j in range(start, end+1):
                    if j != i:
                        print(f"      {lines[j-1].strip()}")
                print()
    
    if not found:
        print("No status definitions found in settings.py")
        
        # Let's look for any configuration dictionaries
        print("\nLooking for configuration dictionaries:")
        in_dict = False
        dict_lines = []
        for i, line in enumerate(lines, 1):
            if '{' in line and '=' in line:
                print(f"\nPossible config at line {i}: {line.strip()}")
                in_dict = True
                dict_lines = [line.strip()]
            elif in_dict:
                dict_lines.append(line.strip())
                if '}' in line:
                    # End of dictionary
                    print("\n".join(dict_lines))
                    in_dict = False
                    dict_lines = []
    
    # Also check for any imported constants
    print("\n" + "=" * 60)
    print("Looking for imported constants:")
    for i, line in enumerate(lines, 1):
        if 'import' in line and any(x in line for x in ['const', 'status']):
            print(f"Line {i:4d}: {line.strip()}")
    
else:
    print(f"❌ File not found: {file_path}")

print("\n" + "=" * 60)