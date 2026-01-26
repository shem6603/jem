from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from .models import Item, BundleType, Customer, Order, OrderItem, CustomerOrder, CustomerOrderItem, BankingInfo, PushSubscription


def csrf_failure(request, reason=""):
    """Custom CSRF failure view"""
    messages.error(request, 'Security error: Invalid request. Please refresh the page and try again.')
    return redirect('core:home')


def offline(request):
    """Offline page for PWA"""
    return render(request, 'core/offline.html')


def privacy_policy(request):
    """Privacy policy page - required for app store listings (e.g. Google Play)"""
    return render(request, 'core/privacy.html')


def is_staff_user(user):
    """Check if user is staff"""
    return user.is_authenticated and user.is_staff


def favicon_ico(request):
    """Handle favicon.ico requests - redirect to PNG favicon"""
    from django.contrib.staticfiles.storage import staticfiles_storage
    try:
        return HttpResponseRedirect(staticfiles_storage.url('favicons/favicon.png'))
    except:
        # Return 204 No Content if favicon doesn't exist
        from django.http import HttpResponse
        return HttpResponse(status=204)


def home(request):
    """Customer-facing home page"""
    bundle_types = BundleType.objects.filter(is_active=True)
    context = {
        'bundle_types': bundle_types,
    }
    return render(request, 'core/home.html', context)


def dashboard(request):
    """Admin Dashboard - Profit Center"""
    # Calculate all-time totals from admin orders (Order model)
    all_admin_orders = Order.objects.filter(status='completed')
    admin_revenue = all_admin_orders.aggregate(Sum('total_revenue'))['total_revenue__sum'] or Decimal('0.00')
    admin_cost = all_admin_orders.aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0.00')
    admin_profit = all_admin_orders.aggregate(Sum('net_profit'))['net_profit__sum'] or Decimal('0.00')
    
    # Calculate all-time totals from customer orders (CustomerOrder model)
    all_customer_orders = CustomerOrder.objects.filter(status='completed')
    customer_revenue = all_customer_orders.aggregate(Sum('total_revenue'))['total_revenue__sum'] or Decimal('0.00')
    customer_cost = all_customer_orders.aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0.00')
    customer_profit = all_customer_orders.aggregate(Sum('net_profit'))['net_profit__sum'] or Decimal('0.00')
    
    # Combine totals from both order types
    total_revenue = admin_revenue + customer_revenue
    total_cost = admin_cost + customer_cost
    total_net_profit = admin_profit + customer_profit
    
    # Current inventory levels
    items = Item.objects.all().order_by('category', 'name')
    low_stock_items = items.filter(current_stock__lt=5)
    
    # Recent sales (last 10 orders from both types)
    recent_admin_sales = list(all_admin_orders[:10])
    recent_customer_sales = list(all_customer_orders[:10])
    recent_sales = (recent_admin_sales + recent_customer_sales)[:10]
    
    # Calculate average profit margin (combining both order types)
    total_orders_count = all_admin_orders.count() + all_customer_orders.count()
    if total_orders_count > 0:
        # Calculate weighted average margin
        admin_margin_sum = all_admin_orders.aggregate(Sum('profit_margin'))['profit_margin__sum'] or Decimal('0.00')
        customer_margin_sum = all_customer_orders.aggregate(Sum('profit_margin'))['profit_margin__sum'] or Decimal('0.00')
        total_margin_sum = admin_margin_sum + customer_margin_sum
        avg_margin = float(total_margin_sum) / total_orders_count if total_orders_count > 0 else 0
    else:
        avg_margin = 0
    
    context = {
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'total_net_profit': total_net_profit,
        'items': items,
        'low_stock_items': low_stock_items,
        'recent_sales': recent_sales,
        'avg_margin': avg_margin,
        'total_orders': total_orders_count,
    }
    
    return render(request, 'core/dashboard.html', context)


@login_required
@user_passes_test(is_staff_user, login_url='admin_login')
def inventory(request):
    """Inventory management view"""
    items = Item.objects.all().order_by('category', 'name')
    
    # Group by category
    snacks = items.filter(category='snack')
    juices = items.filter(category='juice')
    
    context = {
        'items': items,
        'snacks': snacks,
        'juices': juices,
    }
    
    return render(request, 'core/inventory.html', context)


# ============================================
# Customer Ordering System
# ============================================

# Bundle prices
BUNDLE_PRICES = {
    '10_snacks': Decimal('1000.00'),
    '25_snacks': Decimal('3000.00'),
    '25_juices': Decimal('2700.00'),
    'mega_mix': Decimal('5500.00'),
}

