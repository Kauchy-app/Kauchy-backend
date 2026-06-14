from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import uuid
import requests
from decimal import Decimal
from django.conf import settings
from paymentapp.models import BuyerWallet, VendorWallet, Transaction
from paymentapp.serializers import BuyerWalletSerializer, VendorWalletSerializer, TransactionSerializer
from .models import TopUpMOdel
from .serializers import TopUpSerializer
from rest_framework.permissions import IsAuthenticated


class TopUpWAlletView(APIView):
    def post(self,request):
        user = request.user
        amount = request.data.get("amount")
        callback_url = request.data.get("callback_url")
        
        try:
            amount = int(amount)
        except (ValueError, TypeError):
            return Response({"error": "Invalid amount"})

        if not amount or amount <=0:
            return Response({"error": "Invalid amount"})
        

        try:
            if request.user.role == 'vendor':
                wallet = VendorWallet.objects.get(vendor=user)
            else:
                wallet = BuyerWallet.objects.get(user=user)
        except (BuyerWallet.DoesNotExist, VendorWallet.DoesNotExist):
            return Response({"error": "Wallet not found."}, status=status.HTTP_404_NOT_FOUND)
        
        reference = str(uuid.uuid4()).replace("-", "")[:12]
        headers ={
            "Authorization":f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type":"application/json"
        }

        data={
            "email":user.email,
            "amount":amount*100,
            "reference":reference,
            "metadata":{"wallet_top_up":True}
        }
        if callback_url:
            data["callback_url"] = callback_url

        res = requests.post("https://api.paystack.co/transaction/initialize",json=data,headers=headers)

        res_data= res.json()

        if res_data["status"] or res_data["data"]["status"]=="success":
            # Ensure we persist the generated reference so the DB unique constraint
            # is respected and later verification can look up the transaction.
            try:
                if request.user.role == 'vendor':
                    TopUpMOdel.objects.create(
                        vendor=wallet,
                        amount=amount,
                        status="PENDING",
                        transaction_type="TOPUP",
                        reference=reference,
                    )
                else:
                    TopUpMOdel.objects.create(
                        buyer=wallet,
                        amount=amount,
                        status="PENDING",
                        transaction_type="TOPUP",
                        reference=reference,
                    )
            except Exception:
                # If a rare collision or DB error occurs, generate a fresh reference
                # and attempt a single retry to avoid IntegrityError on empty/duplicate refs.
                reference = str(uuid.uuid4()).replace("-", "")[:12]
                TopUpMOdel.objects.create(
                    buyer=wallet,
                    amount=amount,
                    status="PENDING",
                    transaction_type="TOPUP",
                    reference=reference,
                )

            return Response({
                "message":"TOPUP initialize successfully","details":res_data
            },status=status.HTTP_200_OK)
        return Response({"error":"Failed to initialize top-up","detail": res_data},status=status.HTTP_400_BAD_REQUEST)
    

class VerifyTopupView(APIView):
    def get(self,request,reference):
        headers = {
            "Authorization":f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type":"application/json"
        }

        res = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers=headers
            
            )
        res_data = res.json()

        if res_data.get('status') or (res_data.get("data") and res_data["data"].get("status") == "success"):

            user = request.user
            try:
                if request.user.role == 'vendor':
                    wallet = VendorWallet.objects.get(vendor=user)
                else:
                    wallet = BuyerWallet.objects.get(user=user)
            except (BuyerWallet.DoesNotExist, VendorWallet.DoesNotExist):
                return Response({"error": "Wallet not found."}, status=status.HTTP_404_NOT_FOUND)
            
            transaction_owner=None
            

            # Try to find the transaction regardless of status so we can be idempotent.
            transaction = TopUpMOdel.objects.filter(reference=reference).first()
            if not transaction:
                return Response({"error": "Top-up transaction not found."}, status=status.HTTP_404_NOT_FOUND)
            if transaction.buyer:
                transaction_owner=transaction.buyer.user
            elif transaction.vendor:
                transaction_owner=transaction.vendor.vendor

            if transaction_owner != user:
                return Response({"error": "You are not authorized to verify this transaction."}, status=status.HTTP_403_FORBIDDEN)
            

            
            # If the transaction was already processed, return success with current balance
            if transaction.status == "COMPLETED":
                try:
                    wallet_balance = float(Decimal(wallet.balance))
                except Exception:
                    wallet_balance = None
                return Response({"message": "Top-up already processed.", "wallet_balance": wallet_balance, "data": res_data}, status=status.HTTP_200_OK)

            # At this point the transaction exists and is not completed -> process it
            metadata = res_data.get("data", {})
            amount_kobo = metadata.get("amount", transaction.amount or 0)
            amount_naira= Decimal(amount_kobo)/Decimal(100)


            wallet.balance += amount_naira
            transaction.status = "COMPLETED"

            wallet.save()
            transaction.save()

            # Return the updated wallet balance in major units (Naira)
            try:
                wallet_balance = float(Decimal(wallet.balance))
            except Exception:
                wallet_balance = None

            return Response({
                "data": res_data,
                "wallet_balance": wallet_balance
            }, status=status.HTTP_200_OK)
        return Response({"error":"Failed to verifiy TOPUP"},status=status.HTTP_400_BAD_REQUEST)


class GetWalletBalanceView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        try:
            if user.role == 'vendor':
                data = VendorWallet.objects.get(vendor=request.user)
                serializer = VendorWalletSerializer(data)
            else:
                data = BuyerWallet.objects.get(user=request.user)
                serializer = BuyerWalletSerializer(data)
            print(serializer.data)
            return Response(serializer.data)
        except (VendorWallet.DoesNotExist, BuyerWallet.DoesNotExist):
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)


class WalletHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Get Purchases (Transactions)
        if user.role == 'vendor':
            purchases = Transaction.objects.filter(vendor__vendor=user, status='COMPLETED').order_by('-timestamp')
            topups = TopUpMOdel.objects.filter(vendor__vendor=user, status='COMPLETED').order_by('-created_at')
        else:
            purchases = Transaction.objects.filter(buyer__user=user, status='COMPLETED').order_by('-timestamp')
            topups = TopUpMOdel.objects.filter(buyer__user=user, status='COMPLETED').order_by('-created_at')
            
        purchase_data = TransactionSerializer(purchases, many=True).data
        topup_data = TopUpSerializer(topups, many=True).data
        
        # Add labels to distinguish
        for p in purchase_data:
            p['history_type'] = 'PURCHASE'
            p['date'] = p['timestamp']
            p['type'] = 'debit'
            p['amount'] = float(p['amount'])
            
        for t in topup_data:
            t['history_type'] = 'TOPUP'
            t['date'] = t.get('created_at', None) # If we don't have created_at yet legacy data might be problematic
            t['type'] = 'credit'
            t['amount'] = float(t['amount'])
            t['description'] = 'Wallet Top-up'

        # Combine and sort by date
        history = purchase_data + topup_data
        history.sort(key=lambda x: x.get('date') or '', reverse=True)
        
        return Response(history)
