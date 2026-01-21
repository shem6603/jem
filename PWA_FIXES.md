# PWA Manifest Fixes Applied

## Issues Fixed

Based on PWABuilder audit results, the following fixes have been applied:

### Remaining Warnings (Info Level)
- **Categories**: django-pwa doesn't support manifest categories - this is a minor enhancement suggestion
- **Screenshots**: Placeholder screenshots added - replace with actual app screenshots for best results

### 1. ✅ Icon Links in Manifest
- **Issue**: Icon paths may not resolve correctly
- **Fix**: Using absolute paths starting with `/static/` which resolve correctly
- **Location**: `config/settings.py` → `PWA_APP_ICONS`

### 2. ✅ Icon Types in Manifest
- **Issue**: Icon purpose types may be incorrect
- **Fix**: Added both `'any'` and `'maskable'` purpose types for better compatibility
- **Location**: `config/settings.py` → `PWA_APP_ICONS`

### 3. ✅ Service Worker Registration
- **Issue**: Service worker not properly registered
- **Fix**: 
  - Updated service worker registration to use root-level path `/serviceworker.js` (provided by django-pwa)
  - Service worker file remains at `static/js/serviceworker.js` but is served at root via django-pwa
- **Location**: `templates/base.html` → Service Worker Registration script

### 4. ✅ Icon Sizes
- **Issue**: Icon sizes may not match manifest
- **Fix**: Verified icons are exactly 192x192px and 512x512px
- **Files**: 
  - `static/favicons/icon-192.png` (192x192px)
  - `static/favicons/icon-512.png` (512x512px)

## Current Configuration

### Icons Configuration
```python
PWA_APP_ICONS = [
    {
        'src': '/static/favicons/icon-192.png',
        'sizes': '192x192',
        'type': 'image/png',
        'purpose': 'any'
    },
    {
        'src': '/static/favicons/icon-512.png',
        'sizes': '512x512',
        'type': 'image/png',
        'purpose': 'any'
    },
    {
        'src': '/static/favicons/icon-192.png',
        'sizes': '192x192',
        'type': 'image/png',
        'purpose': 'maskable'
    },
    {
        'src': '/static/favicons/icon-512.png',
        'sizes': '512x512',
        'type': 'image/png',
        'purpose': 'maskable'
    }
]
```

### Service Worker
- **Source File**: `static/js/serviceworker.js`
- **Served At**: `/serviceworker.js` (via django-pwa)
- **Registration**: Automatic in `base.html`

## Testing After Deployment

1. **Check Manifest**: Visit `https://jem.rixsoft.org/manifest.json`
   - Verify icon paths are correct
   - Verify icon types are correct
   - Verify sizes match

2. **Check Service Worker**: 
   - Open Chrome DevTools → Application → Service Workers
   - Should see service worker registered at `/serviceworker.js`
   - Status should be "activated and running"

3. **Check Icons**:
   - Visit `https://jem.rixsoft.org/static/favicons/icon-192.png`
   - Visit `https://jem.rixsoft.org/static/favicons/icon-512.png`
   - Both should load correctly

4. **PWABuilder Test**:
   - Visit https://www.pwabuilder.com/
   - Enter `https://jem.rixsoft.org`
   - Should see reduced errors/warnings

## Deployment Checklist

- [ ] Upload updated `config/settings.py`
- [ ] Upload updated `templates/base.html`
- [ ] Upload updated `static/js/serviceworker.js`
- [ ] Run `python manage.py collectstatic` on server
- [ ] Verify icons are accessible at `/static/favicons/icon-*.png`
- [ ] Verify manifest at `/manifest.json`
- [ ] Verify service worker at `/serviceworker.js`
- [ ] Test in PWABuilder again

## Screenshots (Required for App Stores)

You need to create actual screenshots of your app:

### How to Create Screenshots

1. **Wide Screenshot (1280x720px)**:
   - Open your website on desktop
   - Take a screenshot of the home page
   - Resize/crop to 1280x720px
   - Save as `static/screenshots/screenshot-wide.png`

2. **Mobile Screenshot (540x720px)**:
   - Open your website on mobile (or use browser DevTools mobile view)
   - Take a screenshot
   - Resize/crop to 540x720px
   - Save as `static/screenshots/screenshot-mobile.png`

### Screenshot Tips
- Show your app's best features
- Use clean, clear images
- For app store submission, you may need additional sizes

## Notes

- django-pwa automatically serves `/manifest.json` and `/serviceworker.js` at root level
- Icon files must be accessible via static files (collected with `collectstatic`)
- All paths use absolute URLs starting with `/` for proper resolution
- Service worker scope is automatically set to `/` by django-pwa
- Categories are not supported by django-pwa (minor warning, doesn't affect functionality)