# Bundle requirements
BUNDLE_REQUIREMENTS = {
    '10_snacks': {'snacks': 10, 'juices': 0},
    '25_snacks': {'snacks': 25, 'juices': 0},
    '25_juices': {'snacks': 0, 'juices': 25},
    'mega_mix': {'snacks': 30, 'juices': 24},
    'custom': {'min_snacks': 0, 'min_juices': 0},  # Customer specifies quantities
}


def bundle_builder(request):
    """Step 1: Select Bundle Type"""
    # Clear any existing session data when starting fresh
    if request.method == 'GET' and 'fresh' in request.GET:
        for key in ['bundle_type', 'excluded_snacks', 'excluded_juices', 
                    'starred_snacks', 'starred_juices', 'custom_snack_qty', 'custom_juice_qty', 'selection_mode']:
            request.session.pop(key, None)
    
    if request.method == 'POST':
        bundle_type = request.POST.get('bundle_type')
        selection_mode = request.POST.get('selection_mode', 'select')  # 'select' or 'random'
        
        if bundle_type == 'custom':
            # Validate custom quantities using security utilities
            from .security import validate_integer
            
            snack_valid, custom_snack_qty, snack_error = validate_integer(
                request.POST.get('custom_snack_qty', 0) or 0,
                min_value=0,
                max_value=1000,
                allow_zero=True
            )
            juice_valid, custom_juice_qty, juice_error = validate_integer(
                request.POST.get('custom_juice_qty', 0) or 0,
                min_value=0,
                max_value=1000,
                allow_zero=True
            )
            
            if not snack_valid or not juice_valid:
                messages.error(request, 'Invalid quantity values. Please enter valid numbers.')
                return redirect('core:bundle_builder')
            
            # Validate: minimum 10 snacks OR 10 juices OR (10 snacks AND 10 juices)
            valid = False
            if custom_snack_qty >= 10 and custom_juice_qty == 0:
                valid = True  # 10+ snacks, no juices
            elif custom_juice_qty >= 10 and custom_snack_qty == 0:
                valid = True  # 10+ juices, no snacks
            elif custom_snack_qty >= 10 and custom_juice_qty >= 10:
                valid = True  # 10+ of each
            
            if not valid:
                messages.error(request, 'Custom bundle requires: minimum 10 snacks (with 0 juices), OR minimum 10 juices (with 0 snacks), OR minimum 10 snacks AND 10 juices.')
            else:
                request.session['bundle_type'] = bundle_type
                request.session['custom_snack_qty'] = custom_snack_qty
                request.session['custom_juice_qty'] = custom_juice_qty
                request.session['selection_mode'] = selection_mode
                
                # If random mode, skip selection and go directly to details
                if selection_mode == 'random':
                    # Clear any previous selections
                    request.session['excluded_snacks'] = []
                    request.session['excluded_juices'] = []
                    request.session['starred_snacks'] = []
                    request.session['starred_juices'] = []
                    return redirect('core:bundle_builder_details')
                else:
                    return redirect('core:bundle_builder_select')
        
        elif bundle_type in BUNDLE_REQUIREMENTS:
            request.session['bundle_type'] = bundle_type
            request.session['selection_mode'] = selection_mode
            
            # If random mode, skip selection and go directly to details
            if selection_mode == 'random':
                # Clear any previous selections
                request.session['excluded_snacks'] = []
                request.session['excluded_juices'] = []
                request.session['starred_snacks'] = []
                request.session['starred_juices'] = []
                return redirect('core:bundle_builder_details')
            else:
                return redirect('core:bundle_builder_select')
        else:
            messages.error(request, 'Please select a valid bundle type.')
    
    context = {
        'bundle_prices': BUNDLE_PRICES,
    }
    return render(request, 'core/order_step1_bundle.html', context)


