#!/bin/bash

# Quick Unix Setup for Document Generator PDF Environment
# This script installs everything needed for consistent PDF rendering

echo "🚀 Setting up Document Generator PDF environment..."

# Install fonts and libraries
sudo apt-get update && sudo apt-get install -y \
    fonts-liberation \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-noto \
    fonts-noto-core \
    fontconfig \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    libx11-6 \
    libxss1 \
    libgconf-2-4 \
    wkhtmltopdf

# Update font cache
sudo fc-cache -fv

# Create environment variables
echo "📝 Creating environment variables..."
cat > ~/.pdf_env << 'EOF'
export QT_QPA_PLATFORM=offscreen
export DISPLAY=:99
export QT_QPA_FONTDIR=/usr/share/fonts
export FONTCONFIG_PATH=/etc/fonts
export WKHTMLTOPDF_PATH=/usr/bin/wkhtmltopdf
EOF

echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Add these environment variables to your application:"
echo "   source ~/.pdf_env"
echo ""
echo "2. Or add them to your systemd service file"
echo ""
echo "3. Restart your application"
echo ""
echo "4. Test with: python scripts/check_pdf_environment.py"
echo ""
echo "Environment variables created in ~/.pdf_env:"
cat ~/.pdf_env 