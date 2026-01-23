#!/usr/bin/env python3
"""
Verification script for Floating Chat addon installation.
Checks all components and dependencies.
"""

import sys
import os
from pathlib import Path

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} (need 3.8+)")
        return False

def check_pyside6():
    """Check PySide6 installation"""
    try:
        import PySide6
        from PySide6.QtCore import QT_VERSION_STR
        print(f"✓ PySide6 installed (Qt {QT_VERSION_STR})")
        return True
    except ImportError:
        print("✗ PySide6 not installed")
        print("  Install with: pip install PySide6")
        return False

def check_addon_files():
    """Check if all addon files exist"""
    addon_dir = Path("addons/floating_chat")
    
    required_files = [
        "__init__.py",
        "main.py",
        "floating_button.py",
        "chat_window.py",
        "status_widget.py"
    ]
    
    doc_files = [
        "README.md",
        "QUICK_START.md",
        "FEATURES.md",
        "CHANGELOG.md",
        "EXAMPLE_USAGE.md"
    ]
    
    all_good = True
    
    print("\nChecking addon files:")
    for file in required_files:
        file_path = addon_dir / file
        if file_path.exists():
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} (missing)")
            all_good = False
    
    print("\nChecking documentation:")
    for file in doc_files:
        file_path = addon_dir / file
        if file_path.exists():
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} (missing)")
    
    return all_good

def check_imports():
    """Check if addon can be imported"""
    try:
        from addons.floating_chat import main
        print("\n✓ Addon imports successfully")
        return True
    except ImportError as e:
        print(f"\n✗ Import error: {e}")
        return False

def check_classes():
    """Check if all classes are available"""
    try:
        from addons.floating_chat.main import FloatingChatAddon
        from addons.floating_chat.floating_button import FloatingChatButton
        from addons.floating_chat.chat_window import FloatingChatWindow
        from addons.floating_chat.status_widget import FloatingChatStatusWidget
        
        print("\nChecking classes:")
        print("  ✓ FloatingChatAddon")
        print("  ✓ FloatingChatButton")
        print("  ✓ FloatingChatWindow")
        print("  ✓ FloatingChatStatusWidget")
        return True
    except ImportError as e:
        print(f"\n✗ Class import error: {e}")
        return False

def check_platform():
    """Check platform compatibility"""
    platform = sys.platform
    print(f"\nPlatform: {platform}")
    
    if platform == "win32":
        print("  ✓ Windows detected")
        print("  ✓ Full feature support")
    elif platform.startswith("linux"):
        print("  ✓ Linux detected")
        print("  ℹ For best results, use X11 (not Wayland)")
        print("    Set: QT_QPA_PLATFORM=xcb")
    elif platform == "darwin":
        print("  ✓ macOS detected")
        print("  ✓ Full feature support")
    else:
        print(f"  ⚠ Unknown platform: {platform}")
        print("  ⚠ May have compatibility issues")
    
    return True

def main():
    """Run all verification checks"""
    print("=" * 60)
    print("Floating Chat Addon - Installation Verification")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("PySide6 Installation", check_pyside6),
        ("Addon Files", check_addon_files),
        ("Addon Imports", check_imports),
        ("Addon Classes", check_classes),
        ("Platform Compatibility", check_platform)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Error checking {name}: {e}")
            results.append((name, False))
        print()
    
    # Summary
    print("=" * 60)
    print("Verification Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")
    
    print()
    print(f"Result: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! Floating Chat addon is ready to use.")
        print("\nNext steps:")
        print("1. Launch GGUF Loader: python launch.py")
        print("2. Load an AI model")
        print("3. Look for the blue floating button")
        print("4. Click it to start chatting!")
        print("\nFor help, see: addons/floating_chat/QUICK_START.md")
        return 0
    else:
        print("\n⚠ Some checks failed. Please fix the issues above.")
        print("\nFor help, see: addons/floating_chat/README.md")
        return 1

if __name__ == "__main__":
    sys.exit(main())
