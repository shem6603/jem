# Setting VAPID Keys on GoDaddy (cPanel Python App)

## Problem
cPanel Environment Variables in GoDaddy's Python App can get removed or not persist properly.

## Solution: Set Keys Directly in passenger_wsgi.py

This is the **most reliable method** for GoDaddy hosting.

### Step 1: Generate VAPID Keys

On your local machine or server:
```bash
python generate_vapid_keys.py
```

You'll get output like:
```
VAPID_PRIVATE_KEY=abc123xyz...
VAPID_PUBLIC_KEY=xyz789abc...
```

### Step 2: Edit passenger_wsgi.py

Open `passenger_wsgi.py` and find these lines (around line 18-19):
```python
os.environ.setdefault('VAPID_PRIVATE_KEY', '')
os.environ.setdefault('VAPID_PUBLIC_KEY', '')
```

Replace the empty strings with your actual keys:
```python
os.environ.setdefault('VAPID_PRIVATE_KEY', 'your-private-key-here')
os.environ.setdefault('VAPID_PUBLIC_KEY', 'your-public-key-here')
```

**Example:**
```python
os.environ.setdefault('VAPID_PRIVATE_KEY', 'ME8wDQYJKoZIhvcNAQEBBQADPAAwOQIuA...')
os.environ.setdefault('VAPID_PUBLIC_KEY', 'BEluA...')
```

### Step 3: Update Email in settings.py

In `config/settings.py`, update line 324:
```python
VAPID_CLAIMS = {
    "sub": "mailto:youremail@gmail.com"  # Your real email
}
```

### Step 4: Upload and Restart

1. Upload the modified `passenger_wsgi.py` to your server
2. In cPanel "Setup Python App", click **Restart Application**

### Step 5: Test

1. Go to `https://jem.rixsoft.org/admin/test-push/`
2. Refresh the page
3. VAPID Key should show "Configured" (green)

---

## Alternative: Use .env File (If passenger_wsgi.py doesn't work)

### Step 1: Create .env File on Server

Via cPanel File Manager or SSH, create `.env` file in your project root (same folder as `manage.py`):

```env
VAPID_PRIVATE_KEY=your-private-key-here
VAPID_PUBLIC_KEY=your-public-key-here
```

### Step 2: Set Permissions

Make sure `.env` file is readable but not publicly accessible:
- Permissions: `600` or `640`
- Owner: Your cPanel user

### Step 3: Restart Application

In cPanel "Setup Python App", click **Restart Application**

---

## Security Notes

⚠️ **Important:**
- The `passenger_wsgi.py` file will contain your private key
- Make sure it's **NOT** in your `.gitignore` exclusion (or exclude it if you use git)
- Never commit private keys to version control
- If using `.env`, make sure it's in `.gitignore`

---

## Troubleshooting

### Keys still not working?

1. **Check file encoding**: Make sure `passenger_wsgi.py` is saved as UTF-8
2. **Check for typos**: Copy keys exactly, no extra spaces
3. **Restart app**: Always restart after making changes
4. **Check logs**: Look at cPanel error logs for Python errors
5. **Test locally first**: Make sure keys work in development

### Still shows "Not configured"?

1. Verify keys are in the file (check `passenger_wsgi.py`)
2. Make sure you restarted the application
3. Clear browser cache and refresh
4. Check browser console for JavaScript errors
5. Verify the keys are valid (run `generate_vapid_keys.py` again if needed)

---

## Why This Works

Setting environment variables in `passenger_wsgi.py` is more reliable because:
- It runs before Django loads
- GoDaddy's Passenger respects these settings
- No dependency on cPanel's environment variable system
- Works consistently across restarts
