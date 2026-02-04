"""
Test script for the update checker
Run this to test if update checking works
"""
from update_checker import UpdateChecker

def main():
    print("=" * 60)
    print("GGUF Loader - Update Checker Test")
    print("=" * 60)
    
    checker = UpdateChecker()
    print(f"\nCurrent version: {checker.current_version}")
    print(f"Checking for updates from: {checker.GITHUB_API_URL}")
    print("\nPlease wait...")
    
    update_info = checker.check_for_updates()
    
    if update_info is None:
        print("\n❌ Failed to check for updates (network error or API issue)")
        return
    
    print("\n" + "=" * 60)
    if update_info.get('available'):
        print("✅ UPDATE AVAILABLE!")
        print("=" * 60)
        print(f"Current version:  {update_info['current_version']}")
        print(f"Latest version:   {update_info['latest_version']}")
        print(f"Download URL:     {update_info['download_url']}")
        print(f"Release page:     {update_info['release_url']}")
        print("\nRelease Notes:")
        print("-" * 60)
        notes = update_info.get('release_notes', 'No notes available')
        # Truncate if too long
        if len(notes) > 500:
            notes = notes[:500] + "..."
        print(notes)
    else:
        print("✅ YOU'RE UP TO DATE!")
        print("=" * 60)
        print(f"Current version: {update_info['current_version']}")
        print(f"Latest version:  {update_info['latest_version']}")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
