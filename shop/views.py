from django.shortcuts import render
from django.views.generic import *
from .models import Product

#상품 목록 페이지(사진,이름,가격 등의 리스트)
class ProductListView(ListView):
    model = Product #상품 모델 불러옴
    template_name = 'shop/product_list.html' #html경로
    context_object_name = "products" #html에서 사용될 이름


# 상품의 상세 페이지 (상세 설명, 남은 개수)
class ProductDetailView(DetailView):
    model = Product
    template_name = 'shop/product_dateil.html'
    context_object_name = "product"
# Create your views here.
