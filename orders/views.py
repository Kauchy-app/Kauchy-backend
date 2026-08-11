from django.shortcuts import render
from .models import Order
from .serializers import OrderSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from django.db import transaction as db_transaction
from wallet.models import EscrowWallet
from paymentapp.models import VendorWallet, BuyerWallet, Transaction
from django.db.models import F
from notification.utils import send_notification_to_user
from django.utils import timezone

# Create your views here.

from datetime import timedelta

def auto_reject_expired_orders(user):
    three_days_ago = timezone.now() - timedelta(days=3)
    expired_orders = Order.objects.filter(
        Q(vendor=user) | Q(buyer=user),
        status='pending',
        created_at__lte=three_days_ago
    )
    for order in expired_orders:
        with db_transaction.atomic():
            # Refresh order from DB to ensure no race conditions
            try:
                locked_order = Order.objects.select_for_update().get(id=order.id, status='pending')
            except Order.DoesNotExist:
                continue
                
            try:
                escrow = EscrowWallet.objects.select_for_update().get(order=locked_order)
                buyer_wallet = BuyerWallet.objects.select_for_update().get(user=locked_order.buyer)
                buyer_wallet.balance = F('balance') + escrow.amount
                buyer_wallet.save()
                escrow.status = "CANCELLED"
                escrow.save()
            except (EscrowWallet.DoesNotExist, BuyerWallet.DoesNotExist):
                pass
            
            # Return stock
            from Products_app.models import Product
            for item in locked_order.items.all():
                if item.product:
                    Product.objects.filter(id=item.product.id).update(quantity=F('quantity') + item.quantity)
            
            # Set to expired instead of deleting
            locked_order.status = 'expired'
            locked_order.is_read_by_buyer = False
            locked_order.is_read_by_vendor = False
            locked_order.save()
            
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

