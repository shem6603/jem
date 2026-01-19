# GoDaddy Deployment Checklist

Quick reference for deploying this Django app to GoDaddy with Python 3.11.13.

## Pre-Deployment

- [x] All code committed and tested locally
- [x] `DEBUG=False` ready for production
- [x] Secure `SECRET_KEY` generated
- [x] `ALLOWED_HOSTS` includes your domain (jem.rixsoft.org)

## cPanel Setup

1. [ ] Log into GoDaddy cPanel
2. [ ] Navigate to **Setup Python App** / **Application Manager**
3. [ ] Create new application:
   - Python Version: **3.11.13** (or closest 3.11.x)
   - Application Root: Your project directory path
   - Application URL: Your domain
   - Startup File: `passenger_wsgi.py`
   - Entry Point: `application`
4. [ ] Set Environment Variables:
   ```
   SECRET_KEY=_-t1$d+1k8(=ginq(te!k049$m20r(m5f2@*(k5ykt3dj*ihe0
   DEBUG=False
   ALLOWED_HOSTS=jem.rixsoft.org,www.jem.rixsoft.org
   DB_NAME=jem_customer
   DB_USER=jem_auto
   DB_PASSWORD=your-database-password
   DB_HOST=localhost
   DB_PORT=3306
   ```
   **Note**: Get database password from GoDaddy cPanel > MySQL Databases

## File Upload

Upload these files to your GoDaddy server:
- [ ] All project files (config/, core/, templates/, etc.)
- [ ] `manage.py`
- [ ] `passenger_wsgi.py`
- [ ] `requirements.txt`
- [ ] `.htaccess`
- [ ] `.gitignore` (optional)

## Installation Commands

Run these in cPanel Terminal or SSH:

```bash
# Activate virtual environment
source /home/username/virtualenv/jem.rixsoft.org/3.11/bin/activate

# Navigate to project
cd /home/username/jem.rixsoft.org

# Install dependencies
pip install -r requirements.txt

# Run migrations (connects to MySQL database)
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser (if needed)
python manage.py createsuperuser
```

## Final Steps

- [ ] Restart application in cPanel
- [ ] Test your domain in browser
- [ ] Verify static files are loading
- [ ] Test admin panel (if created superuser)
- [ ] Check error logs if issues occur

## Common Issues

| Issue | Solution |
|-------|----------|
| 500 Error | Check error logs, verify ALLOWED_HOSTS, ensure DEBUG=False |
| Static files 404 | Run `collectstatic`, check WhiteNoise middleware |
| Module not found | Verify passenger_wsgi.py paths are correct |
| Database errors | Run migrations, check database permissions |

## Support

- GoDaddy Support: For hosting/CPanel issues
- Django Docs: https://docs.djangoproject.com/
- Project README: See README.md for detailed instructions
