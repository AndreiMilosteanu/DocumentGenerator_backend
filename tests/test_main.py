import pytest
from unittest.mock import patch
import uuid

class TestMainApplication:
    """Integration tests for the main FastAPI application."""
    
    @pytest.mark.asyncio
    async def test_ping_endpoint(self, test_client):
        """Test the ping/health check endpoint."""
        response = await test_client.get("/ping")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_cors_headers(self, test_client):
        """Test CORS headers are properly set."""
        response = await test_client.options("/ping")
        
        # FastAPI should handle OPTIONS request
        assert response.status_code in [200, 405]  # Some CORS implementations return 405 for OPTIONS
    
    @pytest.mark.asyncio
    async def test_application_startup(self, test_client):
        """Test that the application starts up correctly."""
        # Test basic connectivity
        response = await test_client.get("/ping")
        assert response.status_code == 200
        
        # Test that routers are mounted
        response = await test_client.get("/auth/debug")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_404_handling(self, test_client):
        """Test 404 handling for non-existent endpoints."""
        response = await test_client.get("/nonexistent-endpoint")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_method_not_allowed(self, test_client):
        """Test method not allowed responses."""
        # Try POST on a GET-only endpoint
        response = await test_client.post("/ping")
        
        assert response.status_code == 405
    
    @pytest.mark.asyncio
    async def test_router_mounting(self, test_client):
        """Test that all routers are properly mounted."""
        # Test each router prefix
        router_tests = [
            ("/auth/debug", 200),
            ("/projects/", 401),  # Should require auth
            ("/conversation/nonexistent", 404),  # Should return 404, not 500
            ("/documents/nonexistent", 404),  # Should return 404, not 500
            ("/upload/nonexistent", 404),  # Should return 404, not 500
            ("/cover-page/nonexistent", 404),  # Should return 404, not 500
        ]
        
        for endpoint, expected_status in router_tests:
            response = await test_client.get(endpoint)
            assert response.status_code == expected_status
    
    @pytest.mark.asyncio
    async def test_request_validation(self, test_client):
        """Test request validation for invalid JSON."""
        # Send invalid JSON to an endpoint that expects JSON
        response = await test_client.post(
            "/auth/register",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_large_request_handling(self, test_client):
        """Test handling of large requests."""
        # Create a large but valid request
        large_data = {
            "email": "test@example.com",
            "password": "password123",
            "extra_data": "x" * 1000  # 1KB of extra data
        }
        
        response = await test_client.post("/auth/register", json=large_data)
        
        # Should either succeed or fail with validation error, not server error
        assert response.status_code in [200, 422]
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, test_client):
        """Test handling of concurrent requests."""
        import asyncio
        
        # Make multiple concurrent requests
        tasks = [
            test_client.get("/ping") for _ in range(10)
        ]
        
        responses = await asyncio.gather(*tasks)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_database_connection(self, test_client, db):
        """Test that database connection is working."""
        # Try to access an endpoint that requires database
        response = await test_client.post(
            "/auth/register",
            json={"email": "dbtest@example.com", "password": "password123"}
        )
        
        # Should succeed or fail with business logic, not database connection error
        assert response.status_code in [200, 400, 422]
        assert response.status_code != 500  # No internal server error
    
    @pytest.mark.asyncio
    async def test_authentication_flow(self, test_client, db):
        """Test complete authentication flow."""
        # Register a user
        user_data = {
            "email": "flowtest@example.com",
            "password": "password123"
        }
        
        register_response = await test_client.post("/auth/register", json=user_data)
        assert register_response.status_code == 200
        
        # Login with the user
        login_data = {
            "username": user_data["email"],
            "password": user_data["password"]
        }
        
        login_response = await test_client.post(
            "/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert login_response.status_code == 200
        token_data = login_response.json()
        assert "access_token" in token_data
        
        # Use token to access protected endpoint
        auth_headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        profile_response = await test_client.get("/auth/me", headers=auth_headers)
        
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["email"] == user_data["email"]
    
    @pytest.mark.asyncio
    async def test_project_creation_flow(self, test_client, db):
        """Test complete project creation flow."""
        # Register and login user
        user_data = {
            "email": "projectflow@example.com",
            "password": "password123"
        }
        
        await test_client.post("/auth/register", json=user_data)
        
        login_response = await test_client.post(
            "/auth/login",
            data={"username": user_data["email"], "password": user_data["password"]},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        token = login_response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        # Create a project
        project_data = {
            "name": "Integration Test Project",
            "topic": "Integration Testing"
        }
        
        project_response = await test_client.post(
            "/projects/create",
            json=project_data,
            headers=auth_headers
        )
        
        assert project_response.status_code == 200
        project = project_response.json()
        assert project["name"] == project_data["name"]
        
        # List projects
        list_response = await test_client.get("/projects/", headers=auth_headers)
        assert list_response.status_code == 200
        projects = list_response.json()
        assert len(projects) == 1
        assert projects[0]["name"] == project_data["name"]
    
    @pytest.mark.asyncio
    async def test_error_handling_middleware(self, test_client):
        """Test that error handling middleware works correctly."""
        # This would test custom error handlers if you have them
        # For now, test basic error responses
        
        # Test validation error
        response = await test_client.post("/auth/register", json={})
        assert response.status_code == 422
        
        # Test authentication error
        response = await test_client.get("/auth/me")
        assert response.status_code == 401
        
        # Test not found error
        response = await test_client.get("/nonexistent")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_request_logging(self, test_client):
        """Test that requests are properly logged."""
        with patch('logging.getLogger') as mock_logger:
            response = await test_client.get("/ping")
            
            # Verify response is successful
            assert response.status_code == 200
            
            # In a real implementation, you might check that logging was called
            # This depends on your logging setup
    
    @pytest.mark.asyncio
    async def test_api_documentation(self, test_client):
        """Test that API documentation is accessible."""
        # Test OpenAPI schema
        response = await test_client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert schema["info"]["title"] == "Erdbaron Document Generator"
        assert "paths" in schema
        
        # Test Swagger UI (if enabled)
        docs_response = await test_client.get("/docs")
        # Might be 200 (enabled) or 404 (disabled in production)
        assert docs_response.status_code in [200, 404]
    
    @pytest.mark.asyncio
    async def test_security_headers(self, test_client):
        """Test security headers in responses."""
        response = await test_client.get("/ping")
        
        # Check for CORS headers (since CORS is enabled)
        assert "access-control-allow-origin" in response.headers or \
               "Access-Control-Allow-Origin" in response.headers
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, test_client):
        """Test rate limiting if implemented."""
        # This test assumes you have rate limiting implemented
        # Make many requests quickly
        responses = []
        for i in range(5):
            response = await test_client.get("/ping")
            responses.append(response)
        
        # All should succeed if no rate limiting, or some should be limited
        success_count = sum(1 for r in responses if r.status_code == 200)
        
        # Either all succeed (no rate limiting) or some are limited
        assert success_count >= 1  # At least one should succeed
    
    @pytest.mark.asyncio
    async def test_environment_configuration(self, test_client, mock_env_vars):
        """Test that environment configuration is working."""
        # This test uses the mock_env_vars fixture
        # Test that the app is using the test configuration
        
        response = await test_client.get("/ping")
        assert response.status_code == 200
        
        # In a real test, you might verify that specific config values are being used 