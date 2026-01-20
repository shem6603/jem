"""
Admin views for secure backend management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import time
from collections import defaultdict

# Rate limiting storage (in production, use Redis or database)
_login_attempts = defaultdict(list)
_max_attempts = 5
_lockout_duration = 300  # 5 minutes


def is_staff_user(user):
    """Check if user is staff"""
    return user.is_authenticated and user.is_staff


def check_rate_limit(request):
    """Check if IP has exceeded login attempts"""
    ip_address = request.META.get('REMOTE_ADDR', 'unknown')
    now = time.time()
    
    # Clean old attempts
    _login_attempts[ip_address] = [
        attempt_time for attempt_time in _login_attempts[ip_address]
        if now - attempt_time < _lockout_duration
    ]
    
    # Check if locked out
    if len(_login_attempts[ip_address]) >= _max_attempts:
        return False
    
    return True


def record_failed_attempt(request):
    """Record a failed login attempt"""
    ip_address = request.META.get('REMOTE_ADDR', 'unknown')
    _login_attempts[ip_address].append(time.time())


def get_lockout_time_remaining(request):
    """Get remaining lockout time in seconds"""
    ip_address = request.META.get('REMOTE_ADDR', 'unknown')
    if len(_login_attempts[ip_address]) >= _max_attempts:
        oldest_attempt = min(_login_attempts[ip_address])
        elapsed = time.time() - oldest_attempt
        remaining = _lockout_duration - elapsed
        return max(0, int(remaining))
    return 0


@csrf_protect
@require_http_methods(["GET", "POST"])
def admin_login(request):
    """Secure admin login view"""
    # Redirect if already logged in
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')
    
    # Check rate limiting
    if not check_rate_limit(request):
        remaining = get_lockout_time_remaining(request)
        minutes = remaining // 60
        seconds = remaining % 60
        messages.error(
            request,
            f'Too many failed login attempts. Please try again in {minutes}m {seconds}s.'
        )
        return render(request, 'admin/login.html', {'lockout': True, 'remaining': remaining})
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me') == 'on'
        
        if not username or not password:
            messages.error(request, 'Please provide both username and password.')
            record_failed_attempt(request)
            return render(request, 'admin/login.html')
        
        # Authenticate user
        user = auth.authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_staff or user.is_superuser:
                # Clear failed attempts
                ip_address = request.META.get('REMOTE_ADDR', 'unknown')
                _login_attempts[ip_address] = []
                
                # Login user
                login(request, user)
                
                # Set session expiry
                if not remember_me:
                    request.session.set_expiry(3600)  # 1 hour
                else:
                    request.session.set_expiry(1209600)  # 2 weeks
                
                # Log last login
                user.last_login = timezone.now()
                user.save(update_fields=['last_login'])
                
                messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
                
                # Redirect to dashboard
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'You do not have permission to access the admin panel.')
                record_failed_attempt(request)
        else:
            messages.error(request, 'Invalid username or password.')
            record_failed_attempt(request)
    
    return render(request, 'admin/login.html')


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
def admin_logout(request):
    """Admin logout view"""
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('admin_login')


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
def admin_dashboard(request):
    """Admin dashboard with profit and revenue stats"""
    from .models import Order, Item
    from django.db.models import Sum
    
    # Calculate totals from completed orders
    completed_orders = Order.objects.filter(status='completed')
    total_revenue = completed_orders.aggregate(Sum('total_revenue'))['total_revenue__sum'] or Decimal('0.00')
    total_cost = completed_orders.aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0.00')
    total_profit = completed_orders.aggregate(Sum('net_profit'))['net_profit__sum'] or Decimal('0.00')
    
    # Low stock products
    low_stock_items = Item.objects.filter(current_stock__lt=5).order_by('current_stock', 'name')
    
    context = {
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'total_profit': total_profit,
        'low_stock_items': low_stock_items,
    }
    
    return render(request, 'admin/dashboard.html', context)


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
def admin_order_records(request):
    """Order records page"""
    from .models import Order
    from django.db.models import Sum
    
    # Get all orders
    orders = Order.objects.select_related('customer', 'bundle_type').order_by('-created_at')
    
    # Calculate totals
    total_revenue = orders.aggregate(Sum('total_revenue'))['total_revenue__sum'] or Decimal('0.00')
    total_cost = orders.aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0.00')
    total_profit = orders.aggregate(Sum('net_profit'))['net_profit__sum'] or Decimal('0.00')
    
    context = {
        'orders': orders,
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'total_profit': total_profit,
    }
    
    return render(request, 'admin/order_records.html', context)


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
def admin_inventory(request):
    """Inventory page split into Snacks and Juices"""
    from .models import Item
    
    snacks = Item.objects.filter(category='snack').order_by('name')
    juices = Item.objects.filter(category='juice').order_by('name')
    
    context = {
        'snacks': snacks,
        'juices': juices,
    }
    
    return render(request, 'admin/inventory.html', context)


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
@csrf_protect
@require_http_methods(["GET", "POST"])
def admin_add_item(request):
    """Add new item to inventory"""
    from .models import Item
    from decimal import Decimal
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', '').strip()
        cost_per_bag = request.POST.get('cost_per_bag', '').strip()
        units_per_bag = request.POST.get('units_per_bag', '').strip()
        current_stock = request.POST.get('current_stock', '0').strip()
        is_spicy = request.POST.get('is_spicy') == 'on'
        image = request.FILES.get('image')
        
        # Validation
        errors = []
        if not name:
            errors.append('Item name is required.')
        if not category or category not in ['snack', 'juice']:
            errors.append('Please select a valid category.')
        if not cost_per_bag:
            errors.append('Cost per bag/case is required.')
        if not units_per_bag:
            errors.append('Units per bag/case is required.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                cost_per_bag_decimal = Decimal(cost_per_bag)
                units_per_bag_int = int(units_per_bag)
                stock_int = int(current_stock) if current_stock else 0
                
                if cost_per_bag_decimal <= 0:
                    messages.error(request, 'Cost per bag/case must be greater than 0.')
                elif units_per_bag_int <= 0:
                    messages.error(request, 'Units per bag/case must be greater than 0.')
                elif stock_int < 0:
                    messages.error(request, 'Stock cannot be negative.')
                else:
                    # cost_price will be auto-calculated in the model's save() method
                    item = Item.objects.create(
                        name=name,
                        category=category,
                        cost_per_bag=cost_per_bag_decimal,
                        units_per_bag=units_per_bag_int,
                        current_stock=stock_int,
                        is_spicy=is_spicy if category == 'snack' else False,
                    )
                    
                    if image:
                        item.image = image
                        item.save()
                    
                    messages.success(request, f'Item "{name}" has been added to inventory. Cost per unit: ${item.cost_price:.4f}')
                    return redirect('admin_inventory')
            except ValueError:
                messages.error(request, 'Please enter valid numbers.')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
    
    return render(request, 'admin/add_item.html')


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
@csrf_protect
@require_http_methods(["GET", "POST"])
def admin_edit_item(request, item_id):
    """Edit existing item in inventory"""
    from .models import Item
    from decimal import Decimal
    
    item = get_object_or_404(Item, id=item_id)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', '').strip()
        cost_per_bag = request.POST.get('cost_per_bag', '').strip()
        units_per_bag = request.POST.get('units_per_bag', '').strip()
        current_stock = request.POST.get('current_stock', '0').strip()
        is_spicy = request.POST.get('is_spicy') == 'on'
        image = request.FILES.get('image')
        remove_image = request.POST.get('remove_image') == 'on'
        
        # Validation
        errors = []
        if not name:
            errors.append('Item name is required.')
        if not category or category not in ['snack', 'juice']:
            errors.append('Please select a valid category.')
        if not cost_per_bag:
            errors.append('Cost per bag/case is required.')
        if not units_per_bag:
            errors.append('Units per bag/case is required.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                cost_per_bag_decimal = Decimal(cost_per_bag)
                units_per_bag_int = int(units_per_bag)
                stock_int = int(current_stock) if current_stock else 0
                
                if cost_per_bag_decimal <= 0:
                    messages.error(request, 'Cost per bag/case must be greater than 0.')
                elif units_per_bag_int <= 0:
                    messages.error(request, 'Units per bag/case must be greater than 0.')
                elif stock_int < 0:
                    messages.error(request, 'Stock cannot be negative.')
                else:
                    # Update item fields
                    item.name = name
                    item.category = category
                    item.cost_per_bag = cost_per_bag_decimal
                    item.units_per_bag = units_per_bag_int
                    item.current_stock = stock_int
                    item.is_spicy = is_spicy if category == 'snack' else False
                    
                    # Handle image
                    if remove_image:
                        item.image = None
                    elif image:
                        item.image = image
                    
                    # cost_price will be auto-calculated in the model's save() method
                    item.save()
                    
                    messages.success(request, f'Item "{name}" has been updated. Cost per unit: ${item.cost_price:.2f}')
                    return redirect('admin_inventory')
            except ValueError:
                messages.error(request, 'Please enter valid numbers.')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
    
    context = {
        'item': item,
    }
    return render(request, 'admin/edit_item.html', context)


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
@csrf_protect
@require_http_methods(["GET", "POST"])
def admin_accounting(request):
    """Accounting page with receipt upload"""
    from .models import Receipt, Order
    from django.db.models import Sum
    from decimal import Decimal
    
    # Calculate total revenue from orders
    completed_orders = Order.objects.filter(status='completed')
    total_revenue_from_orders = completed_orders.aggregate(Sum('total_revenue'))['total_revenue__sum'] or Decimal('0.00')
    
    # Calculate total expenses from receipts
    total_expenses = Receipt.objects.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
    
    # Calculate remaining revenue
    remaining_revenue = total_revenue_from_orders - total_expenses
    
    # Get all receipts
    receipts = Receipt.objects.select_related('uploaded_by').order_by('-created_at')
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        amount = request.POST.get('amount', '').strip()
        description = request.POST.get('description', '').strip()
        receipt_file = request.FILES.get('receipt_file')
        
        if not title:
            messages.error(request, 'Title is required.')
        elif not amount:
            messages.error(request, 'Amount is required.')
        elif not receipt_file:
            messages.error(request, 'Receipt file is required.')
        else:
            try:
                amount_decimal = Decimal(amount)
                receipt = Receipt.objects.create(
                    title=title,
                    amount=amount_decimal,
                    description=description,
                    receipt_file=receipt_file,
                    uploaded_by=request.user
                )
                messages.success(request, f'Receipt "{receipt.title}" uploaded successfully!')
                return redirect('admin_accounting')
            except Exception as e:
                messages.error(request, f'Error uploading receipt: {str(e)}')
    
    context = {
        'receipts': receipts,
        'total_revenue_from_orders': total_revenue_from_orders,
        'total_expenses': total_expenses,
        'remaining_revenue': remaining_revenue,
    }
    
    return render(request, 'admin/accounting.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='admin_login')
@csrf_protect
@require_http_methods(["GET", "POST"])
def admin_create_user(request):
    """Create new admin user (superuser only)"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        is_staff = request.POST.get('is_staff') == 'on'
        is_superuser = request.POST.get('is_superuser') == 'on'
        
        # Validation
        errors = []
        
        if not username:
            errors.append('Username is required.')
        elif len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        elif User.objects.filter(username=username).exists():
            errors.append('Username already exists.')
        
        if email:
            try:
                validate_email(email)
                if User.objects.filter(email=email).exists():
                    errors.append('Email already exists.')
            except ValidationError:
                errors.append('Invalid email address.')
        
        if not password:
            errors.append('Password is required.')
        elif len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        elif password != password_confirm:
            errors.append('Passwords do not match.')
        
        # Check password strength
        if password:
            has_upper = any(c.isupper() for c in password)
            has_lower = any(c.islower() for c in password)
            has_digit = any(c.isdigit() for c in password)
            
            if not (has_upper and has_lower and has_digit):
                errors.append('Password must contain uppercase, lowercase, and numbers.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        is_staff=is_staff,
                        is_superuser=is_superuser,
                    )
                    messages.success(request, f'User "{user.username}" created successfully!')
                    return redirect('admin_users')
            except Exception as e:
                messages.error(request, f'Error creating user: {str(e)}')
    
    return render(request, 'admin/create_user.html')


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='admin_login')
def admin_users(request):
    """List all admin users"""
    users = User.objects.filter(is_staff=True).order_by('-date_joined')
    return render(request, 'admin/users.html', {'users': users})


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='admin_login')
@csrf_protect
@require_http_methods(["POST"])
def admin_delete_user(request, user_id):
    """Delete admin user (superuser only)"""
    if request.user.id == user_id:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('admin_users')
    
    user = get_object_or_404(User, id=user_id, is_staff=True)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User "{username}" has been deleted.')
    
    return redirect('admin_users')
