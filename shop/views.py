
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
# from django.shortcuts import render, get_object_or_404
# # get_object_or_404 >> 페이지 없음(404)
# from .models import Product
# from django.db.models import F
# from django.urls import reverse
# from django.views import generic
# from django.http import HttpResponseRedirect, JsonResponse
# from django.utils import timezone
# from django.urls import reverse_lazy
# import datetime
# Create your views here.
class IndexView(generic.ListView):
    template_name = "shop/home.html"
    context_object_name = "product_list"

    def get_queryset(self):
        return Product.objects.all()

class ProductDetailView(generic.DetailView):
        model = Product
        template_name = "shop/product_detail.html"