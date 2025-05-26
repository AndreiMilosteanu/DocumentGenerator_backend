#!/usr/bin/env python3
"""
Diagnostic script to check PDF generation environment.
This script helps identify differences between local and deployed environments
that could cause PDF rendering inconsistencies.
"""

import subprocess
import sys
import os
import platform
from pathlib import Path

def check_wkhtmltopdf():
    """Check wkhtmltopdf installation and version"""
    print("=== wkhtmltopdf Check ===")
    
    # Try different possible paths
    possible_paths = [
        "wkhtmltopdf",  # System PATH
        "/usr/bin/wkhtmltopdf",  # Linux default
        "/usr/local/bin/wkhtmltopdf",  # Linux alternative
        "C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe",  # Windows default
        "/opt/wkhtmltopdf/bin/wkhtmltopdf",  # Docker/container path
    ]
    
    wkhtmltopdf_path = None
    for path in possible_paths:
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                wkhtmltopdf_path = path
                print(f"✓ Found wkhtmltopdf at: {path}")
                print(f"  Version: {result.stdout.strip()}")
                break
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    if not wkhtmltopdf_path:
        print("✗ wkhtmltopdf not found in any standard location")
        return None
    
    # Check extended info
    try:
        result = subprocess.run([wkhtmltopdf_path, "--extended-help"], capture_output=True, text=True, timeout=10)
        if "qt" in result.stdout.lower():
            print("✓ Qt-based version detected (recommended)")
        else:
            print("⚠ Non-Qt version detected (may cause rendering issues)")
    except:
        print("? Could not determine wkhtmltopdf type")
    
    return wkhtmltopdf_path

def check_system_fonts():
    """Check available system fonts"""
    print("\n=== System Fonts Check ===")
    
    system = platform.system().lower()
    
    if system == "linux":
        # Check for common font packages
        font_dirs = [
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            "/home/.fonts",
            "/etc/fonts"
        ]
        
        found_fonts = []
        for font_dir in font_dirs:
            if os.path.exists(font_dir):
                found_fonts.append(font_dir)
        
        print(f"Font directories found: {len(found_fonts)}")
        for font_dir in found_fonts:
            print(f"  - {font_dir}")
        
        # Check for Arial specifically (common issue)
        arial_found = False
        for font_dir in found_fonts:
            arial_path = Path(font_dir)
            if any(arial_path.rglob("*arial*")):
                arial_found = True
                break
        
        if arial_found:
            print("✓ Arial font family found")
        else:
            print("⚠ Arial font family not found (may cause font substitution)")
            print("  Consider installing: apt-get install fonts-liberation fonts-dejavu-core")
    
    elif system == "windows":
        fonts_dir = "C:\\Windows\\Fonts"
        if os.path.exists(fonts_dir):
            print(f"✓ Windows fonts directory found: {fonts_dir}")
            arial_path = os.path.join(fonts_dir, "arial.ttf")
            if os.path.exists(arial_path):
                print("✓ Arial font found")
            else:
                print("⚠ Arial font not found")
        else:
            print("✗ Windows fonts directory not found")
    
    else:
        print(f"Font check not implemented for {system}")

def check_environment_variables():
    """Check relevant environment variables"""
    print("\n=== Environment Variables ===")
    
    env_vars = [
        "WKHTMLTOPDF_PATH",
        "FONTCONFIG_PATH",
        "DISPLAY",
        "QT_QPA_PLATFORM",
        "QT_QPA_FONTDIR"
    ]
    
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            print(f"✓ {var}={value}")
        else:
            print(f"- {var} not set")

def check_python_packages():
    """Check Python packages related to PDF generation"""
    print("\n=== Python Packages ===")
    
    packages = ["pdfkit", "jinja2", "PyPDF2"]
    
    for package in packages:
        try:
            __import__(package)
            if package == "pdfkit":
                import pdfkit
                print(f"✓ {package} version: {pdfkit.__version__ if hasattr(pdfkit, '__version__') else 'unknown'}")
            else:
                print(f"✓ {package} installed")
        except ImportError:
            print(f"✗ {package} not installed")

def test_basic_pdf_generation(wkhtmltopdf_path):
    """Test basic PDF generation"""
    print("\n=== PDF Generation Test ===")
    
    if not wkhtmltopdf_path:
        print("✗ Cannot test PDF generation - wkhtmltopdf not found")
        return
    
    # Create a simple HTML test
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; font-size: 11pt; }
            .test { margin: 20px; }
        </style>
    </head>
    <body>
        <div class="test">
            <h1>PDF Generation Test</h1>
            <p>This is a test document to verify PDF generation.</p>
            <p>Font: Arial, Size: 11pt</p>
        </div>
    </body>
    </html>
    """
    
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as html_file:
            html_file.write(test_html)
            html_path = html_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
            pdf_path = pdf_file.name
        
        # Test PDF generation
        cmd = [
            wkhtmltopdf_path,
            '--page-size', 'A4',
            '--margin-top', '20mm',
            '--margin-bottom', '20mm',
            '--margin-left', '20mm',
            '--margin-right', '20mm',
            '--encoding', 'UTF-8',
            '--footer-center', '[page] / [topage]',
            '--footer-font-size', '9',
            html_path,
            pdf_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            print(f"✓ PDF generation successful (size: {pdf_size} bytes)")
            
            # Check if footer was rendered
            if pdf_size > 1000:  # Reasonable minimum size
                print("✓ PDF appears to have content")
            else:
                print("⚠ PDF seems too small, may be missing content")
        else:
            print(f"✗ PDF generation failed")
            if result.stderr:
                print(f"  Error: {result.stderr}")
        
        # Cleanup
        try:
            os.unlink(html_path)
            os.unlink(pdf_path)
        except:
            pass
            
    except Exception as e:
        print(f"✗ PDF generation test failed: {e}")

def main():
    """Run all diagnostic checks"""
    print("PDF Environment Diagnostic Tool")
    print("=" * 50)
    print(f"Platform: {platform.platform()}")
    print(f"Python: {sys.version}")
    print()
    
    wkhtmltopdf_path = check_wkhtmltopdf()
    check_system_fonts()
    check_environment_variables()
    check_python_packages()
    test_basic_pdf_generation(wkhtmltopdf_path)
    
    print("\n" + "=" * 50)
    print("Diagnostic complete!")
    
    if not wkhtmltopdf_path:
        print("\n⚠ RECOMMENDATIONS:")
        print("1. Install wkhtmltopdf with Qt support")
        print("2. Ensure it's in your system PATH or set WKHTMLTOPDF_PATH")
    
    print("\n💡 For consistent PDF rendering:")
    print("1. Use the same wkhtmltopdf version on all environments")
    print("2. Install the same font packages")
    print("3. Set QT_QPA_PLATFORM=offscreen for headless environments")

if __name__ == "__main__":
    main() 