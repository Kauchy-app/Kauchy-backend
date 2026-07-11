from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from orders.models import Order
from paymentapp.models import Transaction, BuyerWallet, VendorWallet


class Command(BaseCommand):
    help = (
        "Backfill PURCHASE/COMPLETED Transaction rows for orders that were "
        "completed before sale-recording was added. Analytics (revenue, units "
        "sold, top products) read from Transaction, so historical completed "
        "orders are invisible without this. Idempotent — safe to run repeatedly."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be created without writing to the DB.",
        )
        parser.add_argument(
            "--statuses",
            default="completed",
            help=(
                "Comma-separated order statuses to backfill (case-insensitive). "
                "Defaults to 'completed' (the correct production behaviour). Pass "
                "e.g. 'completed,accepted' to also seed analytics from in-progress "
                "orders for testing/demo dashboards."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        statuses = [s.strip().lower() for s in options["statuses"].split(",") if s.strip()]

        # status stored inconsistently in the past (e.g. 'COMPLETED'); match case-insensitively.
        from django.db.models import Q
        status_filter = Q()
        for s in statuses:
            status_filter |= Q(status__iexact=s)
        completed_orders = Order.objects.filter(status_filter).prefetch_related("items")
        self.stdout.write(f"Matching orders with status in {statuses}: {completed_orders.count()} found")

        created = 0
        skipped = 0
        for order in completed_orders:
            buyer_wallet = BuyerWallet.objects.filter(user=order.buyer).first()
            vendor_wallet = VendorWallet.objects.filter(vendor=order.vendor).first()

            for item in order.items.all():
                reference = f"PURCHASE-{order.id}-{item.id}"
                if Transaction.objects.filter(reference=reference).exists():
                    skipped += 1
                    continue

                if dry_run:
                    created += 1
                    self.stdout.write(
                        f"[dry-run] would create {reference}: "
                        f"qty={item.quantity} amount={item.price * item.quantity}"
                    )
                    continue

                with db_transaction.atomic():
                    Transaction.objects.create(
                        buyer=buyer_wallet,
                        vendor=vendor_wallet,
                        product=item.product,
                        amount=item.price * item.quantity,
                        quantity=item.quantity,
                        transaction_type="PURCHASE",
                        status="COMPLETED",
                        reference=reference,
                    )
                    created += 1

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Backfill complete: {created} transaction(s) created, "
            f"{skipped} already existed."
        ))
