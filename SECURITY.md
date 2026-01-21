# Security Measures

This document outlines all security protections implemented in the J.E.M application.

## 1. SQL Injection Protection

### Django ORM Protection
- **All database queries use Django ORM** - No raw SQL queries
- Django ORM automatically escapes and parameterizes all queries
- Database configuration uses parameterized connections

### Input Validation
- All user inputs are validated before database operations
- Integer/decimal inputs validated using `validate_integer()` and `validate_decimal()` utilities
- String inputs sanitized using `sanitize_string()` utility
- No direct string concatenation in queries

## 2. Cross-Site Scripting (XSS) Protection

### Template Auto-Escaping
- Django templates automatically escape all variables by default
- Manual HTML escaping via `sanitize_string()` utility for extra safety
- User-generated content is sanitized before display

### Input Sanitization
- All user-provided strings are sanitized:
  - HTML tags are escaped
  - Null bytes removed
  - Length limits enforced
  - Special characters handled safely

## 3. Cross-Site Request Forgery (CSRF) Protection

### CSRF Middleware
- `CsrfViewMiddleware` enabled in `MIDDLEWARE`
- All POST forms include `{% csrf_token %}`
- CSRF tokens validated on all POST requests
- Custom CSRF failure view provides user-friendly error messages

### CSRF Cookie Security
- `CSRF_COOKIE_HTTPONLY = True` - Prevents JavaScript access
- `CSRF_COOKIE_SAMESITE = 'Lax'` - CSRF protection
- `CSRF_COOKIE_SECURE = True` in production (HTTPS only)

## 4. File Upload Security

### File Validation
- File type validation (allowed extensions: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.pdf`)
- File size limits:
  - Images: Maximum 5MB
  - Documents: Maximum 10MB
- MIME type checking to prevent file type spoofing
- Filename sanitization to prevent directory traversal attacks

### Upload Locations
- Files stored in `MEDIA_ROOT` with secure paths
- Payment proofs: `payment_proofs/%Y/%m/%d/`
- Receipts: `receipts/%Y/%m/%d/`
- Item images: `items/`

## 5. Authentication & Authorization

### Login Security
- Rate limiting: Maximum 5 login attempts per 5 minutes per IP
- Account lockout after failed attempts
- Staff-only access enforced via `@user_passes_test(is_staff_user)`
- Password validation:
  - Minimum 8 characters
  - Cannot be all numeric
  - Cannot be common passwords
  - Cannot be too similar to username

### Session Security
- `SESSION_COOKIE_HTTPONLY = True` - Prevents JavaScript access
- `SESSION_COOKIE_SAMESITE = 'Lax'` - CSRF protection
- `SESSION_COOKIE_SECURE = True` in production (HTTPS only)
- `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`
- `SESSION_SAVE_EVERY_REQUEST = True` - Extends session on activity
- Custom session cookie name: `jem_sessionid`

## 6. Input Validation & Sanitization

### String Inputs
- Customer names, phone numbers, pickup spots sanitized
- Maximum length limits enforced
- HTML escaping applied
- Null byte removal

### Numeric Inputs
- All integers validated: `validate_integer()`
- All decimals validated: `validate_decimal()`
- Range checks (min/max values)
- Zero value validation where appropriate

### Phone Number Validation
- Jamaican phone format validation
- Format: `1-876-XXX-XXXX` or `876-XXX-XXXX`
- Automatic formatting applied

## 7. Security Headers

### HTTP Security Headers
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-Content-Type-Options: nosniff` - Prevents MIME type sniffing
- `Referrer-Policy: strict-origin-when-cross-origin`
- `SECURE_BROWSER_XSS_FILTER = True` - Browser XSS filter

### Production-Only Headers
- `SECURE_HSTS_SECONDS = 31536000` - Force HTTPS for 1 year
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- `SECURE_HSTS_PRELOAD = True`
- `SECURE_SSL_REDIRECT = True` - Force HTTPS redirects
- `SECURE_PROXY_SSL_HEADER` - For proxy/load balancer setups

## 8. Database Security

### Connection Security
- Database credentials stored in environment variables (never in code)
- MySQL strict mode enabled: `STRICT_TRANS_TABLES`
- UTF-8 encoding: `utf8mb4`
- Connection pooling disabled (`CONN_MAX_AGE = 0`) for security

### Query Protection
- All queries use Django ORM (parameterized)
- No raw SQL queries
- Model-level validation
- Foreign key constraints (`on_delete=PROTECT` for critical relations)

## 9. Rate Limiting

### Login Rate Limiting
- Maximum 5 attempts per 5 minutes per IP address
- Session-based rate limiting for login attempts
- Lockout message with remaining time

### General Rate Limiting Utility
- `rate_limit_check()` function available for any view
- Configurable limits and time windows
- Session-based tracking

## 10. Error Handling

### Secure Error Messages
- Generic error messages to users (don't reveal system details)
- Detailed errors logged server-side only
- CSRF failures handled gracefully
- Validation errors provide helpful feedback

## 11. Security Utilities Module

### Location: `core/security.py`

Provides reusable security functions:
- `validate_file_upload()` - File upload validation
- `sanitize_string()` - String sanitization
- `validate_phone_number()` - Phone format validation
- `validate_decimal()` - Decimal number validation
- `validate_integer()` - Integer validation
- `validate_email()` - Email format validation
- `sanitize_filename()` - Filename sanitization
- `validate_url()` - URL validation
- `rate_limit_check()` - Rate limiting

## 12. Protected Views

### Admin Views
- All admin views require `@login_required`
- All admin views require `@user_passes_test(is_staff_user)`
- CSRF protection on all POST requests: `@csrf_protect`
- HTTP method restrictions: `@require_http_methods(["GET", "POST"])`

### Customer Views
- CSRF protection on all forms
- Input validation on all user inputs
- File upload validation

## 13. Environment Variables

### Sensitive Data Storage
- `SECRET_KEY` - Django secret key (never commit)
- `DB_PASSWORD` - Database password (never commit)
- `DEBUG` - Debug mode (False in production)
- `ALLOWED_HOSTS` - Allowed hostnames
- `CSRF_TRUSTED_ORIGINS` - Trusted origins for CSRF

## 14. Password Security

### Password Requirements
- Minimum 8 characters
- Cannot be all numeric
- Cannot be common passwords
- Cannot be too similar to username
- Django's built-in validators enforced

## Best Practices Implemented

1. ✅ **Never trust user input** - All inputs validated
2. ✅ **Principle of least privilege** - Staff-only admin access
3. ✅ **Defense in depth** - Multiple layers of security
4. ✅ **Secure defaults** - Security settings enabled by default
5. ✅ **Input validation** - Validate, sanitize, then use
6. ✅ **Error handling** - Don't reveal system details
7. ✅ **Session security** - Secure cookies, timeouts
8. ✅ **File upload security** - Type, size, and content validation
9. ✅ **Rate limiting** - Prevent brute force attacks
10. ✅ **Security headers** - Additional browser protections

## Security Checklist for Deployment

- [ ] Set `DEBUG=False` in production
- [ ] Use strong `SECRET_KEY` (generate new one)
- [ ] Set `ALLOWED_HOSTS` to your domain
- [ ] Use HTTPS (SSL certificate)
- [ ] Set secure database password
- [ ] Enable all security headers
- [ ] Review file upload limits
- [ ] Test rate limiting
- [ ] Review user permissions
- [ ] Regular security updates

## Reporting Security Issues

If you discover a security vulnerability, please:
1. Do not create a public issue
2. Contact the administrator directly
3. Provide details of the vulnerability
4. Allow time for fixes before disclosure
