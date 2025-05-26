# PDF Generation Troubleshooting Guide

This guide helps resolve common PDF generation issues, particularly differences between local and deployed environments.

## Common Issues

### 1. Different Font Sizes Between Environments

**Symptoms:**
- PDFs generated locally have different font sizes than on the server
- Text appears larger or smaller than expected
- Layout inconsistencies

**Causes:**
- Different wkhtmltopdf versions
- Missing font files on the server
- Different DPI settings
- Font substitution occurring

**Solutions:**

#### For Docker/Container Deployments:
```bash
# Ensure proper fonts are installed in Dockerfile
RUN apt-get update && apt-get install -y \
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    wkhtmltopdf
```

#### For Direct Server Deployments:
```bash
# Install required fonts on Ubuntu/Debian
sudo apt-get install fonts-liberation fonts-dejavu-core fontconfig

# Install required fonts on CentOS/RHEL
sudo yum install liberation-fonts dejavu-fonts fontconfig

# Refresh font cache
sudo fc-cache -fv
```

### 2. Missing Pagination/Footers

**Symptoms:**
- Page numbers not appearing
- Footers missing entirely
- Footer content cut off

**Causes:**
- wkhtmltopdf version differences
- Missing Qt support
- Incorrect margin settings
- Headless environment issues

**Solutions:**

#### Environment Variables (add to your deployment):
```bash
export QT_QPA_PLATFORM=offscreen
export DISPLAY=:99
```

#### For Docker deployments, add to Dockerfile:
```dockerfile
ENV QT_QPA_PLATFORM=offscreen
ENV DISPLAY=:99
```

#### Ensure Qt-based wkhtmltopdf:
```bash
# Check if you have Qt support
wkhtmltopdf --extended-help | grep -i qt

# If not, install Qt-based version
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb
sudo dpkg -i wkhtmltox_0.12.6-1.focal_amd64.deb
```

### 3. Inconsistent Rendering

**Symptoms:**
- Different layout between environments
- Text wrapping differently
- Images not displaying correctly

**Solutions:**

#### Use Consistent wkhtmltopdf Options:
The application now includes enhanced PDF options for consistency:
- High DPI settings (300 DPI)
- Disabled compression
- Consistent viewport size
- Disabled JavaScript for predictable rendering

#### Version Consistency:
Ensure the same wkhtmltopdf version across all environments:
```bash
# Check version
wkhtmltopdf --version

# For consistent deployment, pin the version in Dockerfile
RUN wget -O wkhtmltox.deb https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb \
    && dpkg -i wkhtmltox.deb \
    && rm wkhtmltox.deb
```

## Diagnostic Tools

### 1. Environment Diagnostic
Run this script to check your environment:
```bash
python scripts/check_pdf_environment.py
```

This will check:
- wkhtmltopdf installation and version
- Available fonts
- Environment variables
- Basic PDF generation test

### 2. PDF Consistency Test
Run this script to test PDF generation:
```bash
python scripts/test_pdf_consistency.py
```

This will:
- Generate a test PDF
- Report size and page count
- Save a test file for manual inspection

## Configuration Recommendations

### 1. Environment Variables
Set these in your deployment environment:
```bash
# Required for headless operation
QT_QPA_PLATFORM=offscreen
DISPLAY=:99

# Optional: Custom wkhtmltopdf path
WKHTMLTOPDF_PATH=/usr/local/bin/wkhtmltopdf

# Optional: Font configuration
FONTCONFIG_PATH=/etc/fonts
```

### 2. Docker Configuration
Use the updated Dockerfile which includes:
- Proper font packages
- Required system libraries
- Environment variables for headless operation

### 3. System Requirements
Ensure these packages are installed:
- `wkhtmltopdf` (with Qt support)
- `fonts-liberation`
- `fonts-dejavu-core`
- `fontconfig`
- `libxrender1`
- `libxext6`
- `libfontconfig1`

## Testing Your Setup

### 1. Quick Test
```bash
# Test wkhtmltopdf directly
echo '<html><body><h1>Test</h1><p>Page: <span class="page"></span></p></body></html>' > test.html
wkhtmltopdf --footer-center '[page]' test.html test.pdf
```

### 2. Application Test
```bash
# Run the consistency test
python scripts/test_pdf_consistency.py

# Check the generated PDF file for:
# - Correct font rendering
# - Proper pagination
# - Footer appearance
```

## Common Error Messages

### "wkhtmltopdf: cannot connect to X server"
**Solution:** Set `QT_QPA_PLATFORM=offscreen`

### "Font not found" or font substitution warnings
**Solution:** Install proper font packages and refresh font cache

### "Footer not rendering"
**Solution:** Ensure Qt-based wkhtmltopdf and proper environment variables

### "Different font sizes"
**Solution:** Use consistent DPI settings and ensure same fonts are available

## Version Compatibility

### Recommended Versions:
- **wkhtmltopdf:** 0.12.6 (with Qt support)
- **Python pdfkit:** Latest version
- **Fonts:** liberation-fonts, dejavu-fonts

### Known Issues:
- wkhtmltopdf 0.12.5 and earlier: Footer rendering issues
- Non-Qt versions: Inconsistent font rendering
- Alpine Linux: Font rendering problems (use Debian/Ubuntu base)

## Support

If you continue to experience issues:

1. Run both diagnostic scripts and compare outputs between environments
2. Check the application logs for PDF generation errors
3. Verify that the same wkhtmltopdf version is used everywhere
4. Ensure all required fonts are installed and accessible

For additional help, include the output of the diagnostic scripts when reporting issues. 