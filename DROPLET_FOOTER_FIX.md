# Fixing wkhtmltopdf Footer Issue on Your Droplet

## Problem
The footer (company information and page numbers) is not appearing in PDFs generated on your droplet, while it works fine locally on Windows.

## Root Cause
This is a common issue with wkhtmltopdf in headless Linux environments. The most likely causes are:

1. **Missing environment variables** for headless operation
2. **Non-Qt version** of wkhtmltopdf (reduced functionality)
3. **Missing fonts** or font configuration issues

## Quick Fix (Recommended)

### Step 1: Upload and Run the Fix Script

1. Upload these files to your droplet:
   - `scripts/fix_droplet_footer.sh`
   - `scripts/diagnose_droplet_pdf.py`

2. SSH into your droplet and run:
```bash
cd /path/to/your/DocumentGenerator_backend
chmod +x scripts/fix_droplet_footer.sh
./scripts/fix_droplet_footer.sh
```

This script will:
- Install required fonts and libraries
- Install Qt-based wkhtmltopdf if needed
- Set up environment variables
- Test footer rendering
- Provide next steps

### Step 2: Update Your Application Environment

After running the fix script, you need to ensure your application uses the environment variables.

#### Option A: If using systemd service
Edit your service file:
```bash
sudo nano /etc/systemd/system/your-app.service
```

Add these lines in the `[Service]` section:
```ini
Environment=QT_QPA_PLATFORM=offscreen
Environment=DISPLAY=:99
```

Then restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart your-app
```

#### Option B: If running manually
Source the environment before starting your app:
```bash
source ~/.pdf_env
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

#### Option C: If using Docker
Add to your Dockerfile:
```dockerfile
ENV QT_QPA_PLATFORM=offscreen
ENV DISPLAY=:99
```

## Manual Fix (If Script Doesn't Work)

### 1. Install Required Packages
```bash
sudo apt-get update
sudo apt-get install -y \
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    wkhtmltopdf
```

### 2. Check wkhtmltopdf Version
```bash
wkhtmltopdf --version
```

If it doesn't mention "Qt" or "patched qt", you need the Qt-based version:

```bash
# For Ubuntu 20.04
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb
sudo dpkg -i wkhtmltox_0.12.6-1.focal_amd64.deb
sudo apt-get install -f
```

### 3. Set Environment Variables
```bash
export QT_QPA_PLATFORM=offscreen
export DISPLAY=:99
```

Add these to your application's environment permanently.

### 4. Test Footer Rendering
```bash
echo '<html><body><h1>Test</h1></body></html>' > test.html
wkhtmltopdf --footer-center "Test Footer" --footer-right "[page]" test.html test.pdf
```

## Diagnostic Tools

### Run the Diagnostic Script
```bash
python scripts/diagnose_droplet_pdf.py
```

This will check:
- wkhtmltopdf version and Qt support
- Environment variables
- Font availability
- Generate a test PDF with footer

### Check Your Application Logs
Look for any wkhtmltopdf errors in your application logs:
```bash
# If using systemd
sudo journalctl -u your-app -f

# If running manually
tail -f your-app.log
```

## Common Issues and Solutions

### Issue: "cannot connect to X server"
**Solution:** Set `QT_QPA_PLATFORM=offscreen`

### Issue: Footer appears but is cut off
**Solution:** Increase bottom margin in your PDF options

### Issue: Different fonts than local
**Solution:** Install the same fonts on both environments

### Issue: wkhtmltopdf command not found
**Solution:** Install wkhtmltopdf or set `WKHTMLTOPDF_PATH`

## Verification

After applying the fix:

1. **Test the diagnostic script:**
   ```bash
   python scripts/diagnose_droplet_pdf.py
   ```

2. **Generate a test PDF through your application**

3. **Check that the footer contains:**
   - Company info: "Erdbaron HQ SRL | Preot Bacca 15 | 55065 Hermannstadt"
   - Page numbers: "1 / 3" format
   - Footer line above the text

## Environment Variables Reference

Your application needs these environment variables:

```bash
# Critical for headless operation
QT_QPA_PLATFORM=offscreen
DISPLAY=:99

# Optional but recommended
WKHTMLTOPDF_PATH=/usr/local/bin/wkhtmltopdf
FONTCONFIG_PATH=/etc/fonts
QT_QPA_FONTDIR=/usr/share/fonts
```

## Still Having Issues?

1. Run the diagnostic script and share the output
2. Check if the test PDF from the diagnostic script has a footer
3. Compare wkhtmltopdf versions between local and droplet
4. Verify that your application is actually using the environment variables

The most common fix is simply setting `QT_QPA_PLATFORM=offscreen` and ensuring you have the Qt-based version of wkhtmltopdf installed. 