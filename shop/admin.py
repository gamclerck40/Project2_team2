from django.contrib import admin
from .models import Account, Category, Product, Transaction
# Register your models here.
admin.site.register(Account)
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Transaction)