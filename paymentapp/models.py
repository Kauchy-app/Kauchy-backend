from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.
User = get_user_model()

class VendorWallet(models.Model):
    vendor=models.OneToOneField(User, on_delete=models.CASCADE, related_name="Vendor")
    balance=models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

class BuyerWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="Buyer")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

class Transaction(models.Model):
    buyer = models.ForeignKey(BuyerWallet, on_delete=models.SET_NULL, null=True, related_name="buyer_transactions")
    vendor = models.ForeignKey(VendorWallet, on_delete=models.SET_NULL, null=True, related_name="vendor_transactions")
    # new product FK (nullable, will not break existing rows)
    product = models.ForeignKey('Products_app.Product', null=True, blank=True, on_delete=models.SET_NULL, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    quantity = models.PositiveIntegerField(default=1)
    reference = models.CharField(max_length=100, unique=True)
    status_choices = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]
    status = models.CharField(max_length=10, choices=status_choices, default='PENDING')

    transaction_type_choices = [
        ('TOPUP', 'Top Up'),
        ('PURCHASE', 'Purchase'),
        ('WITHDRAWAL', 'Withdrawal'),
    ]
    transaction_type = models.CharField(max_length=20, choices=transaction_type_choices)
