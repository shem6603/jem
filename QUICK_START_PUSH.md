# Quick Start: Fix "VAPID Key: Not configured"

## Step 1: Generate VAPID Keys

Run this command in your project directory:

```bash
python generate_vapid_keys.py
```

**If you get an error about missing `cryptography`:**
```bash
pip install cryptography
python generate_vapid_keys.py
```

## Step 2: Add Keys to .env File

The script will output something like:
```
VAPID_PRIVATE_KEY=abc123...
VAPID_PUBLIC_KEY=xyz789...
```

**Copy these lines** and add them to your `.env` file in the project root:

```env
VAPID_PRIVATE_KEY=your-private-key-here
VAPID_PUBLIC_KEY=your-public-key-here
```

## Step 3: Update Email in settings.py

Open `config/settings.py` and find:
```python
VAPID_CLAIMS = {
    "sub": "mailto:your-email@example.com"  # Change this!
}
```

**Change the email** to your actual email address:
```python
VAPID_CLAIMS = {
    "sub": "mailto:youremail@gmail.com"  # Your real email
}
```

## Step 4: Restart Django Server

**Stop your server** (Ctrl+C) and **restart it**:
```bash
python manage.py runserver
```

## Step 5: Test Again

1. Go to `/admin/test-push/`
2. Refresh the page
3. The "VAPID Key" status should now show **"Configured"** (green)
4. Click "Subscribe to Push Notifications"
5. Grant permission when prompted
6. Send a test notification!

## Troubleshooting

### Still shows "Not configured"?
- Make sure `.env` file is in the project root (same folder as `manage.py`)
- Make sure you restarted the server after adding keys
- Check that the keys don't have extra spaces or quotes in `.env`
- Verify `.env` file is being loaded (check other env vars work)

### Can't install cryptography?
Try:
```bash
pip install --upgrade pip
pip install cryptography
```

Or use Node.js method:
```bash
npm install -g web-push
web-push generate-vapid-keys
```

### Keys look wrong?
Make sure:
- No quotes around the keys in `.env`
- No spaces before/after the `=` sign
- Keys are on separate lines
- File is saved as `.env` (not `.env.txt`)
