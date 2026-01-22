#!/usr/bin/env python
"""
Generate VAPID keys for push notifications
Run this script to generate VAPID public and private keys
"""
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def generate_vapid_keys():
    """
    Generate VAPID public and private keys in the correct format.
    
    Returns:
        tuple: (private_key_pem, public_key_base64url)
        - private_key_pem: PEM-encoded private key (for pywebpush)
        - public_key_base64url: Base64url-encoded public key (for browser Push API)
    """
    # Generate private key using P-256 curve (required for VAPID)
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    
    # Get public key
    public_key = private_key.public_key()
    
    # Serialize private key to PEM format (this is what pywebpush expects)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    # Get public key as uncompressed point (65 bytes: 0x04 + 32 bytes X + 32 bytes Y)
    # This format is required by the browser Push API
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    
    # Convert to base64url format WITHOUT padding (VAPID spec requirement)
    public_key_b64 = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')
    
    return private_pem, public_key_b64


if __name__ == '__main__':
    print("Generating VAPID keys for push notifications...")
    print("=" * 60)
    
    try:
        private_key, public_key = generate_vapid_keys()
        
        print("\n[OK] VAPID Keys Generated Successfully!")
        print("\n" + "=" * 60)
        print("PUBLIC KEY (for browser/frontend):")
        print("=" * 60)
        print(f"\n{public_key}\n")
        
        print("=" * 60)
        print("PRIVATE KEY (for server/backend - keep secret!):")
        print("=" * 60)
        print(f"\n{private_key}")
        
        print("=" * 60)
        print("\nFor GoDaddy cPanel, add to passenger_wsgi.py:")
        print("=" * 60)
        print(f"""
import os
os.environ.setdefault('VAPID_PUBLIC_KEY', '{public_key}')
os.environ.setdefault('VAPID_PRIVATE_KEY', '''{private_key.strip()}''')
""")
        
        print("=" * 60)
        print("\n[!] IMPORTANT:")
        print("   1. Keep your private key secret!")
        print("   2. Never commit keys to version control")
        print("   3. The private key is in PEM format (multi-line)")
        print("=" * 60)
        
    except ImportError as e:
        print(f"\n[ERROR] Missing required library - {e}")
        print("\nInstall it with:")
        print("   pip install cryptography")
    except Exception as e:
        print(f"\n[ERROR] Error generating keys: {e}")
        import traceback
        traceback.print_exc()
