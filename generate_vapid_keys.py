#!/usr/bin/env python
"""
Generate VAPID keys for push notifications
Run this script to generate VAPID public and private keys
"""
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

def generate_vapid_keys():
    """Generate VAPID public and private keys in the correct format"""
    # Generate private key using P-256 curve (SECP256R1)
    private_key = ec.generate_private_key(ec.SECP256R1())
    
    # Get public key
    public_key = private_key.public_key()
    
    # Serialize private key to DER format, then encode to base64url
    private_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Serialize public key to uncompressed point format
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    
    # Convert to base64url format (VAPID format)
    # Remove padding and use URL-safe base64
    private_key_b64 = base64.urlsafe_b64encode(private_der).decode('utf-8').rstrip('=')
    
    # For public key, remove the first byte (0x04) which indicates uncompressed format
    # Then encode to base64url
    public_key_raw = public_bytes[1:]  # Remove 0x04 prefix
    public_key_b64 = base64.urlsafe_b64encode(public_key_raw).decode('utf-8').rstrip('=')
    
    return private_key_b64, public_key_b64


if __name__ == '__main__':
    print("Generating VAPID keys for push notifications...")
    print("=" * 60)
    
    try:
        private_key, public_key = generate_vapid_keys()
        
        print("\n✅ VAPID Keys Generated Successfully!")
        print("\n" + "=" * 60)
        print("Add these to your .env file:")
        print("=" * 60)
        print(f"\nVAPID_PRIVATE_KEY={private_key}")
        print(f"VAPID_PUBLIC_KEY={public_key}")
        print("\n" + "=" * 60)
        print("\n⚠️  IMPORTANT: Keep your private key secret!")
        print("   Never commit it to version control.")
        print("\n" + "=" * 60)
        print("\nAfter adding to .env, restart your Django server.")
        print("=" * 60)
        
    except ImportError as e:
        print("\n❌ Error: Missing required library")
        print(f"   {e}")
        print("\nInstall it with:")
        print("   pip install cryptography")
    except Exception as e:
        print(f"\n❌ Error generating keys: {e}")
        import traceback
        traceback.print_exc()
        print("\nAlternative: Use Node.js web-push:")
        print("   npm install -g web-push")
        print("   web-push generate-vapid-keys")
