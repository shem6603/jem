"""
Management command to check for orders that are 24 hours old without payment
and send reminder emails to admin
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import CustomerOrder
from core.email_utils import send_payment_reminder_notification


class Command(BaseCommand):
    help = 'Check for orders 24 hours old without payment and send reminder emails'

    def handle(self, *args, **options):
        # Calculate 24 hours ago
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        
        # Find orders that:
        # 1. Are at least 24 hours old
        # 2. Are in 'approved' status (awaiting payment)
        # 3. Have not had payment uploaded
        # 4. Have not had reminder sent yet
        orders_needing_reminder = CustomerOrder.objects.filter(
            created_at__lte=twenty_four_hours_ago,
            status='approved',
            payment_proof__isnull=True,
            payment_reminder_sent=False
        )
        
        count = 0
        for order in orders_needing_reminder:
            try:
                # Send reminder email
                success = send_payment_reminder_notification(order)
                if success:
                    # Mark reminder as sent
                    order.payment_reminder_sent = True
                    order.save(update_fields=['payment_reminder_sent'])
                    count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Reminder sent for order {order.order_reference}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ Failed to send reminder for order {order.order_reference}'
                        )
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Error processing order {order.order_reference}: {e}'
                    )
                )
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('No orders needing payment reminders.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully sent {count} payment reminder email(s).'
                )
            )
