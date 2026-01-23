"""
Email utilities for sending notifications via Resend
"""
import resend
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


def get_resend_client():
    """Get Resend client instance"""
    api_key = getattr(settings, 'RESEND_API_KEY', '')
    if not api_key:
        return None
    # Set the API key globally for resend
    resend.api_key = api_key
    return resend


def send_order_notification_to_admin(order):
    """
    Send email notification to admin when a new order is created
    
    Args:
        order: CustomerOrder instance
    """
    api_key = getattr(settings, 'RESEND_API_KEY', '')
    if not api_key:
        print("Warning: RESEND_API_KEY not configured. Email not sent.")
        return False
    
    # Set API key globally
    resend.api_key = api_key
    
    admin_email = getattr(settings, 'ADMIN_EMAIL', 'justeatmore876@gmail.com')
    from_email = getattr(settings, 'FROM_EMAIL', 'orders@jem.rixsoft.org')
    
    # Get order items
    order_items = order.customer_order_items.select_related('item').all()
    
    # Build items list
    items_html = "<ul>"
    for item in order_items:
        star = " ⭐" if item.is_starred else ""
        items_html += f"<li>{item.quantity}x {item.item.name}{star}</li>"
    items_html += "</ul>"
    
    # Build email content
    subject = f"New Order: {order.order_reference} - {order.get_bundle_type_display()}"
    
    # Determine status message
    if order.status == 'pending_approval':
        status_msg = "⚠️ <strong>Pending Approval</strong> - Custom bundle requires admin review"
    else:
        status_msg = "✅ <strong>Approved</strong> - Ready for payment"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #F97316;">🔔 New Order Notification</h2>
            
            <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin-top: 0;">Order Details</h3>
                <p><strong>Order Reference:</strong> {order.order_reference}</p>
                <p><strong>Bundle Type:</strong> {order.get_bundle_type_display()}</p>
                <p><strong>Status:</strong> {status_msg}</p>
                <p><strong>Order Date:</strong> {order.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
            </div>
            
            <div style="background: #fff; padding: 15px; border: 1px solid #ddd; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin-top: 0;">Customer Information</h3>
                <p><strong>Name:</strong> {order.customer_name}</p>
                <p><strong>Phone:</strong> {order.customer_phone}</p>
                {f'<p><strong>WhatsApp:</strong> {order.customer_whatsapp}</p>' if order.customer_whatsapp else ''}
                <p><strong>Pickup Location:</strong> {order.pickup_spot}</p>
            </div>
            
            <div style="background: #fff; padding: 15px; border: 1px solid #ddd; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin-top: 0;">Items Selected</h3>
                {items_html}
            </div>
            
            {f'''
            <div style="background: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin-top: 0;">Financial Summary</h3>
                <p><strong>Total Revenue:</strong> ${order.total_revenue:,.2f} JMD</p>
                <p><strong>Total Cost:</strong> ${order.total_cost:,.2f} JMD</p>
                <p><strong>Net Profit:</strong> ${order.net_profit:,.2f} JMD</p>
                <p><strong>Profit Margin:</strong> {order.profit_margin:.1f}%</p>
            </div>
            ''' if order.total_revenue > 0 else ''}
            
            <div style="margin-top: 30px; padding-top: 20px; border-top: 2px solid #F97316;">
                <p style="color: #666; font-size: 14px;">
                    <a href="https://jem.rixsoft.org/admin/customer-orders/{order.id}/" 
                       style="background: #F97316; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        View Order in Admin Panel
                    </a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        params = {
            "from": from_email,
            "to": [admin_email],
            "subject": subject,
            "html": html_content,
        }
        email = resend.Emails.send(params)
        print(f"Email sent successfully: {email}")
        return True
    except Exception as e:
        print(f"Error sending order notification email: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_order_confirmation_to_customer(order):
    """
    Send order confirmation email to customer (if email available)
    Currently not used as customers don't provide email, but kept for future use
    """
    # Customer email not collected in current flow
    # This function is reserved for future implementation
    pass


def send_order_status_update(order, old_status, new_status):
    """
    Send email notification when order status changes
    
    Args:
        order: CustomerOrder instance
        old_status: Previous status
        new_status: New status
    """
    api_key = getattr(settings, 'RESEND_API_KEY', '')
    if not api_key:
        print("Warning: RESEND_API_KEY not configured. Email not sent.")
        return False
    
    # Set API key globally
    resend.api_key = api_key
    
    admin_email = getattr(settings, 'ADMIN_EMAIL', 'justeatmore876@gmail.com')
    from_email = getattr(settings, 'FROM_EMAIL', 'orders@jem.rixsoft.org')
    
    # Status-specific email content
    status_emails = {
        'approved': {
            'subject': f"Order {order.order_reference} Approved - Payment Required",
            'admin_html': f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #F97316;">✅ Order Approved</h2>
                    <p>Order <strong>{order.order_reference}</strong> has been approved.</p>
                    <p><strong>Customer:</strong> {order.customer_name}</p>
                    <p><strong>Total Amount:</strong> ${order.total_revenue:,.2f} JMD</p>
                    <p>Customer has been notified to make payment within 24 hours.</p>
                </div>
            </body>
            </html>
            """,
        },
        'payment_verified': {
            'subject': f"Payment Verified for Order {order.order_reference}",
            'admin_html': f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #10b981;">💰 Payment Verified</h2>
                    <p>Payment for order <strong>{order.order_reference}</strong> has been verified.</p>
                    <p><strong>Customer:</strong> {order.customer_name}</p>
                    <p><strong>Amount:</strong> ${order.total_revenue:,.2f} JMD</p>
                    <p>Inventory has been reduced. Order is ready for processing.</p>
                </div>
            </body>
            </html>
            """,
        },
        'completed': {
            'subject': f"Order {order.order_reference} Completed",
            'admin_html': f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #10b981;">🎉 Order Completed</h2>
                    <p>Order <strong>{order.order_reference}</strong> has been marked as completed.</p>
                    <p><strong>Customer:</strong> {order.customer_name}</p>
                    <p><strong>Total Revenue:</strong> ${order.total_revenue:,.2f} JMD</p>
                    <p><strong>Profit:</strong> ${order.net_profit:,.2f} JMD ({order.profit_margin:.1f}%)</p>
                </div>
            </body>
            </html>
            """,
        },
    }
    
    # Only send email for specific status changes
    if new_status not in status_emails:
        return False
    
    email_config = status_emails[new_status]
    
    try:
        params = {
            "from": from_email,
            "to": [admin_email],
            "subject": email_config['subject'],
            "html": email_config['admin_html'],
        }
        email = resend.Emails.send(params)
        print(f"Status update email sent successfully: {email}")
        return True
    except Exception as e:
        print(f"Error sending status update email: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_payment_instructions_to_customer(order):
    """
    Send payment instructions to customer when order is approved
    Note: Since customers don't provide email, this would need to be sent via WhatsApp
    or SMS. For now, this function is a placeholder for future implementation.
    """
    # Customer email not collected in current flow
    # This would need integration with WhatsApp Business API or SMS service
    pass


def send_suggestion_notification(suggestion):
    """
    Send email notification to admin when a customer submits a suggestion
    
    Args:
        suggestion: CustomerSuggestion instance
    """
    api_key = getattr(settings, 'RESEND_API_KEY', '')
    if not api_key:
        print("Warning: RESEND_API_KEY not configured. Email not sent.")
        return False
    
    # Set API key globally
    resend.api_key = api_key
    
    admin_email = getattr(settings, 'ADMIN_EMAIL', 'justeatmore876@gmail.com')
    from_email = getattr(settings, 'FROM_EMAIL', 'orders@jem.rixsoft.org')
    
    suggestion_type_display = dict(suggestion.SUGGESTION_TYPES).get(suggestion.suggestion_type, suggestion.suggestion_type)
    
    subject = f"New Customer Suggestion: {suggestion_type_display}"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #F97316;">💡 New Customer Suggestion</h2>
            
            <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Type:</strong> {suggestion_type_display}</p>
                {f'<p><strong>Item Name:</strong> {suggestion.item_name}</p>' if suggestion.item_name else ''}
                <p><strong>Customer:</strong> {suggestion.customer_name}</p>
                {f'<p><strong>Phone:</strong> {suggestion.customer_phone}</p>' if suggestion.customer_phone else ''}
                {f'<p><strong>Order Reference:</strong> {suggestion.order.order_reference}</p>' if suggestion.order else ''}
                <p><strong>Submitted:</strong> {suggestion.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
            </div>
            
            <div style="background: #fff; padding: 15px; border: 1px solid #ddd; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin-top: 0;">Message</h3>
                <p style="white-space: pre-wrap;">{suggestion.message}</p>
            </div>
            
            <div style="margin-top: 30px; padding-top: 20px; border-top: 2px solid #F97316;">
                <p style="color: #666; font-size: 14px;">
                    <a href="https://jem.rixsoft.org/admin/suggestions/" 
                       style="background: #F97316; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        View All Suggestions
                    </a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        params = {
            "from": from_email,
            "to": [admin_email],
            "subject": subject,
            "html": html_content,
        }
        email = resend.Emails.send(params)
        print(f"Suggestion email sent successfully: {email}")
        return True
    except Exception as e:
        print(f"Error sending suggestion email: {e}")
        import traceback
        traceback.print_exc()
        return False
