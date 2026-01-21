"""
Security utilities for input validation, sanitization, and protection
"""
import re
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.utils.html import escape
from django.utils.text import slugify


# File upload security
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
ALLOWED_DOCUMENT_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png']
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


def validate_file_upload(file, allowed_extensions=None, max_size=None):
    """
    Validate file upload for security
    
    Args:
        file: Django UploadedFile object
        allowed_extensions: List of allowed file extensions (default: images)
        max_size: Maximum file size in bytes (default: MAX_FILE_SIZE)
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_IMAGE_EXTENSIONS
    
    if max_size is None:
        max_size = MAX_FILE_SIZE
    
    # Check file size
    if file.size > max_size:
        return False, f'File size exceeds maximum allowed size of {max_size / (1024*1024):.1f}MB'
    
    # Check file extension
    file_name = file.name.lower()
    file_extension = None
    for ext in allowed_extensions:
        if file_name.endswith(ext.lower()):
            file_extension = ext
            break
    
    if not file_extension:
        return False, f'Invalid file type. Allowed types: {", ".join(allowed_extensions)}'
    
    # Check MIME type (basic check)
    content_type = file.content_type
    if 'image' in content_type and file_extension not in ALLOWED_IMAGE_EXTENSIONS:
        return False, 'File type mismatch detected'
    
    return True, None


def sanitize_string(value, max_length=None):
    """
    Sanitize string input to prevent XSS and SQL injection
    
    Args:
        value: String to sanitize
        max_length: Maximum length allowed
    
    Returns:
        str: Sanitized string
    """
    if value is None:
        return ''
    
    # Convert to string and strip whitespace
    value = str(value).strip()
    
    # Remove null bytes (can cause issues)
    value = value.replace('\x00', '')
    
    # Limit length if specified
    if max_length and len(value) > max_length:
        value = value[:max_length]
    
    # Escape HTML to prevent XSS (Django templates do this, but extra safety)
    value = escape(value)
    
    return value


def validate_phone_number(phone):
    """
    Validate phone number format (Jamaican format)
    
    Args:
        phone: Phone number string
    
    Returns:
        tuple: (is_valid, cleaned_phone)
    """
    if not phone:
        return False, None
    
    # Remove common separators
    cleaned = re.sub(r'[\s\-\(\)]', '', phone.strip())
    
    # Check if it's a valid format (Jamaican: 1-876-XXX-XXXX or 876-XXX-XXXX)
    if re.match(r'^(\+?1)?876\d{7}$', cleaned):
        # Format as 1-876-XXX-XXXX
        if cleaned.startswith('1876'):
            return True, f"{cleaned[:1]}-{cleaned[1:4]}-{cleaned[4:7]}-{cleaned[7:]}"
        elif cleaned.startswith('876'):
            return True, f"1-{cleaned[:3]}-{cleaned[3:6]}-{cleaned[6:]}"
    
    # Also allow local format XXX-XXXX
    if re.match(r'^\d{7}$', cleaned):
        return True, cleaned
    
    return False, None


def validate_decimal(value, min_value=None, max_value=None, allow_zero=True):
    """
    Safely validate and convert to Decimal
    
    Args:
        value: Value to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        allow_zero: Whether zero is allowed
    
    Returns:
        tuple: (is_valid, decimal_value, error_message)
    """
    if value is None or value == '':
        return False, None, 'Value is required'
    
    try:
        decimal_value = Decimal(str(value))
        
        # Check zero
        if not allow_zero and decimal_value == 0:
            return False, None, 'Value cannot be zero'
        
        # Check minimum
        if min_value is not None and decimal_value < min_value:
            return False, None, f'Value must be at least {min_value}'
        
        # Check maximum
        if max_value is not None and decimal_value > max_value:
            return False, None, f'Value must be at most {max_value}'
        
        return True, decimal_value, None
    
    except (ValueError, InvalidOperation):
        return False, None, 'Invalid number format'


def validate_integer(value, min_value=None, max_value=None, allow_zero=True):
    """
    Safely validate and convert to integer
    
    Args:
        value: Value to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        allow_zero: Whether zero is allowed
    
    Returns:
        tuple: (is_valid, integer_value, error_message)
    """
    if value is None or value == '':
        return False, None, 'Value is required'
    
    try:
        int_value = int(value)
        
        # Check zero
        if not allow_zero and int_value == 0:
            return False, None, 'Value cannot be zero'
        
        # Check minimum
        if min_value is not None and int_value < min_value:
            return False, None, f'Value must be at least {min_value}'
        
        # Check maximum
        if max_value is not None and int_value > max_value:
            return False, None, f'Value must be at most {max_value}'
        
        return True, int_value, None
    
    except (ValueError, TypeError):
        return False, None, 'Invalid integer format'


def validate_email(email):
    """
    Validate email format
    
    Args:
        email: Email string
    
    Returns:
        tuple: (is_valid, cleaned_email)
    """
    if not email:
        return False, None
    
    email = email.strip().lower()
    
    # Basic email regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(email_pattern, email):
        return True, email
    
    return False, None


def sanitize_filename(filename):
    """
    Sanitize filename to prevent directory traversal and other attacks
    
    Args:
        filename: Original filename
    
    Returns:
        str: Sanitized filename
    """
    if not filename:
        return 'file'
    
    # Remove path components
    filename = filename.split('/')[-1].split('\\')[-1]
    
    # Remove dangerous characters
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')
    
    return filename


def validate_url(url):
    """
    Validate URL format
    
    Args:
        url: URL string
    
    Returns:
        tuple: (is_valid, cleaned_url)
    """
    if not url:
        return False, None
    
    url = url.strip()
    
    # Basic URL validation
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
    
    if re.match(url_pattern, url):
        return True, url
    
    return False, None


def rate_limit_check(request, key_prefix, max_requests=5, window_seconds=60):
    """
    Simple rate limiting check using session
    
    Args:
        request: Django request object
        key_prefix: Unique key prefix for this rate limit
        max_requests: Maximum requests allowed
        window_seconds: Time window in seconds
    
    Returns:
        tuple: (is_allowed, remaining_attempts)
    """
    import time
    
    session_key = f'rate_limit_{key_prefix}'
    current_time = time.time()
    
    # Get or initialize rate limit data
    rate_limit_data = request.session.get(session_key, {'count': 0, 'reset_time': current_time + window_seconds})
    
    # Reset if window expired
    if current_time > rate_limit_data['reset_time']:
        rate_limit_data = {'count': 0, 'reset_time': current_time + window_seconds}
    
    # Check limit
    if rate_limit_data['count'] >= max_requests:
        remaining = 0
        return False, remaining
    
    # Increment count
    rate_limit_data['count'] += 1
    request.session[session_key] = rate_limit_data
    
    remaining = max_requests - rate_limit_data['count']
    return True, remaining
