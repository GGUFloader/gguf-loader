#!/usr/bin/env python3
"""
Test script to check addon detection
"""
import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def test_addon_detection():
    try:
        from addon_manager import AddonManager
        
        # Create addon manager
        manager = AddonManager()
        
        # Scan for addons
        print("Scanning for addons...")
        addons = manager.scan_addons()
        print(f"Found addons: {addons}")
        
        # Try to load addons
        print("\nLoading addons...")
        results = manager.load_all_addons()
        print(f"Load results: {results}")
        
        # Check loaded addons
        loaded = manager.get_loaded_addons()
        print(f"Successfully loaded: {loaded}")
        
        return len(loaded) > 0
        
    except Exception as e:
        print(f"Error testing addons: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_addon_detection()
    print(f"\nAddon detection test: {'PASSED' if success else 'FAILED'}")