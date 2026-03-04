#!/usr/bin/env python3
"""
Quick installer for PDF generation support.
Detects OS and installs required dependencies.
"""

import sys
import platform
import subprocess
from pathlib import Path

def run_command(cmd, shell=False):
    """Run a command and return success status"""
    try:
        subprocess.run(cmd, check=True, shell=shell, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

def install_python_packages():
    """Install Python packages"""
    print("📦 Installing Python packages...")
    packages = ["weasyprint", "markdown"]
    
    for pkg in packages:
        print(f"  Installing {pkg}...")
        if run_command([sys.executable, "-m", "pip", "install", pkg]):
            print(f"  ✓ {pkg} installed")
        else:
            print(f"  ✗ {pkg} installation failed")
            return False
    return True

def install_macos_deps():
    """Install macOS dependencies via Homebrew"""
    print("\n🍎 macOS detected")
    print("📦 Installing system dependencies via Homebrew...")
    
    # Check if brew is installed
    if not run_command(["which", "brew"]):
        print("  ✗ Homebrew not found. Please install from https://brew.sh")
        return False
    
    deps = ["cairo", "pango", "gdk-pixbuf", "libffi"]
    for dep in deps:
        print(f"  Installing {dep}...")
        run_command(["brew", "install", dep])
    
    print("  ✓ System dependencies installed")
    return True

def install_linux_deps():
    """Install Linux dependencies via apt"""
    print("\n🐧 Linux detected")
    print("📦 Installing system dependencies via apt...")
    
    deps = [
        "build-essential", "python3-dev", "python3-pip",
        "python3-setuptools", "python3-wheel", "python3-cffi",
        "libcairo2", "libpango-1.0-0", "libpangocairo-1.0-0",
        "libgdk-pixbuf2.0-0", "libffi-dev", "shared-mime-info"
    ]
    
    cmd = ["sudo", "apt-get", "install", "-y"] + deps
    print(f"  Running: {' '.join(cmd)}")
    print("  (You may be prompted for your password)")
    
    if run_command(cmd):
        print("  ✓ System dependencies installed")
        return True
    else:
        print("  ✗ Installation failed. You may need to run manually:")
        print(f"    {' '.join(cmd)}")
        return False

def install_windows_deps():
    """Windows usually works out of the box"""
    print("\n🪟 Windows detected")
    print("  Windows typically works with pip install alone.")
    print("  If you encounter issues, install GTK3 runtime from:")
    print("  https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer")
    return True

def test_installation():
    """Test if WeasyPrint works"""
    print("\n🧪 Testing installation...")
    try:
        from weasyprint import HTML
        import markdown
        
        # Create a simple test
        md_text = "# Test\n\nThis is a test."
        html_text = markdown.markdown(md_text)
        html = HTML(string=f"<html><body>{html_text}</body></html>")
        
        # Try to render (don't save)
        html.render()
        
        print("  ✓ WeasyPrint is working!")
        return True
    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("  Contract Review Agent - PDF Support Installer")
    print("=" * 60)
    
    os_type = platform.system()
    
    # Install system dependencies based on OS
    if os_type == "Darwin":  # macOS
        if not install_macos_deps():
            print("\n⚠️  System dependency installation failed")
            print("You may need to install manually. See PDF_AND_TIMING_GUIDE.md")
    
    elif os_type == "Linux":
        if not install_linux_deps():
            print("\n⚠️  System dependency installation failed")
            print("You may need to install manually. See PDF_AND_TIMING_GUIDE.md")
    
    elif os_type == "Windows":
        install_windows_deps()
    
    else:
        print(f"\n⚠️  Unknown OS: {os_type}")
        print("Please install dependencies manually. See PDF_AND_TIMING_GUIDE.md")
    
    # Install Python packages
    print()
    if not install_python_packages():
        print("\n❌ Installation failed")
        print("Try manually: pip install weasyprint markdown")
        sys.exit(1)
    
    # Test installation
    if test_installation():
        print("\n" + "=" * 60)
        print("  ✅ PDF support installed successfully!")
        print("=" * 60)
        print("\nYou can now generate PDFs:")
        print("  python main.py rv contract.pdf --format pdf")
        print("  python main.py pdf report.md")
        print("\nSee PDF_AND_TIMING_GUIDE.md for more info.")
    else:
        print("\n" + "=" * 60)
        print("  ⚠️  Installation completed but test failed")
        print("=" * 60)
        print("\nTroubleshooting:")
        print("1. Check PDF_AND_TIMING_GUIDE.md for OS-specific instructions")
        print("2. Try: pip install --upgrade weasyprint")
        print("3. Restart your terminal/IDE")
        sys.exit(1)

if __name__ == "__main__":
    main()
