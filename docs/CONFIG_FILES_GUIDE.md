# Configuration Files Guide (Historical)

> **📜 Historical document** — describes configuration files from the PySide6-era build.
> The current build (v2.3.0) uses `ggufloader/config.py` and
> `ggufloader/config/model_families.json` for configuration. The `mixins/` and
> `feedback_config.json` files below are no longer used.

## 📋 JSON Files in Root Directory

### ✅ Files You NEED

#### 1. `feedback_config.json` (Required - User Config)
**Purpose:** Stores your FormSpree endpoint for the feedback system
**Used by:** `mixins/utils_mixin.py`
**Status:** Gitignored (private)

```json
{
  "endpoint_url": "https://formspree.io/f/YOUR_FORM_ID"
}
```

**Action:** Keep this file, update with your FormSpree ID

---

### 📝 Files You SHOULD KEEP (Examples)

#### 2. `feedback_config.example.json` (Template)
**Purpose:** Example template for users to copy
**Status:** Committed to git (public)

```json
{
  "endpoint_url": "https://formspree.io/f/YOUR_FORM_ID",
  "description": "Replace YOUR_FORM_ID with your actual FormSpree form ID"
}
```

**Action:** Keep as template for users

---

### ❌ Files You DON'T NEED (Unused)

#### 3. `email_config.json` (NOT USED)
**Purpose:** Old email configuration (replaced by feedback_config.json)
**Used by:** Nothing (no references in code)
**Status:** Gitignored

**Action:** DELETE - Not used anywhere

#### 4. `email_config.example.json` (NOT USED)
**Purpose:** Example for old email system
**Used by:** Nothing
**Status:** Committed to git

**Action:** DELETE - Old system, not needed

#### 5. `email_config.smtp.example.json` (NOT USED)
**Purpose:** SMTP example for old email system
**Used by:** Nothing
**Status:** Committed to git

**Action:** DELETE - Old system, not needed

#### 6. `metadata.json` (NOT USED)
**Purpose:** Project metadata (unclear purpose)
**Used by:** Nothing (no references in code)
**Status:** Committed to git

**Action:** DELETE or MOVE to docs/ if needed for website

---

## 🎯 Recommended Actions

### Delete These Files:
```bash
# Old email system (replaced by FormSpree)
email_config.json
email_config.example.json
email_config.smtp.example.json

# Unused metadata
metadata.json
```

### Keep These Files:
```bash
# Active configuration
feedback_config.json (your private config)

# Template for users
feedback_config.example.json (example template)
```

---

## 📁 Proposed Clean Structure

### Root Directory (After Cleanup)
```
Root:
├── feedback_config.json          # Your config (gitignored)
└── feedback_config.example.json  # Template (committed)
```

### Alternative: Move to config/ folder
```
config/
├── feedback_config.json          # Your config (gitignored)
└── feedback_config.example.json  # Template (committed)
```

---

## 🔧 If You Delete email_config Files

The old email system is not used. The feedback system now uses:
- **FormSpree** (via `feedback_config.json`)
- No SMTP configuration needed
- No email client configuration needed

---

## 📊 Summary

| File | Status | Action |
|------|--------|--------|
| `feedback_config.json` | ✅ Used | Keep (update with your FormSpree ID) |
| `feedback_config.example.json` | ✅ Template | Keep (for users) |
| `email_config.json` | ❌ Unused | Delete |
| `email_config.example.json` | ❌ Unused | Delete |
| `email_config.smtp.example.json` | ❌ Unused | Delete |
| `metadata.json` | ❌ Unused | Delete or move to docs/ |

---

## 🚀 Quick Cleanup Commands

### Windows (PowerShell)
```powershell
# Delete unused files
Remove-Item email_config.json
Remove-Item email_config.example.json
Remove-Item email_config.smtp.example.json
Remove-Item metadata.json
```

### Linux/macOS
```bash
# Delete unused files
rm email_config.json
rm email_config.example.json
rm email_config.smtp.example.json
rm metadata.json
```

---

## ✅ After Cleanup

You'll have a clean root directory with only:
- `feedback_config.json` - Your active config
- `feedback_config.example.json` - Template for users

Much cleaner and less confusing!
