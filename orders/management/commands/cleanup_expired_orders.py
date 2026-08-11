from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from orders.models import Order
from wallet.models import EscrowWallet
from paymentapp.models import BuyerWallet
from Products_app.models import Product
from django.db import transaction as db_transaction
from django.db.models import F

class Command(BaseCommand):
    help = 'Cleans up pending orders that are older than 3 days by expiring them and refunding buyers'

    def handle(self, *args, **options):
        three_days_ago = timezone.now() - timedelta(days=3)
        expired_orders = Order.objects.filter(status='pending', created_at__lte=three_days_ago)

        count = 0
        from notification.utils import send_notification_to_user

        for order in expired_orders:
            with db_transaction.atomic():
                try:
                    locked_order = Order.objects.select_for_update().get(id=order.id, status='pending')
                except Order.DoesNotExist:
                    continue
                    
                # Refund buyer
                try:
                    escrow = EscrowWallet.objects.select_for_update().get(order=locked_order)
                    buyer_wallet = BuyerWallet.objects.select_for_update().get(user=locked_order.buyer)
                    buyer_wallet.balance = F('balance') + escrow.amount
                    buyer_wallet.save()
                    escrow.status = "CANCELLED"
                    escrow.save()
                except (EscrowWallet.DoesNotExist, BuyerWallet.DoesNotExist):
                    pass # Proceed to expire order anyway

                # Return stock
                for item in locked_order.items.all():
                    if item.product:
                        Product.objects.filter(id=item.product.id).update(quantity=F('quantity') + item.quantity)

                # Set status to expired
                locked_order.status = 'expired'
                locked_order.is_read_by_buyer = False
                locked_order.is_read_by_vendor = False
                locked_order.save()
                count += 1
                
                send_notification_to_user(
                    user=locked_order.buyer,
                    title="Order Expired",
                    message=f"Your order {locked_order.id} was not confirmed in time and has expired. You have been refunded.",
                    notification_type="order",
                    link=f"/orders?id={locked_order.id}"
                )
                send_notification_to_user(
                    user=locked_order.vendor,
                    title="Order Expired",
                    message=f"Order {locked_order.id} expired automatically because it was not confirmed within 3 days.",
                    notification_type="order",
                    link=f"/orders?id={locked_order.id}"
                )
                
        self.stdout.write(self.style.SUCCESS(f'Successfully expired {count} orders.'))
