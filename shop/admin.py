from django.contrib import admin
from .models import Account, Category, Product, ProductImage, Transaction
from django.contrib import admin
# Register your models here.

admin.site.register(Account)
admin.site.register(Category)
admin.site.register(Transaction)


class ProductDetailImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3
    fields = ("image", "sort_order")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductDetailImageInline]