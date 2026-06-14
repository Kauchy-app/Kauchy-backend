"""Helpers that adjust a user's personalization signals.

Scores only ever move on *intentional* actions (likes), never on passive
feed views. Negative deltas (unlikes) are floored at zero so the
PositiveIntegerField columns never violate their DB check constraint.
"""
from django.db.models import F

from .models import UserCategoryModel, UserVendorAffinity


def _authed(user):
    return bool(user) and getattr(user, "is_authenticated", False)


def add_category_interest(user, category, delta=1):
    """Raise/lower the user's interest in a product category."""
    if not _authed(user) or not category:
        return
    obj, created = UserCategoryModel.objects.get_or_create(
        user=user, category=category, defaults={"view_count": max(delta, 0)},
    )
    if created:
        return
    if delta < 0:
        # Only decrement when it won't drop below zero.
        UserCategoryModel.objects.filter(pk=obj.pk, view_count__gte=-delta).update(
            view_count=F("view_count") + delta
        )
    else:
        UserCategoryModel.objects.filter(pk=obj.pk).update(view_count=F("view_count") + delta)


def add_vendor_affinity(user, vendor, delta=1):
    """Raise/lower how much the user gravitates toward a vendor."""
    if not _authed(user) or vendor is None:
        return
    # Don't build affinity toward your own store.
    if getattr(vendor, "pk", None) == getattr(user, "pk", None):
        return
    obj, created = UserVendorAffinity.objects.get_or_create(
        user=user, vendor=vendor, defaults={"score": max(delta, 0)},
    )
    if created:
        return
    if delta < 0:
        UserVendorAffinity.objects.filter(pk=obj.pk, score__gte=-delta).update(
            score=F("score") + delta
        )
    else:
        UserVendorAffinity.objects.filter(pk=obj.pk).update(score=F("score") + delta)
