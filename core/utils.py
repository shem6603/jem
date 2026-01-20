"""
Smart Bundle Generation Utility
Generates optimized bundles that meet profit margin requirements
"""
from decimal import Decimal
from django.db.models import Q


# Minimum profit margin (38%)
MIN_PROFIT_MARGIN = Decimal('0.38')


def generate_smart_bundle(bundle_config, customer_favorites=None):
    """
    Generate a smart bundle that meets profit margin requirements.
    
    Args:
        bundle_config (dict): Configuration for the bundle
            - name (str): Bundle name
            - selling_price (Decimal): The fixed selling price
            - snack_limit (int): Number of snacks required
            - juice_limit (int): Number of juices required
            - packaging_cost (Decimal): Cost of packaging (default 0)
        
        customer_favorites (QuerySet/List): Item objects the customer specifically requested
    
    Returns:
        dict: {
            'selected_snacks': list of (Item, quantity) tuples,
            'selected_juices': list of (Item, quantity) tuples,
            'total_cost': Decimal,
            'estimated_profit': Decimal,
            'profit_margin': Decimal,
            'success': bool,
            'message': str
        }
    """
    from .models import Item
    
    # Extract config values
    selling_price = Decimal(str(bundle_config.get('selling_price', 0)))
    snack_limit = int(bundle_config.get('snack_limit', 0))
    juice_limit = int(bundle_config.get('juice_limit', 0))
    packaging_cost = Decimal(str(bundle_config.get('packaging_cost', 0)))
    
    if customer_favorites is None:
        customer_favorites = []
    
    # Get favorite item IDs for easy lookup
    favorite_ids = set(item.id for item in customer_favorites)
    
    # ========================================
    # STEP 1: Calculate the Budget
    # ========================================
    # Max_Allowable_Cost = Revenue - (Revenue * 0.38) - Packaging_Cost
    # This is: Revenue * (1 - 0.38) - Packaging_Cost = Revenue * 0.62 - Packaging_Cost
    max_allowable_cost = (selling_price * (1 - MIN_PROFIT_MARGIN)) - packaging_cost
    
    # ========================================
    # STEP 2: Phase 1 - Add Favorites (High Priority)
    # ========================================
    selected_snacks = []  # List of (Item, quantity) tuples
    selected_juices = []  # List of (Item, quantity) tuples
    
    snacks_added = 0
    juices_added = 0
    
    # Separate favorites by category
    favorite_snacks = [item for item in customer_favorites if item.category == 'snack' and item.current_stock > 0]
    favorite_juices = [item for item in customer_favorites if item.category == 'juice' and item.current_stock > 0]
    
    # Add favorite snacks (1 each initially)
    for item in favorite_snacks:
        if snacks_added < snack_limit:
            selected_snacks.append({'item': item, 'quantity': 1, 'is_favorite': True})
            snacks_added += 1
    
    # Add favorite juices (1 each initially)
    for item in favorite_juices:
        if juices_added < juice_limit:
            selected_juices.append({'item': item, 'quantity': 1, 'is_favorite': True})
            juices_added += 1
    
    # ========================================
    # STEP 3: Phase 2 - Fill the Gaps (Volume Strategy)
    # ========================================
    # Query remaining items sorted by stock (highest first) - use what we have too much of
    
    # Get IDs of already selected items
    selected_snack_ids = set(s['item'].id for s in selected_snacks)
    selected_juice_ids = set(j['item'].id for j in selected_juices)
    
    # Fill snacks
    if snacks_added < snack_limit:
        # Get available snacks sorted by stock (highest first)
        available_snacks = Item.objects.filter(
            category='snack',
            current_stock__gt=0
        ).exclude(
            id__in=selected_snack_ids
        ).order_by('-current_stock')  # Highest stock first
        
        for item in available_snacks:
            if snacks_added >= snack_limit:
                break
            selected_snacks.append({'item': item, 'quantity': 1, 'is_favorite': False})
            snacks_added += 1
    
    # Fill juices (skip if limit is 0)
    if juice_limit > 0 and juices_added < juice_limit:
        # Get available juices sorted by stock (highest first)
        available_juices = Item.objects.filter(
            category='juice',
            current_stock__gt=0
        ).exclude(
            id__in=selected_juice_ids
        ).order_by('-current_stock')  # Highest stock first
        
        for item in available_juices:
            if juices_added >= juice_limit:
                break
            selected_juices.append({'item': item, 'quantity': 1, 'is_favorite': False})
            juices_added += 1
    
    # Now distribute quantities to meet limits
    # We have items selected, but each has quantity 1
    # We need to distribute remaining quantities
    
    total_snacks_needed = snack_limit
    total_juices_needed = juice_limit
    
    current_snack_count = len(selected_snacks)
    current_juice_count = len(selected_juices)
    
    # Distribute remaining snack quantities (prioritize favorites and cheap items)
    if current_snack_count > 0 and total_snacks_needed > current_snack_count:
        remaining_snacks = total_snacks_needed - current_snack_count
        
        # Sort by cost (cheapest first), but favorites get priority
        sorted_snacks = sorted(selected_snacks, key=lambda x: (0 if x['is_favorite'] else 1, x['item'].cost_price))
        
        # Distribute remaining to cheapest items (with favorites getting priority)
        while remaining_snacks > 0:
            for snack in sorted_snacks:
                if remaining_snacks <= 0:
                    break
                snack['quantity'] += 1
                remaining_snacks -= 1
    
    # Distribute remaining juice quantities
    if current_juice_count > 0 and total_juices_needed > current_juice_count:
        remaining_juices = total_juices_needed - current_juice_count
        
        # Sort by cost (cheapest first), but favorites get priority
        sorted_juices = sorted(selected_juices, key=lambda x: (0 if x['is_favorite'] else 1, x['item'].cost_price))
        
        # Distribute remaining to cheapest items (with favorites getting priority)
        while remaining_juices > 0:
            for juice in sorted_juices:
                if remaining_juices <= 0:
                    break
                juice['quantity'] += 1
                remaining_juices -= 1
    
    # ========================================
    # STEP 4: Phase 3 - The "Profit Protector" Loop
    # ========================================
    def calculate_total_cost():
        """Calculate total cost of current selection"""
        total = Decimal('0')
        for s in selected_snacks:
            total += s['item'].cost_price * Decimal(str(s['quantity']))
        for j in selected_juices:
            total += j['item'].cost_price * Decimal(str(j['quantity']))
        return total
    
    current_total_cost = calculate_total_cost()
    max_iterations = 500
    iteration = 0
    
    while current_total_cost > max_allowable_cost and iteration < max_iterations:
        iteration += 1
        swap_made = False
        
        # Find the most expensive item that is NOT a favorite
        # Check snacks first
        non_favorite_snacks = [s for s in selected_snacks if not s['is_favorite'] and s['quantity'] > 0]
        non_favorite_juices = [j for j in selected_juices if not j['is_favorite'] and j['quantity'] > 0]
        
        # Sort by cost per unit (most expensive first)
        all_non_favorites = []
        for s in non_favorite_snacks:
            all_non_favorites.append(('snack', s, s['item'].cost_price))
        for j in non_favorite_juices:
            all_non_favorites.append(('juice', j, j['item'].cost_price))
        
        # Sort by cost descending (most expensive first)
        all_non_favorites.sort(key=lambda x: x[2], reverse=True)
        
        for category, expensive_item, cost in all_non_favorites:
            if swap_made:
                break
            
            # Find the cheapest available item in the same category
            current_item_ids = set()
            if category == 'snack':
                current_item_ids = set(s['item'].id for s in selected_snacks)
            else:
                current_item_ids = set(j['item'].id for j in selected_juices)
            
            # Get cheapest item not already selected
            cheapest_item = Item.objects.filter(
                category=category,
                current_stock__gt=0
            ).exclude(
                id__in=current_item_ids
            ).order_by('cost_price').first()
            
            if cheapest_item and cheapest_item.cost_price < expensive_item['item'].cost_price:
                # Perform swap: Reduce expensive item quantity, add cheap item
                if expensive_item['quantity'] > 1:
                    # Just reduce quantity of expensive item
                    expensive_item['quantity'] -= 1
                    
                    # Add cheap item or increase its quantity
                    if category == 'snack':
                        # Check if cheap item already in list
                        found = False
                        for s in selected_snacks:
                            if s['item'].id == cheapest_item.id:
                                s['quantity'] += 1
                                found = True
                                break
                        if not found:
                            selected_snacks.append({'item': cheapest_item, 'quantity': 1, 'is_favorite': False})
                    else:
                        found = False
                        for j in selected_juices:
                            if j['item'].id == cheapest_item.id:
                                j['quantity'] += 1
                                found = True
                                break
                        if not found:
                            selected_juices.append({'item': cheapest_item, 'quantity': 1, 'is_favorite': False})
                    
                    swap_made = True
                
                elif expensive_item['quantity'] == 1:
                    # Replace entirely
                    if category == 'snack':
                        selected_snacks.remove(expensive_item)
                        # Add cheap item
                        found = False
                        for s in selected_snacks:
                            if s['item'].id == cheapest_item.id:
                                s['quantity'] += 1
                                found = True
                                break
                        if not found:
                            selected_snacks.append({'item': cheapest_item, 'quantity': 1, 'is_favorite': False})
                    else:
                        selected_juices.remove(expensive_item)
                        found = False
                        for j in selected_juices:
                            if j['item'].id == cheapest_item.id:
                                j['quantity'] += 1
                                found = True
                                break
                        if not found:
                            selected_juices.append({'item': cheapest_item, 'quantity': 1, 'is_favorite': False})
                    
                    swap_made = True
        
        if not swap_made:
            # No valid swaps possible, break
            break
        
        # Recalculate cost
        current_total_cost = calculate_total_cost()
    
    # ========================================
    # STEP 5: Calculate Final Values
    # ========================================
    final_total_cost = calculate_total_cost() + packaging_cost
    estimated_profit = selling_price - final_total_cost
    profit_margin = (estimated_profit / selling_price * 100) if selling_price > 0 else Decimal('0')
    
    # Clean up: remove items with 0 quantity
    selected_snacks = [s for s in selected_snacks if s['quantity'] > 0]
    selected_juices = [j for j in selected_juices if j['quantity'] > 0]
    
    # Check if we met the margin requirement
    success = profit_margin >= (MIN_PROFIT_MARGIN * 100)
    
    # Build result message
    if success:
        message = f"Bundle generated successfully with {profit_margin:.1f}% profit margin."
    else:
        message = f"Warning: Could only achieve {profit_margin:.1f}% margin (target: {MIN_PROFIT_MARGIN * 100}%). Consider adjusting favorites or pricing."
    
    return {
        'selected_snacks': [(s['item'], s['quantity'], s['is_favorite']) for s in selected_snacks],
        'selected_juices': [(j['item'], j['quantity'], j['is_favorite']) for j in selected_juices],
        'total_cost': final_total_cost,
        'estimated_profit': estimated_profit,
        'profit_margin': profit_margin,
        'success': success,
        'message': message,
        'snack_count': sum(s['quantity'] for s in selected_snacks),
        'juice_count': sum(j['quantity'] for j in selected_juices),
        'max_allowable_cost': max_allowable_cost + packaging_cost,  # Include packaging for reference
    }


