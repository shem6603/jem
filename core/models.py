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
