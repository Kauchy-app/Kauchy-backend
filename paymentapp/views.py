from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from userCart.models import CartItem
from userCart.serializers import CartItemSerializer 
from .models import Transaction, VendorWallet, BuyerWallet
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
from orders.models import Order
from wallet.models import EscrowWallet
from django.contrib.auth import get_user_model
User = get_user_model()

class InitializeOrderView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
            summary="Purchase Multiple Items from Wallet",
            description="Checkout all cart items for the user. Debits buyer wallet, credits vendor wallets, updates stock, and completes transactions.",
            request=inline_serializer(
                name='CheckoutRequest',
                fields={
                    'cart_id': serializers.ListField(
                        child=serializers.IntegerField(),
                        required=False,
                        help_text='List of cart item IDs to purchase. If not provided, all cart items will be purchased.'
                    )
                }
            ),
            responses={
                200: inline_serializer(
                    name='CheckoutSuccessResponse',
                    fields={
                        'message': serializers.CharField(),
                        'total_amount_naira': serializers.DecimalField(max_digits=10, decimal_places=2),
                        'items_purchased': serializers.IntegerField(),
                        'cart_details': serializers.ListField(),
                        'transactions': serializers.IntegerField(),
                    }
                ),
                400: inline_serializer(
                    name='CheckoutErrorResponse',
                    fields={
                        'error': serializers.CharField(),
                        'balance_naira': serializers.DecimalField(max_digits=10, decimal_places=2, required=False),
                        'required_naira': serializers.DecimalField(max_digits=10, decimal_places=2, required=False),
                    }
                ),
                404: inline_serializer(
                    name='NotFoundResponse',
                    fields={'error': serializers.CharField()}
                ),
                409: inline_serializer(
                    name='ConflictResponse',
                    fields={'error': serializers.CharField()}
                ),
            },
            examples=[
                OpenApiExample(
                    'Checkout Selected Items',
                    summary='Checkout specific cart items',
                    description='Process only selected cart items by providing their IDs.',
                    value={"cart_id": [1, 2, 3]},
                    request_only=True,
                ),
                OpenApiExample(
                    'Checkout All Items',
                    summary='Checkout all cart items',
                    description='Process all items in cart without specifying cart IDs.',
                    value={},
                    request_only=True,
                ),

                OpenApiExample(
                    'Success Response',
                    summary='Successful checkout',
                    description='Returns transaction details and updated balances.',
                    value={
                        "message": "Checkout successful. All items purchased.",
                        "total_amount_naira": 150.50,
                        "items_purchased": 3,
                        "cart_details": [
                            {
                                "cart_item_id": 1,
                                "product_id": 10,
                                "product_name": "Laptop",
                                "quantity": 1,
                                "price_per_unit_naira": 100.00,
                                "item_total_naira": 100.00
                            }
                        ],
                        "transactions": 2
                    },
                    response_only=True,
                    status_codes=['200'],
                ),
                OpenApiExample(
                    'Insufficient Funds',
                    summary='Not enough balance',
                    description='Returns error when wallet balance is insufficient.',
                    value={
                        "error": "Insufficient funds.",
                        "balance_naira": 50.00,
                        "required_naira": 150.50
                    },
                    response_only=True,
                    status_codes=['400'],
                ),
            ]
        )

    def post(self, request):
        """Checkout all items in user's cart"""
        user = request.user

        ids=request.data.get("cart_id")

        if isinstance(ids,str):
            ids=[i.strip() for i in ids.split(",")]
        if ids:
            try:
                ids=[int(i) for i in ids]
            except ValueError:
                return Response({"error":"Invalid cart IDs."}, status=status.HTTP_400_BAD_REQUEST)
            cart_items = CartItem.objects.select_related("product").filter(user=user, id__in=ids)
        else:
            cart_items = CartItem.objects.select_related("product").filter(user=user)
        if not cart_items.exists():
            return Response({"error": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate total and group by vendor
        total_amount_naira = Decimal('0.00')
        # cart_details = []
        per_item_totals = {}
        vendor_items ={}

        for cart_item in cart_items:
            product = cart_item.product
            quantity = cart_item.quantity
            
            # product.vendor_id actually returns the User instance in Django 
            # if the field is defined as models.ForeignKey 
            # (which it is in your Product model)
            vendor_user = product.vendor_id
            
            # Safely grab the integer ID
            vendor_id = vendor_user.id if hasattr(vendor_user, 'id') else vendor_user

            try:
                price_naira = Decimal(product.price)
            except Exception:
                price_naira = Decimal(str(product.price))

            # Total for this item
            item_total_naira = price_naira * quantity
            total_amount_naira += item_total_naira
            per_item_totals[cart_item.id] = item_total_naira

            # cart_details.append({
            #     "cart_item_id": cart_item.id,
            #     "product_id": product.id,
            #     "product_name": product.product_name,
            #     "vendor_id": vendor_id,
            #     "quantity": quantity,
            #     "price_per_unit_naira": float(price_naira),
            #     "item_total_naira": float(item_total_naira),
            # })

            if vendor_id not in vendor_items:
                vendor_items[vendor_id] = []
            vendor_items[vendor_id].append({
                "cart_item_id": cart_item.id,
                "product_name": product.product_name,
                "quantity": quantity,
                "amount":item_total_naira,
                "product_id":product.id

            })
            # print(vendor_items)
        # Start atomic transaction
        with db_transaction.atomic():
            # Get buyer wallet
            try:
                buyer_wallet = BuyerWallet.objects.select_for_update().get(user=user)
            except BuyerWallet.DoesNotExist:
                return Response({"error": "Buyer wallet not found."}, status=status.HTTP_404_NOT_FOUND)

            # Check funds before processing
            if float(buyer_wallet.balance) < total_amount_naira:
                return Response({
                    "error": "Insufficient funds.",
                    "balance_naira": float(buyer_wallet.balance),
                    "required_naira": total_amount_naira,
                }, status=status.HTTP_400_BAD_REQUEST)
            orders_created = []
            
            # Process each vendor's items
            from orders.models import OrderItem
            from notification.utils import send_notification_to_user
            
            for vendor_id, items in vendor_items.items():
                vendor_total = Decimal('0.00')
                
                # Process each item for this vendor
                for item in items:
                    product_id = item['product_id']
                    product_name = item['product_name']
                    quantity = item['quantity']
                    amount = item['amount']

                    # Get product and lock it
                    product = Product.objects.select_for_update().get(pk=product_id)

                    # Check stock
                    if product.quantity < quantity:
                        return Response({
                            "error": f"Insufficient stock for {product_name}. Available: {product.quantity}, Requested: {quantity}",
                        }, status=status.HTTP_409_CONFLICT)

                    # Deduct stock
                    Product.objects.filter(pk=product_id).update(quantity=F('quantity') - quantity)
                    vendor_total += amount

                vendor_user = User.objects.get(id=vendor_id)
                
                # Create ONE order per vendor
                order = Order.objects.create(
                    buyer=user,
                    vendor=vendor_user,  # Changed from vendor_id to vendor (ForeignKey field)
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

                # Create Escrow record
                EscrowWallet.objects.create(
                    order=order,
                    amount=vendor_total,
                    status="HELD"
                )

                # Send notification to vendor
                send_notification_to_user(
                    user=vendor_user,
                    title="New Order Received",
                    message=f"You have a new order (ID: {order.id}) from {user.username}. Please review it.",
                    notification_type="order",
                    link=f"/orders?id={order.id}"
                )

            # Debit buyer wallet ONCE (after all orders created)
            BuyerWallet.objects.filter(pk=buyer_wallet.pk).update(
                balance=F('balance') - total_amount_naira
            )

            # Clear purchased cart items
            if ids:
                CartItem.objects.filter(user=user, id__in=ids).delete()
            else:
                CartItem.objects.filter(user=user).delete()

            return Response({
                "message": "Orders created. Awaiting QR code validation.",
                "total_amount_naira": float(total_amount_naira),
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
                


        #         # Create transaction record
        #         reference = str(uuid.uuid4()).replace("-", "")[:12]
        #         transaction = Transaction.objects.create(
        #             buyer=buyer_wallet,
        #             vendor=vendor_wallet,
        #             product=product,
        #             amount=item_total_naira,
        #             quantity=quantity,
        #             reference=reference,
        #             status="COMPLETED",
        #             transaction_type="PURCHASE",
        #         )
        #         transactions_created.append(transaction)

        #     # Debit buyer wallet once (atomic)
        #     BuyerWallet.objects.filter(pk=buyer_wallet.pk).update(
        #         balance=F('balance') - total_amount_naira
        #     )

        #     # Credit each vendor wallet (atomic)
        #     for vendor_id, amount_naira in vendor_credits.items():
        #         try:
        #             VendorWallet.objects.filter(vendor_id=vendor_id).update(
        #                 balance=F('balance') + amount_naira
        #             )
        #         except Exception:
        #             return Response({"error": f"Failed to credit vendor {vendor_id}."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        #     # Clear cart
        #     if ids:
        #         CartItem.objects.filter(user=user, id__in=ids).delete()
        #     else:
        #         CartItem.objects.filter(user=user).delete()

        # return Response({
        #     "message": "Checkout successful. All items purchased.",
        #     "total_amount_naira": total_amount_naira,
        #     "items_purchased": len(cart_details),
        #     "cart_details": cart_details,
        #     "transactions": len(transactions_created),
        # }, status=status.HTTP_200_OK)