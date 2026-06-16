import paramiko
import os
from pathlib import Path

SERVER = "216.219.88.67"
USER = "root"
PASSWORD = "AltriaAdmin786786"
REMOTE_PATH = "/root/xshield_ai_small/"
LOCAL_PATH = r"D:\xshield_recordings"

print("=" * 60)
print("    XSHIELD RECORDING DOWNLOADER")
print("=" * 60)

Path(LOCAL_PATH).mkdir(parents=True, exist_ok=True)
print(f"\n📁 Folder: {LOCAL_PATH}")

print("\n[1/3] Connecting to server...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER, username=USER, password=PASSWORD)
print("✅ Connected")

print("\n[2/3] Getting file list...")
stdin, stdout, stderr = ssh.exec_command(f"ls -1 {REMOTE_PATH}*.mp3 2>/dev/null")
files = stdout.read().decode().strip().split('\n')
files = [f for f in files if f and f.endswith('.mp3')]

if not files:
    print("❌ No MP3 files found!")
    ssh.close()
    exit()

print(f"✅ Found {len(files)} recordings")

print("\n[3/3] Downloading...")
print("-" * 60)

sftp = ssh.open_sftp()
downloaded = 0

for i, filename in enumerate(files, 1):
    remote_file = os.path.join(REMOTE_PATH, filename)
    local_file = os.path.join(LOCAL_PATH, filename)
    
    if os.path.exists(local_file):
        print(f"⏭️  [{i}/{len(files)}] {filename[:50]} (exists)")
        continue
    
    print(f"📥 [{i}/{len(files)}] {filename[:50]}... ", end="", flush=True)
    
    try:
        sftp.get(remote_file, local_file)
        size = os.path.getsize(local_file) // 1024
        print(f"✅ ({size} KB)")
        downloaded += 1
    except Exception as e:
        print(f"❌ Failed")

sftp.close()
ssh.close()

print("-" * 60)
print(f"\n📊 Downloaded: {downloaded}/{len(files)}")
print(f"📁 Location: {LOCAL_PATH}")
print("\n✨ Complete!")
