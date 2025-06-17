# Testing Guide for Erdbaron Document Generator

This directory contains the test suite for the FastAPI backend application.

## Test Structure

```
tests/
├── __init__.py          # Test package initialization
├── conftest.py          # Pytest fixtures and configuration
├── test_auth.py         # Authentication system tests
├── test_main.py         # Main application integration tests
├── test_models.py       # Database model tests
├── test_projects.py     # Projects router tests
├── test_utils.py        # Utility function tests
└── README.md           # This file
```

## Prerequisites

Make sure you have the testing dependencies installed:

```bash
pip install -r requirements.txt
```

The test dependencies include:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities
- `httpx` - Async HTTP client for testing
- `faker` - Test data generation

## Running Tests

### Using the Test Runner Script

The easiest way to run tests is using the provided test runner:

```bash
# Run all tests with coverage
python run_tests.py

# Run only unit tests
python run_tests.py --type unit

# Run integration tests
python run_tests.py --type integration

# Run authentication tests
python run_tests.py --type auth

# Run model tests only
python run_tests.py --type models

# Run fast tests (exclude slow tests)
python run_tests.py --type fast

# Run specific test file
python run_tests.py --file test_auth.py

# Run specific test function
python run_tests.py --file test_auth.py --function test_login_success

# Run only failed tests from last run
python run_tests.py --failed

# Run with verbose output
python run_tests.py --verbose

# Install dependencies and run tests
python run_tests.py --install-deps
```

### Using Pytest Directly

You can also run pytest directly:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run specific test
pytest tests/test_auth.py::TestAuthRoutes::test_login_success

# Run tests matching pattern
pytest -k "test_login"

# Run tests with markers
pytest -m "auth"
pytest -m "not slow"

# Run verbose
pytest -v

# Run only failed tests
pytest --lf
```

## Test Categories

### Unit Tests
- Test individual functions and methods in isolation
- Mock external dependencies
- Fast execution
- Located in: `test_auth.py`, `test_utils.py`, `test_models.py`

### Integration Tests
- Test complete workflows and API endpoints
- Use test database
- Test component interactions
- Located in: `test_main.py`, `test_projects.py`

### Test Markers

Tests are marked with the following markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.auth` - Authentication-related tests
- `@pytest.mark.database` - Tests requiring database
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.slow` - Slow-running tests

## Test Database

Tests use a separate SQLite database (`test_db.sqlite3`) that is:
- Created fresh for each test session
- Automatically cleaned up after tests
- Isolated from the production database

## Test Fixtures

Key fixtures available in `conftest.py`:

- `db` - Fresh database connection for each test
- `test_client` - Async HTTP client for API testing
- `sync_client` - Synchronous HTTP client
- `test_user` - Pre-created test user
- `admin_user` - Pre-created admin user
- `auth_headers` - Authorization headers for authenticated requests
- `admin_headers` - Authorization headers for admin requests
- `test_document` - Pre-created test document
- `test_project` - Pre-created test project
- `mock_openai` - Mocked OpenAI API calls
- `temp_file` - Temporary file for upload testing

## Mocking

The test suite mocks external services:

- **OpenAI API**: Mocked to prevent actual API calls during testing
- **File System**: Temporary files and directories for testing
- **Environment Variables**: Test-specific configuration

## Coverage

Test coverage is configured to:
- Generate HTML reports in `htmlcov/`
- Exclude test files and virtual environments
- Require minimum 80% coverage
- Show missing lines in terminal output

View coverage report:
```bash
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
xdg-open htmlcov/index.html # Linux
```

## Writing New Tests

### Test File Structure

```python
import pytest
from models import MyModel

class TestMyFeature:
    """Test cases for my feature."""
    
    @pytest.mark.asyncio
    async def test_feature_success(self, db, test_user):
        """Test successful feature operation."""
        # Arrange
        setup_data = {"key": "value"}
        
        # Act
        result = await my_feature_function(setup_data)
        
        # Assert
        assert result.status == "success"
    
    @pytest.mark.asyncio
    async def test_feature_failure(self, db):
        """Test feature failure handling."""
        with pytest.raises(ExpectedException):
            await my_feature_function(invalid_data)
```

### API Test Example

```python
@pytest.mark.asyncio
async def test_api_endpoint(self, test_client, auth_headers):
    """Test API endpoint."""
    response = await test_client.post(
        "/api/endpoint",
        json={"data": "value"},
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "expected_value"
```

### Database Test Example

```python
@pytest.mark.asyncio
async def test_model_creation(self, db):
    """Test model creation."""
    model = await MyModel.create(
        field1="value1",
        field2="value2"
    )
    
    assert model.field1 == "value1"
    assert model.created_at is not None
```

## Debugging Tests

### Verbose Output
```bash
pytest -vv -s
```

### Debug Specific Test
```bash
pytest tests/test_auth.py::test_login_success -vv -s
```

### Show Local Variables on Failure
```bash
pytest --tb=long -vv
```

### Drop into Debugger on Failure
```bash
pytest --pdb
```

## Continuous Integration

The test suite is designed to run in CI environments:

- Uses environment variables for configuration
- Handles missing external services gracefully
- Provides machine-readable output formats
- Generates coverage reports

## Best Practices

1. **Isolation**: Each test should be independent
2. **Clarity**: Test names should describe what is being tested
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Mock External Services**: Don't make real API calls
5. **Use Fixtures**: Reuse common test setup
6. **Test Edge Cases**: Include error conditions and edge cases
7. **Keep Tests Fast**: Mock heavy operations
8. **Clean Up**: Use fixtures for cleanup

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Ensure test database is properly initialized
   - Check `conftest.py` database fixtures

2. **Import Errors**
   - Verify all dependencies are installed
   - Check Python path includes project root

3. **Async Test Issues**
   - Use `@pytest.mark.asyncio` for async tests
   - Ensure `pytest-asyncio` is installed

4. **Coverage Issues**
   - Check `.coveragerc` configuration
   - Ensure all source files are included

### Getting Help

- Check pytest documentation: https://docs.pytest.org/
- Review FastAPI testing guide: https://fastapi.tiangolo.com/tutorial/testing/
- Look at existing tests for examples 