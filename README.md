# Django Web Application

A Django web application built with Python 3.11.13.

## Features

- Django 4.2+ framework
- Python 3.11.13
- SQLite database (default)
- Environment variable support
- Modern, responsive UI
- Admin panel

## Prerequisites

- Python 3.11+ (3.11.13 recommended, but 3.11+ compatible)
- pip (Python package manager)

## Setup Instructions

### 1. Create a Virtual Environment

```bash
# On Windows
python -m venv venv

# Activate the virtual environment
# On Windows (PowerShell)
venv\Scripts\Activate.ps1

# On Windows (Command Prompt)
venv\Scripts\activate.bat
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Create a `.env` file in the root directory:

**For Local Development (SQLite):**
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

**For Production/GoDaddy (MySQL):**
```env
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=jem.rixsoft.org,www.jem.rixsoft.org
DB_NAME=jem_customer
DB_USER=jem_auto
DB_PASSWORD=your-database-password
DB_HOST=localhost
DB_PORT=3306
```

**Important:** 
- Generate a secure secret key:
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
- For local development, you can use SQLite (no DB credentials needed)
- For GoDaddy, you must provide MySQL database credentials

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Create a Superuser (Optional)

```bash
python manage.py createsuperuser
```

This will allow you to access the admin panel at `/admin/`.

### 6. Run the Development Server

```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

## Project Structure

```
jem/
├── config/              # Project configuration
│   ├── settings.py      # Django settings
│   ├── urls.py          # Main URL configuration
│   ├── wsgi.py          # WSGI configuration
│   └── asgi.py          # ASGI configuration
├── core/                # Main application
│   ├── views.py         # View functions
│   ├── urls.py          # App URL configuration
│   ├── models.py        # Database models
│   └── admin.py         # Admin configuration
├── templates/           # HTML templates
├── static/              # Static files (CSS, JS, images)
├── media/               # User uploaded files
├── manage.py            # Django management script
├── passenger_wsgi.py    # GoDaddy Passenger WSGI entry point
├── .htaccess            # Apache configuration for GoDaddy
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Available URLs

- `/` - Home page
- `/about/` - About page
- `/admin/` - Admin panel (requires superuser)

## Development

### Running Tests

```bash
python manage.py test
```

### Creating a New App

```bash
python manage.py startapp appname
```

### Making Migrations

After creating or modifying models:

```bash
python manage.py makemigrations
python manage.py migrate
```

## GoDaddy Deployment (Python 3.11.13)

This project is configured for deployment on GoDaddy shared hosting with Python 3.11.13.

### Prerequisites

- GoDaddy hosting account with cPanel access
- "Setup Python App" or "Application Manager" enabled in cPanel
- Python 3.11.13 available in Python Selector

### Deployment Steps

#### 1. Upload Project Files

Upload all project files to your GoDaddy hosting account via FTP or cPanel File Manager. The project should be in a directory like `/home/username/jem.rixsoft.org/` or similar.

#### 2. Create Python Application in cPanel

1. Log into your GoDaddy cPanel
2. Navigate to **Setup Python App** or **Application Manager** (under Software section)
3. Click **Create Application**
4. Configure:
   - **Python Version**: Select **3.11.13** (or closest available 3.11.x)
   - **Application Root**: `/home/username/yourdomain.com` (your project directory)
   - **Application URL**: Your domain or subdomain
   - **Application Startup File**: `passenger_wsgi.py`
   - **Application Entry Point**: `application`
5. Click **Create**

#### 3. Install Dependencies

In cPanel Terminal or via SSH:

```bash
# Activate the virtual environment (created by cPanel)
source /home/username/virtualenv/jem.rixsoft.org/3.11/bin/activate

# Navigate to project directory
cd /home/username/jem.rixsoft.org

# Install dependencies
pip install -r requirements.txt
```

Alternatively, in cPanel's "Setup Python App":
- Go to your application's configuration
- In "Configuration files" section, add `requirements.txt`
- Click **Run Pip Install**

#### 4. Configure Database Connection

**Get Database Credentials from GoDaddy:**

1. In cPanel, go to **MySQL Databases** or **phpMyAdmin**
2. Find your database: `jem_customer`
3. Note the database user: `jem_auto`
4. Get the database password (if you don't know it, you may need to reset it in cPanel)
5. The database host is typically `localhost` on GoDaddy

**Set Environment Variables in cPanel:**

In cPanel "Setup Python App" > Environment Variables, add:

```
SECRET_KEY=your-generated-secret-key-here
DEBUG=False
ALLOWED_HOSTS=jem.rixsoft.org,www.jem.rixsoft.org
DB_NAME=jem_customer
DB_USER=jem_auto
DB_PASSWORD=your-database-password-here
DB_HOST=localhost
DB_PORT=3306
```

**Important**: 
- Generate a secure secret key:
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
- Keep your database password secure and never commit it to version control

#### 5. Run Database Migrations

In Terminal or SSH:

```bash
source /home/username/virtualenv/yourdomain.com/3.11/bin/activate
cd /home/username/yourdomain.com
python manage.py migrate
```

#### 6. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

#### 7. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

#### 8. Restart Application

In cPanel "Setup Python App", click **Restart Application**.

### Important Files for GoDaddy

- `passenger_wsgi.py` - Entry point for GoDaddy's Passenger server
- `.htaccess` - Apache configuration for static files and routing
- `requirements.txt` - Python dependencies (includes WhiteNoise for static files)
- `.env` - Environment variables (set via cPanel Environment Variables instead)

### Troubleshooting

**Issue**: ModuleNotFoundError or import errors
- **Solution**: Verify `passenger_wsgi.py` has correct project name (`config`)

**Issue**: Static files not loading
- **Solution**: Run `python manage.py collectstatic --noinput` and ensure WhiteNoise is in middleware

**Issue**: 500 Internal Server Error
- **Solution**: Check cPanel error logs, verify `ALLOWED_HOSTS` includes your domain, ensure `DEBUG=False` in production

**Issue**: Cannot find "Setup Python App"
- **Solution**: Contact GoDaddy support to enable Python support on your hosting plan

### Production Checklist

- [ ] `DEBUG=False` in environment variables
- [ ] Secure `SECRET_KEY` set
- [ ] `ALLOWED_HOSTS` includes your domain
- [ ] Static files collected (`collectstatic`)
- [ ] Database migrations applied
- [ ] Superuser created (if needed)
- [ ] Application restarted in cPanel

## General Production Deployment

For other hosting platforms:

1. Set `DEBUG=False` in your `.env` file
2. Generate a secure `SECRET_KEY`
3. Update `ALLOWED_HOSTS` with your domain
4. Set up a proper database (PostgreSQL recommended)
5. Configure static files serving
6. Set up proper security headers

## License

This project is open source and available under the MIT License.
