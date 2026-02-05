#!/usr/bin/env python3
"""
Diagnose Real App - Check what attributes and signals are actually available
"""

import sys
import os
import logging

# Add current directory to path for imports
sys.path.insert(0, '.')

def diagnose_real_app():
    """Diagnose the real AIChat app to see what's available."""
    print("=== Diagnosing Real AIChat App ===")
    
    try:
        from PySide6.QtWidgets import QApplication
        from ui.ai_chat_window import AIChat
        from addons.agentic_chatbot.main import AgenticChatbotAddon
        
        # Create QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("1. Creating real AIChat app...")
        
        # Create real AIChat app
        real_app = AIChat()
        
        print("   ✓ AIChat app created")
        
        print("2. Inspecting AIChat app attributes...")
        
        # Check for model attribute
        print(f"   - Has 'model' attribute: {hasattr(real_app, 'model')}")
        if hasattr(real_app, 'model'):
            print(f"   - Model value: {real_app.model}")
            print(f"   - Model type: {type(real_app.model)}")
        
        # Check for signals
        signals_to_check = ['model_loaded', 'generation_finished', 'generation_error']
        for signal_name in signals_to_check:
            has_signal = hasattr(real_app, signal_name)
            print(f"   - Has '{signal_name}' signal: {has_signal}")
            if has_signal:
                signal_obj = getattr(real_app, signal_name)
                print(f"     - Signal type: {type(signal_obj)}")
        
        print("3. Creating addon with real app...")
        
        # Create addon
        addon = AgenticChatbotAddon(real_app)
        
        print("   ✓ Addon created")
        
        print("4. Inspecting addon's gguf_app reference...")
        
        # Check addon's gguf_app
        print(f"   - Addon has 'gguf_app' attribute: {hasattr(addon, 'gguf_app')}")
        if hasattr(addon, 'gguf_app'):
            gguf_app = addon.gguf_app
            print(f"   - gguf_app value: {gguf_app}")
            print(f"   - gguf_app type: {type(gguf_app)}")
            print(f"   - gguf_app is same as real_app: {gguf_app is real_app}")
            
            # Check gguf_app attributes
            print(f"   - gguf_app has 'model' attribute: {hasattr(gguf_app, 'model')}")
            if hasattr(gguf_app, 'model'):
                print(f"   - gguf_app.model value: {gguf_app.model}")
                print(f"   - gguf_app.model type: {type(gguf_app.model)}")
            
            # Check gguf_app signals
            for signal_name in signals_to_check:
                has_signal = hasattr(gguf_app, signal_name)
                print(f"   - gguf_app has '{signal_name}' signal: {has_signal}")
        
        print("5. Starting addon...")
        
        if addon.start():
            print("   ✓ Addon started successfully")
        else:
            print("   ❌ Addon failed to start")
            return False
        
        print("6. Testing model loading simulation...")
        
        # Simulate loading a model
        from unittest.mock import Mock
        mock_model = Mock()
        mock_model.__class__.__name__ = 'Llama'
        
        # Set model in real app
        real_app.model = mock_model
        print(f"   - Set model in real_app: {real_app.model}")
        
        # Check if addon can see the model
        if hasattr(addon, 'gguf_app') and hasattr(addon.gguf_app, 'model'):
            print(f"   - Addon can see model: {addon.gguf_app.model}")
            print(f"   - Model is same object: {addon.gguf_app.model is mock_model}")
        
        # Emit model_loaded signal
        print("   - Emitting model_loaded signal...")
        real_app.model_loaded.emit(mock_model)
        
        print("7. Testing agent window creation...")
        
        from addons.agentic_chatbot.agent_window import AgentWindow
        
        # Create agent window
        agent_window = AgentWindow(addon)
        print("   ✓ Agent window created")
        
        # Test model detection
        print("8. Testing model detection in agent window...")
        
        # Check what the agent window sees
        print(f"   - Agent window addon: {agent_window.addon}")
        print(f"   - Agent window addon.gguf_app: {getattr(agent_window.addon, 'gguf_app', 'NOT FOUND')}")
        
        if hasattr(agent_window.addon, 'gguf_app'):
            gguf_app = agent_window.addon.gguf_app
            print(f"   - gguf_app has model attr: {hasattr(gguf_app, 'model')}")
            if hasattr(gguf_app, 'model'):
                print(f"   - gguf_app.model: {gguf_app.model}")
        
        # Test model detection method
        model_detected = agent_window._is_model_loaded()
        print(f"   - Model detected by agent window: {model_detected}")
        
        # Check UI status
        status_text = agent_window.model_status_label.text()
        print(f"   - UI status text: {status_text}")
        
        # Test manual refresh
        print("9. Testing manual refresh...")
        agent_window._refresh_model_status()
        
        status_text_after = agent_window.model_status_label.text()
        print(f"   - UI status after refresh: {status_text_after}")
        
        # Final assessment
        if model_detected and "Ready" in status_text_after:
            print("\n✅ SUCCESS: Real app integration working")
            return True
        else:
            print(f"\n❌ FAILED: Real app integration not working")
            print(f"   - Model detected: {model_detected}")
            print(f"   - UI status: {status_text_after}")
            return False
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            if 'agent_window' in locals():
                agent_window.close()
            if 'addon' in locals():
                addon.stop()
            if 'real_app' in locals():
                real_app.close()
        except:
            pass

def main():
    """Run diagnosis."""
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    
    print("Starting real app diagnosis...")
    
    success = diagnose_real_app()
    
    print(f"\n{'='*50}")
    if success:
        print("✅ Diagnosis completed successfully")
    else:
        print("❌ Diagnosis found issues")
    print('='*50)
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)