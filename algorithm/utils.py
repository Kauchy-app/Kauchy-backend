from .models import UserCategoryModel, UserVendorAffinity
from Products_app.models import Product, ProductView
import random


def personalized_feed(user):
    products = Product.objects.select_related('vendor_id').all()
    user_categories = {uc.category: uc for uc in UserCategoryModel.objects.filter(user=user)}
    vendor_affinity = {a.vendor_id: a.score for a in UserVendorAffinity.objects.filter(user=user)}
    seen_ids = set(ProductView.objects.filter(user=user).values_list('product_id', flat=True))

    scored_products = []

    for product in products:
        user_view = user_categories.get(product.category)
        if user_view:
            category_boost = 1 + (user_view.view_count * 0.1)
        else:
            category_boost = 1

        if product.vendor_id.institute == user.institute:
            location_boost = 2.0
        else:
            location_boost = 1.0

        # Raised when the user likes this vendor's products/content.
        affinity = vendor_affinity.get(product.vendor_id_id, 0)
        vendor_boost = 1 + (affinity * 0.2)

        if product.view_count > 100:
            popularity_boost = 1.3
        elif product.view_count > 50:
            popularity_boost = 1.15
        else:
            popularity_boost = 1.0

        total_boost = category_boost * location_boost * vendor_boost * popularity_boost
        score = total_boost * random.random()
        seen = product.id in seen_ids
        scored_products.append((seen, score, product))

    # Already-seen products sink to the bottom; within each group, highest score first.
    scored_products.sort(key=lambda x: (x[0], -x[1]))
    recommended_products = [product for seen, score, product in scored_products]

    return recommended_products
