#!/bin/bash

# Setup script for Unix PDF environment
# Run this script on your Unix server to ensure consistent PDF rendering

echo "=== Setting up Unix PDF Environment ==="

# Update package list
echo "Updating package list..."
sudo apt-get update

# Install essential fonts
echo "Installing fonts..."
sudo apt-get install -y \
    fonts-liberation \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-noto \
    fonts-noto-core \
    fontconfig

# Install additional system libraries for wkhtmltopdf
echo "Installing system libraries..."
sudo apt-get install -y \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    libx11-6 \
    libxss1 \
    libgconf-2-4

# Update font cache
echo "Updating font cache..."
sudo fc-cache -fv

# Set up environment variables
echo "Setting up environment variables..."

# Create environment file for the application
cat > /tmp/pdf_env_vars << 'EOF'
# PDF Environment Variables
export QT_QPA_PLATFORM=offscreen
export DISPLAY=:99
export QT_QPA_FONTDIR=/usr/share/fonts
export FONTCONFIG_PATH=/etc/fonts
export WKHTMLTOPDF_PATH=/usr/bin/wkhtmltopdf
EOF

echo "Environment variables created in /tmp/pdf_env_vars"
echo "Add these to your application's environment:"
cat /tmp/pdf_env_vars

# Check if wkhtmltopdf is installed
echo ""
echo "=== Checking wkhtmltopdf installation ==="
if command -v wkhtmltopdf &> /dev/null; then
    echo "✓ wkhtmltopdf is installed"
    wkhtmltopdf --version
else
    echo "⚠ wkhtmltopdf not found. Installing..."
    sudo apt-get install -y wkhtmltopdf
fi

# Test font availability
echo ""
echo "=== Checking font availability ==="
fc-list | grep -i arial && echo "✓ Arial fonts found" || echo "⚠ Arial fonts not found (will use substitutes)"
fc-list | grep -i liberation && echo "✓ Liberation fonts found" || echo "⚠ Liberation fonts not found"
fc-list | grep -i dejavu && echo "✓ DejaVu fonts found" || echo "⚠ DejaVu fonts not found"

echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "1. Source the environment variables in your application startup"
echo "2. Restart your application"
echo "3. Test PDF generation"
echo ""
echo "To apply environment variables to your current session:"
echo "source /tmp/pdf_env_vars" 