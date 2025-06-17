# Deployment Guide for Digital Ocean

This guide outlines the steps to deploy this application on a Digital Ocean droplet.

## Prerequisites

1. A Digital Ocean account
2. A PostgreSQL database (can be a managed database from Digital Ocean)

## Deployment Steps

### 1. Create a Digital Ocean Droplet

- Create a new droplet with Ubuntu LTS
- Recommended specs: 2GB RAM, 1 vCPU, 50GB SSD
- Enable monitoring
- Add your SSH key for secure access

### 2. Set Up the Server

SSH into your droplet and run the following commands:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

Log out and log back in for the docker group to take effect.

### 3. Set Up the Database

#### Option 1: Use Digital Ocean Managed Database

1. Create a PostgreSQL database in Digital Ocean
2. Note the connection details
3. Make sure the database allows connections from your droplet

#### Option 2: Run PostgreSQL in Docker

```bash
docker run --name postgres \
  -e POSTGRES_PASSWORD=yourpassword \
  -e POSTGRES_USER=youruser \
  -e POSTGRES_DB=yourdb \
  -v postgres_data:/var/lib/postgresql/data \
  -p 5432:5432 \
  -d postgres:14
```

### 4. Deploy the Application

Clone your repository and build the Docker image:

```bash
git clone https://github.com/yourusername/yourrepo.git
cd yourrepo

# Create .env file with your configuration
cat > .env << EOF
DATABASE_URL=postgres://youruser:yourpassword@localhost:5432/yourdb
# Add other environment variables here
EOF

# Build and run the Docker image
docker build -t document_generator .
docker run -d \
  --name document_generator \
  -p 8000:8000 \
  --env-file .env \
  --restart always \
  document_generator
```

### 5. Set Up Nginx as a Reverse Proxy (Optional but Recommended)

```bash
# Install Nginx
sudo apt install -y nginx

# Configure Nginx
sudo nano /etc/nginx/sites-available/document_generator
```

Add the following configuration:

```
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and restart Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/document_generator /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6. Set Up SSL with Let's Encrypt (Recommended)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 7. Updating the Application

To update the application:

```bash
cd yourrepo
git pull
docker build -t document_generator .
docker stop document_generator
docker rm document_generator
docker run -d \
  --name document_generator \
  -p 8000:8000 \
  --env-file .env \
  --restart always \
  document_generator
```

## Database Migrations

When updating the application, you may need to run database migrations:

```bash
# Enter the container
docker exec -it document_generator bash

# Run migrations
python migrations.py upgrade
```

## Monitoring and Maintenance

- Set up regular backups of your database
- Consider using Digital Ocean's monitoring tools
- Set up log rotation for application logs

## Troubleshooting

If you encounter issues:

1. Check the application logs: `docker logs document_generator`
2. Verify database connectivity
3. Ensure environment variables are correctly set
4. Check that migrations have been applied correctly 