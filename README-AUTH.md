# Authentication Setup

This document explains how to set up and use the authentication system for the Document Generator backend.

## Setup

1. Add the following line to your `.env` file:
   ```
   JWT_SECRET_KEY=your-secret-key-should-be-at-least-32-characters
   ```
   Replace with a secure random string of at least 32 characters.

2. Run the migration script to create the admin user:
   ```
   python -m scripts.migrate_users
   ```
   This will prompt you to create the first admin user with email and password.

3. Restart the application:
   ```
   uvicorn main:app --reload
   ```

## API Endpoints

### Authentication

- **Register a new user**: `POST /auth/register`
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword"
  }
  ```

- **Login**: `POST /auth/login`
  ```json
  {
    "username": "user@example.com",
    "password": "securepassword"
  }
  ```
  Returns a JWT token.

- **Get current user**: `GET /auth/me`
  Requires authentication header: `Authorization: Bearer {token}`

- **Create admin user** (only available during initial setup): `POST /auth/create-admin`
  ```json
  {
    "email": "admin@example.com",
    "password": "secureadminpassword"
  }
  ```

### Access Control

- Regular users can only see and modify their own projects
- Admin users can see and modify all projects
- All endpoints in the `/projects/*` routes now require authentication

## Frontend Integration

Update your frontend application to:

1. Store the JWT token after login
2. Include the token in all API requests:
   ```
   Authorization: Bearer {token}
   ```
3. Implement login/registration screens
4. Handle token expiration and refresh

## Security Notes

- JWT tokens are valid for 30 days by default
- Passwords are hashed using bcrypt
- Always use HTTPS in production
- The `JWT_SECRET_KEY` should be kept secure and not committed to version control 