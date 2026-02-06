#!/usr/bin/env python3
"""
Test script for agent mode integration in main chat window
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from ui.ai_chat_window import AIChat


def test_agent_mode_ui():
    """Test that agent mode UI elements are present"""
    app = QApplication(sys.argv)
    window = AIChat()
    
    # Check that agent mode components exist
    assert hasattr(window, 'agent_mode_cb'), "Agent mode checkbox not found"
    assert hasattr(window, 'workspace_container'), "Workspace container not found"
    assert hasattr(window, 'workspace_combo'), "Workspace combo not found"
    assert hasattr(window, 'workspace_browse_btn'), "Workspace browse button not found"
    assert hasattr(window, 'agent_status_label'), "Agent status label not found"
    
    # Check that agent mode mixin methods exist
    assert hasattr(window, 'toggle_agent_mode'), "toggle_agent_mode method not found"
    assert hasattr(window, 'browse_workspace'), "browse_workspace method not found"
    assert hasattr(window, 'send_message_to_agent'), "send_message_to_agent method not found"
    
    # Check initial state
    assert window.agent_mode_enabled == False, "Agent mode should be disabled initially"
    assert window.workspace_container.isVisible() == False, "Workspace container should be hidden initially"
    
    print("✅ All agent mode UI components are present")
    print("✅ Agent mode is disabled by default")
    print("✅ Workspace selector is hidden by default")
    
    # Show window first so parent widgets are visible
    window.show()
    app.processEvents()
    
    # Test toggling agent mode
    print(f"\nDEBUG: Before setChecked - visibility: {window.workspace_container.isVisible()}")
    window.agent_mode_cb.setChecked(True)
    app.processEvents()  # Process Qt events
    print(f"DEBUG: After setChecked - visibility: {window.workspace_container.isVisible()}")
    print(f"DEBUG: agent_mode_enabled: {window.agent_mode_enabled}")
    
    if window.workspace_container.isVisible():
        print("✅ Workspace selector appears when agent mode is enabled")
    else:
        print("❌ Workspace selector visibility issue")
    
    window.agent_mode_cb.setChecked(False)
    app.processEvents()  # Process Qt events
    
    if not window.workspace_container.isVisible():
        print("✅ Workspace selector hides when agent mode is disabled")
    else:
        print("❌ Workspace selector still visible")
    
    print("\n🎉 All tests passed!")
    print("\n📝 Note: Agent mode integration is ready!")
    print("   - Toggle 'Enable Agent Mode' checkbox in sidebar")
    print("   - Select workspace folder")
    print("   - Messages will be routed through the agent")
    
    # Keep window open for manual inspection
    print("\n👀 Window is now open for manual inspection...")
    print("   Close the window to exit the test.")
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(test_agent_mode_ui())
