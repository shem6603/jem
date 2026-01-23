from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Item(models.Model):
    """Individual snack or juice item in inventory"""
    CATEGORY_CHOICES = [
        ('snack', 'Snack'),
        ('juice', 'Juice'),
    ]
    
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    cost_per_bag = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], help_text="Cost per bag/case", default=Decimal('0.01'))
    units_per_bag = models.IntegerField(default=1, validators=[MinValueValidator(1)], help_text="Number of units in one bag/case")
    cost_price = models.DecimalField(max_digits=10, decimal_places=4, validators=[MinValueValidator(Decimal('0.01'))], help_text="Auto-calculated: cost per unit")
    sell_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], blank=True, null=True, help_text="Sell price (set via different logic)")
    current_stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    image = models.ImageField(upload_to='items/', blank=True, null=True)
    is_spicy = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['current_stock']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.category})"
    
    def save(self, *args, **kwargs):
        """Override save to auto-calculate cost_price from cost_per_bag and units_per_bag"""
        if self.cost_per_bag and self.units_per_bag and self.units_per_bag > 0:
            self.cost_price = self.cost_per_bag / Decimal(str(self.units_per_bag))
        super().save(*args, **kwargs)
    
    @property
    def is_low_stock(self):
        """Check if stock is below 5"""
        return self.current_stock < 5
    
    @property
    def profit_per_unit(self):
        """Calculate profit per unit"""
        if self.sell_price:
            return self.sell_price - self.cost_price
        return None
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.sell_price and self.sell_price > 0:
            return ((self.sell_price - self.cost_price) / self.sell_price) * 100
        return None


