"""
Signals for inventory management
Automatically deduct stock when orders are placed
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import Order, OrderItem


@receiver(post_save, sender=OrderItem)
def deduct_stock_on_order(sender, instance, created, **kwargs):
    """Deduct stock when an order item is created"""
    if created and instance.order.status == 'pending':
        item = instance.item
        if item.current_stock >= instance.quantity:
            item.current_stock -= instance.quantity
            item.save()
        else:
            # This shouldn't happen if validation is working, but handle it
            raise ValueError(f"Insufficient stock for {item.name}. Available: {item.current_stock}, Requested: {instance.quantity}")


@receiver(pre_delete, sender=OrderItem)
def restore_stock_on_delete(sender, instance, **kwargs):
    """Restore stock if order item is deleted (order cancelled)"""
    if instance.order.status == 'pending':
        item = instance.item
        item.current_stock += instance.quantity
        item.save()
