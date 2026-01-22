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

# Set VAPID keys directly here (more reliable than cPanel env vars)
# Generate keys using: python generate_vapid_keys.py
# Then replace the values below:
os.environ.setdefault('VAPID_PRIVATE_KEY', 'MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg_HV4PNhpBQbZMoRL2YvNYLwi04ixHAU_FfahS81JH7uhRANCAAT1ucKkEamDYixn4-jKkzTunKAM0YtyzSmmmhkpg7ULw0nzR1kY00BdqQ9aBNJ7APfueOMyUm9rFQDldZQcrfw0')
os.environ.setdefault('VAPID_PUBLIC_KEY', '9bnCpBGpg2IsZ-PoypM07pygDNGLcs0pppoZKYO1C8NJ80dZGNNAXakPWgTSewD37njjMlJvaxUA5XWUHK38NA')

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
