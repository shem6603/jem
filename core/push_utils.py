"""
Utility functions for sending push notifications
"""
import json
from pywebpush import webpush, WebPushException
from django.conf import settings
from .models import PushSubscription


def send_push_notification_to_all(title, body, url='/', icon='/static/favicons/icon-192.png'):
    """
    Send push notification to all subscribed users
    
    Args:
        title: Notification title
        body: Notification body text
        url: URL to open when notification is clicked
        icon: Icon URL for the notification
    
    Returns:
        dict: {'success_count': int, 'error_count': int, 'errors': list}
    """
    vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
    vapid_public_key = getattr(settings, 'VAPID_PUBLIC_KEY', None)
    vapid_claims = getattr(settings, 'VAPID_CLAIMS', {})
    
    if not vapid_private_key or not vapid_public_key:
        return {
            'success_count': 0,
            'error_count': 0,
            'errors': ['VAPID keys not configured']
        }
    
    subscriptions = PushSubscription.objects.all()
    success_count = 0
    error_count = 0
    errors = []
    
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
            # If subscription is invalid (410 Gone, 404 Not Found), remove it
            if e.response and e.response.status_code in [410, 404]:
                subscription.delete()
            error_count += 1
            errors.append(f"Subscription {subscription.id}: {str(e)}")
        except Exception as e:
            error_count += 1
            errors.append(f"Subscription {subscription.id}: {str(e)}")
    
    return {
        'success_count': success_count,
        'error_count': error_count,
        'errors': errors
    }


def send_order_notification(order):
    """
    Send push notification when order status changes
    
    Args:
        order: CustomerOrder instance
    """
    status_messages = {
        'approved': f'Order {order.order_reference} has been approved!',
        'payment_verified': f'Payment verified for order {order.order_reference}',
        'processing': f'Order {order.order_reference} is being prepared',
        'completed': f'Order {order.order_reference} is ready for pickup!',
    }
    
    message = status_messages.get(order.status)
    if message:
        send_push_notification_to_all(
            title='Order Update - J.E.M',
            body=message,
            url=f'/order/status/{order.order_reference}/',
            icon='/static/favicons/icon-192.png'
        )
