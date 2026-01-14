#!/usr/bin/env python
"""
Web application entry point
Run this to start the Flask web server
"""

import os
import sys
from web_app import app

if __name__ == "__main__":
    # Ensure all directories exist
    os.makedirs("scans", exist_ok=True)
    os.makedirs("static", exist_ok=True)

    print("Starting VacationManager web server...")
    print("Access the mobile app at: http://localhost:5000")
    print("API endpoints available at: http://localhost:5000/api/")

    app.run(host='0.0.0.0', port=5000, debug=False)