def bundle_builder_select(request):
    """Step 2: Select items to INCLUDE in the bundle (inclusion model)"""
    bundle_type = request.session.get('bundle_type')
    if not bundle_type:
        messages.error(request, 'Please select a bundle type first.')
        return redirect('core:bundle_builder')
    
    requirements = BUNDLE_REQUIREMENTS[bundle_type]
    all_snacks = Item.objects.filter(category='snack', current_stock__gt=0).order_by('name')
    all_juices = Item.objects.filter(category='juice', current_stock__gt=0).order_by('name')
    
    # Get custom quantities if applicable
    custom_snack_qty = request.session.get('custom_snack_qty', 0)
    custom_juice_qty = request.session.get('custom_juice_qty', 0)
    
    # Get previously selected items from session (items customer wants)
    # For backward compatibility, we'll convert from excluded to selected if needed
    excluded_snacks = request.session.get('excluded_snacks', [])
    excluded_juices = request.session.get('excluded_juices', [])
    selected_snacks = request.session.get('selected_snacks', [])
    selected_juices = request.session.get('selected_juices', [])
    starred_snacks = request.session.get('starred_snacks', [])
    starred_juices = request.session.get('starred_juices', [])
    
    # If we have excluded items but no selected items, convert (backward compatibility)
    if excluded_snacks or excluded_juices:
        if not selected_snacks and not selected_juices:
            all_snack_ids = list(all_snacks.values_list('id', flat=True))
            all_juice_ids = list(all_juices.values_list('id', flat=True))
            selected_snacks = [sid for sid in all_snack_ids if sid not in excluded_snacks]
            selected_juices = [jid for jid in all_juice_ids if jid not in excluded_juices]
            request.session['selected_snacks'] = selected_snacks
            request.session['selected_juices'] = selected_juices
            # Clear old excluded items
            request.session.pop('excluded_snacks', None)
            request.session.pop('excluded_juices', None)
    
    if request.method == 'POST':
        # Get selected items (checkboxes - items customer wants)
        selected_snack_ids = [int(x) for x in request.POST.getlist('selected_snacks')]
        selected_juice_ids = [int(x) for x in request.POST.getlist('selected_juices')]
        
        # Get starred items (max 2 each) - these are from the selected items
        # Validate IDs to prevent injection
        from .security import validate_integer
        
        starred_snack_ids = []
        for snack_id_str in request.POST.getlist('starred_snacks')[:2]:
            is_valid, snack_id, error = validate_integer(snack_id_str, min_value=1, allow_zero=False)
            if is_valid:
                starred_snack_ids.append(snack_id)
        
        starred_juice_ids = []
        for juice_id_str in request.POST.getlist('starred_juices')[:2]:
            is_valid, juice_id, error = validate_integer(juice_id_str, min_value=1, allow_zero=False)
            if is_valid:
                starred_juice_ids.append(juice_id)
        
        # Validation: minimum selection requirements
        errors = []
        
        # Minimum selection requirements
        MIN_SNACKS = 5
        MIN_JUICES = 3
        
        # If customer selects any items, they must meet minimum requirements
        # If they select 0 items, that's fine (they can use random selection)
        
        if bundle_type in ['10_snacks', '25_snacks', 'mega_mix']:
            if len(selected_snack_ids) > 0 and len(selected_snack_ids) < MIN_SNACKS:
                errors.append(f'You must select at least {MIN_SNACKS} different snacks. Currently selected: {len(selected_snack_ids)}')
        if bundle_type in ['25_juices', 'mega_mix']:
            if len(selected_juice_ids) > 0 and len(selected_juice_ids) < MIN_JUICES:
                errors.append(f'You must select at least {MIN_JUICES} different juices. Currently selected: {len(selected_juice_ids)}')
        elif bundle_type == 'custom':
            # Validate based on what customer requested
            if custom_snack_qty > 0 and len(selected_snack_ids) > 0 and len(selected_snack_ids) < MIN_SNACKS:
                errors.append(f'You must select at least {MIN_SNACKS} different snacks. Currently selected: {len(selected_snack_ids)}')
            if custom_juice_qty > 0 and len(selected_juice_ids) > 0 and len(selected_juice_ids) < MIN_JUICES:
                errors.append(f'You must select at least {MIN_JUICES} different juices. Currently selected: {len(selected_juice_ids)}')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Save to session (selected items and starred items)
            # Calculate excluded items (all items minus selected) for the algorithm
            all_snack_ids = list(all_snacks.values_list('id', flat=True))
            all_juice_ids = list(all_juices.values_list('id', flat=True))
            excluded_snack_ids = [sid for sid in all_snack_ids if sid not in selected_snack_ids]
            excluded_juice_ids = [jid for jid in all_juice_ids if jid not in selected_juice_ids]
            
            request.session['selected_snacks'] = selected_snack_ids
            request.session['selected_juices'] = selected_juice_ids
            request.session['excluded_snacks'] = excluded_snack_ids  # For algorithm compatibility
            request.session['excluded_juices'] = excluded_juice_ids  # For algorithm compatibility
            request.session['starred_snacks'] = starred_snack_ids
            request.session['starred_juices'] = starred_juice_ids
            return redirect('core:bundle_builder_details')
    
    # Determine which sections to show
    if bundle_type == 'custom':
        show_snacks = custom_snack_qty > 0
        show_juices = custom_juice_qty > 0
    else:
        show_snacks = bundle_type in ['10_snacks', '25_snacks', 'mega_mix']
        show_juices = bundle_type in ['25_juices', 'mega_mix']
    
    context = {
        'bundle_type': bundle_type,
        'bundle_type_display': dict(CustomerOrder.BUNDLE_TYPE_CHOICES).get(bundle_type, bundle_type),
        'requirements': requirements,
        'snacks': all_snacks,
        'juices': all_juices,
        'selected_snacks': selected_snacks,
        'selected_juices': selected_juices,
        'excluded_snacks': excluded_snacks,  # For backward compatibility in template
        'excluded_juices': excluded_juices,  # For backward compatibility in template
        'starred_snacks': starred_snacks,
        'starred_juices': starred_juices,
        'show_snacks': show_snacks,
        'show_juices': show_juices,
        'is_custom': bundle_type == 'custom',
        'bundle_price': BUNDLE_PRICES.get(bundle_type),
        'custom_snack_qty': custom_snack_qty,
        'custom_juice_qty': custom_juice_qty,
    }
    return render(request, 'core/order_step2_select.html', context)


