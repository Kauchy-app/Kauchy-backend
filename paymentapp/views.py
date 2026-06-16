from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from userCart.models import CartItem
from userCart.serializers import CartItemSerializer
from .models import Transaction, VendorWallet, BuyerWallet, PendingPurchase
from Products_app.models import Product
from rest_framework.permissions import IsAuthenticated

import uuid
from django.conf import settings
import requests
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.db import transaction as db_transaction
from django.db.models import F
from decimal import Decimal
from rest_framework import serializers
from drf_spectacular.utils import inline_serializer
from orders.models import Order, OrderItem
from wallet.models import EscrowWallet
from notification.utils import send_notification_to_user
from django.contrib.auth import get_user_model
User = get_user_model()


class InsufficientStock(Exception):
    """Raised when a product no longer has enough stock to fulfil a line item."""
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def build_vendor_items(line_items):
    """Turn a flat list of {product_id, quantity} into a vendor-grouped structure.

    Returns (vendor_items, total_amount). Raises Product.DoesNotExist if any
    product id is unknown. Prices are read from the live Product rows, never
    trusted from the client.
    """
    product_ids = [li["product_id"] for li in line_items]
    products = Product.objects.in_bulk(product_ids)

    total_amount = Decimal('0.00')
    vendor_items = {}

    for li in line_items:
        product = products.get(li["product_id"])
        if not product:
            raise Product.DoesNotExist(f"Product {li['product_id']} not found.")

        quantity = li["quantity"]
        # product.vendor_id resolves to the User instance (FK); grab its id safely.
        vendor_user = product.vendor_id
        vendor_id = vendor_user.id if hasattr(vendor_user, 'id') else vendor_user

        price = Decimal(str(product.price))
        item_total = price * quantity
        total_amount += item_total

        vendor_items.setdefault(vendor_id, []).append({
            "product_id": product.id,
            "product_name": product.product_name,
            "quantity": quantity,
            "amount": item_total,
        })

    return vendor_items, total_amount


def materialize_orders(buyer, vendor_items):
    """Create one Order (+ items + HELD escrow) per vendor, deducting stock.

    Must be called inside an atomic block with the buyer wallet already locked
    when paying from wallet. Raises InsufficientStock if any product ran out.
    Does NOT debit the buyer wallet — callers decide how the money arrives
    (wallet debit vs. confirmed card payment).
    """
    orders_created = []

    for vendor_id, items in vendor_items.items():
        vendor_total = Decimal('0.00')

        for item in items:
            product = Product.objects.select_for_update().get(pk=item["product_id"])
            if product.quantity < item["quantity"]:
                raise InsufficientStock(
                    f"Insufficient stock for {item['product_name']}. "
                    f"Available: {product.quantity}, Requested: {item['quantity']}"
                )
            Product.objects.filter(pk=item["product_id"]).update(
                quantity=F('quantity') - item["quantity"]
            )
            vendor_total += item["amount"]

        vendor_user = User.objects.get(id=vendor_id)

        order = Order.objects.create(
            buyer=buyer,
            vendor=vendor_user,
            amount=vendor_total,
            status='pending'
        )
        orders_created.append(order)

        for item in items:
            OrderItem.objects.create(
                order=order,
                product_id=item['product_id'],
                quantity=item['quantity'],
                price=item['amount'] / item['quantity']
            )

        EscrowWallet.objects.create(order=order, amount=vendor_total, status="HELD")

        send_notification_to_user(
            user=vendor_user,
            title="New Order Received",
            message=f"You have a new order (ID: {order.id}) from {buyer.username}. Please review it.",
            notification_type="order",
            link=f"/orders?id={order.id}"
        )

    return orders_created


