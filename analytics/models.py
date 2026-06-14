from django.db import models

# Create your models here.

from django.db import models
from django.conf import settings
from Products_app.models import Product

class DailyAnalytics(models.Model):
    """Daily snapshot of key metrics."""
    date = models.DateField(auto_now_add=True, unique=True)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_sales_quantity = models.PositiveIntegerField(default=0)
    active_products_count = models.PositiveIntegerField(default=0)
    total_stock_units = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-date']
        verbose_name = "Daily Analytics"
        verbose_name_plural = "Daily Analytics"

    def __str__(self):
        return f"Analytics {self.date}"

class ProductStockSnapshot(models.Model):
    """Track stock levels over time for a product."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_history')
    quantity = models.PositiveIntegerField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['product', '-recorded_at']),
        ]
        verbose_name = "Product Stock Snapshot"
        verbose_name_plural = "Product Stock Snapshots"

    def __str__(self):
        return f"{self.product.product_name} - {self.quantity} units @ {self.recorded_at}"

class TopSellingProduct(models.Model):
    """Cached top-selling products (updated daily/hourly)."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='top_selling_records')
    units_sold = models.PositiveIntegerField(default=0)
    revenue_generated = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    period_start = models.DateField()  # e.g., start of this week/month
    period_end = models.DateField()
    rank = models.PositiveIntegerField()

    class Meta:
        ordering = ['period_start', 'rank']
        unique_together = [['product', 'period_start', 'period_end']]
        verbose_name = "Top Selling Product"
        verbose_name_plural = "Top Selling Products"

    def __str__(self):
        return f"{self.product.product_name} - Rank {self.rank} ({self.period_start} to {self.period_end})"