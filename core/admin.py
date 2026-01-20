from django.contrib import admin
from .models import Item, BundleType, Customer, Order, OrderItem, Receipt, CustomerOrder, CustomerOrderItem, BankingInfo


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'current_stock', 'cost_price', 'sell_price', 'profit_per_unit', 'profit_margin', 'is_spicy', 'is_low_stock']
    list_filter = ['category', 'is_spicy']
    search_fields = ['name']
    list_editable = ['current_stock', 'cost_price', 'sell_price']
    readonly_fields = ['profit_per_unit', 'profit_margin', 'is_low_stock', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'image', 'is_spicy')
        }),
        ('Pricing', {
            'fields': ('cost_price', 'sell_price', 'profit_per_unit', 'profit_margin')
        }),
        ('Inventory', {
            'fields': ('current_stock', 'is_low_stock')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BundleType)
class BundleTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'required_snacks', 'required_juices', 'total_items', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'pickup_spot', 'order_count', 'created_at']
    search_fields = ['name', 'phone', 'pickup_spot']
    readonly_fields = ['created_at']
    
    def order_count(self, obj):
        return obj.orders.count()
    order_count.short_description = 'Total Orders'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['subtotal', 'cost']
    fields = ['item', 'quantity', 'subtotal', 'cost']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'bundle_type', 'status', 'total_revenue', 'net_profit', 'profit_margin', 'created_at']
    list_filter = ['status', 'created_at', 'bundle_type']
    search_fields = ['customer__name', 'customer__phone', 'customer__pickup_spot']
    readonly_fields = ['total_revenue', 'total_cost', 'net_profit', 'profit_margin', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('customer', 'bundle_type', 'status')
        }),
        ('Financial Summary', {
            'fields': ('total_revenue', 'total_cost', 'net_profit', 'profit_margin')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Recalculate totals after saving
        obj.calculate_totals()


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ['title', 'amount', 'uploaded_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


# Customer Order Management
class CustomerOrderItemInline(admin.TabularInline):
    model = CustomerOrderItem
    extra = 0
    readonly_fields = ['subtotal_cost']
    fields = ['item', 'quantity', 'is_starred', 'subtotal_cost']


@admin.register(CustomerOrder)
class CustomerOrderAdmin(admin.ModelAdmin):
    list_display = ['order_reference', 'customer_name', 'bundle_type', 'status', 'total_revenue', 'net_profit', 'created_at']
    list_filter = ['status', 'bundle_type', 'created_at']
    search_fields = ['order_reference', 'customer_name', 'customer_phone', 'pickup_spot']
    readonly_fields = ['order_reference', 'total_cost', 'created_at', 'updated_at', 'approved_at']
    inlines = [CustomerOrderItemInline]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_reference', 'status', 'bundle_type')
        }),
        ('Customer Details', {
            'fields': ('customer_name', 'customer_phone', 'customer_whatsapp', 'pickup_spot')
        }),
        ('Financial', {
            'fields': ('total_revenue', 'total_cost', 'net_profit', 'profit_margin')
        }),
        ('Payment', {
            'fields': ('payment_proof', 'payment_method')
        }),
        ('Admin', {
            'fields': ('admin_notes', 'approved_by', 'approved_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_orders', 'verify_payments', 'mark_completed']
    
    def approve_orders(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status='pending_approval').update(
            status='approved',
            approved_at=timezone.now(),
            approved_by=request.user
        )
        self.message_user(request, f'{queryset.count()} order(s) approved.')
    approve_orders.short_description = 'Approve selected orders'
    
    def verify_payments(self, request, queryset):
        queryset.filter(status='payment_uploaded').update(status='payment_verified')
        self.message_user(request, f'{queryset.count()} payment(s) verified.')
    verify_payments.short_description = 'Verify payments for selected orders'
    
    def mark_completed(self, request, queryset):
        queryset.filter(status__in=['payment_verified', 'processing']).update(status='completed')
        self.message_user(request, f'{queryset.count()} order(s) marked completed.')
    mark_completed.short_description = 'Mark selected orders as completed'


@admin.register(BankingInfo)
class BankingInfoAdmin(admin.ModelAdmin):
    list_display = ['bank_name', 'account_name', 'account_number', 'is_active', 'created_at']
    list_filter = ['is_active', 'bank_name']
    search_fields = ['bank_name', 'account_name', 'account_number']
    list_editable = ['is_active']
