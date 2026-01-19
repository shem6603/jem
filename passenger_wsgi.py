"""
Passenger WSGI file for GoDaddy cPanel deployment.
This file is used by GoDaddy's Passenger application server.
"""
import os
import sys
from pathlib import Path

# Get the directory containing this file
BASE_DIR = Path(__file__).resolve().parent

# Add the project directory to Python path
sys.path.insert(0, str(BASE_DIR))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
