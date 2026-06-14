from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum

from Products_app.models import Product
from paymentapp.models import Transaction


class AnalyticsOverview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Vendor products
        products_qs = Product.objects.filter(vendor_id=user)

        total_stock = products_qs.aggregate(total_stock=Sum('quantity'))['total_stock'] or 0
        active_products = products_qs.filter(quantity__gt=0).count()

        # Transactions for this vendor (VendorWallet.vendor -> User)
        vendor_tx_qs = Transaction.objects.filter(
            transaction_type='PURCHASE',
            status='COMPLETED',
            vendor__vendor=user
        )

        total_revenue = vendor_tx_qs.aggregate(total=Sum('amount'))['total'] or 0
        total_sales_quantity = vendor_tx_qs.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0

        product_views = Product.objects.filter(vendor_id=user)
        views = 0
        for i in product_views:
            views += int(i.view_count)

        return Response({
            'total_revenue': float(total_revenue),
            'total_sales_quantity': int(total_sales_quantity),
            'active_products_count': int(active_products),
            'total_stock_units': int(total_stock),
            'total_views': int(views),
            'rating': int(user.rating)
        })


class TopProductsView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Require Transaction.product FK to compute per-product sales
        tx_fields = [f.name for f in Transaction._meta.get_fields()]
        if 'product' not in tx_fields:
            return Response({
                'detail': "Top-products requires a `product` FK on Transaction. "
                          "Add `product = ForeignKey(Product, ...)` to paymentapp.Transaction."
            }, status=400)

        qs = Transaction.objects.filter(
            transaction_type='PURCHASE',
            status='COMPLETED',
            # vendor__vendor=user,
            product__isnull=False
        ).values(
            'product__id', 'product__product_name', 'product__price', 'product__image_url', 'product__view_count', 'product__description', 'product__vendor_id__username', 'product__quantity'
        ).annotate(
            units_sold=Sum('quantity'),
            revenue=Sum('amount')
        ).order_by('-units_sold')[:10]

        results = []
        for item in qs:
            results.append({
                'product_id': item['product__id'],
                'product_name': item['product__product_name'],
                'image_url': item['product__image_url'],
                'description': item['product__description'],
                'vendor_name': item['product__vendor_id__username'],
                'view_count': item['product__view_count'],
                'quantity': item['product__quantity'],
                'unit_price': float(item['product__price']) if item['product__price'] is not None else None,
                'units_sold': int(item['units_sold'] or 0),
                'revenue': float(item['revenue'] or 0),
            })
        return Response(results)


class StockLevelsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        threshold = request.query_params.get('threshold')

        qs = Product.objects.filter(vendor_name=user).values('id', 'product_name', 'quantity', 'price')
        if threshold is not None:
            try:
                t = int(threshold)
                qs = qs.filter(quantity__lte=t)
            except ValueError:
                return Response({'detail': 'threshold must be integer'}, status=400)

        items = []
        for p in qs:
            items.append({
                'id': p['id'],
                'product_name': p['product_name'],
                'quantity': p['quantity'],
                'price': float(p['price']) if p['price'] is not None else None,
            })

        return Response(items)
    
class TopProductsVendorView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Require Transaction.product FK to compute per-product sales
        tx_fields = [f.name for f in Transaction._meta.get_fields()]
        if 'product' not in tx_fields:
            return Response({
                'detail': "Top-products requires a `product` FK on Transaction. "
                          "Add `product = ForeignKey(Product, ...)` to paymentapp.Transaction."
            }, status=400)

        qs = Transaction.objects.filter(
            transaction_type='PURCHASE',
            status='COMPLETED',
            vendor__vendor=user,
            product__isnull=False
        ).values(
            'product__id', 'product__product_name', 'product__price', 'product__image_url', 'product__view_count', 'product__description', 'product__vendor_id__username', 'product__quantity'
        ).annotate(
            units_sold=Sum('quantity'),
            revenue=Sum('amount')
        ).order_by('-units_sold')[:5]

        results = []
        for item in qs:
            results.append({
                'product_id': item['product__id'],
                'product_name': item['product__product_name'],
                'image_url': item['product__image_url'],
                'description': item['product__description'],
                'vendor_name': item['product__vendor_id__username'],
                'view_count': item['product__view_count'],
                'quantity': item['product__quantity'],
                'unit_price': float(item['product__price']) if item['product__price'] is not None else None,
                'units_sold': int(item['units_sold'] or 0),
                'revenue': float(item['revenue'] or 0),
            })
        return Response(results)