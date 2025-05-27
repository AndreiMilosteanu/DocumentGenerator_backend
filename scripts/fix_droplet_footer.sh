#!/bin/bash

echo "🔧 Fixing wkhtmltopdf footer issue on droplet..."
echo "================================================"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "⚠ Please don't run this script as root. Run as your regular user."
    exit 1
fi

# Update package list
echo "📦 Updating package list..."
sudo apt-get update

# Install required packages
echo "📦 Installing required packages..."
sudo apt-get install -y \
    fonts-liberation \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fontconfig \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    libx11-6 \
    libxss1 \
    libgconf-2-4

# Check current wkhtmltopdf version
echo ""
echo "🔍 Checking current wkhtmltopdf..."
if command -v wkhtmltopdf &> /dev/null; then
    current_version=$(wkhtmltopdf --version 2>&1)
    echo "Current version: $current_version"
    
    # Check if it's Qt-based
    if echo "$current_version" | grep -qi "qt"; then
        echo "✓ Qt-based version detected"
        qt_based=true
    else
        echo "⚠ Non-Qt version detected - this may cause footer issues"
        qt_based=false
    fi
else
    echo "✗ wkhtmltopdf not found"
    qt_based=false
fi

# Install Qt-based wkhtmltopdf if needed
if [ "$qt_based" = false ]; then
    echo ""
    echo "📥 Installing Qt-based wkhtmltopdf..."
    
    # Detect Ubuntu version
    ubuntu_version=$(lsb_release -rs 2>/dev/null || echo "20.04")
    
    if [[ "$ubuntu_version" == "20.04" ]]; then
        package_url="https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb"
    elif [[ "$ubuntu_version" == "18.04" ]]; then
        package_url="https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.bionic_amd64.deb"
    else
        # Default to focal for newer versions
        package_url="https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb"
    fi
    
    echo "Downloading wkhtmltopdf package..."
    wget -O /tmp/wkhtmltox.deb "$package_url"
    
    if [ $? -eq 0 ]; then
        echo "Installing wkhtmltopdf package..."
        sudo dpkg -i /tmp/wkhtmltox.deb
        
        # Fix any dependency issues
        sudo apt-get install -f -y
        
        # Clean up
        rm -f /tmp/wkhtmltox.deb
        
        echo "✓ Qt-based wkhtmltopdf installed"
    else
        echo "✗ Failed to download wkhtmltopdf package"
    fi
fi

# Update font cache
echo ""
echo "🔤 Updating font cache..."
sudo fc-cache -fv

# Set up environment variables
echo ""
echo "🌍 Setting up environment variables..."

# Create environment file
cat > ~/.pdf_env << 'EOF'
# PDF Environment Variables for wkhtmltopdf
export QT_QPA_PLATFORM=offscreen
export DISPLAY=:99
export QT_QPA_FONTDIR=/usr/share/fonts
export FONTCONFIG_PATH=/etc/fonts
export WKHTMLTOPDF_PATH=/usr/local/bin/wkhtmltopdf
EOF

echo "✓ Environment variables created in ~/.pdf_env"

# Add to .bashrc if not already there
if ! grep -q "source ~/.pdf_env" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# PDF Environment Variables" >> ~/.bashrc
    echo "source ~/.pdf_env" >> ~/.bashrc
    echo "✓ Added to ~/.bashrc"
fi

# Source the environment for current session
source ~/.pdf_env

echo ""
echo "🧪 Testing wkhtmltopdf with footer..."

# Create a simple test
cat > /tmp/test_footer.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
    </style>
</head>
<body>
    <h1>Footer Test</h1>
    <p>This is a test document to verify footer rendering.</p>
    <p>The footer should appear at the bottom with company info and page numbers.</p>
</body>
</html>
EOF

# Test footer rendering
wkhtmltopdf \
    --page-size A4 \
    --margin-bottom 25mm \
    --footer-center "Erdbaron HQ SRL | Preot Bacca 15 | 55065 Hermannstadt" \
    --footer-right "[page] / [topage]" \
    --footer-font-size 9 \
    --footer-spacing 10 \
    --footer-line \
    /tmp/test_footer.html \
    /tmp/test_footer.pdf

if [ $? -eq 0 ] && [ -f /tmp/test_footer.pdf ]; then
    pdf_size=$(stat -c%s /tmp/test_footer.pdf)
    echo "✅ Test PDF generated successfully (size: $pdf_size bytes)"
    echo "📄 Test file: /tmp/test_footer.pdf"
    echo "   Download this file to verify footer appears correctly"
else
    echo "❌ Test PDF generation failed"
fi

# Clean up test HTML
rm -f /tmp/test_footer.html

echo ""
echo "🎯 NEXT STEPS:"
echo "=============="
echo "1. Restart your application to pick up the new environment variables"
echo "2. If using systemd service, add these environment variables to your service file:"
echo "   Environment=QT_QPA_PLATFORM=offscreen"
echo "   Environment=DISPLAY=:99"
echo ""
echo "3. If using Docker, add these to your Dockerfile:"
echo "   ENV QT_QPA_PLATFORM=offscreen"
echo "   ENV DISPLAY=:99"
echo ""
echo "4. Test your application's PDF generation"
echo ""
echo "5. If still having issues, run the diagnostic script:"
echo "   python scripts/diagnose_droplet_pdf.py"
echo ""
echo "✅ Setup complete! Your environment should now support footer rendering." 