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
from decimal import Decimal, InvalidOperation
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
@csrf_protect
@require_http_methods(["GET", "POST"])
def admin_add_order(request):
    """Simple admin order creation - select order type and items"""
    from .models import Item, Customer, Order, OrderItem, BundleType
    
    # Get or create predefined bundle types
    bundle_10_snacks, _ = BundleType.objects.get_or_create(
        name='10 Snacks',
        defaults={'required_snacks': 10, 'required_juices': 0, 'is_active': True}
    )
    bundle_25_snacks, _ = BundleType.objects.get_or_create(
        name='25 Snacks',
        defaults={'required_snacks': 25, 'required_juices': 0, 'is_active': True}
    )
    bundle_25_juices, _ = BundleType.objects.get_or_create(
        name='25 Juices',
        defaults={'required_snacks': 0, 'required_juices': 25, 'is_active': True}
    )
    bundle_mega_mix, _ = BundleType.objects.get_or_create(
        name='Mega Mix',
        defaults={'required_snacks': 30, 'required_juices': 24, 'is_active': True}
    )
    
    # Get all available items
    items = Item.objects.filter(current_stock__gt=0).order_by('category', 'name')
    snacks = items.filter(category='snack')
    juices = items.filter(category='juice')
    
    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        pickup_spot = request.POST.get('pickup_spot', '').strip()
        order_date = request.POST.get('order_date', '').strip()
        order_type = request.POST.get('order_type', '').strip()
        custom_order_name = request.POST.get('custom_order_name', '').strip()
        use_inventory = request.POST.get('use_inventory') == 'on'
        total_revenue = request.POST.get('total_revenue', '').strip()
        total_cost = request.POST.get('total_cost', '').strip()
        net_profit = request.POST.get('net_profit', '').strip()
        
        if not customer_name:
            messages.error(request, 'Customer name is required.')
        elif not pickup_spot:
            messages.error(request, 'Pickup spot is required.')
        elif not order_date:
            messages.error(request, 'Order date is required.')
        elif not order_type:
            messages.error(request, 'Order type is required.')
        else:
            # Validate manual financial inputs when not using inventory
            if not use_inventory:
                if not total_revenue:
                    messages.error(request, 'Revenue is required when not using inventory.')
                    return render(request, 'admin/add_order.html', {
                        'snacks': snacks,
                        'juices': juices,
                        'customer_name': customer_name,
                        'customer_phone': customer_phone,
                        'pickup_spot': pickup_spot,
                        'order_date': order_date,
                        'order_type': order_type,
                        'custom_order_name': custom_order_name,
                        'total_revenue': total_revenue,
                        'total_cost': total_cost,
                        'net_profit': net_profit,
                        'use_inventory': use_inventory,
                    })
                elif not total_cost:
                    messages.error(request, 'Total cost is required when not using inventory.')
                    return render(request, 'admin/add_order.html', {
                        'snacks': snacks,
                        'juices': juices,
                        'customer_name': customer_name,
                        'customer_phone': customer_phone,
                        'pickup_spot': pickup_spot,
                        'order_date': order_date,
                        'order_type': order_type,
                        'custom_order_name': custom_order_name,
                        'total_revenue': total_revenue,
                        'total_cost': total_cost,
                        'net_profit': net_profit,
                        'use_inventory': use_inventory,
                    })
                else:
                    try:
                        total_revenue_decimal = Decimal(total_revenue)
                        total_cost_decimal = Decimal(total_cost)
                        if total_revenue_decimal < 0 or total_cost_decimal < 0:
                            messages.error(request, 'Revenue and cost must be positive numbers.')
                            return render(request, 'admin/add_order.html', {
                                'snacks': snacks,
                                'juices': juices,
                                'customer_name': customer_name,
                                'customer_phone': customer_phone,
                                'pickup_spot': pickup_spot,
                                'order_date': order_date,
                                'order_type': order_type,
                                'custom_order_name': custom_order_name,
                                'total_revenue': total_revenue,
                                'total_cost': total_cost,
                                'net_profit': net_profit,
                                'use_inventory': use_inventory,
                            })
                    except (ValueError, InvalidOperation):
                        messages.error(request, 'Please enter valid numbers for revenue and cost.')
                        return render(request, 'admin/add_order.html', {
                            'snacks': snacks,
                            'juices': juices,
                            'customer_name': customer_name,
                            'customer_phone': customer_phone,
                            'pickup_spot': pickup_spot,
                            'order_date': order_date,
                            'order_type': order_type,
                            'custom_order_name': custom_order_name,
                            'total_revenue': total_revenue,
                            'total_cost': total_cost,
                            'net_profit': net_profit,
                            'use_inventory': use_inventory,
                        })
            
            # Determine bundle type and requirements
            bundle_type = None
            required_snacks = 0
            required_juices = 0
            
            if use_inventory:
                if order_type == 'custom':
                    if not custom_order_name:
                        messages.error(request, 'Please enter a custom order name.')
                        return render(request, 'admin/add_order.html', {
                            'snacks': snacks,
                            'juices': juices,
                            'customer_name': customer_name,
                            'customer_phone': customer_phone,
                            'pickup_spot': pickup_spot,
                            'order_type': order_type,
                            'custom_order_name': custom_order_name,
                            'use_inventory': use_inventory,
                        })
                    # Create custom bundle type
                    bundle_type, _ = BundleType.objects.get_or_create(
                        name=custom_order_name,
                        defaults={'required_snacks': 0, 'required_juices': 0, 'is_active': True}
                    )
                    required_snacks = 0
                    required_juices = 0
                elif order_type == '10_snacks':
                    bundle_type = bundle_10_snacks
                    required_snacks = 10
                    required_juices = 0
                elif order_type == '25_snacks':
                    bundle_type = bundle_25_snacks
                    required_snacks = 25
                    required_juices = 0
                elif order_type == '25_juices':
                    bundle_type = bundle_25_juices
                    required_snacks = 0
                    required_juices = 25
                elif order_type == 'mega_mix':
                    bundle_type = bundle_mega_mix
                    required_snacks = 30
                    required_juices = 24
                else:
                    messages.error(request, 'Invalid order type selected.')
                    return render(request, 'admin/add_order.html', {
                        'snacks': snacks,
                        'juices': juices,
                        'customer_name': customer_name,
                        'customer_phone': customer_phone,
                        'pickup_spot': pickup_spot,
                        'use_inventory': use_inventory,
                    })
            else:
                # For back-dated orders (not using inventory), create bundle from order type
                if order_type == 'custom':
                    if not custom_order_name:
                        messages.error(request, 'Please enter a custom order name.')
                        return render(request, 'admin/add_order.html', {
                            'snacks': snacks,
                            'juices': juices,
                            'customer_name': customer_name,
                            'customer_phone': customer_phone,
                            'pickup_spot': pickup_spot,
                            'order_date': order_date,
                            'order_type': order_type,
                            'custom_order_name': custom_order_name,
                            'total_revenue': total_revenue,
                            'total_cost': total_cost,
                            'net_profit': net_profit,
                            'use_inventory': use_inventory,
                        })
                    bundle_type, _ = BundleType.objects.get_or_create(
                        name=custom_order_name,
                        defaults={'required_snacks': 0, 'required_juices': 0, 'is_active': True}
                    )
                elif order_type == '10_snacks':
                    bundle_type = bundle_10_snacks
                elif order_type == '25_snacks':
                    bundle_type = bundle_25_snacks
                elif order_type == '25_juices':
                    bundle_type = bundle_25_juices
                elif order_type == 'mega_mix':
                    bundle_type = bundle_mega_mix
                else:
                    messages.error(request, 'Invalid order type selected.')
                    return render(request, 'admin/add_order.html', {
                        'snacks': snacks,
                        'juices': juices,
                        'customer_name': customer_name,
                        'customer_phone': customer_phone,
                        'pickup_spot': pickup_spot,
                        'order_date': order_date,
                        'order_type': order_type,
                        'custom_order_name': custom_order_name,
                        'total_revenue': total_revenue,
                        'total_cost': total_cost,
                        'net_profit': net_profit,
                        'use_inventory': use_inventory,
                    })
            
            # Only get items if use_inventory is checked
            selected_snacks = []
            selected_juices = []
            total_snacks = 0
            total_juices = 0
            
            if use_inventory:
                for snack in snacks:
                    quantity_str = request.POST.get(f'snack_{snack.id}', '').strip()
                    if quantity_str:
                        try:
                            quantity = int(quantity_str)
                            if quantity > 0:
                                if quantity > snack.current_stock:
                                    messages.error(request, f'Cannot order {quantity} units of {snack.name}. Only {snack.current_stock} units available.')
                                    return render(request, 'admin/add_order.html', {
                                        'snacks': snacks,
                                        'juices': juices,
                                        'customer_name': customer_name,
                                        'customer_phone': customer_phone,
                                        'pickup_spot': pickup_spot,
                                        'order_type': order_type,
                                        'custom_order_name': custom_order_name,
                                        'use_inventory': use_inventory,
                                    })
                                selected_snacks.append((snack, quantity))
                                total_snacks += quantity
                        except ValueError:
                            pass
                
                for juice in juices:
                    quantity_str = request.POST.get(f'juice_{juice.id}', '').strip()
                    if quantity_str:
                        try:
                            quantity = int(quantity_str)
                            if quantity > 0:
                                if quantity > juice.current_stock:
                                    messages.error(request, f'Cannot order {quantity} units of {juice.name}. Only {juice.current_stock} units available.')
                                    return render(request, 'admin/add_order.html', {
                                        'snacks': snacks,
                                        'juices': juices,
                                        'customer_name': customer_name,
                                        'customer_phone': customer_phone,
                                        'pickup_spot': pickup_spot,
                                        'order_type': order_type,
                                        'custom_order_name': custom_order_name,
                                        'use_inventory': use_inventory,
                                    })
                                selected_juices.append((juice, quantity))
                                total_juices += quantity
                        except ValueError:
                            pass
                
                # Validate quantities for predefined types
                if order_type != 'custom':
                    if required_snacks > 0 and total_snacks != required_snacks:
                        messages.error(request, f'Please select exactly {required_snacks} snacks. You selected {total_snacks}.')
                        return render(request, 'admin/add_order.html', {
                            'snacks': snacks,
                            'juices': juices,
                            'customer_name': customer_name,
                            'customer_phone': customer_phone,
                            'pickup_spot': pickup_spot,
                            'order_type': order_type,
                            'custom_order_name': custom_order_name,
                            'use_inventory': use_inventory,
                        })
                    if required_juices > 0 and total_juices != required_juices:
                        messages.error(request, f'Please select exactly {required_juices} juices. You selected {total_juices}.')
                        return render(request, 'admin/add_order.html', {
                            'snacks': snacks,
                            'juices': juices,
                            'customer_name': customer_name,
                            'customer_phone': customer_phone,
                            'pickup_spot': pickup_spot,
                            'order_type': order_type,
                            'custom_order_name': custom_order_name,
                            'use_inventory': use_inventory,
                        })
                
                if not selected_snacks and not selected_juices:
                    messages.error(request, 'Please select at least one item when using inventory.')
                    return render(request, 'admin/add_order.html', {
                        'snacks': snacks,
                        'juices': juices,
                        'customer_name': customer_name,
                        'customer_phone': customer_phone,
                        'pickup_spot': pickup_spot,
                        'order_type': order_type,
                        'custom_order_name': custom_order_name,
                        'use_inventory': use_inventory,
                    })
            
            # Create order (works with or without inventory)
            try:
                # Create or get customer
                customer, created = Customer.objects.get_or_create(
                    name=customer_name,
                    defaults={'phone': customer_phone, 'pickup_spot': pickup_spot}
                )
                # Update pickup spot if customer exists
                if not created and pickup_spot:
                    customer.pickup_spot = pickup_spot
                    customer.save()
                
                # Parse order date if provided
                from django.utils import timezone
                from datetime import datetime
                order_created_at = timezone.now()
                if order_date:
                    try:
                        order_created_at = timezone.make_aware(datetime.strptime(order_date, '%Y-%m-%d'))
                    except ValueError:
                        pass  # Use current time if date parsing fails
                
                # Create order
                order = Order.objects.create(
                    customer=customer,
                    bundle_type=bundle_type,
                    status='completed',
                )
                # Override created_at if custom date was provided
                if order_date:
                    Order.objects.filter(id=order.id).update(created_at=order_created_at)
                    order.refresh_from_db()
                
                # Handle order items and financials based on use_inventory flag
                if use_inventory:
                    # Create order items and update stock
                    for item, quantity in selected_snacks + selected_juices:
                        OrderItem.objects.create(order=order, item=item, quantity=quantity)
                        item.current_stock -= quantity
                        item.save()
                    
                    # Refresh order to ensure order_items relationship is loaded
                    order.refresh_from_db()
                    
                    # Recalculate totals (Revenue, Total Cost, Profit)
                    # Currently uses: Revenue = sum(item.sell_price * quantity), Cost = sum(item.cost_price * quantity), Profit = Revenue - Cost
                    # TODO: User will provide custom calculation logic for Revenue and Profit
                    order.calculate_totals()
                else:
                    # For back-dated orders, use manual financial inputs with direct update
                    # to avoid calculate_totals() being called in save()
                    try:
                        revenue_decimal = Decimal(total_revenue)
                        cost_decimal = Decimal(total_cost)
                        profit_decimal = Decimal(net_profit) if net_profit else (revenue_decimal - cost_decimal)
                        margin = (profit_decimal / revenue_decimal * 100) if revenue_decimal > 0 else Decimal('0')
                        
                        # Use direct update to avoid triggering calculate_totals() in save()
                        Order.objects.filter(id=order.id).update(
                            total_revenue=revenue_decimal,
                            total_cost=cost_decimal,
                            net_profit=profit_decimal,
                            profit_margin=margin
                        )
                    except (ValueError, InvalidOperation):
                        messages.error(request, 'Invalid financial values provided.')
                        return render(request, 'admin/add_order.html', {
                            'snacks': snacks,
                            'juices': juices,
                            'customer_name': customer_name,
                            'customer_phone': customer_phone,
                            'pickup_spot': pickup_spot,
                            'order_date': order_date,
                            'order_type': order_type,
                            'custom_order_name': custom_order_name,
                            'total_revenue': total_revenue,
                            'total_cost': total_cost,
                            'net_profit': net_profit,
                            'use_inventory': use_inventory,
                        })
                
                if use_inventory:
                    messages.success(request, f'Order #{order.id} created successfully! Stock has been deducted.')
                else:
                    messages.success(request, f'Order #{order.id} created successfully! (Back-dated order - inventory not affected)')
                return redirect('admin_order_records')
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
    
    # Set default date to today
    from django.utils import timezone
    default_date = timezone.now().strftime('%Y-%m-%d')
    
    context = {
        'snacks': snacks,
        'juices': juices,
        'order_date': default_date,
        'total_revenue': '',
        'total_cost': '',
        'net_profit': '',
    }
    return render(request, 'admin/add_order.html', context)


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
@csrf_protect
@require_http_methods(["GET", "POST"])
def admin_edit_order(request, order_id):
    """Edit existing order"""
    from .models import Item, Customer, Order, OrderItem, BundleType
    
    order = get_object_or_404(Order, id=order_id)
    
    # Get or create predefined bundle types
    bundle_10_snacks, _ = BundleType.objects.get_or_create(
        name='10 Snacks',
        defaults={'required_snacks': 10, 'required_juices': 0, 'is_active': True}
    )
    bundle_25_snacks, _ = BundleType.objects.get_or_create(
        name='25 Snacks',
        defaults={'required_snacks': 25, 'required_juices': 0, 'is_active': True}
    )
    bundle_25_juices, _ = BundleType.objects.get_or_create(
        name='25 Juices',
        defaults={'required_snacks': 0, 'required_juices': 25, 'is_active': True}
    )
    bundle_mega_mix, _ = BundleType.objects.get_or_create(
        name='Mega Mix',
        defaults={'required_snacks': 30, 'required_juices': 24, 'is_active': True}
    )
    
    # Get all items (including those with 0 stock for editing)
    items = Item.objects.all().order_by('category', 'name')
    snacks = items.filter(category='snack')
    juices = items.filter(category='juice')
    
    # Get existing order items
    existing_order_items = {item.item.id: item.quantity for item in order.order_items.all()}
    
    # Prepare snacks and juices with existing quantities and available stock
    snacks_with_data = []
    for snack in snacks:
        existing_qty = existing_order_items.get(snack.id, 0)
        available_stock = snack.current_stock + existing_qty
        snacks_with_data.append({
            'item': snack,
            'existing_qty': existing_qty,
            'available_stock': available_stock,
        })
    
    juices_with_data = []
    for juice in juices:
        existing_qty = existing_order_items.get(juice.id, 0)
        available_stock = juice.current_stock + existing_qty
        juices_with_data.append({
            'item': juice,
            'existing_qty': existing_qty,
            'available_stock': available_stock,
        })
    
    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        pickup_spot = request.POST.get('pickup_spot', '').strip()
        order_date = request.POST.get('order_date', '').strip()
        order_type = request.POST.get('order_type', '').strip()
        custom_order_name = request.POST.get('custom_order_name', '').strip()
        use_inventory = request.POST.get('use_inventory') == 'on'
        total_revenue = request.POST.get('total_revenue', '').strip()
        total_cost = request.POST.get('total_cost', '').strip()
        net_profit = request.POST.get('net_profit', '').strip()
        
        # Track if there are validation errors
        has_errors = False
        
        if not customer_name:
            messages.error(request, 'Customer name is required.')
            has_errors = True
        elif not pickup_spot:
            messages.error(request, 'Pickup spot is required.')
            has_errors = True
        elif not order_date:
            messages.error(request, 'Order date is required.')
            has_errors = True
        elif not order_type:
            messages.error(request, 'Order type is required.')
            has_errors = True
        else:
            # Validate manual financial inputs when not using inventory
            if not use_inventory:
                if not total_revenue:
                    messages.error(request, 'Revenue is required when not using inventory.')
                    has_errors = True
                elif not total_cost:
                    messages.error(request, 'Total cost is required when not using inventory.')
                    has_errors = True
                else:
                    try:
                        total_revenue_decimal = Decimal(total_revenue)
                        total_cost_decimal = Decimal(total_cost)
                        if total_revenue_decimal < 0 or total_cost_decimal < 0:
                            messages.error(request, 'Revenue and cost must be positive numbers.')
                            has_errors = True
                    except (ValueError, InvalidOperation):
                        messages.error(request, 'Please enter valid numbers for revenue and cost.')
                        has_errors = True
            
            if not has_errors:
                # Determine bundle type
                bundle_type = None
                required_snacks = 0
                required_juices = 0
                
                if use_inventory:
                    if order_type == 'custom':
                        if not custom_order_name:
                            messages.error(request, 'Please enter a custom order name.')
                            has_errors = True
                        else:
                            bundle_type, _ = BundleType.objects.get_or_create(
                                name=custom_order_name,
                                defaults={'required_snacks': 0, 'required_juices': 0, 'is_active': True}
                            )
                            required_snacks = 0
                            required_juices = 0
                    elif order_type == '10_snacks':
                        bundle_type = bundle_10_snacks
                        required_snacks = 10
                        required_juices = 0
                    elif order_type == '25_snacks':
                        bundle_type = bundle_25_snacks
                        required_snacks = 25
                        required_juices = 0
                    elif order_type == '25_juices':
                        bundle_type = bundle_25_juices
                        required_snacks = 0
                        required_juices = 25
                    elif order_type == 'mega_mix':
                        bundle_type = bundle_mega_mix
                        required_snacks = 30
                        required_juices = 24
                else:
                    # For back-dated orders
                    if order_type == 'custom':
                        if not custom_order_name:
                            messages.error(request, 'Please enter a custom order name.')
                            has_errors = True
                        else:
                            bundle_type, _ = BundleType.objects.get_or_create(
                                name=custom_order_name,
                                defaults={'required_snacks': 0, 'required_juices': 0, 'is_active': True}
                            )
                    elif order_type == '10_snacks':
                        bundle_type = bundle_10_snacks
                    elif order_type == '25_snacks':
                        bundle_type = bundle_25_snacks
                    elif order_type == '25_juices':
                        bundle_type = bundle_25_juices
                    elif order_type == 'mega_mix':
                        bundle_type = bundle_mega_mix
                
                if bundle_type and not has_errors:
                    try:
                        # Update customer
                        order.customer.name = customer_name
                        order.customer.phone = customer_phone
                        order.customer.pickup_spot = pickup_spot
                        order.customer.save()
                        
                        # Update bundle type
                        order.bundle_type = bundle_type
                        
                        # Update order date
                        from django.utils import timezone
                        from datetime import datetime
                        if order_date:
                            try:
                                order_created_at = timezone.make_aware(datetime.strptime(order_date, '%Y-%m-%d'))
                                Order.objects.filter(id=order.id).update(created_at=order_created_at)
                            except ValueError:
                                pass
                        
                        # Handle order items and financials
                        if use_inventory:
                            # Get selected items
                            selected_snacks = []
                            selected_juices = []
                            total_snacks = 0
                            total_juices = 0
                            
                            for snack in snacks:
                                quantity_str = request.POST.get(f'snack_{snack.id}', '').strip()
                                if quantity_str:
                                    try:
                                        quantity = int(quantity_str)
                                        if quantity > 0:
                                            # Check stock availability (add back old quantity first)
                                            old_quantity = existing_order_items.get(snack.id, 0)
                                            available_stock = snack.current_stock + old_quantity
                                            if quantity > available_stock:
                                                messages.error(request, f'Cannot order {quantity} units of {snack.name}. Only {available_stock} units available.')
                                                has_errors = True
                                                break
                                            selected_snacks.append((snack, quantity))
                                            total_snacks += quantity
                                    except ValueError:
                                        pass
                            
                            for juice in juices:
                                if has_errors:
                                    break
                                quantity_str = request.POST.get(f'juice_{juice.id}', '').strip()
                                if quantity_str:
                                    try:
                                        quantity = int(quantity_str)
                                        if quantity > 0:
                                            old_quantity = existing_order_items.get(juice.id, 0)
                                            available_stock = juice.current_stock + old_quantity
                                            if quantity > available_stock:
                                                messages.error(request, f'Cannot order {quantity} units of {juice.name}. Only {available_stock} units available.')
                                                has_errors = True
                                                break
                                            selected_juices.append((juice, quantity))
                                            total_juices += quantity
                                    except ValueError:
                                        pass
                            
                            # Validate quantities for predefined types
                            if not has_errors:
                                if order_type != 'custom':
                                    if required_snacks > 0 and total_snacks != required_snacks:
                                        messages.error(request, f'Please select exactly {required_snacks} snacks. You selected {total_snacks}.')
                                        has_errors = True
                                    if required_juices > 0 and total_juices != required_juices:
                                        messages.error(request, f'Please select exactly {required_juices} juices. You selected {total_juices}.')
                                        has_errors = True
                                
                                if not has_errors:
                                    # Restore old stock quantities
                                    for item_id, old_quantity in existing_order_items.items():
                                        try:
                                            item = Item.objects.get(id=item_id)
                                            item.current_stock += old_quantity
                                            item.save()
                                        except Item.DoesNotExist:
                                            pass
                                    
                                    # Delete old order items
                                    order.order_items.all().delete()
                                    
                                    # Create new order items and update stock
                                    for item, quantity in selected_snacks + selected_juices:
                                        OrderItem.objects.create(order=order, item=item, quantity=quantity)
                                        item.current_stock -= quantity
                                        item.save()
                                    
                                    # Refresh order to ensure order_items relationship is loaded
                                    order.refresh_from_db()
                                    order.save()
                                    order.calculate_totals()
                                    messages.success(request, f'Order #{order.id} updated successfully!')
                                    return redirect('admin_order_records')
                        else:
                            # Update financials for back-dated orders using direct update to avoid calculate_totals()
                            revenue_decimal = Decimal(total_revenue)
                            cost_decimal = Decimal(total_cost)
                            profit_decimal = Decimal(net_profit) if net_profit else (revenue_decimal - cost_decimal)
                            margin = (profit_decimal / revenue_decimal * 100) if revenue_decimal > 0 else Decimal('0')
                            
                            # Use direct update to avoid triggering calculate_totals() in save()
                            Order.objects.filter(id=order.id).update(
                                bundle_type=bundle_type,
                                total_revenue=revenue_decimal,
                                total_cost=cost_decimal,
                                net_profit=profit_decimal,
                                profit_margin=margin
                            )
                            messages.success(request, f'Order #{order.id} updated successfully!')
                            return redirect('admin_order_records')
                    except Exception as e:
                        messages.error(request, f'An error occurred: {str(e)}')
    
    # Determine current order type from bundle
    current_order_type = ''
    current_custom_name = ''
    if order.bundle_type:
        bundle_name = order.bundle_type.name
        if bundle_name == '10 Snacks':
            current_order_type = '10_snacks'
        elif bundle_name == '25 Snacks':
            current_order_type = '25_snacks'
        elif bundle_name == '25 Juices':
            current_order_type = '25_juices'
        elif bundle_name == 'Mega Mix':
            current_order_type = 'mega_mix'
        else:
            current_order_type = 'custom'
            current_custom_name = bundle_name
    
    # Determine if order uses inventory (has order items)
    has_order_items = order.order_items.exists()
    
    # Set default date
    from django.utils import timezone
    order_date = order.created_at.strftime('%Y-%m-%d') if order.created_at else timezone.now().strftime('%Y-%m-%d')
    
    context = {
        'order': order,
        'snacks': snacks,
        'juices': juices,
        'snacks_with_data': snacks_with_data,
        'juices_with_data': juices_with_data,
        'existing_order_items': existing_order_items,
        'customer_name': order.customer.name,
        'customer_phone': order.customer.phone or '',
        'pickup_spot': order.customer.pickup_spot or '',
        'order_date': order_date,
        'order_type': current_order_type,
        'custom_order_name': current_custom_name,
        'total_revenue': str(order.total_revenue),
        'total_cost': str(order.total_cost),
        'net_profit': str(order.net_profit),
        'use_inventory': has_order_items,
    }
    return render(request, 'admin/edit_order.html', context)


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