class GetAllOrders(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request):
        user = request.user
        
        # Lazy expiration check
        auto_reject_expired_orders(user)

        data = Order.objects.filter(
            Q(vendor=user) | Q(buyer=user)
        ).select_related("vendor", "buyer").prefetch_related("items", "items__product").order_by('-created_at')

        serializer = OrderSerializer(data, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ValidateOrderQRCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        buyer = request.user
        order_id = request.data.get("order_id")

        if not order_id:
            return Response({"error":"Order ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        with db_transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(id=order_id)
            except Order.DoesNotExist:
                return Response({"error":"Order not found"}, status=status.HTTP_404_NOT_FOUND)

            if order.buyer_id != buyer.id:
                return Response({"error":"You are not authorized to validate this order"}, status=status.HTTP_403_FORBIDDEN)
            # Completion is valid from any active pre-completion state. The vendor
            # may have already accepted the order ('accepted'/'awaiting'); only
            # terminal states ('completed', 'expired') block a QR validation.
            if order.status not in ("pending", "accepted", "awaiting"):
                return Response({"error":f"Order already {order.status}",
                                 "current_status":order.status},status=status.HTTP_400_BAD_REQUEST)

            try:
                escrow = EscrowWallet.objects.select_for_update().get(order=order)
            except EscrowWallet.DoesNotExist:
                return Response({"error":"vendor wallet not found"},status= status.HTTP_404_NOT_FOUND)
            
            if escrow.status != "HELD":
                return Response({"error":"Escrow is not in HELD status"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                vendor_wallet = VendorWallet.objects.select_for_update().get(vendor_id=order.vendor_id)
            except VendorWallet.DoesNotExist:
                    return Response({"error":"vendor wallet not found"},status= status.HTTP_404_NOT_FOUND)
            
            VendorWallet.objects.filter(vendor_id=order.vendor_id).update(
                balance= F('balance') + escrow.amount)

            # Record the sale as Transaction rows so analytics (revenue, units
            # sold, top products) have data to aggregate. One row per line item
            # keeps per-product reporting accurate.
            buyer_wallet = BuyerWallet.objects.filter(user=order.buyer).first()
            for item in order.items.all():
                Transaction.objects.get_or_create(
                    reference=f"PURCHASE-{order.id}-{item.id}",
                    defaults={
                        'buyer': buyer_wallet,
                        'vendor': vendor_wallet,
                        'product': item.product,
                        'amount': item.price * item.quantity,
                        'quantity': item.quantity,
                        'transaction_type': 'PURCHASE',
                        'status': 'COMPLETED',
                    },
                )

            escrow.status = "RELEASED"
            escrow.released_at = timezone.now()
            escrow.save()
            order.status = "completed"
            order.is_read_by_buyer = False
            order.is_read_by_vendor = False
            order.save()

            send_notification_to_user(
                user=order.buyer,
                title="Order Confirmed",
                message=f"Your order {order.id} has been completed successfully.",
                notification_type="order",
                link=f"/orders?id={order.id}"
            )
            send_notification_to_user(
                user=order.vendor,
                title="Order Confirmed",
                message=f"You have successfully completed order {order.id}.",
                notification_type="order",
                link=f"/orders?id={order.id}"
            )

            return Response({
                "message": "Order validated and payment released from escrow successfully.",
                "order_id": order.id,
                "amount_released": str(escrow.amount),
                "order_status": order.status
            }, status=status.HTTP_200_OK)

class VendorRespondOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        vendor = request.user
        order_id = request.data.get("order_id")
        action = request.data.get("action") # 'accept' or 'reject'

        if action not in ['accept', 'reject']:
            return Response({"error": "Invalid action. Use 'accept' or 'reject'"}, status=status.HTTP_400_BAD_REQUEST)

        with db_transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(id=order_id, vendor=vendor)
            except Order.DoesNotExist:
                return Response({"error": "Order not found or you are not authorized"}, status=status.HTTP_404_NOT_FOUND)

            if order.status != "pending":
                return Response({"error": f"Order cannot be modified. Current status: {order.status}"}, status=status.HTTP_400_BAD_REQUEST)

            if action == 'accept':
                order.status = 'accepted'
                order.is_read_by_buyer = False
                order.save()
                send_notification_to_user(
                    user=order.buyer,
                    title="Order Accepted",
                    message=f"Your order {order.id} has been accepted by the vendor.",
                    notification_type="order",
                    link=f"/orders?id={order.id}"
                )
                return Response({"message": "Order accepted successfully", "status": order.status})
            
            elif action == 'reject':
                # Refund buyer
                from paymentapp.models import BuyerWallet
                from Products_app.models import Product
                
                try:
                    escrow = EscrowWallet.objects.select_for_update().get(order=order)
                except EscrowWallet.DoesNotExist:
                    return Response({"error": "Escrow wallet not found"}, status=status.HTTP_404_NOT_FOUND)
                
                try:
                    buyer_wallet = BuyerWallet.objects.select_for_update().get(user=order.buyer)
                except BuyerWallet.DoesNotExist:
                    return Response({"error": "Buyer wallet not found"}, status=status.HTTP_404_NOT_FOUND)

                buyer_wallet.balance = F('balance') + escrow.amount
                buyer_wallet.save()

                escrow.status = "CANCELLED"
                escrow.save()

                # Return stock
                for item in order.items.all():
                    if item.product:
                        Product.objects.filter(id=item.product.id).update(quantity=F('quantity') + item.quantity)

                order.status = 'expired'
                order.is_read_by_buyer = False
                order.save()

                send_notification_to_user(
                    user=order.buyer,
                    title="Order Rejected",
                    message=f"Your order {order_id} was rejected by the vendor. The amount has been refunded to your wallet.",
                    notification_type="order",
                    link=f"/orders?id={order_id}"
                )
                return Response({"message": "Order rejected. Buyer refunded.", "status": "expired"})

class MarkOrderReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        if not order_id:
            return Response({"error": "Order ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        
        user = request.user
        if order.buyer == user:
            order.is_read_by_buyer = True
            order.save(update_fields=['is_read_by_buyer'])
        elif order.vendor == user:
            order.is_read_by_vendor = True
            order.save(update_fields=['is_read_by_vendor'])
        else:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
            
        return Response({"message": "Order marked as read"}, status=status.HTTP_200_OK)