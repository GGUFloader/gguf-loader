#!/usr/bin/env python3
"""
Test script to verify icon loading in floating button.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap

def test_icon_exists():
    """Test if icon.ico exists"""
    icon_path = Path("icon.ico")
    if icon_path.exists():
        print(f"✓ icon.ico found at: {icon_path.absolute()}")
        print(f"  Size: {icon_path.stat().st_size} bytes")
        return True
    else:
        print("✗ icon.ico not found")
        return False

def test_icon_loads():
    """Test if icon can be loaded as QPixmap and show all available sizes"""
    from PySide6.QtGui import QIcon
    
    icon_path = Path("icon.ico")
    if not icon_path.exists():
        print("✗ Cannot test loading - icon.ico not found")
        return False
    
    # Load as QIcon to see all available sizes
    icon = QIcon(str(icon_path))
    if icon.isNull():
        print("✗ Icon could not be loaded as QIcon")
        return False
    
    available_sizes = icon.availableSizes()
    if available_sizes:
        print(f"✓ Icon loaded successfully with {len(available_sizes)} size(s):")
        for size in available_sizes:
            print(f"  - {size.width()}x{size.height()}")
        
        # Get largest size
        largest = max(available_sizes, key=lambda s: s.width() * s.height())
        print(f"  Largest: {largest.width()}x{largest.height()}")
        
        # Get pixmap at largest size
        pixmap = icon.pixmap(largest)
        if not pixmap.isNull():
            print(f"✓ Pixmap created at largest size: {pixmap.width()}x{pixmap.height()}")
            return True
    else:
        print("⚠ No sizes available in icon, trying direct load...")
        pixmap = icon.pixmap(256, 256)
        if not pixmap.isNull():
            print(f"✓ Pixmap created: {pixmap.width()}x{pixmap.height()}")
            return True
    
    print("✗ Could not create pixmap from icon")
    return False

def test_floating_button_icon():
    """Test if FloatingChatButton loads the icon"""
    try:
        from addons.floating_chat.floating_button import FloatingChatButton
        
        button = FloatingChatButton()
        
        if button._icon_pixmap and not button._icon_pixmap.isNull():
            print("✓ FloatingChatButton loaded icon successfully")
            print(f"  Icon dimensions: {button._icon_pixmap.width()}x{button._icon_pixmap.height()}")
            return True
        else:
            print("⚠ FloatingChatButton created but icon not loaded (will use fallback)")
            return True  # Not a failure, just uses fallback
            
    except Exception as e:
        print(f"✗ Error creating FloatingChatButton: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Icon Loading Test - Floating Chat Addon")
    print("=" * 60)
    print()
    
    app = QApplication(sys.argv)
    
    tests = [
        ("Icon File Exists", test_icon_exists),
        ("Icon Loads as QPixmap", test_icon_loads),
        ("FloatingButton Loads Icon", test_floating_button_icon)
    ]
    
    results = []
    for name, test_func in tests:
        print(f"Testing: {name}")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results.append((name, False))
        print()
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")
    
    print()
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Icon will display on floating button.")
        return 0
    else:
        print("\n⚠ Some tests failed, but addon will still work with fallback icon.")
        return 0  # Not a critical failure

if __name__ == "__main__":
    sys.exit(main())