def generate_bundle_for_order(order, target_margin=38):
    """
    Generate optimized bundle quantities for an existing CustomerOrder.
    This is a wrapper that integrates with the existing order system.
    
    Args:
        order: CustomerOrder instance
        target_margin: Target profit margin percentage (default 38)
    
    Returns:
        dict with new quantities and financial summary
    """
    from .models import Item, CustomerOrderItem
    
    # Get current order items
    order_items = order.customer_order_items.select_related('item')
    
    # Build bundle config from order
    bundle_config = {
        'name': order.get_bundle_type_display(),
        'selling_price': order.total_revenue if order.total_revenue > 0 else Decimal('0'),
        'snack_limit': sum(oi.quantity for oi in order_items if oi.item.category == 'snack'),
        'juice_limit': sum(oi.quantity for oi in order_items if oi.item.category == 'juice'),
        'packaging_cost': Decimal('0'),  # Can be configured if needed
    }
    
    # Get customer favorites (starred items)
    customer_favorites = [oi.item for oi in order_items if oi.is_starred]
    
    # If no selling price set, calculate based on margin
    if bundle_config['selling_price'] == 0:
        # We'll need to calculate suggested price after
        pass
    
    # Generate smart bundle
    result = generate_smart_bundle(bundle_config, customer_favorites)
    
    return result
