from django.db import models
from paymentapp.models import BuyerWallet,VendorWallet
from django.contrib.auth import get_user_model

User = get_user_model()

PAYMENT_STATUS = [
    ("PENDING","pending"),
    ("COMPLETED","completed")
]

ESCROW_STATUS = [
    ("HELD","held"),
    ("RELEASED","released"),
    ("REFUNDED","refunded")
]

class TopUpMOdel(models.Model):
    buyer = models.ForeignKey(BuyerWallet,on_delete=models.CASCADE,null=True, related_name="topup_wallet")
    vendor = models.ForeignKey(VendorWallet,on_delete=models.CASCADE,null=True, related_name="vendor_topup_wallet")
    amount=models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10,choices=PAYMENT_STATUS,default="PENDING")
    transaction_type = models.CharField(max_length=10, default="TOPUP")
    reference = models.CharField(max_length=36, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class EscrowWallet(models.Model):
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='escrow')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    held_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ESCROW_STATUS, default="HELD")

    def __str__(self):
        return f"Escrow for Order {self.order.id} - Status: {self.status}"