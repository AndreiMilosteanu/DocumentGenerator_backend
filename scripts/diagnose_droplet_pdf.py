#!/usr/bin/env python3
"""
Droplet PDF Diagnostic Script
This script helps diagnose why wkhtmltopdf footer is not appearing on your droplet.
"""

import subprocess
import sys
import os
import tempfile
import platform
from pathlib import Path

def check_wkhtmltopdf_version():
    """Check wkhtmltopdf version and capabilities"""
    print("=== wkhtmltopdf Version Check ===")
    
    try:
        # Check version
        result = subprocess.run(["wkhtmltopdf", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✓ wkhtmltopdf version: {result.stdout.strip()}")
            
            # Check if it's Qt-based
            if "with patched qt" in result.stdout.lower() or "qt" in result.stdout.lower():
                print("✓ Qt-based version detected (good for footers)")
            else:
                print("⚠ Non-Qt version detected (may cause footer issues)")
                print("  Consider installing Qt-based version")
        else:
            print("✗ wkhtmltopdf not found or error running")
            return False
    except Exception as e:
        print(f"✗ Error checking wkhtmltopdf: {e}")
        return False
    
    # Check extended help for Qt support
    try:
        result = subprocess.run(["wkhtmltopdf", "--extended-help"], capture_output=True, text=True, timeout=10)
        if "qt" in result.stdout.lower():
            print("✓ Extended help shows Qt support")
        else:
            print("⚠ Extended help doesn't mention Qt")
    except:
        print("? Could not check extended help")
    
    return True

def check_environment():
    """Check environment variables crucial for headless operation"""
    print("\n=== Environment Variables ===")
    
    critical_vars = {
        "QT_QPA_PLATFORM": "offscreen",
        "DISPLAY": ":99"
    }
    
    optional_vars = {
        "WKHTMLTOPDF_PATH": "/usr/bin/wkhtmltopdf",
        "FONTCONFIG_PATH": "/etc/fonts",
        "QT_QPA_FONTDIR": "/usr/share/fonts"
    }
    
    all_good = True
    
    print("Critical variables for headless operation:")
    for var, recommended in critical_vars.items():
        value = os.environ.get(var)
        if value:
            if value == recommended:
                print(f"✓ {var}={value}")
            else:
                print(f"⚠ {var}={value} (recommended: {recommended})")
        else:
            print(f"✗ {var} not set (should be: {recommended})")
            all_good = False
    
    print("\nOptional variables:")
    for var, recommended in optional_vars.items():
        value = os.environ.get(var)
        if value:
            print(f"✓ {var}={value}")
        else:
            print(f"- {var} not set (optional: {recommended})")
    
    return all_good

def test_footer_rendering():
    """Test footer rendering specifically"""
    print("\n=== Footer Rendering Test ===")
    
    # Create test HTML
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body { 
                font-family: Arial, sans-serif; 
                font-size: 12pt; 
                margin: 0;
                padding: 20px;
            }
            .page { page-break-after: always; }
        </style>
    </head>
    <body>
        <div class="page">
            <h1>Page 1</h1>
            <p>This is the first page of the test document.</p>
            <p>The footer should appear at the bottom with company info and page numbers.</p>
        </div>
        <div class="page">
            <h1>Page 2</h1>
            <p>This is the second page of the test document.</p>
            <p>The footer should show "2 / 2" for page numbers.</p>
        </div>
        <div>
            <h1>Page 3</h1>
            <p>This is the third and final page.</p>
            <p>The footer should show "3 / 3" for page numbers.</p>
        </div>
    </body>
    </html>
    """
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as html_file:
            html_file.write(test_html)
            html_path = html_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
            pdf_path = pdf_file.name
        
        # Test with the same options as your application
        cmd = [
            "wkhtmltopdf",
            "--page-size", "A4",
            "--margin-top", "20mm",
            "--margin-right", "20mm",
            "--margin-bottom", "25mm",
            "--margin-left", "20mm",
            "--encoding", "UTF-8",
            "--footer-center", "Erdbaron HQ SRL | Preot Bacca 15 | 55065 Hermannstadt",
            "--footer-right", "[page] / [topage]",
            "--footer-font-size", "9",
            "--footer-spacing", "10",
            "--footer-line", "",
            "--quiet",
            "--disable-smart-shrinking",
            "--enable-local-file-access",
            "--print-media-type",
            "--page-offset", "0",
            "--no-pdf-compression",
            "--minimum-font-size", "8",
            "--dpi", "300",
            "--image-dpi", "300",
            "--image-quality", "100",
            "--load-error-handling", "ignore",
            "--load-media-error-handling", "ignore",
            "--disable-javascript",
            "--no-stop-slow-scripts",
            "--debug-javascript",
            "--viewport-size", "1024x768",
            "--zoom", "1.0",
            html_path,
            pdf_path
        ]
        
        print("Running wkhtmltopdf with footer options...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            if os.path.exists(pdf_path):
                pdf_size = os.path.getsize(pdf_path)
                print(f"✓ PDF generated successfully (size: {pdf_size} bytes)")
                print(f"✓ Test PDF saved as: {pdf_path}")
                print("  Please download and check if footer appears in this test PDF")
                
                # Don't delete the test file so user can examine it
                print(f"\n📄 Test file location: {pdf_path}")
                print("   Download this file to check if footer is visible")
                
                return True
            else:
                print("✗ PDF file was not created")
        else:
            print(f"✗ wkhtmltopdf failed with return code: {result.returncode}")
            if result.stderr:
                print(f"  Error output: {result.stderr}")
            if result.stdout:
                print(f"  Standard output: {result.stdout}")
        
        # Clean up HTML file
        try:
            os.unlink(html_path)
        except:
            pass
            
    except Exception as e:
        print(f"✗ Footer test failed: {e}")
        return False
    
    return False

def check_fonts():
    """Check available fonts"""
    print("\n=== Font Check ===")
    
    try:
        # Check if fontconfig is available
        result = subprocess.run(["fc-list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            fonts = result.stdout.lower()
            
            # Check for common fonts
            font_checks = [
                ("Arial", "arial" in fonts),
                ("Liberation", "liberation" in fonts),
                ("DejaVu", "dejavu" in fonts),
                ("Noto", "noto" in fonts)
            ]
            
            for font_name, found in font_checks:
                if found:
                    print(f"✓ {font_name} fonts found")
                else:
                    print(f"- {font_name} fonts not found")
            
            # Count total fonts
            font_count = len(result.stdout.strip().split('\n'))
            print(f"Total fonts available: {font_count}")
            
        else:
            print("⚠ fontconfig (fc-list) not available")
    except:
        print("⚠ Could not check fonts")

def provide_recommendations():
    """Provide specific recommendations for fixing footer issues"""
    print("\n=== RECOMMENDATIONS ===")
    
    print("If footer is not appearing on your droplet, try these steps:")
    print()
    print("1. Set environment variables (add to your .env or systemd service):")
    print("   export QT_QPA_PLATFORM=offscreen")
    print("   export DISPLAY=:99")
    print()
    print("2. Install Qt-based wkhtmltopdf if you have the reduced version:")
    print("   wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb")
    print("   sudo dpkg -i wkhtmltox_0.12.6-1.focal_amd64.deb")
    print("   sudo apt-get install -f  # Fix any dependency issues")
    print()
    print("3. Install required fonts:")
    print("   sudo apt-get install fonts-liberation fonts-dejavu-core fontconfig")
    print("   sudo fc-cache -fv")
    print()
    print("4. If using systemd service, add environment variables to your service file:")
    print("   Environment=QT_QPA_PLATFORM=offscreen")
    print("   Environment=DISPLAY=:99")
    print()
    print("5. If using Docker, add to your Dockerfile:")
    print("   ENV QT_QPA_PLATFORM=offscreen")
    print("   ENV DISPLAY=:99")
    print()
    print("6. Restart your application after making changes")

def main():
    """Run all diagnostic checks"""
    print("🔍 Droplet PDF Footer Diagnostic")
    print("=" * 50)
    print(f"Platform: {platform.platform()}")
    print(f"Python: {sys.version}")
    print()
    
    # Run all checks
    wkhtmltopdf_ok = check_wkhtmltopdf_version()
    env_ok = check_environment()
    check_fonts()
    
    if wkhtmltopdf_ok:
        footer_test_ok = test_footer_rendering()
    else:
        footer_test_ok = False
    
    print("\n" + "=" * 50)
    print("DIAGNOSTIC SUMMARY:")
    print(f"wkhtmltopdf: {'✓' if wkhtmltopdf_ok else '✗'}")
    print(f"Environment: {'✓' if env_ok else '✗'}")
    print(f"Footer test: {'✓' if footer_test_ok else '✗'}")
    
    if not env_ok or not footer_test_ok:
        provide_recommendations()
    else:
        print("\n✅ All checks passed! Footer should be working.")

if __name__ == "__main__":
    main() 