def bundle_builder_details(request):
    """Step 3: Enter customer details and submit order"""
    bundle_type = request.session.get('bundle_type')
    excluded_snacks = request.session.get('excluded_snacks', [])
    excluded_juices = request.session.get('excluded_juices', [])
    selected_snacks = request.session.get('selected_snacks', [])
    selected_juices = request.session.get('selected_juices', [])
    starred_snacks = request.session.get('starred_snacks', [])
    starred_juices = request.session.get('starred_juices', [])
    custom_snack_qty = request.session.get('custom_snack_qty', 0)
    custom_juice_qty = request.session.get('custom_juice_qty', 0)
    
    if not bundle_type:
        messages.error(request, 'Please start from the beginning.')
        return redirect('core:bundle_builder')
    
    # Get all available items
    all_snacks = Item.objects.filter(category='snack', current_stock__gt=0)
    all_juices = Item.objects.filter(category='juice', current_stock__gt=0)
    
    # Determine which items to use: if selected items exist (inclusion model), use only those
    # Otherwise, use all items minus excluded (exclusion model)
    if selected_snacks or selected_juices:
        # Inclusion model: only use selected items
        snack_items = [item for item in all_snacks if item.id in selected_snacks]
        juice_items = [item for item in all_juices if item.id in selected_juices]
        # Calculate excluded items (all items minus selected) for algorithm
        all_snack_ids = list(all_snacks.values_list('id', flat=True))
        all_juice_ids = list(all_juices.values_list('id', flat=True))
        excluded_item_ids = [sid for sid in all_snack_ids if sid not in selected_snacks] + \
                           [jid for jid in all_juice_ids if jid not in selected_juices]
    else:
        # Exclusion model: use all items minus excluded
        snack_items = [item for item in all_snacks if item.id not in excluded_snacks]
        juice_items = [item for item in all_juices if item.id not in excluded_juices]
        excluded_item_ids = excluded_snacks + excluded_juices
    
    if not snack_items and not juice_items:
        messages.error(request, 'Please include at least one item in your bundle.')
        return redirect('core:bundle_builder_select')
    
    # Calculate for display using the new smart bundle algorithm
    from .utils import generate_smart_bundle
    
    is_custom = bundle_type == 'custom'
    
    # Get customer favorites (starred items) - must be from selected/included items
    customer_favorites = []
    for item in snack_items:
        if item.id in starred_snacks:
            customer_favorites.append(item)
    for item in juice_items:
        if item.id in starred_juices:
            customer_favorites.append(item)
    
    if is_custom:
        # Custom bundle - calculate suggested price based on 38% margin
        # First, we need to estimate the price
        bundle_config = {
            'name': 'Custom Bundle',
            'selling_price': Decimal('0'),  # Will be calculated
            'snack_limit': custom_snack_qty,
            'juice_limit': custom_juice_qty,
            'packaging_cost': Decimal('0'),
        }
        
        # Run algorithm to get cost estimate first
        result = generate_smart_bundle(bundle_config, customer_favorites, excluded_item_ids)
        
        # For custom, suggested_price is calculated based on cost + 38% margin
        total_cost = result['total_cost']
        margin_factor = Decimal('0.62')  # 1 - 0.38
        suggested_price = (int(total_cost / margin_factor / 100) + 1) * 100
        
        # Re-run with the calculated price to ensure margin
        bundle_config['selling_price'] = suggested_price
        result = generate_smart_bundle(bundle_config, customer_favorites, excluded_item_ids)
        total_cost = result['total_cost']
        
    else:
        # Fixed bundle - use fixed price
        requirements = BUNDLE_REQUIREMENTS[bundle_type]
        fixed_price = BUNDLE_PRICES[bundle_type]
        
        bundle_config = {
            'name': dict(CustomerOrder.BUNDLE_TYPE_CHOICES).get(bundle_type, bundle_type),
            'selling_price': fixed_price,
            'snack_limit': requirements.get('snacks', 0),
            'juice_limit': requirements.get('juices', 0),
            'packaging_cost': Decimal('0'),
        }
        
        # Run the smart bundle algorithm
        result = generate_smart_bundle(bundle_config, customer_favorites, excluded_item_ids)
        total_cost = result['total_cost']
        suggested_price = fixed_price
    
    # Convert result to quantities dict for backward compatibility
    quantities = {}
    for item, qty, is_fav in result['selected_snacks']:
        quantities[item.id] = qty
    for item, qty, is_fav in result['selected_juices']:
        quantities[item.id] = qty
    
    # Prepare items with quantities for display (include subtotal cost)
    snacks_with_qty = [
        (item, qty, is_fav, item.cost_price * Decimal(str(qty))) 
        for item, qty, is_fav in result['selected_snacks'] if qty > 0
    ]
    juices_with_qty = [
        (item, qty, is_fav, item.cost_price * Decimal(str(qty))) 
        for item, qty, is_fav in result['selected_juices'] if qty > 0
    ]
    
    # Get banking info
    banking_info = BankingInfo.objects.filter(is_active=True).first()
    
    if request.method == 'POST':
        # Sanitize and validate user inputs
        from .security import sanitize_string, validate_phone_number
        
        customer_name = sanitize_string(request.POST.get('customer_name', ''), max_length=200)
        customer_phone_raw = request.POST.get('customer_phone', '').strip()
        customer_whatsapp_raw = request.POST.get('customer_whatsapp', '').strip()
        pickup_spot = sanitize_string(request.POST.get('pickup_spot', ''), max_length=200)
        
        # Validate phone numbers
        phone_valid, customer_phone = validate_phone_number(customer_phone_raw)
        if not phone_valid and customer_phone_raw:
            messages.error(request, 'Invalid phone number format. Please use format: 1-876-XXX-XXXX')
            return redirect('core:bundle_builder_details')
        
        whatsapp_valid, customer_whatsapp = validate_phone_number(customer_whatsapp_raw)
        if not whatsapp_valid and customer_whatsapp_raw:
            messages.error(request, 'Invalid WhatsApp number format. Please use format: 1-876-XXX-XXXX')
            return redirect('core:bundle_builder_details')
        
        if not customer_whatsapp:
            customer_whatsapp = customer_phone  # Use phone if WhatsApp not provided
        
        errors = []
        if not customer_name:
            errors.append('Name is required.')
        if not customer_phone:
            errors.append('Phone number is required.')
        if not pickup_spot:
            errors.append('Pickup spot is required.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Create the order
            status = 'pending_approval' if is_custom else 'approved'
            
            order = CustomerOrder.objects.create(
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_whatsapp=customer_whatsapp or customer_phone,
                pickup_spot=pickup_spot,
                bundle_type=bundle_type,
                status=status,
                total_revenue=suggested_price if not is_custom else Decimal('0'),  # Custom waits for approval
                total_cost=total_cost,
            )
            
            # Create order items from the smart bundle result
            for item, qty, is_fav in result['selected_snacks']:
                if qty > 0:
                    CustomerOrderItem.objects.create(
                        order=order,
                        item=item,
                        quantity=qty,
                        is_starred=is_fav
                    )
            for item, qty, is_fav in result['selected_juices']:
                if qty > 0:
                    CustomerOrderItem.objects.create(
                        order=order,
                        item=item,
                        quantity=qty,
                        is_starred=is_fav
                    )
            
            # Calculate totals for non-custom
            if not is_custom:
                order.total_revenue = suggested_price
                order.net_profit = result['estimated_profit']
                order.profit_margin = result['profit_margin']
                
                # Validate margin is at least 38%
                if not result['success']:
                    # Algorithm couldn't achieve target margin, set status to pending_approval
                    # Don't show error message to customer - admin will handle it
                    order.status = 'pending_approval'
                
                order.save()
            
            # Send email notification to admin when order is created
            try:
                from .email_utils import send_order_notification_to_admin
                email_sent = send_order_notification_to_admin(order)
                if email_sent:
                    print(f"Order notification email sent successfully for order {order.order_reference}")
                else:
                    print(f"Warning: Order notification email failed for order {order.order_reference}")
            except Exception as e:
                # Don't fail order creation if email fails
                print(f"Error sending order notification email: {e}")
                import traceback
                traceback.print_exc()
            
            # Clear session
            for key in ['bundle_type', 'selected_snacks', 'selected_juices', 'starred_snacks', 'starred_juices']:
                request.session.pop(key, None)
            
            # Redirect to appropriate page
            if is_custom:
                return redirect('core:order_pending', order_ref=order.order_reference)
            else:
                return redirect('core:order_payment', order_ref=order.order_reference)
    
    snack_total_units = sum(
        qty for item_id, qty in quantities.items()
        if item_id in {item.id for item in snack_items}
    )
    juice_total_units = sum(
        qty for item_id, qty in quantities.items()
        if item_id in {item.id for item in juice_items}
    )

    context = {
        'bundle_type': bundle_type,
        'bundle_type_display': dict(CustomerOrder.BUNDLE_TYPE_CHOICES).get(bundle_type, bundle_type),
        'is_custom': is_custom,
        'snacks_with_qty': snacks_with_qty,
        'juices_with_qty': juices_with_qty,
        'total_items': sum(quantities.values()),
        'snack_total_units': snack_total_units,
        'juice_total_units': juice_total_units,
        'bundle_price': None if is_custom else suggested_price,
        'banking_info': banking_info,
    }
    return render(request, 'core/order_step3_details.html', context)


def order_pending(request, order_ref):
    """Page shown to customers with custom bundles waiting for approval"""
    order = get_object_or_404(CustomerOrder, order_reference=order_ref)
    
    if not order.is_custom or order.status != 'pending_approval':
        return redirect('core:order_status', order_ref=order_ref)
    
    context = {
        'order': order,
    }
    return render(request, 'core/order_pending.html', context)


def order_payment(request, order_ref):
    """Payment page - show banking info and allow payment proof upload"""
    order = get_object_or_404(CustomerOrder, order_reference=order_ref)
    
    if order.status == 'pending_approval':
        return redirect('core:order_pending', order_ref=order_ref)
    
    if order.status in ['payment_verified', 'processing', 'completed']:
        return redirect('core:order_status', order_ref=order_ref)
    
    banking_info = BankingInfo.objects.filter(is_active=True)
    
    if request.method == 'POST':
        payment_proof = request.FILES.get('payment_proof')
        payment_method = request.POST.get('payment_method', '').strip()
        
        if payment_proof:
            # Validate file upload for security
            from .security import validate_file_upload, sanitize_string, ALLOWED_DOCUMENT_EXTENSIONS, MAX_IMAGE_SIZE
            
            is_valid, error_msg = validate_file_upload(
                payment_proof, 
                allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS,
                max_size=MAX_IMAGE_SIZE
            )
            
            if not is_valid:
                messages.error(request, f'Security validation failed: {error_msg}')
                return render(request, 'core/order_payment.html', {
                    'order': order,
                    'banking_info': banking_info,
                })
            
            # Sanitize payment method
            payment_method = sanitize_string(payment_method, max_length=50)
            
            order.payment_proof = payment_proof
            order.payment_method = payment_method
            order.status = 'payment_uploaded'
            order.save()
            
            # Send email notification to admin
            try:
                from .email_utils import send_payment_uploaded_notification
                send_payment_uploaded_notification(order)
            except Exception as e:
                print(f"Error sending payment uploaded email: {e}")
                # Don't fail the payment upload if email fails
            
            messages.success(request, 'Payment proof uploaded successfully! We will verify and confirm your order.')
            return redirect('core:order_status', order_ref=order_ref)
        else:
            messages.error(request, 'Please upload your payment proof.')
    
    context = {
        'order': order,
        'banking_info': banking_info,
    }
    return render(request, 'core/order_payment.html', context)


def order_status(request, order_ref):
    """Order status page - shows status, bundle, order reference. Payment upload when approved."""
    order = get_object_or_404(CustomerOrder, order_reference=order_ref)
    
    # Handle payment upload if status is 'approved'
    if request.method == 'POST' and order.status == 'approved':
        payment_proof = request.FILES.get('payment_proof')
        payment_method = request.POST.get('payment_method', '').strip()
        
        if payment_proof:
            # Validate file upload for security
            from .security import validate_file_upload, sanitize_string, ALLOWED_DOCUMENT_EXTENSIONS, MAX_IMAGE_SIZE
            
            is_valid, error_msg = validate_file_upload(
                payment_proof, 
                allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS,
                max_size=MAX_IMAGE_SIZE
            )
            
            if not is_valid:
                messages.error(request, f'Security validation failed: {error_msg}')
            else:
                # Sanitize payment method
                payment_method = sanitize_string(payment_method, max_length=50)
                
                order.payment_proof = payment_proof
                order.payment_method = payment_method
                order.status = 'payment_uploaded'
                order.save()
                
                # Send email notification to admin
                try:
                    from .email_utils import send_payment_uploaded_notification
                    send_payment_uploaded_notification(order)
                except Exception as e:
                    print(f"Error sending payment uploaded email: {e}")
                    # Don't fail the payment upload if email fails
                
                messages.success(request, 'Payment proof uploaded successfully! We will verify and confirm your order.')
                return redirect('core:order_status', order_ref=order_ref)
        else:
            messages.error(request, 'Please upload your payment proof.')
    
    order_items = order.customer_order_items.select_related('item')
    banking_info = BankingInfo.objects.filter(is_active=True)
    
    context = {
        'order': order,
        'order_items': order_items,
        'banking_info': banking_info,
        'verified': True,
    }
    return render(request, 'core/order_status.html', context)


def check_order(request):
    """Check order status by order reference only. Shows status, bundle, and order reference."""
    if request.method == 'POST':
        order_ref = request.POST.get('order_ref', '').strip().upper()
        
        if order_ref:
            try:
                order = CustomerOrder.objects.get(order_reference=order_ref)
                return redirect('core:order_status', order_ref=order.order_reference)
            except CustomerOrder.DoesNotExist:
                messages.error(request, 'Order not found. Please check the reference number.')
        else:
            messages.error(request, 'Please enter your order reference.')
    
    return render(request, 'core/check_order.html')


def my_orders(request):
    """View all orders for a customer by phone number or order reference"""
    orders = []
    phone_verified = False
    search_type = None
    
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        order_ref = request.POST.get('order_ref', '').strip().upper()
        
        # Check if searching by order reference
        if order_ref:
            try:
                order = CustomerOrder.objects.get(order_reference=order_ref)
                # Verify phone matches if provided
                if phone:
                    phone_normalized = ''.join(filter(str.isdigit, phone))
                    order_phone_normalized = ''.join(filter(str.isdigit, order.customer_phone))
                    if phone_normalized == order_phone_normalized:
                        orders = [order]
                        phone_verified = True
                        request.session[f'verified_phone_{order_ref}'] = phone_normalized
                        messages.success(request, 'Order found!')
                    else:
                        messages.error(request, 'Phone number does not match this order.')
                else:
                    orders = [order]
                    phone_verified = True
                    messages.success(request, 'Order found!')
                    search_type = 'order_ref'
            except CustomerOrder.DoesNotExist:
                messages.error(request, 'Order not found. Please check the order reference.')
        
        # Check if searching by phone number
        elif phone:
            phone_normalized = ''.join(filter(str.isdigit, phone))
            # Find all orders with this phone number
            all_orders = CustomerOrder.objects.filter(
                customer_phone__icontains=phone_normalized[-10:]  # Match last 10 digits
            ).order_by('-created_at')
            
            # Further filter by exact match (normalized)
            matching_orders = []
            for order in all_orders:
                order_phone_normalized = ''.join(filter(str.isdigit, order.customer_phone))
                if phone_normalized == order_phone_normalized:
                    matching_orders.append(order)
            
            if matching_orders:
                orders = matching_orders
                phone_verified = True
                # Store verified phone in session for all orders
                for order in orders:
                    request.session[f'verified_phone_{order.order_reference}'] = phone_normalized
                messages.success(request, f'Found {len(orders)} order(s) for this phone number.')
                search_type = 'phone'
            else:
                messages.error(request, 'No orders found for this phone number.')
        else:
            messages.error(request, 'Please enter either your phone number or order reference.')
    
    context = {
        'orders': orders,
        'phone_verified': phone_verified,
        'search_type': search_type,
    }
    return render(request, 'core/my_orders.html', context)


# Legacy Bundle Builder views - redirect to new flow
def bundle_builder_snacks(request):
    return redirect('core:bundle_builder')


def bundle_builder_juices(request):
    return redirect('core:bundle_builder')


def bundle_builder_review(request):
    return redirect('core:bundle_builder')


def clear_bundle_session(request):
    """Clear bundle builder session data"""
    for key in ['bundle_type', 'excluded_snacks', 'excluded_juices', 'starred_snacks', 'starred_juices', 
                'custom_snack_qty', 'custom_juice_qty']:
        request.session.pop(key, None)
    messages.info(request, 'Order session cleared.')
    return redirect('core:bundle_builder')


@csrf_exempt
@require_http_methods(["POST"])
@csrf_exempt
@require_http_methods(["POST"])
def push_subscribe(request):
    """Register a push notification subscription"""
    import json
    
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        keys = data.get('keys', {})
        
        if not endpoint or not keys:
            return JsonResponse({'error': 'Missing endpoint or keys'}, status=400)
        
        # Get or create subscription
        subscription, created = PushSubscription.objects.get_or_create(
            endpoint=endpoint,
            defaults={
                'keys': keys,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
            }
        )
        
        if not created:
            # Update existing subscription
            subscription.keys = keys
            subscription.user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]
            subscription.save()
        
        return JsonResponse({'success': True, 'message': 'Subscription registered'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def push_unsubscribe(request):
    """Unregister a push notification subscription"""
    import json
    
    try:
        data = json.loads(request.body)
        endpoint = data.get('endpoint')
        
        if not endpoint:
            return JsonResponse({'error': 'Missing endpoint'}, status=400)
        
        PushSubscription.objects.filter(endpoint=endpoint).delete()
        
        return JsonResponse({'success': True, 'message': 'Subscription removed'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def send_push_notification(request):
    """Send push notification to all subscribers (admin only)"""
    import json
    from pywebpush import webpush, WebPushException
    from django.conf import settings
    
    try:
        data = json.loads(request.body)
        title = data.get('title', 'J.E.M - Just Eat More')
        body = data.get('body', 'You have a new notification!')
        url = data.get('url', '/')
        icon = data.get('icon', '/static/favicons/icon-192.png')
        
        # Get VAPID keys from settings
        vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
        vapid_public_key = getattr(settings, 'VAPID_PUBLIC_KEY', None)
        vapid_claims = getattr(settings, 'VAPID_CLAIMS', {})
        
        if not vapid_private_key or not vapid_public_key:
            return JsonResponse({
                'error': 'VAPID keys not configured. Please set VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY in settings.'
            }, status=500)
        
        # Get all subscriptions
        subscriptions = PushSubscription.objects.all()
        success_count = 0
        error_count = 0
        
        notification_payload = json.dumps({
            'title': title,
            'body': body,
            'icon': icon,
            'badge': icon,
            'url': url,
            'tag': 'jem-notification',
            'data': {'url': url}
        })
        
        for subscription in subscriptions:
            try:
                webpush(
                    subscription_info={
                        'endpoint': subscription.endpoint,
                        'keys': subscription.keys
                    },
                    data=notification_payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims=vapid_claims
                )
                success_count += 1
            except WebPushException as e:
                # If subscription is invalid, remove it
                if e.response and e.response.status_code in [410, 404]:
                    subscription.delete()
                error_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Notification sent to {success_count} subscribers',
            'success_count': success_count,
            'error_count': error_count
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_vapid_public_key(request):
    """Return VAPID public key for client-side push subscription"""
    from django.conf import settings
    vapid_public_key = getattr(settings, 'VAPID_PUBLIC_KEY', '')
    return JsonResponse({'publicKey': vapid_public_key})


@csrf_exempt
@require_http_methods(["POST"])
def submit_suggestion(request):
    """Handle customer suggestion submission"""
    import json
    from .models import CustomerSuggestion
    
    try:
        data = json.loads(request.body)
        suggestion_type = data.get('suggestion_type')
        item_name = data.get('item_name', '').strip()
        message = data.get('message', '').strip()
        customer_name = data.get('customer_name', '').strip()
        customer_phone = data.get('customer_phone', '').strip()
        
        # Validation
        if not suggestion_type or suggestion_type not in ['new_item', 'feedback']:
            return JsonResponse({'success': False, 'error': 'Invalid suggestion type'}, status=400)
        
        if not message:
            return JsonResponse({'success': False, 'error': 'Message is required'}, status=400)
        
        if not customer_name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)
        
        # For new_item type, item_name is required
        if suggestion_type == 'new_item' and not item_name:
            return JsonResponse({'success': False, 'error': 'Item name is required for new item requests'}, status=400)
        
        # Create suggestion
        suggestion = CustomerSuggestion.objects.create(
            suggestion_type=suggestion_type,
            item_name=item_name if suggestion_type == 'new_item' else '',
            message=message,
            customer_name=customer_name,
            customer_phone=customer_phone,
        )
        
        # Note: Suggestions are only viewed in admin section, no email notifications
        
        return JsonResponse({'success': True, 'message': 'Suggestion submitted successfully'})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
