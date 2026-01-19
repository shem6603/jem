# Database Setup Guide for GoDaddy

This guide will help you connect your Django app to the MySQL database on GoDaddy.

## Database Information

From your GoDaddy cPanel:
- **Database Name**: `jem_customer`
- **Database User**: `jem_auto`
- **Database Host**: `localhost` (typical for GoDaddy)
- **Database Port**: `3306` (default MySQL port)

## Step 1: Get Database Password

1. Log into your GoDaddy cPanel
2. Navigate to **MySQL Databases** or **Databases** section
3. Find the database user `jem_auto`
4. If you don't know the password:
   - Click on the user to view details
   - Or reset the password in the MySQL Databases section
   - **Save this password securely** - you'll need it for environment variables

## Step 2: Configure Environment Variables

In cPanel "Setup Python App" > Environment Variables, add these variables:

```
DB_NAME=jem_customer
DB_USER=jem_auto
DB_PASSWORD=your-actual-password-here
DB_HOST=localhost
DB_PORT=3306
```

**Important**: Replace `your-actual-password-here` with the actual password for the `jem_auto` user.

## Step 3: Install MySQL Client

The `mysqlclient` package is already in `requirements.txt`. When you run:

```bash
pip install -r requirements.txt
```

It will install the MySQL client library needed to connect to your database.

## Step 4: Test Database Connection

After setting environment variables and installing dependencies, test the connection:

```bash
# Activate virtual environment
source /home/username/virtualenv/jem.rixsoft.org/3.11/bin/activate

# Navigate to project
cd /home/username/jem.rixsoft.org

# Test database connection
python manage.py check --database default
```

## Step 5: Run Migrations

Once the database connection is working, run migrations:

```bash
python manage.py migrate
```

This will create all necessary tables in your `jem_customer` database.

## Step 6: Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

## Troubleshooting

### Issue: "Access denied for user"
- **Solution**: Verify the password is correct in environment variables
- Check that the user `jem_auto` has privileges on `jem_customer` database

### Issue: "Can't connect to MySQL server"
- **Solution**: Verify `DB_HOST=localhost` is correct
- Some GoDaddy setups may use a different host - check your cPanel MySQL settings

### Issue: "Unknown database 'jem_customer'"
- **Solution**: Verify the database name is correct
- Ensure the database exists in your GoDaddy cPanel

### Issue: "mysqlclient not found"
- **Solution**: Install system dependencies first (on some systems):
  ```bash
  # May need to install MySQL development headers
  # Contact GoDaddy support if mysqlclient installation fails
  ```

## Local Development

For local development, you can use SQLite (no database credentials needed). The app will automatically use SQLite if `DB_NAME` environment variable is not set.

## Security Notes

- **Never commit database passwords to version control**
- Use environment variables for all sensitive credentials
- The `.env` file is already in `.gitignore` for local development
- On GoDaddy, use cPanel Environment Variables (not files)

## Verification

After setup, verify the connection works:

```bash
python manage.py dbshell
```

If successful, you'll see the MySQL prompt. Type `exit` to leave.
