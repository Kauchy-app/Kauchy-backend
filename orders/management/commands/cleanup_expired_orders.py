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
    help = 'Cleans up pending orders that are older than 2 days by deleting them and refunding buyers'

    def handle(self, *args, **options):
        two_days_ago = timezone.now() - timedelta(days=2)
        expired_orders = Order.objects.filter(status='pending', created_at__lte=two_days_ago)

        count = 0
        for order in expired_orders:
            with db_transaction.atomic():
                # Refund buyer
                try:
                    escrow = EscrowWallet.objects.select_for_update().get(order=order)
                    buyer_wallet = BuyerWallet.objects.select_for_update().get(user=order.buyer)
                    buyer_wallet.balance = F('balance') + escrow.amount
                    buyer_wallet.save()
                    escrow.status = "CANCELLED"
                    escrow.save()
                except (EscrowWallet.DoesNotExist, BuyerWallet.DoesNotExist):
                    pass # Proceed to delete order anyway

                # Return stock
                for item in order.items.all():
                    if item.product:
                        Product.objects.filter(id=item.product.id).update(quantity=F('quantity') + item.quantity)

                # Delete the order
                order.delete()
                count += 1
                
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} expired orders.'))
