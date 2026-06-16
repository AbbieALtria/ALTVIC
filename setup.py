# setup.py - Quick setup script

import os
import sys
import subprocess

def setup():
    print("=" * 60)
    print("ALTRIA OPS - Setup Script")
    print("=" * 60)
    
    # Check Python version
    python_version = sys.version_info
    print(f"\n📌 Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 6):
        print("❌ Python 3.6 or higher required!")
        return
    
    # Install requirements
    print("\n📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Packages installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install packages: {e}")
        return
    
    # Check if .env exists
    if not os.path.exists(".env"):
        print("\n📝 Creating .env file from template...")
        with open(".env", "w") as f:
            f.write("""# Database Configuration
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password_here
DB_NAME=asterisk
DB_PORT=3306

# System Settings
TIMEZONE=Asia/Manila
LANGUAGE=en
EXPORT_DIR=data/exports/
""")
        print("✅ .env file created! Please edit it with your database credentials.")
    else:
        print("\n✅ .env file already exists.")
    
    # Create necessary directories
    os.makedirs("data/exports", exist_ok=True)
    os.makedirs("data/logs", exist_ok=True)
    os.makedirs("data/cache", exist_ok=True)
    
    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("\nNext steps:")
    print("1. Edit the .env file with your database credentials")
    print("2. Run 'python test_db.py' to test connection")
    print("3. Run 'python main.py' to start the application")
    print("=" * 60)

if __name__ == "__main__":
    setup()