class BundleType(models.Model):
    """Defines bundle rules (e.g., Big Bundle requires 30 snacks + 24 juices)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    required_snacks = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    required_juices = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.required_snacks} Snacks + {self.required_juices} Juices)"
    
    @property
    def total_items(self):
        """Total items required for this bundle"""
        return self.required_snacks + self.required_juices


class Customer(models.Model):
    """Customer information"""
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True, null=True)
    pickup_spot = models.CharField(max_length=200, blank=True, null=True, help_text="Pickup location/spot")
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class Order(models.Model):
    """Order linking Customer to Bundle with automatic profit calculations"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders')
    bundle_type = models.ForeignKey(BundleType, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Auto-calculated fields
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    profit_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Order #{self.id} - {self.customer.name} - {self.bundle_type.name}"
    
    def calculate_totals(self):
        """Calculate total revenue, cost, profit, and margin"""
        # Force a fresh query to ensure we get all order items
        order_items = list(OrderItem.objects.filter(order_id=self.id).select_related('item'))
        
        # Fixed revenue prices based on bundle type
        bundle_revenue_prices = {
            '10 Snacks': Decimal('1000.00'),
            '25 Snacks': Decimal('3000.00'),
            '25 Juices': Decimal('2700.00'),
            'Mega Mix': Decimal('5500.00'),
        }
        
        # Check if this bundle type has a fixed price
        bundle_name = self.bundle_type.name if self.bundle_type else ''
        if bundle_name in bundle_revenue_prices:
            # Use fixed revenue price for predefined bundles
            self.total_revenue = bundle_revenue_prices[bundle_name]
        else:
            # For custom orders, calculate revenue from item sell prices
            self.total_revenue = sum(
                (item.item.sell_price * item.quantity) if item.item.sell_price else Decimal('0.00')
                for item in order_items
            )
        
        # Always calculate cost from items - ensure cost_price exists
        self.total_cost = Decimal('0.00')
        for item in order_items:
            if item.item.cost_price:
                self.total_cost += item.item.cost_price * Decimal(str(item.quantity))
        
        self.net_profit = self.total_revenue - self.total_cost
        
        if self.total_revenue > 0:
            self.profit_margin = (self.net_profit / self.total_revenue) * 100
        else:
            self.profit_margin = 0
        
        # Update fields directly in database without triggering save() to avoid recursion
        if self.id:
            Order.objects.filter(id=self.id).update(
                total_revenue=self.total_revenue,
                total_cost=self.total_cost,
                net_profit=self.net_profit,
                profit_margin=self.profit_margin
            )
    
    def save(self, *args, **kwargs):
        """Override save to auto-calculate totals"""
        # Save first to get an ID if this is a new object
        super().save(*args, **kwargs)
        # Calculate totals after order items are saved
        # calculate_totals() uses update() to avoid recursion
        if self.id:
            self.calculate_totals()
            # Refresh from database to get updated values
            self.refresh_from_db()


class OrderItem(models.Model):
    """Individual items in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    
    class Meta:
        unique_together = ['order', 'item']
    
    def __str__(self):
        return f"{self.quantity}x {self.item.name} in Order #{self.order.id}"
    
    @property
    def subtotal(self):
        """Subtotal for this order item"""
        if self.item.sell_price:
            return self.item.sell_price * self.quantity
        return Decimal('0.00')
    
    @property
    def cost(self):
        """Total cost for this order item"""
        return self.item.cost_price * self.quantity


class Receipt(models.Model):
    """Receipts for accounting purposes"""
    title = models.CharField(max_length=200)
    receipt_file = models.FileField(upload_to='receipts/%Y/%m/%d/')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='uploaded_receipts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - ${self.amount} ({self.created_at.date()})"


class CustomerOrder(models.Model):
    """Customer-submitted orders that require approval for custom bundles"""
    STATUS_CHOICES = [
        ('pending_approval', 'Pending Approval'),  # For custom bundles
        ('approved', 'Approved'),  # Admin approved, awaiting payment
        ('payment_uploaded', 'Payment Uploaded'),  # Customer uploaded proof
        ('payment_verified', 'Payment Verified'),  # Admin verified payment
        ('processing', 'Processing'),  # Being prepared
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    BUNDLE_TYPE_CHOICES = [
        ('10_snacks', '10 Snacks'),
        ('25_snacks', '25 Snacks'),
        ('25_juices', '25 Juices'),
        ('mega_mix', 'Mega Mix'),
        ('custom', 'Custom'),
    ]
    
    # Customer info
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20)
    customer_whatsapp = models.CharField(max_length=20, blank=True, null=True)
    pickup_spot = models.CharField(max_length=200, help_text="Pickup location")
    
    # Order details
    bundle_type = models.CharField(max_length=20, choices=BUNDLE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_approval')
    
    # For custom bundles - admin can modify
    admin_notes = models.TextField(blank=True, help_text="Notes from admin about order modifications")
    
    # Financial (calculated by algorithm for custom, fixed for standard)
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    profit_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Payment proof
    payment_proof = models.ImageField(upload_to='payment_proofs/%Y/%m/%d/', blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., Bank Transfer, NCB, etc.")
    
    # Tracking
    order_reference = models.CharField(max_length=20, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_orders')
    payment_deadline = models.DateTimeField(null=True, blank=True, help_text="24-hour deadline for payment after approval")
    payment_reminder_sent = models.BooleanField(default=False, help_text="Whether payment reminder email has been sent")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['bundle_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Order {self.order_reference} - {self.customer_name} - {self.get_bundle_type_display()}"
    
    def save(self, *args, **kwargs):
        if not self.order_reference:
            # Generate unique order reference
            import random
            import string
            while True:
                ref = 'JEM-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                if not CustomerOrder.objects.filter(order_reference=ref).exists():
                    self.order_reference = ref
                    break
        super().save(*args, **kwargs)
    
    def calculate_totals(self):
        """Calculate totals based on order items"""
        items = self.customer_order_items.select_related('item')
        
        # Fixed prices for standard bundles
        fixed_prices = {
            '10_snacks': Decimal('1000.00'),
            '25_snacks': Decimal('3000.00'),
            '25_juices': Decimal('2700.00'),
            'mega_mix': Decimal('5500.00'),
        }
        
        if self.bundle_type in fixed_prices:
            self.total_revenue = fixed_prices[self.bundle_type]
        else:
            # For custom, revenue is calculated to maintain profit margin
            pass  # Will be set by algorithm
        
        # Calculate total cost
        self.total_cost = sum(
            item.item.cost_price * Decimal(str(item.quantity))
            for item in items
        )
        
        self.net_profit = self.total_revenue - self.total_cost
        if self.total_revenue > 0:
            self.profit_margin = (self.net_profit / self.total_revenue) * 100
        
        CustomerOrder.objects.filter(id=self.id).update(
            total_revenue=self.total_revenue,
            total_cost=self.total_cost,
            net_profit=self.net_profit,
            profit_margin=self.profit_margin
        )
    
    @property
    def is_custom(self):
        return self.bundle_type == 'custom'
    
    @property
    def needs_approval(self):
        return self.is_custom and self.status == 'pending_approval'
    
    @property
    def can_show_price(self):
        """Price is visible for standard bundles, or approved custom bundles"""
        if not self.is_custom:
            return True
        return self.status not in ['pending_approval']
    
    def is_payment_overdue(self):
        """Check if payment deadline has passed"""
        from django.utils import timezone
        if self.status == 'approved' and self.payment_deadline:
            return timezone.now() > self.payment_deadline
        return False


class CustomerOrderItem(models.Model):
    """Items selected by customer for their order"""
    order = models.ForeignKey(CustomerOrder, on_delete=models.CASCADE, related_name='customer_order_items')
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='customer_order_items')
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    is_starred = models.BooleanField(default=False, help_text="Customer wants more of this item")
    
    class Meta:
        unique_together = ['order', 'item']
    
    def __str__(self):
        star = " ⭐" if self.is_starred else ""
        return f"{self.quantity}x {self.item.name}{star} in {self.order.order_reference}"
    
    @property
    def subtotal_cost(self):
        return self.item.cost_price * self.quantity


class BankingInfo(models.Model):
    """Company banking information for customers to make payments"""
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50)
    account_type = models.CharField(max_length=50, blank=True, help_text="e.g., Savings, Chequing")
    branch = models.CharField(max_length=100, blank=True)
    additional_info = models.TextField(blank=True, help_text="Additional payment instructions")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Banking Info"
        ordering = ['bank_name']
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


class PushSubscription(models.Model):
    """Store push notification subscriptions for users"""
    endpoint = models.TextField(unique=True)  # Changed from URLField to TextField for MariaDB compatibility
    keys = models.JSONField(help_text="Auth and p256dh keys")
    user_agent = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['endpoint'], name='pushsubscription_endpoint_idx'),
        ]
    
    def __str__(self):
        return f"Push Subscription - {self.endpoint[:50]}..."


class CustomerSuggestion(models.Model):
    """Customer suggestions for new items or general feedback"""
    SUGGESTION_TYPES = [
        ('new_item', 'New Item Request'),
        ('feedback', 'General Feedback'),
    ]
    
    order = models.ForeignKey(CustomerOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='suggestions')
    suggestion_type = models.CharField(max_length=20, choices=SUGGESTION_TYPES)
    item_name = models.CharField(max_length=200, blank=True, help_text="Name of item being suggested (for new_item type)")
    message = models.TextField()
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_reviewed = models.BooleanField(default=False)
    admin_response = models.TextField(blank=True, help_text="Admin's response to the suggestion")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['suggestion_type']),
            models.Index(fields=['is_reviewed']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        suggestion_type_display = dict(self.SUGGESTION_TYPES).get(self.suggestion_type, self.suggestion_type)
        return f"{suggestion_type_display} from {self.customer_name} - {self.created_at.strftime('%Y-%m-%d')}"
