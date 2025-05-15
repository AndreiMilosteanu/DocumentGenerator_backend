import secrets
import base64
import os
from pathlib import Path

def generate_secure_key(length=32):
    """Generate a cryptographically secure key"""
    return secrets.token_urlsafe(length)

def update_env_file(jwt_key):
    """Update the .env file with the JWT key"""
    env_path = Path('.env')
    
    # Check if .env file exists
    if not env_path.exists():
        print("Error: .env file not found")
        return False
    
    # Read current .env content
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Check if JWT_SECRET_KEY already exists
    key_exists = False
    new_lines = []
    
    for line in lines:
        if line.strip().startswith('JWT_SECRET_KEY='):
            # Replace the key
            new_lines.append(f'JWT_SECRET_KEY={jwt_key}\n')
            key_exists = True
        else:
            new_lines.append(line)
    
    # Add key if it doesn't exist
    if not key_exists:
        new_lines.append(f'JWT_SECRET_KEY={jwt_key}\n')
    
    # Write back to .env
    with open(env_path, 'w') as f:
        f.writelines(new_lines)
    
    return True

if __name__ == "__main__":
    print("Generating secure JWT secret key...")
    key = generate_secure_key(48)  # Generate a 48-byte key for extra security
    
    print(f"\nGenerated JWT key: {key}")
    
    # Ask if user wants to update .env file
    update = input("\nDo you want to update your .env file with this key? (y/n): ").lower()
    
    if update == 'y':
        if update_env_file(key):
            print("JWT_SECRET_KEY updated in .env file")
        else:
            print("Failed to update .env file. Please add the following line manually:")
            print(f"JWT_SECRET_KEY={key}")
    else:
        print("\nPlease add the following line to your .env file:")
        print(f"JWT_SECRET_KEY={key}") 