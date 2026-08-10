# Feedback System Setup

This guide explains how to set up the feedback system for GGUF Loader.

## Overview

The feedback system allows users to send feedback, bug reports, and feature requests directly from the application. It uses FormSpree (free service) to forward feedback to your email.

## User Experience

Users simply:
1. Click "📧 Send Feedback" button
2. Fill in the form (type, email, message)
3. Click "Send"
4. You receive it in your email inbox!

No configuration needed on the user's end.

## Setup (5 Minutes)

### Step 1: Create FormSpree Account

1. Go to [https://formspree.io/](https://formspree.io/)
2. Sign up (it's free!)
3. Verify your email address

### Step 2: Create a Form

1. Click "New Form" in your dashboard
2. Name it: "GGUF Loader Feedback"
3. Enter your email (where you want to receive feedback)
4. Click "Create Form"

### Step 3: Get Your Form ID

After creating the form, you'll see a URL like:
```
https://formspree.io/f/xyzabc123
```

Copy the part after `/f/` - that's your Form ID (e.g., `xyzabc123`)

### Step 4: Update Configuration

Edit `feedback_config.json` in the root directory:

```json
{
  "endpoint_url": "https://formspree.io/f/YOUR_FORM_ID_HERE"
}
```

Replace `YOUR_FORM_ID_HERE` with your actual Form ID.

### Step 5: Test It

Run the test script:
```bash
python test_feedback_simple.py
```

Or test manually:
1. Run your application
2. Click "📧 Send Feedback"
3. Fill in the form
4. Click "Send Feedback"
5. Check your email inbox!

## How It Works

```
User fills form → App sends to FormSpree → FormSpree emails you
```

### Data Flow

1. User clicks "Send Feedback" button
2. Dialog opens with form fields
3. User fills in feedback type, email, and message
4. App validates the form
5. App sends HTTP POST to FormSpree
6. FormSpree forwards the feedback to your email
7. You receive the feedback in your inbox

### What Gets Sent

```json
{
  "email": "user@example.com",
  "subject": "[GGUF Loader Feedback] Bug Report",
  "message": "The app crashes when I...",
  "feedback_type": "Bug Report"
}
```

## FormSpree Free Tier

✅ 50 submissions per month
✅ Email notifications
✅ Spam filtering
✅ SSL encryption
✅ No credit card required

Need more? Upgrade to paid plan (~$10/month) for unlimited submissions.

## Customization

### Add More Feedback Types

Edit `widgets/feedback_dialog.py`:

```python
self.type_combo.addItems([
    "Bug Report",
    "Feature Request",
    "General Feedback",
    "Question",
    "Your New Type"  # Add here
])
```

### Change Email Subject Format

Edit `widgets/feedback_dialog.py`:

```python
subject = f"[GGUF Loader] {feedback_type}"  # Customize this
```

### Add Auto-Response

In your FormSpree dashboard:
1. Go to Form Settings
2. Enable "Autoresponder"
3. Customize the message users receive

## Troubleshooting

### "Failed to send feedback"

**Causes:**
- No internet connection
- Wrong Form ID in config
- FormSpree service down

**Solutions:**
- Check internet connection
- Verify Form ID in `feedback_config.json`
- Check FormSpree status page

### Not receiving emails

**Causes:**
- Email in spam folder
- Wrong email in FormSpree settings
- FormSpree not configured correctly

**Solutions:**
- Check spam/junk folder
- Verify email in FormSpree dashboard
- Check FormSpree submission log

### "Invalid email" error

This is correct behavior - the user needs to enter a valid email address.

## Monitoring Feedback

### FormSpree Dashboard

View all submissions:
1. Log into FormSpree
2. Click on your form
3. See all submissions with timestamps
4. Export to CSV if needed

### Integration Options

FormSpree can integrate with:
- Slack (get notifications in Slack)
- Discord (get notifications in Discord)
- Webhooks (send to your own server)
- Zapier (automate workflows)

## Security & Privacy

✅ HTTPS/SSL encryption
✅ GDPR compliant
✅ Spam protection included
✅ No user data stored in app
✅ Users control what they share

## Alternative Services

### EmailJS
- Free tier: 200 emails/month
- Website: [https://www.emailjs.com/](https://www.emailjs.com/)

### Netlify Forms
- Free tier: 100 submissions/month
- Requires Netlify site

### Custom Backend
For advanced users, you can create your own backend:

```python
# backend.py
from flask import Flask, request, jsonify
import smtplib

app = Flask(__name__)

@app.route('/api/feedback', methods=['POST'])
def receive_feedback():
    data = request.json
    # Send email using your SMTP
    # ... your code here ...
    return jsonify({'success': True})
```

Then update `feedback_config.json`:
```json
{
  "endpoint_url": "http://localhost:5000/api/feedback"
}
```

## Files

### Core Files
- `widgets/feedback_dialog.py` - Feedback dialog UI
- `feedback_config.json` - Configuration (your Form ID)
- `test_feedback_simple.py` - Test script

### Configuration
- `feedback_config.json` - Active config (gitignored)

## Best Practices

### For Users
- Provide clear, detailed feedback
- Include steps to reproduce bugs
- Be respectful and constructive

### For Developers
- Respond to feedback promptly
- Thank users for their input
- Keep FormSpree dashboard organized
- Monitor submission trends

## Getting Help

- FormSpree Help: [https://help.formspree.io/](https://help.formspree.io/)
- GitHub Issues: [Report problems](https://github.com/GGUFloader/gguf-loader/issues)
- Email: hossainnazary475@gmail.com