class InitializeOrderView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
            summary="Checkout — cart or direct (Buy Now), via wallet or card",
            description=(
                "Create orders for the authenticated buyer. Items can come from the "
                "cart (`cart_id`, or all cart items when omitted) or directly via "
                "`items` (Buy Now). `payment_method` selects the rail: `wallet` debits "
                "the buyer wallet and creates the orders immediately; `card` returns a "
                "Paystack authorization URL, and the orders are created only after the "
                "payment is confirmed via /payment/verify-purchase/<reference>."
            ),
            request=inline_serializer(
                name='CheckoutRequest',
                fields={
                    'cart_id': serializers.ListField(
                        child=serializers.IntegerField(),
                        required=False,
                        help_text='Cart item IDs to purchase. Ignored when `items` is given. If neither is provided, all cart items are purchased.'
                    ),
                    'items': serializers.ListField(
                        child=inline_serializer(
                            name='DirectPurchaseItem',
                            fields={
                                'product_id': serializers.IntegerField(),
                                'quantity': serializers.IntegerField(default=1),
                            }
                        ),
                        required=False,
                        help_text='Direct (Buy Now) purchase — bypasses the cart.'
                    ),
                    'payment_method': serializers.ChoiceField(
                        choices=['wallet', 'card'],
                        default='wallet',
                        required=False,
                        help_text="How to pay. Defaults to 'wallet'."
                    ),
                    'callback_url': serializers.CharField(
                        required=False,
                        help_text='Where Paystack should redirect after a card payment.'
                    ),
                }
            ),
            responses={
                200: inline_serializer(
                    name='CheckoutSuccessResponse',
                    fields={
                        'message': serializers.CharField(),
                        'payment_method': serializers.ChoiceField(choices=['wallet', 'card']),
                        'total_amount_naira': serializers.FloatField(required=False),
                        'orders_created': serializers.IntegerField(required=False),
                        'orders': serializers.ListField(
                            child=inline_serializer(
                                name='InitializePurchaseOrder',
                                fields={
                                    'order_id': serializers.IntegerField(),
                                    'vendor_id': serializers.IntegerField(),
                                    'amount': serializers.FloatField(),
                                    'status': serializers.CharField(),
                                }
                            ),
                            required=False
                        ),
                        'authorization_url': serializers.CharField(required=False, help_text="Present only for card payment."),
                        'reference': serializers.CharField(required=False, help_text="Present only for card payment."),
                        'amount_naira': serializers.FloatField(required=False)
                    }
                )
            },
            examples=[
                OpenApiExample(
                    'Buy Now (card)',
                    summary='Direct single-item purchase paid by card',
                    value={"items": [{"product_id": 55, "quantity": 1}], "payment_method": "card"},
                    request_only=True,
                ),
                OpenApiExample(
                    'Buy Now (wallet)',
                    summary='Direct single-item purchase paid from wallet',
                    value={"items": [{"product_id": 55, "quantity": 1}], "payment_method": "wallet"},
                    request_only=True,
                ),
                OpenApiExample(
                    'Checkout selected cart items (wallet)',
                    value={"cart_id": [1, 2, 3]},
                    request_only=True,
                ),
            ]
        )
    def post(self, request):
        """Checkout from cart or direct items; pay via wallet or card."""
        user = request.user

        payment_method = (request.data.get("payment_method") or "wallet").lower()
        if payment_method not in ("wallet", "card"):
            return Response({"error": "Invalid payment_method. Use 'wallet' or 'card'."},
                            status=status.HTTP_400_BAD_REQUEST)

        # ---- Resolve the line items (direct `items` OR cart) -----------------
        direct_items = request.data.get("items")
        line_items = []        # [{product_id, quantity}]
        source_cart_ids = []   # cart rows to clear after a wallet checkout

        if direct_items:
            if isinstance(direct_items, dict):
                direct_items = [direct_items]
            try:
                for it in direct_items:
                    pid = int(it["product_id"])
                    qty = int(it.get("quantity", 1))
                    if qty <= 0:
                        return Response({"error": "Quantity must be at least 1."},
                                        status=status.HTTP_400_BAD_REQUEST)
                    line_items.append({"product_id": pid, "quantity": qty})
            except (KeyError, ValueError, TypeError):
                return Response({"error": "Invalid items payload."},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            ids = request.data.get("cart_id")
            if isinstance(ids, str):
                ids = [i.strip() for i in ids.split(",")]
            if ids:
                try:
                    ids = [int(i) for i in ids]
                except ValueError:
                    return Response({"error": "Invalid cart IDs."}, status=status.HTTP_400_BAD_REQUEST)
                cart_items = CartItem.objects.select_related("product").filter(user=user, id__in=ids)
            else:
                cart_items = CartItem.objects.select_related("product").filter(user=user)
            if not cart_items.exists():
                return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)
            for ci in cart_items:
                line_items.append({"product_id": ci.product.id, "quantity": ci.quantity})
                source_cart_ids.append(ci.id)

        # ---- Group by vendor / compute total ---------------------------------
        try:
            vendor_items, total_amount = build_vendor_items(line_items)
        except Product.DoesNotExist as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

        # ---- Card rail: init Paystack, defer order creation to verify --------
        if payment_method == "card":
            return self._init_card_payment(request, user, line_items, total_amount)

        # ---- Wallet rail: debit immediately and create orders ----------------
        return self._pay_from_wallet(user, vendor_items, total_amount, source_cart_ids)

    def _pay_from_wallet(self, user, vendor_items, total_amount, source_cart_ids):
        with db_transaction.atomic():
            try:
                buyer_wallet = BuyerWallet.objects.select_for_update().get(user=user)
            except BuyerWallet.DoesNotExist:
                db_transaction.set_rollback(True)
                return Response({"error": "Buyer wallet not found."}, status=status.HTTP_404_NOT_FOUND)

            if Decimal(str(buyer_wallet.balance)) < total_amount:
                db_transaction.set_rollback(True)
                return Response({
                    "error": "Insufficient funds.",
                    "balance_naira": float(buyer_wallet.balance),
                    "required_naira": float(total_amount),
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                orders_created = materialize_orders(user, vendor_items)
            except InsufficientStock as e:
                db_transaction.set_rollback(True)
                return Response({"error": e.message}, status=status.HTTP_409_CONFLICT)

            BuyerWallet.objects.filter(pk=buyer_wallet.pk).update(
                balance=F('balance') - total_amount
            )

            if source_cart_ids:
                CartItem.objects.filter(user=user, id__in=source_cart_ids).delete()

            return Response({
                "message": "Orders created. Awaiting QR code validation.",
                "payment_method": "wallet",
                "total_amount_naira": float(total_amount),
                "orders_created": len(orders_created),
                "orders": [
                    {
                        "order_id": order.id,
                        "vendor_id": order.vendor_id,
                        "amount": float(order.amount),
                        "status": order.status,
                    } for order in orders_created
                ]
            }, status=status.HTTP_200_OK)

    def _init_card_payment(self, request, user, line_items, total_amount):
        """Initialise a Paystack transaction and stash the intended purchase.

        No Order/escrow is created here — that happens in VerifyPurchaseView once
        Paystack confirms the payment.
        """
        if not user.email:
            return Response({"error": "An email is required for card payment."},
                            status=status.HTTP_400_BAD_REQUEST)

        reference = str(uuid.uuid4()).replace("-", "")[:12]
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "email": user.email,
            "amount": int(total_amount * 100),  # kobo
            "reference": reference,
            "metadata": {"direct_purchase": True},
        }
        callback_url = request.data.get("callback_url")
        if callback_url:
            data["callback_url"] = callback_url

        try:
            res = requests.post(
                "https://api.paystack.co/transaction/initialize",
                json=data, headers=headers, timeout=30,
            )
            res_data = res.json()
        except requests.RequestException:
            return Response({"error": "Could not reach the payment provider. Please try again."},
                            status=status.HTTP_502_BAD_GATEWAY)

        if not res_data.get("status"):
            return Response({"error": "Failed to initialize payment.", "detail": res_data},
                            status=status.HTTP_400_BAD_REQUEST)

        PendingPurchase.objects.create(
            buyer=user,
            reference=reference,
            amount=total_amount,
            items=line_items,
            status="PENDING",
        )

        return Response({
            "message": "Payment initialized.",
            "payment_method": "card",
            "authorization_url": res_data["data"]["authorization_url"],
            "reference": reference,
            "amount_naira": float(total_amount),
        }, status=status.HTTP_200_OK)


class VerifyPurchaseView(APIView):
    """Confirm a card direct-purchase: verify the Paystack reference, then create
    the Order(s) + escrow from the stashed PendingPurchase. Idempotent."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Verify Paystack purchase",
        description=(
            "Confirm a card direct-purchase by verifying the Paystack reference. "
            "If successful, creates the Order(s) and escrow from the stashed PendingPurchase. "
            "This endpoint is idempotent."
        ),
        responses={
            200: inline_serializer(
                name='VerifyPurchaseSuccessResponse',
                fields={
                    'message': serializers.CharField(),
                    'total_amount_naira': serializers.FloatField(required=False),
                    'orders_created': serializers.IntegerField(required=False),
                    'orders': serializers.ListField(
                        child=inline_serializer(
                            name='VerifyPurchaseOrder',
                            fields={
                                'order_id': serializers.IntegerField(),
                                'vendor_id': serializers.IntegerField(),
                                'amount': serializers.FloatField(),
                                'status': serializers.CharField(),
                            }
                        ),
                        required=False
                    )
                }
            )
        }
    )
    def get(self, request, reference):
        user = request.user

        pending = PendingPurchase.objects.filter(reference=reference).first()
        if not pending:
            return Response({"error": "Purchase not found."}, status=status.HTTP_404_NOT_FOUND)
        if pending.buyer_id != user.id:
            return Response({"error": "You are not authorized to verify this purchase."},
                            status=status.HTTP_403_FORBIDDEN)

        if pending.status == "COMPLETED":
            return Response({"message": "Purchase already processed."}, status=status.HTTP_200_OK)

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        try:
            res = requests.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers=headers, timeout=30,
            )
            res_data = res.json()
        except requests.RequestException:
            return Response({"error": "Could not reach the payment provider. Please try again."},
                            status=status.HTTP_502_BAD_GATEWAY)

        paid = res_data.get("data", {}).get("status") == "success"
        if not paid:
            pending.status = "FAILED"
            pending.save(update_fields=["status"])
            return Response({"error": "Payment was not successful."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vendor_items, _ = build_vendor_items(pending.items)
        except Product.DoesNotExist as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)

        with db_transaction.atomic():
            # Lock the pending row to avoid a double-create if verify is called twice.
            locked = PendingPurchase.objects.select_for_update().get(pk=pending.pk)
            if locked.status == "COMPLETED":
                return Response({"message": "Purchase already processed."}, status=status.HTTP_200_OK)

            try:
                orders_created = materialize_orders(user, vendor_items)
            except InsufficientStock as e:
                # Payment succeeded but stock is gone — flag for manual refund.
                return Response({
                    "error": e.message,
                    "detail": "Payment received but the order could not be fulfilled. Please contact support for a refund.",
                }, status=status.HTTP_409_CONFLICT)

            locked.status = "COMPLETED"
            locked.save(update_fields=["status"])

        return Response({
            "message": "Payment confirmed. Orders created. Awaiting QR code validation.",
            "total_amount_naira": float(pending.amount),
            "orders_created": len(orders_created),
            "orders": [
                {
                    "order_id": order.id,
                    "vendor_id": order.vendor_id,
                    "amount": float(order.amount),
                    "status": order.status,
                } for order in orders_created
            ]
        }, status=status.HTTP_200_OK)
