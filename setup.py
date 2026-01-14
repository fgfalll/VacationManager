#!/usr/bin/env python
"""
Setup script for VacationManager
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    print("Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error installing requirements: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    print("Creating directories...")
    directories = ["scans", "static", "templates", "generated_docs"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    print("✓ Directories created")

def init_database():
    """Initialize the database"""
    print("Initializing database...")
    try:
        from app.models import create_tables, init_default_data
        create_tables()
        init_default_data()
        print("✓ Database initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        return False

def main():
    print("VacationManager Setup")
    print("=====================")
    print()

    # Check Python version
    if sys.version_info < (3, 10):
        print("✗ Python 3.10 or higher is required")
        print(f"Current version: {sys.version}")
        return

    print(f"✓ Python version: {sys.version}")

    # Install requirements
    if not install_requirements():
        print("\nSetup failed. Please install requirements manually:")
        print("pip install -r requirements.txt")
        return

    # Create directories
    create_directories()

    # Initialize database
    if not init_database():
        print("\nSetup completed with warnings. Database will be created on first run.")
    else:
        print("\n✓ Setup completed successfully!")

    print("\nTo run the applications:")
    print("1. Desktop app: python run_desktop.py")
    print("2. Web app: python run_web.py")
    print("\nWeb app will be available at: http://localhost:5000")

if __name__ == "__main__":
    main()