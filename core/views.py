from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
from decimal import Decimal
from .models import Item, BundleType, Customer, Order, OrderItem


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
    # Calculate all-time totals
    all_orders = Order.objects.filter(status='completed')
    
    total_revenue = all_orders.aggregate(Sum('total_revenue'))['total_revenue__sum'] or Decimal('0.00')
    total_cost = all_orders.aggregate(Sum('total_cost'))['total_cost__sum'] or Decimal('0.00')
    total_net_profit = all_orders.aggregate(Sum('net_profit'))['net_profit__sum'] or Decimal('0.00')
    
    # Current inventory levels
    items = Item.objects.all().order_by('category', 'name')
    low_stock_items = items.filter(current_stock__lt=5)
    
    # Recent sales (last 10 orders)
    recent_sales = all_orders[:10]
    
    # Calculate average profit margin
    if all_orders.exists():
        avg_margin = all_orders.aggregate(
            avg_margin=Sum('profit_margin') / Count('id')
        )['avg_margin'] or 0
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
        'total_orders': all_orders.count(),
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


# Bundle Builder Wizard Views
def bundle_builder(request):
    """Step 1: Select Bundle Type"""
    bundle_types = BundleType.objects.filter(is_active=True)
    
    if request.method == 'POST':
        bundle_type_id = request.POST.get('bundle_type')
        if bundle_type_id:
            bundle_type = get_object_or_404(BundleType, id=bundle_type_id, is_active=True)
            request.session['bundle_type_id'] = bundle_type.id
            return redirect('core:bundle_builder_snacks')
    
    context = {
        'bundle_types': bundle_types,
    }
    return render(request, 'core/bundle_builder_step1.html', context)


def bundle_builder_snacks(request):
    """Step 2: Select Snacks"""
    bundle_type_id = request.session.get('bundle_type_id')
    if not bundle_type_id:
        messages.error(request, 'Please select a bundle type first.')
        return redirect('core:bundle_builder')
    
    bundle_type = get_object_or_404(BundleType, id=bundle_type_id)
    snacks = Item.objects.filter(category='snack', current_stock__gt=0).order_by('name')
    
    selected_snacks = request.session.get('selected_snacks', [])
    
    if request.method == 'POST':
        selected_snack_ids = request.POST.getlist('snacks')
        
        # Validate quantity
        if len(selected_snack_ids) != bundle_type.required_snacks:
            messages.error(
                request, 
                f'Please select exactly {bundle_type.required_snacks} snacks. '
                f'You selected {len(selected_snack_ids)}.'
            )
            return redirect('core:bundle_builder_snacks')
        
        # Validate stock availability
        for snack_id in selected_snack_ids:
            snack = get_object_or_404(Item, id=snack_id, category='snack')
            if snack.current_stock <= 0:
                messages.error(request, f'{snack.name} is out of stock.')
                return redirect('core:bundle_builder_snacks')
        
        request.session['selected_snacks'] = selected_snack_ids
        return redirect('core:bundle_builder_juices')
    
    context = {
        'bundle_type': bundle_type,
        'snacks': snacks,
        'selected_snacks': selected_snacks,
        'required_count': bundle_type.required_snacks,
    }
    return render(request, 'core/bundle_builder_step2.html', context)


def bundle_builder_juices(request):
    """Step 3: Select Juices"""
    bundle_type_id = request.session.get('bundle_type_id')
    selected_snacks = request.session.get('selected_snacks', [])
    
    if not bundle_type_id or not selected_snacks:
        messages.error(request, 'Please complete previous steps first.')
        return redirect('core:bundle_builder')
    
    bundle_type = get_object_or_404(BundleType, id=bundle_type_id)
    juices = Item.objects.filter(category='juice', current_stock__gt=0).order_by('name')
    
    selected_juices = request.session.get('selected_juices', [])
    
    if request.method == 'POST':
        selected_juice_ids = request.POST.getlist('juices')
        
        # Validate quantity
        if len(selected_juice_ids) != bundle_type.required_juices:
            messages.error(
                request, 
                f'Please select exactly {bundle_type.required_juices} juices. '
                f'You selected {len(selected_juice_ids)}.'
            )
            return redirect('core:bundle_builder_juices')
        
        # Validate stock availability
        for juice_id in selected_juice_ids:
            juice = get_object_or_404(Item, id=juice_id, category='juice')
            if juice.current_stock <= 0:
                messages.error(request, f'{juice.name} is out of stock.')
                return redirect('core:bundle_builder_juices')
        
        request.session['selected_juices'] = selected_juice_ids
        return redirect('core:bundle_builder_review')
    
    context = {
        'bundle_type': bundle_type,
        'juices': juices,
        'selected_juices': selected_juices,
        'required_count': bundle_type.required_juices,
    }
    return render(request, 'core/bundle_builder_step3.html', context)


def bundle_builder_review(request):
    """Step 4: Review & Submit"""
    bundle_type_id = request.session.get('bundle_type_id')
    selected_snacks = request.session.get('selected_snacks', [])
    selected_juices = request.session.get('selected_juices', [])
    
    if not bundle_type_id or not selected_snacks or not selected_juices:
        messages.error(request, 'Please complete all previous steps.')
        return redirect('core:bundle_builder')
    
    bundle_type = get_object_or_404(BundleType, id=bundle_type_id)
    
    # Get all selected items
    snack_items = Item.objects.filter(id__in=selected_snacks, category='snack')
    juice_items = Item.objects.filter(id__in=selected_juices, category='juice')
    
    # Calculate totals
    total_revenue = sum(item.sell_price for item in list(snack_items) + list(juice_items))
    total_cost = sum(item.cost_price for item in list(snack_items) + list(juice_items))
    net_profit = total_revenue - total_cost
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    if request.method == 'POST':
        # Get customer info
        customer_name = request.POST.get('customer_name', '').strip()
        customer_email = request.POST.get('customer_email', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        
        if not customer_name:
            messages.error(request, 'Customer name is required.')
            return redirect('core:bundle_builder_review')
        
        # Create or get customer
        customer, created = Customer.objects.get_or_create(
            name=customer_name,
            defaults={'email': customer_email, 'phone': customer_phone}
        )
        
        # Create order
        order = Order.objects.create(
            customer=customer,
            bundle_type=bundle_type,
            status='completed',  # Auto-complete for now
            total_revenue=total_revenue,
            total_cost=total_cost,
            net_profit=net_profit,
            profit_margin=profit_margin,
        )
        
        # Create order items
        for snack in snack_items:
            OrderItem.objects.create(order=order, item=snack, quantity=1)
        
        for juice in juice_items:
            OrderItem.objects.create(order=order, item=juice, quantity=1)
        
        # Recalculate to ensure accuracy
        order.calculate_totals()
        
        # Clear session
        request.session.pop('bundle_type_id', None)
        request.session.pop('selected_snacks', None)
        request.session.pop('selected_juices', None)
        
        messages.success(request, f'Order #{order.id} created successfully!')
        return redirect('core:dashboard')
    
    context = {
        'bundle_type': bundle_type,
        'snack_items': snack_items,
        'juice_items': juice_items,
        'total_revenue': total_revenue,
        'total_cost': total_cost,
        'net_profit': net_profit,
        'profit_margin': profit_margin,
    }
    return render(request, 'core/bundle_builder_step4.html', context)


def clear_bundle_session(request):
    """Clear bundle builder session data"""
    request.session.pop('bundle_type_id', None)
    request.session.pop('selected_snacks', None)
    request.session.pop('selected_juices', None)
    messages.info(request, 'Bundle builder session cleared.')
    return redirect('core:bundle_builder')
