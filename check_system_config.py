# check_system_config.py
import os
import glob

print("=" * 70)
print("SEARCHING FOR STATUS DEFINITIONS IN ALTRIA_OPS")
print("=" * 70)

# Check config directory
config_path = "D:/Altria_Ops/config"
if os.path.exists(config_path):
    print(f"\n📁 Checking config directory: {config_path}")
    config_files = glob.glob(f"{config_path}/*.py")
    for cf in config_files:
        print(f"\n  📄 {os.path.basename(cf)}")
        try:
            with open(cf, 'r', encoding='utf-8') as f:
                content = f.read()
                if any(x in content for x in ['SALE', 'YPSALE', 'PINQRY', 'COMPLETE', 'STATUS']):
                    print("    ✅ Contains status references")
                    # Show relevant lines
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if any(x in line for x in ['SALE', 'YPSALE', 'PINQRY', 'COMPLETE']):
                            if not line.strip().startswith('#'):
                                print(f"      Line {i}: {line.strip()}")
        except Exception as e:
            print(f"    ❌ Error reading: {e}")

# Check core directory for database models or constants
core_path = "D:/Altria_Ops/core"
if os.path.exists(core_path):
    print(f"\n📁 Checking core directory: {core_path}")
    core_files = glob.glob(f"{core_path}/*.py")
    for cf in core_files:
        print(f"\n  📄 {os.path.basename(cf)}")
        try:
            with open(cf, 'r', encoding='utf-8') as f:
                content = f.read()
                if any(x in content for x in ['SALE', 'YPSALE', 'PINQRY', 'COMPLETE']):
                    print(f"    ✅ Contains status references in {os.path.basename(cf)}")
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if any(x in line for x in ['SALE', 'YPSALE', 'PINQRY', 'COMPLETE']):
                            if not line.strip().startswith('#'):
                                print(f"      Line {i}: {line.strip()}")
        except Exception as e:
            print(f"    ❌ Error reading: {e}")

# Check if there's a constants file anywhere
print("\n" + "=" * 70)
print("🔍 SEARCHING FOR CONSTANTS FILES")
print("=" * 70)
constants_files = glob.glob("D:/Altria_Ops/**/*const*.py", recursive=True)
constants_files.extend(glob.glob("D:/Altria_Ops/**/*status*.py", recursive=True))

if constants_files:
    for cf in constants_files:
        print(f"\n📄 {cf}")
        try:
            with open(cf, 'r', encoding='utf-8') as f:
                content = f.read()
                if any(x in content for x in ['SALE', 'YPSALE', 'PINQRY', 'COMPLETE']):
                    print("  ✅ Contains status definitions")
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if any(x in line for x in ['SALE', 'YPSALE', 'PINQRY', 'COMPLETE']):
                            if '=' in line:
                                print(f"    Line {i}: {line.strip()}")
        except:
            print("  ❌ Could not read file")
else:
    print("No constants files found")

# Check the database module for any hardcoded statuses
print("\n" + "=" * 70)
print("🔍 CHECKING DATABASE MODULE FOR STATUS REFERENCES")
print("=" * 70)
db_files = glob.glob("D:/Altria_Ops/core/database*.py")
if db_files:
    for df in db_files:
        print(f"\n📄 {df}")
        try:
            with open(df, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if any(x in line for x in ['SALE', 'YPSALE', 'PINQRY', 'COMPLETE']):
                        print(f"  Line {i}: {line.strip()}")
        except:
            print("  ❌ Could not read file")

# Also check the main.py for any references
print("\n" + "=" * 70)
print("🔍 CHECKING MAIN.PY FOR STATUS REFERENCES")
print("=" * 70)
main_file = "D:/Altria_Ops/main.py"
if os.path.exists(main_file):
    try:
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if any(x in line for x in ['SALE', 'YPSALE', 'PINQRY', 'COMPLETE']):
                    print(f"Line {i}: {line.strip()}")
    except:
        print("❌ Could not read main.py")

print("\n" + "=" * 70)
print("SEARCH COMPLETE")
print("=" * 70)