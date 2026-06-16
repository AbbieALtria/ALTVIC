#!/usr/bin/env python3
"""
Xshield Recording Downloader - Downloads 200 most recent recordings
"""

import os
import paramiko
from pathlib import Path

# Configuration
SERVER = "216.219.88.67"
USER = "root"
PASSWORD = "AltriaAdmin786786"
REMOTE_PATH = "/var/www/html/RECORDINGS/MP3/"
LOCAL_PATH = r"D:\xshield_recordings"

def main():
    print("=" * 60)
    print("    XSHIELD RECORDING DOWNLOADER")
    print("=" * 60)
    
    # Create local folder
    Path(LOCAL_PATH).mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Folder: {LOCAL_PATH}")
    
    # Connect to server
    print("\n[1/3] Connecting to server...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
        print("✅ Connected to server")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return
    
    # Find recording files
    print("\n[2/3] Finding Xshield recordings...")
    command = f'find {REMOTE_PATH} -name "*Xshield*.mp3" -o -name "*8003589107*.mp3" 2>/dev/null | head -200'
    stdin, stdout, stderr = ssh.exec_command(command)
    files = stdout.read().decode().strip().split('\n')
    files = [f.strip() for f in files if f.strip()]
    
    if not files:
        print("❌ No recordings found!")
        ssh.close()
        return
    
    print(f"✅ Found {len(files)} recordings")
    
    # Download files
    print("\n[3/3] Downloading recordings...")
    print("-" * 60)
    
    sftp = ssh.open_sftp()
    downloaded = 0
    skipped = 0
    failed = 0
    
    for i, remote_file in enumerate(files, 1):
        filename = os.path.basename(remote_file)
        local_file = os.path.join(LOCAL_PATH, filename)
        
        if os.path.exists(local_file):
            print(f"⏭️  [{i}/{len(files)}] {filename[:50]} (already exists)")
            skipped += 1
            continue
        
        print(f"📥 [{i}/{len(files)}] {filename[:50]}... ", end="", flush=True)
        
        try:
            sftp.get(remote_file, local_file)
            size = os.path.getsize(local_file) // 1024
            print(f"✅ ({size} KB)")
            downloaded += 1
        except Exception as e:
            print(f"❌ Failed")
            failed += 1
    
    sftp.close()
    ssh.close()
    
    print("-" * 60)
    print("\n📊 SUMMARY")
    print(f"   ✅ New downloads: {downloaded}")
    print(f"   ⏭️  Skipped (exists): {skipped}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📁 Location: {LOCAL_PATH}")
    print("\n✨ Complete!")

if __name__ == "__main__":
    main()
