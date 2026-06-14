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
from paymentapp.models import VendorWallet
from django.db.models import F
from notification.utils import send_notification_to_user
from django.utils import timezone

# Create your views here.


class GetAllOrders(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request):
        user = request.user
        data = Order.objects.filter(
            Q(vendor=user) | Q(buyer=user)
        ).select_related("vendor", "buyer").prefetch_related("items", "items__product")

        serializer = OrderSerializer(data, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ValidateOrderQRCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self,request):
        buyer = request.user
        order_id = request.data.get("order_id")

        if not order_id:
            return Response({"error":"Order ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            order = Order.objects.select_for_update().get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error":"Order not found"}, status=status.HTTP_404_NOT_FOUND)
        
        if order.buyer_id != buyer.id:
            return Response({"error":"You are not authorized to validate this order"}, status=status.HTTP_403_FORBIDDEN)
        if order.status != "pending":
            return Response({"error":f"Order already {order.status}",
                             "current_status":order.status},status=status.HTTP_400_BAD_REQUEST)
        
        with db_transaction.atomic():
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
            
            escrow.status = "RELEASED"
            escrow.released_at = timezone.now()
            escrow.save()   
            order.status = "COMPLETED"
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

                # The user specified: "orders are automatically deleted after 2-days"
                # If they manually reject, we can either delete or set status to expired. Let's delete it so it matches "deleted"
                order.delete()

                send_notification_to_user(
                    user=order.buyer,
                    title="Order Rejected",
                    message=f"Your order {order_id} was rejected by the vendor. The amount has been refunded to your wallet.",
                    notification_type="order",
                    link=f"/orders?id={order_id}"
                )
                return Response({"message": "Order rejected and deleted. Buyer refunded.", "status": "deleted"})