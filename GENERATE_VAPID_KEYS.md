# How to Generate VAPID Keys

## Method 1: Using Python Script (Recommended)

1. **Install cryptography library** (if not already installed):
   ```bash
   pip install cryptography
   ```

2. **Run the key generator script**:
   ```bash
   python generate_vapid_keys.py
   ```

3. **Copy the output** to your `.env` file:
   ```env
   VAPID_PRIVATE_KEY=your-private-key-here
   VAPID_PUBLIC_KEY=your-public-key-here
   ```

## Method 2: Using Node.js (Alternative)

If you have Node.js installed:

1. **Install web-push globally**:
   ```bash
   npm install -g web-push
   ```

2. **Generate keys**:
   ```bash
   web-push generate-vapid-keys
   ```

3. **Copy the output** to your `.env` file

## Method 3: Using Online Tool

You can also use an online VAPID key generator:
- Visit: https://web-push-codelab.glitch.me/
- Click "Generate VAPID Keys"
- Copy the keys to your `.env` file

## After Generating Keys

1. **Add to `.env` file**:
   ```env
   VAPID_PRIVATE_KEY=your-private-key
   VAPID_PUBLIC_KEY=your-public-key
   ```

2. **Update email in `config/settings.py`**:
   ```python
   VAPID_CLAIMS = {
       "sub": "mailto:your-email@example.com"  # Change this!
   }
   ```

3. **Restart your Django server** to load the new keys

## Security Note

⚠️ **Never commit your private key to version control!**
- Keep it in `.env` file (which should be in `.gitignore`)
- Never share it publicly
- If exposed, generate new keys immediately
