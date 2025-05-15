import asyncio
import sys
import os
import logging
import json
from getpass import getpass
import httpx

# Add parent directory to sys.path to allow importing from project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for more detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_login")

async def test_login():
    """
    Test the login functionality by making a request to the /auth/login endpoint
    """
    # Base URL - adjust if your server runs on a different port
    base_url = "http://localhost:8000"
    
    print("\n==== Test Login ====")
    email = input("Enter email: ")
    password = getpass("Enter password: ")
    
    try:
        async with httpx.AsyncClient() as client:
            # Make login request with form data format (x-www-form-urlencoded)
            logger.info(f"Attempting to log in as {email}...")
            
            # OAuth2 expects form data with username/password
            form_data = {
                "username": email,
                "password": password
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            logger.debug(f"Sending request to {base_url}/auth/login with form data")
            response = await client.post(
                f"{base_url}/auth/login",
                data=form_data,
                headers=headers
            )
            
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")
            
            if response.status_code == 200:
                token_data = response.json()
                logger.info("Login successful!")
                logger.info(f"User ID: {token_data['user_id']}")
                logger.info(f"Role: {token_data['role']}")
                logger.info(f"Token: {token_data['access_token'][:20]}...")
                
                # Test the token with /auth/me endpoint
                logger.info("Testing token with /auth/me endpoint...")
                me_response = await client.get(
                    f"{base_url}/auth/me",
                    headers={"Authorization": f"Bearer {token_data['access_token']}"}
                )
                
                if me_response.status_code == 200:
                    me_data = me_response.json()
                    logger.info("Token is valid, user data retrieved:")
                    logger.info(json.dumps(me_data, indent=2))
                else:
                    logger.error(f"Failed to verify token: {me_response.status_code}")
                    logger.error(f"Response: {me_response.text}")
            else:
                logger.error(f"Login failed: {response.status_code}")
                response_text = response.text
                try:
                    # Try to parse as JSON for better error message
                    error_data = response.json()
                    logger.error(f"Error details: {json.dumps(error_data, indent=2)}")
                except:
                    logger.error(f"Response: {response_text}")
    
    except Exception as e:
        logger.error(f"Error during login test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

async def test_registration():
    """
    Test the registration functionality by making a request to the /auth/register endpoint
    """
    # Base URL - adjust if your server runs on a different port
    base_url = "http://localhost:8000"
    
    print("\n==== Test Registration ====")
    email = input("Enter email for new user: ")
    password = getpass("Enter password for new user: ")
    
    try:
        async with httpx.AsyncClient() as client:
            # Make registration request
            logger.info(f"Attempting to register user {email}...")
            
            # Prepare registration data
            json_data = {
                "email": email,
                "password": password
            }
            
            logger.debug(f"Sending request to {base_url}/auth/register with JSON data")
            response = await client.post(
                f"{base_url}/auth/register",
                json=json_data
            )
            
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")
            
            if response.status_code == 200:
                user_data = response.json()
                logger.info("Registration successful!")
                logger.info(f"User ID: {user_data['id']}")
                logger.info(f"Role: {user_data['role']}")
                
                # Test login with the new user
                logger.info("Testing login with the new user...")
                form_data = {
                    "username": email,
                    "password": password
                }
                
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                
                login_response = await client.post(
                    f"{base_url}/auth/login",
                    data=form_data,
                    headers=headers
                )
                
                if login_response.status_code == 200:
                    logger.info("Login successful with the new user!")
                else:
                    logger.error(f"Login failed with new user: {login_response.status_code}")
                    logger.error(f"Response: {login_response.text}")
            else:
                logger.error(f"Registration failed: {response.status_code}")
                try:
                    # Try to parse as JSON for better error message
                    error_data = response.json()
                    logger.error(f"Error details: {json.dumps(error_data, indent=2)}")
                except:
                    logger.error(f"Response: {response.text}")
    
    except Exception as e:
        logger.error(f"Error during registration test: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

async def run_tests():
    """Run all tests"""
    while True:
        print("\n==== Authentication Tests ====")
        print("1. Test Login")
        print("2. Test Registration")
        print("3. Exit")
        
        choice = input("Enter choice (1-3): ")
        
        if choice == "1":
            await test_login()
        elif choice == "2":
            await test_registration()
        elif choice == "3":
            break
        else:
            print("Invalid choice, please try again")

if __name__ == "__main__":
    asyncio.run(run_tests()) 