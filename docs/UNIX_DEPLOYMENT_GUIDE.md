# Unix Deployment Guide for Document Generator

This guide will help you set up the Document Generator backend on a Unix system with consistent PDF rendering that matches your local Windows environment.

## Prerequisites

- Ubuntu/Debian-based Linux system
- Python 3.10+
- sudo access
- Your application code deployed to the server

## Step 1: Run the Setup Script

1. Make the setup script executable:
```bash
chmod +x scripts/setup_unix_pdf_environment.sh
```

2. Run the setup script:
```bash
./scripts/setup_unix_pdf_environment.sh
```

This script will:
- Install essential fonts (Liberation, DejaVu, Noto)
- Install required system libraries
- Update font cache
- Create environment variables file
- Verify wkhtmltopdf installation

## Step 2: Configure Environment Variables

### Option A: Using systemd service (Recommended)

1. Copy the service file template:
```bash
sudo cp scripts/document-generator.service /etc/systemd/system/
```

2. Edit the service file:
```bash
sudo nano /etc/systemd/system/document-generator.service
```

3. Update the following fields:
   - `User=your-app-user` → your actual username
   - `Group=your-app-group` → your actual group
   - `WorkingDirectory=/path/to/your/DocumentGenerator_backend` → actual path
   - `ExecStart=/path/to/your/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000` → actual paths
   - Add your actual environment variables (OPENAI_API_KEY, DATABASE_URL, etc.)

4. Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable document-generator
sudo systemctl start document-generator
```

5. Check service status:
```bash
sudo systemctl status document-generator
```

### Option B: Using environment file

1. Copy the environment variables to your application's environment file:
```bash
cat /tmp/pdf_env_vars >> /path/to/your/.env
```

2. Source the environment in your startup script:
```bash
source /tmp/pdf_env_vars
```

### Option C: Export in shell session

For testing, you can export the variables in your current session:
```bash
source /tmp/pdf_env_vars
```

## Step 3: Verify Installation

1. Run the diagnostic script:
```bash
python scripts/check_pdf_environment.py
```

2. Expected output should show:
   - ✓ wkhtmltopdf found
   - ✓ Qt-based version detected
   - ✓ Liberation/DejaVu fonts found
   - ✓ Environment variables set
   - ✓ PDF generation successful

## Step 4: Test PDF Generation

1. Start your application (if not using systemd):
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

2. Test PDF generation through the API or run the consistency test:
```bash
python scripts/test_pdf_consistency.py
```

## Troubleshooting

### Font Issues
If you see font substitution warnings:
```bash
# Install additional fonts
sudo apt-get install fonts-liberation fonts-dejavu-core fonts-noto
sudo fc-cache -fv
```

### wkhtmltopdf Issues
If wkhtmltopdf is not found:
```bash
# Install wkhtmltopdf
sudo apt-get install wkhtmltopdf

# Verify installation
which wkhtmltopdf
wkhtmltopdf --version
```

### Environment Variable Issues
If environment variables are not being picked up:
```bash
# Check if variables are set
echo $QT_QPA_PLATFORM
echo $WKHTMLTOPDF_PATH

# Re-source the environment file
source /tmp/pdf_env_vars
```

### Permission Issues
If you get permission errors:
```bash
# Make sure your user has access to font directories
ls -la /usr/share/fonts
ls -la /etc/fonts

# Check application file permissions
chown -R your-user:your-group /path/to/DocumentGenerator_backend
```

## Key Differences from Windows

| Component | Windows | Unix |
|-----------|---------|------|
| wkhtmltopdf path | `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe` | `/usr/bin/wkhtmltopdf` |
| Font directory | `C:\Windows\Fonts` | `/usr/share/fonts` |
| Font config | Registry | `/etc/fonts` |
| Environment | Windows Registry | Shell environment |

## Environment Variables Reference

The following environment variables are required for consistent PDF rendering:

```bash
export QT_QPA_PLATFORM=offscreen      # Headless Qt operation
export DISPLAY=:99                    # Virtual display
export QT_QPA_FONTDIR=/usr/share/fonts # Font directory
export FONTCONFIG_PATH=/etc/fonts     # Font configuration
export WKHTMLTOPDF_PATH=/usr/bin/wkhtmltopdf # wkhtmltopdf binary
```

## Monitoring

To monitor your application:

```bash
# Check service logs
sudo journalctl -u document-generator -f

# Check application logs
tail -f /path/to/your/logs/app.log

# Monitor PDF generation
grep "PDF" /path/to/your/logs/app.log
```

## Updates

When updating the application:

1. Stop the service:
```bash
sudo systemctl stop document-generator
```

2. Update your code

3. Restart the service:
```bash
sudo systemctl start document-generator
```

4. Verify PDF generation still works:
```bash
python scripts/check_pdf_environment.py
``` 