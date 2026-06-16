import os
from pathlib import Path

web_dir = Path('D:/Altria_Ops/web')

print("Checking file structure...")
print("=" * 50)

files_to_check = [
    web_dir / 'app.py',
    web_dir / 'templates' / 'dashboard.html',
    web_dir / 'static' / 'css' / 'style.css',
    web_dir / 'static' / 'js' / 'dashboard.js',
]

for file in files_to_check:
    if file.exists():
        print(f"✅ {file}")
    else:
        print(f"❌ {file} - MISSING!")

print("\n" + "=" * 50)
if all(f.exists() for f in files_to_check):
    print("✅ All files are in the correct place!")
else:
    print("❌ Some files are missing. Create them using the commands above.")