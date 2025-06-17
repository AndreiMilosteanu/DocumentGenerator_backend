import pytest
import uuid
from models import User, Document, Project, UserRole, SectionData
from utils.auth import get_password_hash

class TestProjectsRouter:
    """Test cases for the projects API endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_project(self, test_client, db, test_user, auth_headers):
        """Test creating a new project."""
        project_data = {
            "name": "Test Research Project",
            "topic": "AI in Healthcare"
        }
        
        response = await test_client.post(
            "/projects/create",
            json=project_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Research Project"
        assert data["document"]["topic"] == "AI in Healthcare"
        assert "id" in data
        assert "created_at" in data
        assert data["user_id"] == str(test_user.id)
    
    @pytest.mark.asyncio
    async def test_create_project_unauthorized(self, test_client, db):
        """Test creating a project without authentication."""
        project_data = {
            "name": "Unauthorized Project",
            "topic": "Test Topic"
        }
        
        response = await test_client.post("/projects/create", json=project_data)
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_create_project_invalid_data(self, test_client, db, auth_headers):
        """Test creating a project with invalid data."""
        # Missing required fields
        project_data = {"name": "Incomplete Project"}
        
        response = await test_client.post(
            "/projects/create",
            json=project_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_list_user_projects(self, test_client, db, test_user, auth_headers):
        """Test listing projects for the current user."""
        # Create a few projects for the user
        document1 = await Document.create(
            id=str(uuid.uuid4()),
            topic="Document 1"
        )
        document2 = await Document.create(
            id=str(uuid.uuid4()),
            topic="Document 2"
        )
        
        await Project.create(
            id=str(uuid.uuid4()),
            name="Project 1",
            document=document1,
            user=test_user
        )
        await Project.create(
            id=str(uuid.uuid4()),
            name="Project 2",
            document=document2,
            user=test_user
        )
        
        # Create a project for another user (should not be returned)
        other_user = await User.create(
            id=str(uuid.uuid4()),
            email="other@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        document3 = await Document.create(
            id=str(uuid.uuid4()),
            topic="Other Document"
        )
        await Project.create(
            id=str(uuid.uuid4()),
            name="Other Project",
            document=document3,
            user=other_user
        )
        
        response = await test_client.get("/projects/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        project_names = [p["name"] for p in data]
        assert "Project 1" in project_names
        assert "Project 2" in project_names
        assert "Other Project" not in project_names
    
    @pytest.mark.asyncio
    async def test_list_projects_unauthorized(self, test_client, db):
        """Test listing projects without authentication."""
        response = await test_client.get("/projects/")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_project_by_id(self, test_client, db, test_user, auth_headers):
        """Test getting a specific project by ID."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Specific Document"
        )
        project = await Project.create(
            id=str(uuid.uuid4()),
            name="Specific Project",
            document=document,
            user=test_user
        )
        
        response = await test_client.get(
            f"/projects/{project.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Specific Project"
        assert data["id"] == str(project.id)
        assert data["document"]["topic"] == "Specific Document"
    
    @pytest.mark.asyncio
    async def test_get_project_not_found(self, test_client, db, auth_headers):
        """Test getting a non-existent project."""
        fake_id = str(uuid.uuid4())
        response = await test_client.get(
            f"/projects/{fake_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_project_unauthorized_user(self, test_client, db, auth_headers):
        """Test getting a project that belongs to another user."""
        # Create another user and their project
        other_user = await User.create(
            id=str(uuid.uuid4()),
            email="other@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER
        )
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Other User Document"
        )
        other_project = await Project.create(
            id=str(uuid.uuid4()),
            name="Other User Project",
            document=document,
            user=other_user
        )
        
        response = await test_client.get(
            f"/projects/{other_project.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404  # Should not find project that doesn't belong to user
    
    @pytest.mark.asyncio
    async def test_update_project_name(self, test_client, db, test_user, auth_headers):
        """Test updating a project name."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Update Test Document"
        )
        project = await Project.create(
            id=str(uuid.uuid4()),
            name="Original Name",
            document=document,
            user=test_user
        )
        
        update_data = {"name": "Updated Project Name"}
        
        response = await test_client.put(
            f"/projects/{project.id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Project Name"
        assert data["id"] == str(project.id)
    
    @pytest.mark.asyncio
    async def test_update_project_not_found(self, test_client, db, auth_headers):
        """Test updating a non-existent project."""
        fake_id = str(uuid.uuid4())
        update_data = {"name": "New Name"}
        
        response = await test_client.put(
            f"/projects/{fake_id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_delete_project(self, test_client, db, test_user, auth_headers):
        """Test deleting a project."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Delete Test Document"
        )
        project = await Project.create(
            id=str(uuid.uuid4()),
            name="Project to Delete",
            document=document,
            user=test_user
        )
        
        response = await test_client.delete(
            f"/projects/{project.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"]
        
        # Verify project is actually deleted
        deleted_project = await Project.filter(id=project.id).first()
        assert deleted_project is None
    
    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, test_client, db, auth_headers):
        """Test deleting a non-existent project."""
        fake_id = str(uuid.uuid4())
        
        response = await test_client.delete(
            f"/projects/{fake_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_project_sections(self, test_client, db, test_user, auth_headers):
        """Test getting sections for a project."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Sections Test Document"
        )
        project = await Project.create(
            id=str(uuid.uuid4()),
            name="Sections Test Project",
            document=document,
            user=test_user
        )
        
        # Create some section data
        await SectionData.create(
            document=document,
            section="introduction",
            data={"content": "Introduction content"}
        )
        await SectionData.create(
            document=document,
            section="methodology",
            data={"content": "Methodology content"}
        )
        
        response = await test_client.get(
            f"/projects/{project.id}/sections",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        section_names = [s["section"] for s in data]
        assert "introduction" in section_names
        assert "methodology" in section_names
    
    @pytest.mark.asyncio
    async def test_project_with_document_details(self, test_client, db, test_user, auth_headers):
        """Test that project response includes document details."""
        document = await Document.create(
            id=str(uuid.uuid4()),
            topic="Detailed Document",
            thread_id="thread_123"
        )
        project = await Project.create(
            id=str(uuid.uuid4()),
            name="Detailed Project",
            document=document,
            user=test_user
        )
        
        response = await test_client.get(
            f"/projects/{project.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["document"]["topic"] == "Detailed Document"
        assert data["document"]["thread_id"] == "thread_123"
        assert "created_at" in data["document"]
    
    @pytest.mark.asyncio
    async def test_empty_projects_list(self, test_client, db, test_user, auth_headers):
        """Test listing projects when user has no projects."""
        response = await test_client.get("/projects/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data == []
    
    @pytest.mark.asyncio
    async def test_project_creation_with_long_name(self, test_client, db, auth_headers):
        """Test creating a project with a very long name."""
        project_data = {
            "name": "A" * 300,  # Very long name
            "topic": "Test Topic"
        }
        
        response = await test_client.post(
            "/projects/create",
            json=project_data,
            headers=auth_headers
        )
        
        # This might fail due to database constraints, adjust based on your model
        # The response depends on your model's max_length setting
        assert response.status_code in [200, 422]  # Either success or validation error
    
    @pytest.mark.asyncio
    async def test_project_search_functionality(self, test_client, db, test_user, auth_headers):
        """Test project search functionality if implemented."""
        # Create projects with different names
        documents = []
        projects = []
        
        for i, name in enumerate(["Data Science Project", "Machine Learning Study", "AI Research"]):
            doc = await Document.create(
                id=str(uuid.uuid4()),
                topic=f"Topic {i}"
            )
            proj = await Project.create(
                id=str(uuid.uuid4()),
                name=name,
                document=doc,
                user=test_user
            )
            documents.append(doc)
            projects.append(proj)
        
        # If you have search functionality, test it here
        # For now, just test that all projects are returned
        response = await test_client.get("/projects/", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3 