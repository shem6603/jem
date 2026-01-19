from django.contrib import admin
from .models import Item, BundleType, Customer, Order, OrderItem


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
    list_display = ['name', 'email', 'phone', 'order_count', 'created_at']
    search_fields = ['name', 'email', 'phone']
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
    search_fields = ['customer__name', 'customer__email']
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
