from decimal import Decimal

from django.shortcuts import get_object_or_404

from account.models import Account, Address
from shop.models import Cart, Product, UserCoupon
