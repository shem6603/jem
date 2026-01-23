"""
Smart Bundle Generation Utility using Linear Programming (PuLP)
Mathematically guarantees optimal bundles that meet profit margin requirements
"""
from decimal import Decimal
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatus, PULP_CBC_CMD


# Minimum profit margin (38%)
MIN_PROFIT_MARGIN = Decimal('0.38')

# Quantity limits
STARRED_MIN_QTY = 1  # Starred items must have at least 1
STARRED_MAX_QTY = 4  # Starred items can have up to 4
REGULAR_MIN_QTY = 0  # Regular items can be 0 (excluded if too expensive)
REGULAR_MAX_QTY = 2  # Regular items limited to 2 for variety


def solve_smart_bundle(
    bundle_config,
    customer_favorites,
    available_snacks,
    available_juices,
    enforce_margin=True,
    target_margin=None,
    force_non_random=False,
    ignore_stock=False
):
    """
    Use Linear Programming to find the optimal bundle that minimizes cost
    while meeting all constraints.
    
    Args:
        bundle_config (dict): Configuration for the bundle
        customer_favorites (list): List of Item objects that are starred
        available_snacks (list): List of available snack Items
        available_juices (list): List of available juice Items
        enforce_margin (bool): Whether to enforce the profit margin constraint
        target_margin (Decimal): Target profit margin (0-1). If None, uses MIN_PROFIT_MARGIN
        force_non_random (bool): If True, disable variety caps even when no favorites
        ignore_stock (bool): If True, ignore stock limits when solving
    
    Returns:
        dict: Solution with item quantities, or None if infeasible
    """
    selling_price = float(bundle_config.get('selling_price', 0))
    snack_limit = int(bundle_config.get('snack_limit', 0))
    juice_limit = int(bundle_config.get('juice_limit', 0))
    packaging_cost = float(bundle_config.get('packaging_cost', 0))
    
    # Use provided target margin or default to MIN_PROFIT_MARGIN
    margin_to_use = float(target_margin) if target_margin is not None else float(MIN_PROFIT_MARGIN)
    
    # Get favorite IDs for quick lookup
    favorite_ids = set(item.id for item in customer_favorites)
    
    # Detect if this is a random selection (no favorites = variety mode)
    is_random_selection = len(favorite_ids) == 0
    if force_non_random:
        is_random_selection = False
    
    # Create the LP problem - we want to MINIMIZE total cost
    prob = LpProblem("SmartBundle", LpMinimize)
    
    # Create decision variables for each item (quantity to include)
    snack_vars = {}
    juice_vars = {}
    
    # Calculate dynamic max quantities based on available variety
    # This ensures we can fill the bundle even with limited item variety
    num_snacks_available = len(available_snacks)
    num_juices_available = len(available_juices)
    
    # Early exit: if we need items but have none available
    if snack_limit > 0 and num_snacks_available == 0:
        return None
    if juice_limit > 0 and num_juices_available == 0:
        return None
    
    # Calculate total available stock
    total_snack_stock = sum(item.current_stock for item in available_snacks) if available_snacks else 0
    total_juice_stock = sum(item.current_stock for item in available_juices) if available_juices else 0
    
    # Early exit: if total stock is insufficient (unless ignoring stock)
    if not ignore_stock:
        if snack_limit > total_snack_stock:
            return None
        if juice_limit > total_juice_stock:
            return None
    
    # Dynamic max for snacks: ensure we can fill snack_limit
    # Calculate ceiling of (snack_limit / num_items) + generous buffer
    if num_snacks_available > 0 and snack_limit > 0:
        snack_dynamic_max = max(STARRED_MAX_QTY, ((snack_limit + num_snacks_available - 1) // num_snacks_available) + 4)
    else:
        snack_dynamic_max = STARRED_MAX_QTY
    
    # Dynamic max for juices: ensure we can fill juice_limit
    if num_juices_available > 0 and juice_limit > 0:
        juice_dynamic_max = max(STARRED_MAX_QTY, ((juice_limit + num_juices_available - 1) // num_juices_available) + 4)
    else:
        juice_dynamic_max = STARRED_MAX_QTY
    
    # Create variables for snacks
    for item in available_snacks:
        is_favorite = item.id in favorite_ids
        stock_limit = item.current_stock if not ignore_stock else snack_limit
        
        if is_favorite:
            # Starred: must include at least 1, up to dynamic max (capped by stock)
            min_qty = STARRED_MIN_QTY
            max_qty = min(stock_limit, snack_dynamic_max)
        else:
            # Regular: use dynamic max to ensure we can fill the bundle
            min_qty = REGULAR_MIN_QTY
            if is_random_selection:
                # For random selection: limit max to encourage variety
                # Allow max 3 per item to force using more different items
                max_qty = min(stock_limit, 3)
            else:
                # For selected items: allow up to dynamic max
                max_qty = min(stock_limit, snack_dynamic_max)
        
        snack_vars[item.id] = LpVariable(
            f"snack_{item.id}",
            lowBound=min_qty,
            upBound=max_qty,
            cat='Integer'
        )
    
    # Create variables for juices
    for item in available_juices:
        is_favorite = item.id in favorite_ids
        stock_limit = item.current_stock if not ignore_stock else juice_limit
        
        if is_favorite:
            # Starred: must include at least 1, up to dynamic max (capped by stock)
            min_qty = STARRED_MIN_QTY
            max_qty = min(stock_limit, juice_dynamic_max)
        else:
            # Regular: use dynamic max to ensure we can fill the bundle
            min_qty = REGULAR_MIN_QTY
            if is_random_selection:
                # For random selection: limit max to encourage variety
                # Allow max 2 per item (juices are more expensive) to force using more different items
                max_qty = min(stock_limit, 2)
            else:
                # For selected items: allow up to dynamic max
                max_qty = min(stock_limit, juice_dynamic_max)
        
        juice_vars[item.id] = LpVariable(
            f"juice_{item.id}",
            lowBound=min_qty,
            upBound=max_qty,
            cat='Integer'
        )
    
    # Build item lookup for cost calculation
    snack_lookup = {item.id: item for item in available_snacks}
    juice_lookup = {item.id: item for item in available_juices}
    
    # ========================================
    # OBJECTIVE: Minimize Total Cost (with preference for favorites and variety)
    # ========================================
    # Detect if this is a random selection (no favorites = variety mode)
    # (already computed above, kept for clarity)
    
    # Add a small penalty for non-favorites to encourage more favorites
    # This ensures favorites get more quantity when costs are similar
    PENALTY_FACTOR = 0.01  # Small penalty to prefer favorites
    
    total_cost_expr = lpSum([
        float(snack_lookup[item_id].cost_price) * snack_vars[item_id]
        for item_id in snack_vars
    ]) + lpSum([
        float(juice_lookup[item_id].cost_price) * juice_vars[item_id]
        for item_id in juice_vars
    ])
    
    # Add penalty for non-favorites (encourages solver to prefer favorites)
    non_favorite_penalty = lpSum([
        PENALTY_FACTOR * snack_vars[item_id]
        for item_id in snack_vars
        if item_id not in favorite_ids
    ]) + lpSum([
        PENALTY_FACTOR * juice_vars[item_id]
        for item_id in juice_vars
        if item_id not in favorite_ids
    ])
    
    prob += total_cost_expr + non_favorite_penalty, "TotalCost"
    
    # ========================================
    # CONSTRAINTS
    # ========================================
    
    # Constraint 1: Exact snack count
    if snack_limit > 0 and snack_vars:
        prob += lpSum(snack_vars.values()) == snack_limit, "ExactSnackCount"
    
    # Constraint 2: Exact juice count
    if juice_limit > 0 and juice_vars:
        prob += lpSum(juice_vars.values()) == juice_limit, "ExactJuiceCount"
    
    # Constraint 2.5: Ensure all selected items are included (at least 1 unit each)
    # This is important when user selects specific items - they should all be in the bundle
    # Only enforce if we have a small number of items (inclusion model)
    if len(snack_vars) <= snack_limit and snack_limit > 0:
        # If we have fewer or equal items than needed, include all of them
        for item_id, var in snack_vars.items():
            prob += var >= 1, f"IncludeSnack_{item_id}"
    
    if len(juice_vars) <= juice_limit and juice_limit > 0:
        # If we have fewer or equal items than needed, include all of them
        for item_id, var in juice_vars.items():
            prob += var >= 1, f"IncludeJuice_{item_id}"
    
    
    # Constraint 3: Profit Margin (The Balance Enforcer)
    if enforce_margin and selling_price > 0:
        # max_allowed_cost = selling_price * (1 - margin) - packaging_cost
        max_allowed_cost = selling_price * (1 - margin_to_use) - packaging_cost
        
        total_cost_expr = lpSum([
            float(snack_lookup[item_id].cost_price) * snack_vars[item_id]
            for item_id in snack_vars
        ]) + lpSum([
            float(juice_lookup[item_id].cost_price) * juice_vars[item_id]
            for item_id in juice_vars
        ])
        
        prob += total_cost_expr <= max_allowed_cost, "ProfitMarginConstraint"
    
    # Constraint 4: Ensure favorites get more quantity (at least 2 units each when possible)
    # This ensures starred items get more than non-starred items
    favorite_snack_vars = [snack_vars[item_id] for item_id in snack_vars if item_id in favorite_ids]
    favorite_juice_vars = [juice_vars[item_id] for item_id in juice_vars if item_id in favorite_ids]
    
    # Ensure each favorite gets at least 2 units (if we have enough slots and stock)
    # This is a soft constraint - only apply if bundle is large enough
    if favorite_snack_vars:
        # Only enforce if we have at least 2 slots per favorite + some buffer
        slots_needed = len(favorite_snack_vars) * 2
        if snack_limit >= slots_needed + 2:  # Extra buffer for non-favorites
            for item_id in favorite_ids:
                if item_id in snack_vars:
                    item = snack_lookup[item_id]
                    if item.current_stock >= 2:
                        prob += snack_vars[item_id] >= 2, f"FavoriteSnackMin_{item_id}"
    
    if favorite_juice_vars:
        slots_needed = len(favorite_juice_vars) * 2
        if juice_limit >= slots_needed + 2:
            for item_id in favorite_ids:
                if item_id in juice_vars:
                    item = juice_lookup[item_id]
                    if item.current_stock >= 2:
                        prob += juice_vars[item_id] >= 2, f"FavoriteJuiceMin_{item_id}"
    
    # ========================================
    # SOLVE
    # ========================================
    solver = PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    
    # Check if solution found
    if LpStatus[prob.status] != 'Optimal':
        return None
    
    # Extract solution
    result_snacks = []
    result_juices = []
    total_cost = Decimal('0')
    
    for item_id, var in snack_vars.items():
        qty = int(var.varValue) if var.varValue else 0
        if qty > 0:
            item = snack_lookup[item_id]
            is_fav = item_id in favorite_ids
            result_snacks.append({
                'item': item,
                'quantity': qty,
                'is_favorite': is_fav
            })
            total_cost += item.cost_price * Decimal(str(qty))
    
    for item_id, var in juice_vars.items():
        qty = int(var.varValue) if var.varValue else 0
        if qty > 0:
            item = juice_lookup[item_id]
            is_fav = item_id in favorite_ids
            result_juices.append({
                'item': item,
                'quantity': qty,
                'is_favorite': is_fav
            })
            total_cost += item.cost_price * Decimal(str(qty))
    
    return {
        'snacks': result_snacks,
        'juices': result_juices,
        'total_cost': total_cost
    }


def generate_smart_bundle(
    bundle_config,
    customer_favorites=None,
    excluded_item_ids=None,
    target_margin=None,
    allowed_item_ids=None,
    ignore_stock=False
):
    """
    Generate a smart bundle using Linear Programming optimization.
    Mathematically guarantees the minimum cost while meeting all constraints.
    
    Args:
        bundle_config (dict): Configuration for the bundle
            - name (str): Bundle name
            - selling_price (Decimal): The fixed selling price
            - snack_limit (int): Number of snacks required
            - juice_limit (int): Number of juices required
            - packaging_cost (Decimal): Cost of packaging (default 0)
        
        customer_favorites (QuerySet/List): Item objects the customer specifically requested
        excluded_item_ids (list): List of item IDs to exclude from selection
        target_margin (Decimal): Target profit margin as decimal (e.g., 0.38 for 38%). If None, uses MIN_PROFIT_MARGIN
        allowed_item_ids (list): If provided, ONLY these items can be used (for selected orders)
        ignore_stock (bool): If True, ignore stock limits and allow zero-stock items
    
    Returns:
        dict: {
            'selected_snacks': list of (Item, quantity, is_favorite) tuples,
            'selected_juices': list of (Item, quantity, is_favorite) tuples,
            'total_cost': Decimal,
            'estimated_profit': Decimal,
            'profit_margin': Decimal,
            'success': bool,
            'margin_met': bool,
            'message': str
        }
    """
    from .models import Item
    
    # Extract config values
    selling_price = Decimal(str(bundle_config.get('selling_price', 0)))
    snack_limit = int(bundle_config.get('snack_limit', 0))
    juice_limit = int(bundle_config.get('juice_limit', 0))
    packaging_cost = Decimal(str(bundle_config.get('packaging_cost', 0)))
    
    # Use provided target margin or default to MIN_PROFIT_MARGIN
    margin_decimal = Decimal(str(target_margin)) if target_margin is not None else MIN_PROFIT_MARGIN
    
    if customer_favorites is None:
        customer_favorites = []
    
    if excluded_item_ids is None:
        excluded_item_ids = []
    
    excluded_set = set(excluded_item_ids)
    
    # ========================================
    # STEP 1: Inventory Prep
    # ========================================
    if allowed_item_ids is not None:
        # For selected orders: ONLY use items from the allowed list
        if ignore_stock:
            all_items = Item.objects.filter(id__in=allowed_item_ids)
        else:
            all_items = Item.objects.filter(id__in=allowed_item_ids, current_stock__gt=0)
    else:
        # Fetch all items where current_stock > 0, exclude excluded items
        if ignore_stock:
            all_items = Item.objects.exclude(id__in=excluded_set)
        else:
            all_items = Item.objects.filter(current_stock__gt=0).exclude(id__in=excluded_set)
    
    # Split into snacks and juices
    available_snacks = [item for item in all_items if item.category == 'snack']
    available_juices = [item for item in all_items if item.category == 'juice']
    
    # Calculate max allowable cost for reference (using the provided margin)
    max_allowable_cost = (selling_price * (1 - margin_decimal)) - packaging_cost
    
    # ========================================
    # STEP 2: Solve with LP (with margin constraint)
    # ========================================
    solution = solve_smart_bundle(
        bundle_config,
        customer_favorites,
        available_snacks,
        available_juices,
        enforce_margin=True,
        target_margin=margin_decimal,
        force_non_random=allowed_item_ids is not None,
        ignore_stock=ignore_stock
    )
    
    margin_met = True
    
    # ========================================
    # STEP 3: Fallback if infeasible
    # ========================================
    if solution is None:
        # Re-run without profit constraint to get "Best Possible" bundle
        solution = solve_smart_bundle(
            bundle_config,
            customer_favorites,
            available_snacks,
            available_juices,
            enforce_margin=False,
            target_margin=margin_decimal,
            force_non_random=allowed_item_ids is not None,
            ignore_stock=ignore_stock
        )
        margin_met = False
    
    # ========================================
    # STEP 4: Handle complete failure
    # ========================================
    if solution is None:
        # Even without margin constraint, couldn't solve - diagnose the issue
        total_snack_stock = sum(item.current_stock for item in available_snacks) if available_snacks else 0
        total_juice_stock = sum(item.current_stock for item in available_juices) if available_juices else 0
        
        # Build helpful error message
        issues = []
        if snack_limit > 0 and len(available_snacks) == 0:
            issues.append(f"No snacks available in inventory (need {snack_limit})")
        elif snack_limit > total_snack_stock:
            issues.append(f"Not enough snack stock: have {total_snack_stock}, need {snack_limit}")
        
        if juice_limit > 0 and len(available_juices) == 0:
            issues.append(f"No juices available in inventory (need {juice_limit})")
        elif juice_limit > total_juice_stock:
            issues.append(f"Not enough juice stock: have {total_juice_stock}, need {juice_limit}")
        
        if not issues:
            issues.append("Bundle constraints could not be satisfied with current inventory")
        
        error_message = "Unable to create bundle: " + "; ".join(issues)
        
        return {
            'selected_snacks': [],
            'selected_juices': [],
            'total_cost': Decimal('0'),
            'estimated_profit': Decimal('0'),
            'profit_margin': Decimal('0'),
            'success': False,
            'margin_met': False,
            'message': error_message,
            'snack_count': 0,
            'juice_count': 0,
            'max_allowable_cost': max_allowable_cost + packaging_cost,
        }
    
    # ========================================
    # STEP 5: Calculate Final Metrics
    # ========================================
    total_cost = solution['total_cost'] + packaging_cost
    estimated_profit = selling_price - total_cost
    profit_margin = (estimated_profit / selling_price * 100) if selling_price > 0 else Decimal('0')
    
    # Count totals
    snack_count = sum(s['quantity'] for s in solution['snacks'])
    juice_count = sum(j['quantity'] for j in solution['juices'])
    
    # Check if we actually met the target margin (might be slightly off due to rounding)
    success = profit_margin >= (margin_decimal * 100)
    
    # Build result message
    target_margin_pct = margin_decimal * 100
    if success and margin_met:
        message = f"Bundle optimized successfully with {profit_margin:.1f}% profit margin."
    elif not margin_met:
        message = f"Warning: {target_margin_pct:.0f}% margin impossible with selected favorites. Best achievable: {profit_margin:.1f}%. Consider adjusting favorites or pricing."
    else:
        message = f"Bundle created with {profit_margin:.1f}% margin."
    
    return {
        'selected_snacks': [(s['item'], s['quantity'], s['is_favorite']) for s in solution['snacks']],
        'selected_juices': [(j['item'], j['quantity'], j['is_favorite']) for j in solution['juices']],
        'total_cost': total_cost,
        'estimated_profit': estimated_profit,
        'profit_margin': profit_margin,
        'success': success,
        'margin_met': margin_met,
        'message': message,
        'snack_count': snack_count,
        'juice_count': juice_count,
        'max_allowable_cost': max_allowable_cost + packaging_cost,
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
    
    # Check if this is a selected order (has starred items)
    has_starred_items = any(oi.is_starred for oi in order_items)
    
    # Convert margin percentage to decimal
    margin_decimal = Decimal(str(target_margin)) / Decimal('100')
    
    if has_starred_items:
        # Selected order: only use items already in the order
        allowed_item_ids = list(order.customer_order_items.values_list('item_id', flat=True))
        result = generate_smart_bundle(
            bundle_config, 
            customer_favorites, 
            excluded_item_ids=None,
            target_margin=margin_decimal,
            allowed_item_ids=allowed_item_ids
        )
    else:
        # Random order: allow any items
        result = generate_smart_bundle(
            bundle_config, 
            customer_favorites, 
            excluded_item_ids=None,
            target_margin=margin_decimal,
            allowed_item_ids=None
        )
    
    return result