# ============================================
# Customer Order Management
# ============================================

@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
def admin_customer_orders(request):
    """View all customer orders"""
    from .models import CustomerOrder
    from django.db.models import Sum
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    orders = CustomerOrder.objects.all().order_by('-created_at')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Calculate totals
    pending_count = CustomerOrder.objects.filter(status='pending_approval').count()
    payment_uploaded_count = CustomerOrder.objects.filter(status='payment_uploaded').count()
    
    context = {
        'orders': orders,
        'status_filter': status_filter,
        'pending_count': pending_count,
        'payment_uploaded_count': payment_uploaded_count,
        'status_choices': CustomerOrder.STATUS_CHOICES,
    }
    return render(request, 'admin/customer_orders.html', context)


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
@csrf_protect
@require_http_methods(["GET", "POST"])
def admin_customer_order_detail(request, order_id):
    """View and manage a single customer order"""
    from .models import CustomerOrder, CustomerOrderItem
    
    order = get_object_or_404(CustomerOrder, id=order_id)
    order_items = order.customer_order_items.select_related('item')
    target_margin = Decimal(request.session.get('admin_margin_target', '38'))
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            # Set price for custom bundles
            new_price = request.POST.get('new_price', '').strip()
            admin_notes = request.POST.get('admin_notes', '').strip()
            
            # Calculate minimum price for 38% margin
            margin_factor = Decimal('0.62')  # 1 - 0.38
            min_price = order.total_cost / margin_factor
            
            if order.bundle_type == 'custom' and not new_price:
                messages.error(request, 'Please set a price for this custom bundle.')
            else:
                # Determine price to use
                if new_price:
                    try:
                        price_decimal = Decimal(new_price)
                    except (ValueError, InvalidOperation):
                        messages.error(request, 'Invalid price format.')
                        price_decimal = None
                else:
                    # Fixed bundle - use current revenue
                    price_decimal = order.total_revenue
                
                if price_decimal:
                    # Validate that price achieves at least 38% margin
                    if price_decimal < min_price:
                        messages.error(request, f'Price must be at least ${min_price:.0f} JMD to achieve 38% margin. Current price (${price_decimal:.0f}) would result in {(price_decimal - order.total_cost) / price_decimal * 100:.1f}% margin.')
                        # Don't redirect, show error and stay on page
                    else:
                        order.total_revenue = price_decimal
                        order.net_profit = order.total_revenue - order.total_cost
                        if order.total_revenue > 0:
                            order.profit_margin = (order.net_profit / order.total_revenue) * 100
                        
                        order.status = 'approved'
                        order.admin_notes = admin_notes
                        order.approved_at = timezone.now()
                        order.approved_by = request.user
                        order.save()
                        messages.success(request, f'Order {order.order_reference} approved with {order.profit_margin:.1f}% margin!')
                        return redirect('admin_customer_orders')
        
        elif action == 'verify_payment':
            order.status = 'payment_verified'
            order.save()
            messages.success(request, f'Payment for {order.order_reference} verified!')
            return redirect('admin_customer_orders')
        
        elif action == 'mark_processing':
            order.status = 'processing'
            order.save()
            messages.success(request, f'Order {order.order_reference} marked as processing.')
            return redirect('admin_customer_orders')
        
        elif action == 'mark_completed':
            order.status = 'completed'
            order.save()
            messages.success(request, f'Order {order.order_reference} completed!')
            return redirect('admin_customer_orders')
        
        elif action == 'cancel':
            order.status = 'cancelled'
            order.admin_notes = request.POST.get('admin_notes', '')
            order.save()
            messages.success(request, f'Order {order.order_reference} cancelled.')
            return redirect('admin_customer_orders')
        
        elif action == 'update_items':
            # Update item quantities
            for item in order_items:
                qty_key = f'qty_{item.id}'
                new_qty = request.POST.get(qty_key, '').strip()
                if new_qty:
                    try:
                        item.quantity = int(new_qty)
                        item.save()
                    except ValueError:
                        pass
            
            # Recalculate totals
            order.total_cost = sum(
                item.item.cost_price * Decimal(str(item.quantity))
                for item in order.customer_order_items.select_related('item')
            )
            
            # If revenue is already set, recalculate margin and warn if below 38%
            if order.total_revenue > 0:
                order.net_profit = order.total_revenue - order.total_cost
                if order.total_revenue > 0:
                    order.profit_margin = (order.net_profit / order.total_revenue) * 100
                    if order.profit_margin < 38:
                        min_price = order.total_cost / Decimal('0.62')
                        messages.warning(request, f'Current revenue results in {order.profit_margin:.1f}% margin. Minimum price for 38% margin is ${min_price:.0f} JMD.')
            
            order.save()
            messages.success(request, 'Item quantities updated.')

        elif action == 'rerun_algo':
            # Re-run algorithm to redistribute quantities based on margin input
            try:
                margin_input = Decimal(request.POST.get('target_margin', '38').strip())
            except Exception:
                margin_input = Decimal('38')

            if margin_input < 38:
                margin_input = Decimal('38')
            target_margin = margin_input
            request.session['admin_margin_target'] = str(margin_input)

            # Build item lists from current order items
            snack_items = []
            juice_items = []
            starred_snacks = []
            starred_juices = []
            snack_total = 0
            juice_total = 0

            for item in order_items:
                if item.item.category == 'snack':
                    snack_items.append(item.item)
                    snack_total += item.quantity
                    if item.is_starred:
                        starred_snacks.append(item.item.id)
                elif item.item.category == 'juice':
                    juice_items.append(item.item)
                    juice_total += item.quantity
                    if item.is_starred:
                        starred_juices.append(item.item.id)

            from .views import calculate_custom_bundle_quantities
            calc_result = calculate_custom_bundle_quantities(
                snack_items, juice_items, starred_snacks, starred_juices,
                required_snack_qty=snack_total,
                required_juice_qty=juice_total,
                target_margin=float(margin_input)
            )

            # Update quantities
            new_quantities = calc_result.get('quantities', {})
            for item in order_items:
                if item.item_id in new_quantities:
                    item.quantity = int(new_quantities[item.item_id])
                    item.save()

            # Recalculate totals
            order.total_cost = sum(
                item.item.cost_price * Decimal(str(item.quantity))
                for item in order.customer_order_items.select_related('item')
            )
            
            # For fixed bundles, keep adjusting until margin is met
            if order.bundle_type != 'custom' and order.total_revenue > 0:
                # Fixed bundle - adjust until margin is at least 38%
                max_allowed_cost = order.total_revenue * Decimal('0.62')
                all_items_dict = {item.item.id: item.item for item in order_items}
                max_iterations = 100
                iteration = 0
                
                while order.total_cost > max_allowed_cost and iteration < max_iterations:
                    iteration += 1
                    
                    # Shift from expensive to cheap
                    all_items_list = []
                    for item in order_items:
                        if item.quantity > 0:
                            all_items_list.append((item.item.id, item.item, item.quantity))
                    
                    if not all_items_list:
                        break
                    
                    all_items_list.sort(key=lambda x: x[1].cost_price)
                    expensive_items = [x for x in all_items_list if x[2] > 1]
                    cheap_items = [x for x in all_items_list]
                    starred_ids_set = set(starred_snacks + starred_juices)
                    
                    shifted = False
                    for exp_item_id, exp_item, exp_qty in reversed(expensive_items):
                        if shifted:
                            break
                        
                        if exp_item_id in starred_ids_set:
                            min_starred = min((qty for item_id, _, qty in all_items_list if item_id in starred_ids_set), default=0)
                            min_non_starred = min((qty for item_id, _, qty in all_items_list if item_id not in starred_ids_set), default=0)
                            if exp_qty <= max(min_non_starred + 1, 2):
                                continue
                        
                        for cheap_item_id, cheap_item, cheap_qty in cheap_items:
                            if cheap_item_id == exp_item_id:
                                continue
                            if cheap_item_id not in starred_ids_set and exp_item_id in starred_ids_set:
                                continue
                            
                            # Find the order item and update
                            for oi in order_items:
                                if oi.item_id == exp_item_id:
                                    oi.quantity -= 1
                                    oi.save()
                                elif oi.item_id == cheap_item_id:
                                    oi.quantity += 1
                                    oi.save()
                            shifted = True
                            break
                    
                    if not shifted:
                        break
                    
                    # Recalculate cost
                    order.total_cost = sum(
                        item.item.cost_price * Decimal(str(item.quantity))
                        for item in order.customer_order_items.select_related('item')
                    )
            
            # Recalculate margin
            if order.total_revenue > 0:
                order.net_profit = order.total_revenue - order.total_cost
                if order.total_revenue > 0:
                    order.profit_margin = (order.net_profit / order.total_revenue) * 100
            
            order.save()

            if order.bundle_type == 'custom':
                messages.success(request, f'Algorithm re-run with {margin_input}% margin target. Suggested price: ${calc_result.get("suggested_price", 0):.0f} JMD.')
            else:
                messages.success(request, f'Algorithm re-run with {margin_input}% margin target. Current margin: {order.profit_margin:.1f}%.')
    
    # Calculate suggested price for custom bundles (target margin)
    suggested_price = None
    if order.bundle_type == 'custom' and order.total_cost > 0:
        margin_factor = Decimal(str(1 - float(target_margin) / 100))
        if margin_factor > 0:
            suggested_price = int(order.total_cost / margin_factor / 100) * 100 + 100

    suggested_profit = None
    suggested_margin = None
    if suggested_price and order.total_cost > 0:
        suggested_profit = Decimal(str(suggested_price)) - order.total_cost
        if suggested_price > 0:
            suggested_margin = (suggested_profit / Decimal(str(suggested_price))) * 100
    
    context = {
        'order': order,
        'order_items': order_items,
        'suggested_price': suggested_price,
        'suggested_profit': suggested_profit,
        'suggested_margin': suggested_margin,
        'target_margin': target_margin,
    }
    return render(request, 'admin/customer_order_detail.html', context)


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
def admin_banking_info(request):
    """Manage banking information"""
    from .models import BankingInfo
    
    banking_info = BankingInfo.objects.all().order_by('bank_name')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add':
            bank_name = request.POST.get('bank_name', '').strip()
            account_name = request.POST.get('account_name', '').strip()
            account_number = request.POST.get('account_number', '').strip()
            account_type = request.POST.get('account_type', '').strip()
            branch = request.POST.get('branch', '').strip()
            additional_info = request.POST.get('additional_info', '').strip()
            
            if bank_name and account_name and account_number:
                BankingInfo.objects.create(
                    bank_name=bank_name,
                    account_name=account_name,
                    account_number=account_number,
                    account_type=account_type,
                    branch=branch,
                    additional_info=additional_info,
                    is_active=True
                )
                messages.success(request, 'Banking info added!')
            else:
                messages.error(request, 'Please fill in required fields.')
        
        elif action == 'delete':
            bank_id = request.POST.get('bank_id')
            BankingInfo.objects.filter(id=bank_id).delete()
            messages.success(request, 'Banking info deleted.')
        
        elif action == 'toggle':
            bank_id = request.POST.get('bank_id')
            bank = get_object_or_404(BankingInfo, id=bank_id)
            bank.is_active = not bank.is_active
            bank.save()
            messages.success(request, f'Banking info {"activated" if bank.is_active else "deactivated"}.')
        
        return redirect('admin_banking_info')
    
    context = {
        'banking_info': banking_info,
    }
    return render(request, 'admin/banking_info.html', context)
