from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
from decimal import Decimal
from .models import Item, BundleType, Customer, Order, OrderItem, CustomerOrder, CustomerOrderItem, BankingInfo


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


def calculate_custom_bundle_quantities(selected_snacks, selected_juices, starred_snacks, starred_juices, 
                                        required_snack_qty, required_juice_qty, target_margin=38):
    """
    Smart algorithm to calculate optimal quantities for custom bundles.
    GUARANTEES at least target_margin% profit margin, and optimizes for higher margins.
    
    Rules:
    1. Starred items ALWAYS get more quantity than non-starred items
    2. For larger bundles with no stars: give more of cheaper items to boost profit
    3. For starred cheap items: give extra of those to boost profit
    4. For starred expensive items: still give more, but compensate by giving more cheap non-starred items
    
    - selected_snacks/juices: list of Item objects
    - starred_snacks/juices: list of Item IDs that customer wants more of (max 2 each)
    - required_snack_qty: total number of snacks customer wants
    - required_juice_qty: total number of juices customer wants
    - target_margin: minimum profit margin percentage (default 38%)
    
    Returns: dict with {item_id: quantity} and calculated price
    """
    # Enforce minimum margin of 38%
    if target_margin < 38:
        target_margin = 38

    quantities = {}
    
    def distribute_category(items, starred_ids, required_qty):
        """
        Distribute quantities for a single category (snacks or juices).
        Returns dict of {item_id: quantity}
        """
        if not items or required_qty <= 0:
            return {}
        
        result = {}
        
        # Sort items by cost price (cheapest first)
        sorted_items = sorted(items, key=lambda x: x.cost_price)
        
        # Separate starred and non-starred, preserving cost order
        starred_items = [item for item in sorted_items if item.id in starred_ids]
        regular_items = [item for item in sorted_items if item.id not in starred_ids]
        
        num_starred = len(starred_items)
        num_regular = len(regular_items)
        num_total = len(items)
        
        # Initialize all to 0
        for item in items:
            result[item.id] = 0
        
        # Helper: weight by inverse cost (cheaper gets more)
        def weight_by_inverse_cost(item):
            # Avoid divide-by-zero, favor cheaper items
            return float(1 / (item.cost_price + Decimal('0.01')))

        # CASE 1: Small bundle (10-15 items) with no stars
        # Still favor cheaper items slightly (not perfectly even)
        if num_starred == 0 and required_qty <= 15:
            # Minimum 1 each, then allocate remainder by inverse cost weights
            for item in sorted_items:
                result[item.id] = 1
            remaining = required_qty - num_total
            if remaining > 0:
                weights = [weight_by_inverse_cost(item) for item in sorted_items]
                total_weight = sum(weights)
                # Allocate by weight
                for i, item in enumerate(sorted_items):
                    extra = int(remaining * weights[i] / total_weight)
                    result[item.id] += extra
                # Fix rounding remainder by giving to cheapest items
                while sum(result.values()) < required_qty:
                    for item in sorted_items:
                        if sum(result.values()) >= required_qty:
                            break
                        result[item.id] += 1
            return result
        
        # CASE 2: Larger bundle with no stars - strongly favor cheaper items
        if num_starred == 0:
            # Minimum 1 each, then allocate remainder using inverse-cost weights
            for item in sorted_items:
                result[item.id] = 1
            remaining = required_qty - num_total
            if remaining > 0:
                weights = [weight_by_inverse_cost(item) for item in sorted_items]
                total_weight = sum(weights)
                for i, item in enumerate(sorted_items):
                    extra = int(remaining * weights[i] / total_weight)
                    result[item.id] += extra
                # Fix rounding remainder by giving to cheapest items
                while sum(result.values()) < required_qty:
                    for item in sorted_items:
                        if sum(result.values()) >= required_qty:
                            break
                        result[item.id] += 1
            # If we over-allocated, reduce from most expensive first
            while sum(result.values()) > required_qty:
                for item in reversed(sorted_items):
                    if result[item.id] > 1 and sum(result.values()) > required_qty:
                        result[item.id] -= 1
            return result
        
        # CASE 3: Has starred items
        # Rule: Starred items ALWAYS get more than non-starred
        # If starred item is cheap: give even more (boosts profit)
        # If starred item is expensive: still give more, but compensate with cheap non-starred
        
        # Calculate average cost to determine if starred items are cheap or expensive
        avg_cost = sum(item.cost_price for item in items) / len(items)
        
        # Categorize starred items
        cheap_starred = [item for item in starred_items if item.cost_price <= avg_cost]
        expensive_starred = [item for item in starred_items if item.cost_price > avg_cost]
        cheap_regular = [item for item in regular_items if item.cost_price <= avg_cost]
        expensive_regular = [item for item in regular_items if item.cost_price > avg_cost]
        
        # Base quantities - starred get at least 2x what regular gets
        # Calculate minimum base for regular items
        if num_regular > 0:
            # Regular items get minimum 1 each
            regular_base = max(1, required_qty // (num_total + num_starred))  # starred counted twice
        else:
            regular_base = 0
        
        # Starred items get at least 2x regular base
        starred_base = max(regular_base * 2, 2) if num_starred > 0 else 0
        
        # Assign base quantities
        for item in regular_items:
            result[item.id] = regular_base
        for item in starred_items:
            result[item.id] = starred_base
        
        # Calculate how many we've allocated
        allocated = sum(result.values())
        remaining = required_qty - allocated
        
        if remaining > 0:
            # Distribute remaining items strategically
            # Priority order:
            # 1. Cheap starred items (boosts profit AND customer gets more of what they want)
            # 2. Cheap regular items (boosts profit)
            # 3. Expensive starred items (customer wants more)
            # 4. Expensive regular items (last resort)
            
            priority_order = cheap_starred + cheap_regular + expensive_starred + expensive_regular
            
            # First pass: give extra to cheap starred items
            for item in cheap_starred:
                if remaining <= 0:
                    break
                # Give them extra - up to 50% more than current
                extra = max(1, result[item.id] // 2)
                extra = min(extra, remaining)
                result[item.id] += extra
                remaining -= extra
            
            # Second pass: distribute to cheap regular items (weighted, still keep starred higher)
            if remaining > 0 and cheap_regular:
                weights = [weight_by_inverse_cost(item) for item in cheap_regular]
                total_weight = sum(weights)
                for i, item in enumerate(cheap_regular):
                    if remaining <= 0:
                        break
                    extra = int(remaining * weights[i] / total_weight)
                    min_starred_qty = min(result[s.id] for s in starred_items) if starred_items else float('inf')
                    # Keep regular below starred
                    max_extra = max(0, min_starred_qty - 1 - result[item.id])
                    extra = min(extra, max_extra)
                    result[item.id] += extra
                # Remainder to cheapest regular, still below starred
                while remaining > 0:
                    gave_any = False
                    for item in cheap_regular:
                        min_starred_qty = min(result[s.id] for s in starred_items) if starred_items else float('inf')
                        if remaining <= 0:
                            break
                        if result[item.id] + 1 < min_starred_qty:
                            result[item.id] += 1
                            remaining -= 1
                            gave_any = True
                    if not gave_any:
                        break
            
            # Third pass: give LIMITED amount to expensive starred (customer wants it, but don't hurt margin too much)
            # Only give a small amount to expensive starred, then prioritize cheap items
            expensive_starred_limit = min(len(expensive_starred), remaining // 3) if expensive_starred else 0
            for i, item in enumerate(expensive_starred):
                if remaining <= 0 or i >= expensive_starred_limit:
                    break
                result[item.id] += 1
                remaining -= 1
            
            # Fourth pass: any remaining goes to cheapest items
            while remaining > 0:
                for item in sorted_items:
                    if remaining <= 0:
                        break
                    # For non-starred, ensure starred still have more
                    if item.id not in starred_ids:
                        min_starred_qty = min(result[s.id] for s in starred_items) if starred_items else float('inf')
                        if result[item.id] + 1 >= min_starred_qty:
                            continue
                    result[item.id] += 1
                    remaining -= 1
        
        elif remaining < 0:
            # Over-allocated, need to reduce
            # Reduce from expensive non-starred first, then expensive starred
            # But NEVER let non-starred exceed starred
            
            reduction_order = list(reversed(expensive_regular)) + list(reversed(cheap_regular)) + \
                             list(reversed(expensive_starred)) + list(reversed(cheap_starred))
            
            while sum(result.values()) > required_qty:
                reduced = False
                for item in reduction_order:
                    if result[item.id] > 1:
                        # For starred items, only reduce if we must
                        if item.id in starred_ids:
                            # Check if any regular item has same or more
                            max_regular = max((result[r.id] for r in regular_items), default=0)
                            if result[item.id] <= max_regular + 1:
                                continue  # Don't reduce starred below regular
                        result[item.id] -= 1
                        reduced = True
                        break
                if not reduced:
                    break
        
        # Final validation: ensure starred items have more than non-starred
        if starred_items and regular_items:
            min_starred = min(result[item.id] for item in starred_items)
            max_regular = max(result[item.id] for item in regular_items)
            
            if max_regular >= min_starred:
                # Need to rebalance - take from expensive regular, give to starred
                iterations = 0
                while max_regular >= min_starred and iterations < 100:
                    # Find the regular item with most quantity (prefer expensive)
                    regular_by_qty = sorted(regular_items, key=lambda x: (-result[x.id], -x.cost_price))
                    # Find starred item with least quantity
                    starred_by_qty = sorted(starred_items, key=lambda x: result[x.id])
                    
                    if regular_by_qty and result[regular_by_qty[0].id] > 1:
                        result[regular_by_qty[0].id] -= 1
                        result[starred_by_qty[0].id] += 1
                    else:
                        break
                    
                    min_starred = min(result[item.id] for item in starred_items)
                    max_regular = max(result[item.id] for item in regular_items)
                    iterations += 1
        
        return result
    
    # Process snacks
    snack_quantities = distribute_category(selected_snacks, starred_snacks, required_snack_qty)
    quantities.update(snack_quantities)
    
    # Process juices
    juice_quantities = distribute_category(selected_juices, starred_juices, required_juice_qty)
    quantities.update(juice_quantities)
    
    # Calculate total cost
    all_items_dict = {item.id: item for item in selected_snacks + selected_juices}
    total_cost = sum(
        all_items_dict[item_id].cost_price * Decimal(str(qty))
        for item_id, qty in quantities.items()
        if qty > 0
    )
    
    # Calculate price to achieve AT LEAST target margin
    # revenue = cost / (1 - target_margin/100)
    margin_factor = Decimal(str(1 - target_margin / 100))
    if margin_factor > 0 and total_cost > 0:
        suggested_price = total_cost / margin_factor
        # Round up to nearest 100 (this will push margin above target)
        suggested_price = (int(suggested_price / 100) + 1) * 100
    else:
        suggested_price = Decimal('0')
    
    # Calculate actual margin achieved
    actual_margin = Decimal('0')
    if suggested_price > 0:
        actual_margin = ((Decimal(str(suggested_price)) - total_cost) / Decimal(str(suggested_price)) * 100)
    
    # If margin is below target, adjust quantities to favor cheaper items more aggressively
    max_iterations = 50
    iteration = 0
    
    while actual_margin < target_margin and iteration < max_iterations and total_cost > 0:
        iteration += 1
        
        # Strategy: Shift quantities from expensive items to cheaper items
        # Sort all items by cost (cheapest first)
        all_items_list = []
        for item_id, qty in quantities.items():
            if qty > 0 and item_id in all_items_dict:
                all_items_list.append((item_id, all_items_dict[item_id], qty))
        
        if not all_items_list:
            break
        
        # Sort by cost (cheapest first)
        all_items_list.sort(key=lambda x: x[1].cost_price)
        
        # Find expensive items we can reduce and cheap items we can increase
        expensive_items = [x for x in all_items_list if x[2] > 1]  # Items with qty > 1
        cheap_items = [x for x in all_items_list]  # All items, cheapest first
        
        # Check starred constraints
        starred_ids_set = set(starred_snacks + starred_juices)
        
        # Try to shift from expensive to cheap
        shifted = False
        
        # Prioritize reducing expensive NON-starred items first (they hurt margin most)
        non_starred_expensive = [x for x in expensive_items if x[0] not in starred_ids_set]
        starred_expensive = [x for x in expensive_items if x[0] in starred_ids_set]
        
        # Process non-starred expensive first, then starred expensive
        for exp_item_id, exp_item, exp_qty in reversed(non_starred_expensive + starred_expensive):
            if shifted:
                break
            
            # For starred items, check minimum constraint
            if exp_item_id in starred_ids_set:
                min_starred = min((qty for item_id, _, qty in all_items_list if item_id in starred_ids_set), default=0)
                min_non_starred = min((qty for item_id, _, qty in all_items_list if item_id not in starred_ids_set), default=0)
                # Allow reducing starred if it's significantly above non-starred (more than 2 units difference)
                if exp_qty <= max(min_non_starred + 1, 2):
                    continue  # Can't reduce starred below this
            
            # Find cheapest item to increase (prefer cheap starred if available, then cheap non-starred)
            cheap_starred = [x for x in cheap_items if x[0] in starred_ids_set]
            cheap_non_starred = [x for x in cheap_items if x[0] not in starred_ids_set]
            
            # Prefer cheap starred items, then cheap non-starred
            for cheap_item_id, cheap_item, cheap_qty in (cheap_starred + cheap_non_starred):
                if cheap_item_id == exp_item_id:
                    continue
                
                # Don't increase non-starred above starred
                if cheap_item_id not in starred_ids_set and exp_item_id in starred_ids_set:
                    continue  # Can't increase non-starred above starred
                
                # Shift 1 unit from expensive to cheap
                quantities[exp_item_id] -= 1
                quantities[cheap_item_id] += 1
                shifted = True
                break
        
        if not shifted:
            # Can't shift more, break
            break
        
        # Recalculate cost and margin
        total_cost = sum(
            all_items_dict[item_id].cost_price * Decimal(str(qty))
            for item_id, qty in quantities.items()
            if qty > 0
        )
        
        if margin_factor > 0 and total_cost > 0:
            suggested_price = total_cost / margin_factor
            suggested_price = (int(suggested_price / 100) + 1) * 100
            actual_margin = ((Decimal(str(suggested_price)) - total_cost) / Decimal(str(suggested_price)) * 100)
        else:
            break
    
    return {
        'quantities': quantities,
        'total_cost': total_cost,
        'suggested_price': Decimal(str(suggested_price)),
        'actual_margin': actual_margin
    }


def bundle_builder(request):
    """Step 1: Select Bundle Type"""
    # Clear any existing session data when starting fresh
    if request.method == 'GET' and 'fresh' in request.GET:
        for key in ['bundle_type', 'excluded_snacks', 'excluded_juices', 
                    'starred_snacks', 'starred_juices', 'custom_snack_qty', 'custom_juice_qty']:
            request.session.pop(key, None)
    
    if request.method == 'POST':
        bundle_type = request.POST.get('bundle_type')
        
        if bundle_type == 'custom':
            # Get custom quantities
            try:
                custom_snack_qty = int(request.POST.get('custom_snack_qty', 0) or 0)
                custom_juice_qty = int(request.POST.get('custom_juice_qty', 0) or 0)
            except ValueError:
                custom_snack_qty = 0
                custom_juice_qty = 0
            
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
                return redirect('core:bundle_builder_select')
        
        elif bundle_type in BUNDLE_REQUIREMENTS:
            request.session['bundle_type'] = bundle_type
            return redirect('core:bundle_builder_select')
        else:
            messages.error(request, 'Please select a valid bundle type.')
    
    context = {
        'bundle_prices': BUNDLE_PRICES,
    }
    return render(request, 'core/order_step1_bundle.html', context)


def bundle_builder_select(request):
    """Step 2: Select items to EXCLUDE from the bundle (exclusion model)"""
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
    
    # Get previously excluded items from session (items customer doesn't want)
    excluded_snacks = request.session.get('excluded_snacks', [])
    excluded_juices = request.session.get('excluded_juices', [])
    starred_snacks = request.session.get('starred_snacks', [])
    starred_juices = request.session.get('starred_juices', [])
    
    if request.method == 'POST':
        # Get excluded items (checkboxes - items customer doesn't want)
        excluded_snack_ids = [int(x) for x in request.POST.getlist('excluded_snacks')]
        excluded_juice_ids = [int(x) for x in request.POST.getlist('excluded_juices')]
        
        # Get starred items (max 2 each) - these are from the INCLUDED items
        starred_snack_ids = [int(x) for x in request.POST.getlist('starred_snacks')][:2]
        starred_juice_ids = [int(x) for x in request.POST.getlist('starred_juices')][:2]
        
        # Calculate included items (all items minus excluded)
        all_snack_ids = list(all_snacks.values_list('id', flat=True))
        all_juice_ids = list(all_juices.values_list('id', flat=True))
        included_snack_ids = [sid for sid in all_snack_ids if sid not in excluded_snack_ids]
        included_juice_ids = [jid for jid in all_juice_ids if jid not in excluded_juice_ids]
        
        # Validation: must have at least one item included
        errors = []
        
        if bundle_type in ['10_snacks', '25_snacks', 'mega_mix']:
            if len(included_snack_ids) == 0:
                errors.append('You must include at least one snack in your bundle.')
        if bundle_type in ['25_juices', 'mega_mix']:
            if len(included_juice_ids) == 0:
                errors.append('You must include at least one juice in your bundle.')
        elif bundle_type == 'custom':
            # Validate based on what customer requested
            if custom_snack_qty > 0 and len(included_snack_ids) == 0:
                errors.append(f'You must include at least one snack for your {custom_snack_qty} snacks.')
            if custom_juice_qty > 0 and len(included_juice_ids) == 0:
                errors.append(f'You must include at least one juice for your {custom_juice_qty} juices.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Save to session (excluded items and starred items)
            request.session['excluded_snacks'] = excluded_snack_ids
            request.session['excluded_juices'] = excluded_juice_ids
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
        'excluded_snacks': excluded_snacks,
        'excluded_juices': excluded_juices,
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
    
    # Calculate included items (all items minus excluded)
    snack_items = [item for item in all_snacks if item.id not in excluded_snacks]
    juice_items = [item for item in all_juices if item.id not in excluded_juices]
    
    if not snack_items and not juice_items:
        messages.error(request, 'Please include at least one item in your bundle.')
        return redirect('core:bundle_builder_select')
    
    # Calculate for display
    is_custom = bundle_type == 'custom'
    
    if is_custom:
        # Run algorithm with customer-specified quantities
        calc_result = calculate_custom_bundle_quantities(
            snack_items, juice_items, starred_snacks, starred_juices,
            required_snack_qty=custom_snack_qty,
            required_juice_qty=custom_juice_qty
        )
        quantities = calc_result['quantities']
        total_cost = calc_result['total_cost']
        suggested_price = calc_result['suggested_price']
    else:
        # Fixed bundle - use algorithm to ensure 38% margin with fixed price
        requirements = BUNDLE_REQUIREMENTS[bundle_type]
        fixed_price = BUNDLE_PRICES[bundle_type]
        
        # Calculate required quantities
        required_snack_qty = requirements.get('snacks', 0)
        required_juice_qty = requirements.get('juices', 0)
        
        # Calculate maximum allowed cost for 38% margin with fixed price
        # margin = (revenue - cost) / revenue
        # 0.38 = (fixed_price - cost) / fixed_price
        # 0.38 * fixed_price = fixed_price - cost
        # cost = fixed_price - 0.38 * fixed_price = fixed_price * 0.62
        max_allowed_cost = fixed_price * Decimal('0.62')
        
        # Run algorithm with 38% margin target
        calc_result = calculate_custom_bundle_quantities(
            snack_items, juice_items, starred_snacks, starred_juices,
            required_snack_qty=required_snack_qty,
            required_juice_qty=required_juice_qty,
            target_margin=38
        )
        quantities = calc_result['quantities']
        total_cost = calc_result['total_cost']
        
        # If cost exceeds max allowed, keep adjusting quantities until it fits
        all_items_dict = {item.id: item for item in snack_items + juice_items}
        max_iterations = 100
        iteration = 0
        
        while total_cost > max_allowed_cost and iteration < max_iterations:
            iteration += 1
            
            # Shift quantities from expensive to cheap items
            all_items_list = []
            for item_id, qty in quantities.items():
                if qty > 0 and item_id in all_items_dict:
                    all_items_list.append((item_id, all_items_dict[item_id], qty))
            
            if not all_items_list:
                break
            
            # Sort by cost (cheapest first)
            all_items_list.sort(key=lambda x: x[1].cost_price)
            
            # Find expensive items we can reduce
            expensive_items = [x for x in all_items_list if x[2] > 1]
            cheap_items = [x for x in all_items_list]
            
            starred_ids_set = set(starred_snacks + starred_juices)
            
            # Try to shift from expensive to cheap
            shifted = False
            for exp_item_id, exp_item, exp_qty in reversed(expensive_items):
                if shifted:
                    break
                
                # Don't reduce starred items below non-starred minimum
                if exp_item_id in starred_ids_set:
                    min_starred = min((qty for item_id, _, qty in all_items_list if item_id in starred_ids_set), default=0)
                    min_non_starred = min((qty for item_id, _, qty in all_items_list if item_id not in starred_ids_set), default=0)
                    if exp_qty <= max(min_non_starred + 1, 2):
                        continue
                
                # Find cheapest item to increase
                for cheap_item_id, cheap_item, cheap_qty in cheap_items:
                    if cheap_item_id == exp_item_id:
                        continue
                    
                    # Don't increase non-starred above starred
                    if cheap_item_id not in starred_ids_set and exp_item_id in starred_ids_set:
                        continue
                    
                    # Shift 1 unit
                    quantities[exp_item_id] -= 1
                    quantities[cheap_item_id] += 1
                    shifted = True
                    break
            
            if not shifted:
                break
            
            # Recalculate cost
            total_cost = sum(
                all_items_dict[item_id].cost_price * Decimal(str(qty))
                for item_id, qty in quantities.items()
                if qty > 0
            )
        
        suggested_price = fixed_price
    
    # Prepare items with quantities for display
    snacks_with_qty = [(item, quantities.get(item.id, 0), item.id in starred_snacks) for item in snack_items if quantities.get(item.id, 0) > 0]
    juices_with_qty = [(item, quantities.get(item.id, 0), item.id in starred_juices) for item in juice_items if quantities.get(item.id, 0) > 0]
    
    # Get banking info
    banking_info = BankingInfo.objects.filter(is_active=True).first()
    
    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        customer_whatsapp = request.POST.get('customer_whatsapp', '').strip()
        pickup_spot = request.POST.get('pickup_spot', '').strip()
        
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
            
            # Create order items
            all_items = {item.id: item for item in snack_items + juice_items}
            for item_id, qty in quantities.items():
                CustomerOrderItem.objects.create(
                    order=order,
                    item=all_items[item_id],
                    quantity=qty,
                    is_starred=item_id in starred_snacks or item_id in starred_juices
                )
            
            # Calculate totals for non-custom
            if not is_custom:
                order.total_revenue = suggested_price
                order.net_profit = order.total_revenue - order.total_cost
                if order.total_revenue > 0:
                    order.profit_margin = (order.net_profit / order.total_revenue) * 100
                
                # Validate margin is at least 38%
                if order.profit_margin < 38:
                    # This shouldn't happen with algorithm, but if it does, set status to pending_approval
                    order.status = 'pending_approval'
                    messages.warning(request, f'Fixed bundle cost results in {order.profit_margin:.1f}% margin. Order requires admin approval.')
                
                order.save()
            
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
            order.payment_proof = payment_proof
            order.payment_method = payment_method
            order.status = 'payment_uploaded'
            order.save()
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
    """Order status page"""
    order = get_object_or_404(CustomerOrder, order_reference=order_ref)
    order_items = order.customer_order_items.select_related('item')
    
    context = {
        'order': order,
        'order_items': order_items,
    }
    return render(request, 'core/order_status.html', context)


def check_order(request):
    """Allow customer to check their order status"""
    if request.method == 'POST':
        order_ref = request.POST.get('order_ref', '').strip().upper()
        if order_ref:
            try:
                order = CustomerOrder.objects.get(order_reference=order_ref)
                return redirect('core:order_status', order_ref=order.order_reference)
            except CustomerOrder.DoesNotExist:
                messages.error(request, 'Order not found. Please check the reference number.')
    
    return render(request, 'core/check_order.html')


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
