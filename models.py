from django.db import models
from django.contrib import admin
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

# Create your models here.
class Account(models.Model):
    account = models.ForeignKey(User, on_delete=models.CASCADE)
    a_name = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=50)
    account_number = models.CharField(max_length=50)
    balance = models.IntegerField(default=1000000)
    
    def masking_account_number(self):
        acc_num = self.account_number or ""
        if len(acc_num) <= 4:
            return "****"
        return "****-" + acc_num[-4:] 
    def __str__(self):
        return f"{self.a_name}, {self.bank_name}, {self.account_number}"
    
# 조금 더 생각 필요..
class Category(models.Model):
    c_name = models.CharField(max_length=200)

class Transaction(models.Model):
    transaction = models.ForeignKey(User, on_delete=models.CASCADE)
    t_account = models.ForeignKey(Account, on_delete=models.CASCADE)
    t_category = models.ForeignKey(Category, on_delete=models.CASCADE)
    tx_type = models.CharField(max_length=20)
    amount = models.IntegerField(default=0)
    occurred_at = models.DateTimeField
    merchant = models.CharField(max_length=20)
    memo = models.CharField(max_length=600)
    created_at = models.DateTimeField
    updated_at = models.DateTimeField

