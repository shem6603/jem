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

import os
os.environ.setdefault('VAPID_PUBLIC_KEY', 'BEh1VJaAFZQ6B7Y_9ugjRl3nDNexDSEgpBDy0gkvINZssO7RoYh1K9AN4sauxBDl8MAuNzMlN7tk90UtyJUyOrY')
os.environ.setdefault('VAPID_PRIVATE_KEY', 'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgwuUC8e9WXMVKKx8IesQfBLHtQKh4WrA1IZPbiCakEvWhRANCAARIdVSWgBWUOge2P/boI0Zd5wzXsQ0hIKQQ8tIJLyDWbLDu0aGIdSvQDeLGrsQQ5fDALjczJTe7ZPdFLciVMjq2')