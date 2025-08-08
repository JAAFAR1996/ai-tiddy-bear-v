#!/usr/bin/env python3
"""
Production RSA Key Generation Script
===================================
Generates secure RSA key pairs for JWT signing in production environment.
Creates 4096-bit keys for maximum security.
"""

import os
import sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from datetime import datetime


def generate_rsa_key_pair(key_size=4096):
    """Generate RSA key pair with specified size."""
    print(f"🔐 Generating RSA-{key_size} key pair...")
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    # Get private key PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Get public key PEM
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_pem.decode('utf-8'), public_pem.decode('utf-8')


def save_keys_to_files(private_key, public_key):
    """Save keys to secure files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create keys directory
    keys_dir = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/keys"
    os.makedirs(keys_dir, exist_ok=True)
    
    # Save private key
    private_key_file = f"{keys_dir}/jwt_private_key_{timestamp}.pem"
    with open(private_key_file, 'w') as f:
        f.write(private_key)
    
    # Set restrictive permissions on private key
    os.chmod(private_key_file, 0o600)
    
    # Save public key
    public_key_file = f"{keys_dir}/jwt_public_key_{timestamp}.pem"
    with open(public_key_file, 'w') as f:
        f.write(public_key)
    
    return private_key_file, public_key_file


def generate_env_template(private_key, public_key):
    """Generate environment variable template."""
    template = f"""# JWT RSA Keys for Production
# Generated: {datetime.now().isoformat()}
# Key Size: RSA-4096
# SECURITY: Keep these keys secure and never commit to version control

# Private key for JWT signing (KEEP SECRET)
JWT_PRIVATE_KEY="{private_key.replace(chr(10), '\\n')}"

# Public key for JWT verification  
JWT_PUBLIC_KEY="{public_key.replace(chr(10), '\\n')}"

# JWT Configuration
JWT_ALGORITHM=RS256
ENVIRONMENT=production
JWT_ACCESS_TOKEN_TTL=900
JWT_REFRESH_TOKEN_TTL=604800
JWT_REQUIRE_DEVICE_ID=true
JWT_TRACK_IP_ADDRESS=true
JWT_MAX_ACTIVE_SESSIONS=5
"""
    return template


def main():
    """Main key generation process."""
    print("🚀 Production RSA Key Generation")
    print("=" * 40)
    
    try:
        # Generate key pair
        private_key, public_key = generate_rsa_key_pair(4096)
        
        # Save to files
        private_file, public_file = save_keys_to_files(private_key, public_key)
        
        print(f"✅ Private key saved: {private_file}")
        print(f"✅ Public key saved: {public_file}")
        
        # Generate environment template
        env_template = generate_env_template(private_key, public_key)
        
        # Save environment template
        env_file = "/mnt/c/Users/jaafa/Desktop/ai teddy bear/.env.production.template"
        with open(env_file, 'w') as f:
            f.write(env_template)
        
        print(f"✅ Environment template saved: {env_file}")
        
        print("\n" + "=" * 40)
        print("🔐 SECURITY INSTRUCTIONS")
        print("=" * 40)
        print("1. Copy .env.production.template to .env.production")
        print("2. Set ENVIRONMENT=production in your deployment")  
        print("3. Never commit .env.production to version control")
        print("4. Keep private key file secure (permissions: 600)")
        print("5. Backup keys in secure location")
        print("6. Rotate keys every 30 days")
        
        print("\n✅ RSA key generation completed successfully!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error generating RSA keys: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())