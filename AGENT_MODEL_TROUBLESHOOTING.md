# Agent Model Detection Troubleshooting Guide

If the agentic chatbot addon shows "Model: Not loaded" even after loading a model, follow these steps:

## Quick Fix Steps

1. **Load Model First**: Make sure you load a model in the main GGUF Loader window first
   - Click "Load Model" in the main window
   - Wait for the model to fully load (you should see "Model ready!" message)

2. **Refresh Agent Status**: In the agent window, click the refresh button (🔄) next to the model status

3. **Check Console Output**: Look at the console/terminal for debug messages that show what's happening

## Detailed Troubleshooting

### Step 1: Verify Model is Loaded in Main Window
- The main window should show "✅ Loaded: [model_name]" 
- The status should say "Model ready! Start chatting..."
- You should be able to send messages in the main chat

### Step 2: Check Agent Window Status
- Model status should show "🟢 Model: Ready"
- If it shows "🔴 Model: Not loaded", proceed to next steps

### Step 3: Manual Refresh
- Click the refresh button (🔄) in the agent window
- This will force a model detection check
- Watch the console for debug messages

### Step 4: Check Debug Output
Look for these debug messages in the console:

**Good signs:**
```
DEBUG:addons.agentic_chatbot.agent_window:Real Llama model detected
DEBUG:addons.agentic_chatbot.agent_window:Model status updated: Ready
```

**Problem indicators:**
```
DEBUG:addons.agentic_chatbot.agent_window:Model is None
DEBUG:addons.agentic_chatbot.agent_window:No addon available
DEBUG:addons.agentic_chatbot.agent_window:gguf_app has no model attribute
```

### Step 5: Restart if Needed
If the above steps don't work:
1. Close the agent window
2. Stop the agent addon (if running)
3. Restart the agent addon
4. Open the agent window again

## Common Issues and Solutions

### Issue: "No addon available"
**Solution**: Make sure the agentic chatbot addon is properly started before opening the agent window.

### Issue: "gguf_app has no model attribute"
**Solution**: This indicates a problem with the main app integration. Try restarting the entire application.

### Issue: "Model is None"
**Solution**: The model hasn't been loaded in the main window yet. Load a model first.

### Issue: Model loads but agent doesn't detect it
**Solution**: 
1. Try clicking the refresh button (🔄)
2. Check if the model_loaded signal is being emitted properly
3. Restart the agent addon

## Testing Model Detection

You can run the test script to verify model detection is working:

```bash
python test_real_model_detection.py
```

This will test both mock and real model detection scenarios.

## Advanced Debugging

If you're still having issues, you can enable more detailed logging:

1. Edit the agent window code to change logging level:
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

2. Look for these specific debug messages:
   - Model detection attempts
   - Signal connections
   - Model type identification

## Getting Help

If none of these steps work, please provide:
1. Console output with debug messages
2. Steps you followed to load the model
3. Whether the main chat window works correctly
4. Any error messages you see

The model detection has been improved to handle both real Llama models and various edge cases, so following these steps should resolve most issues.