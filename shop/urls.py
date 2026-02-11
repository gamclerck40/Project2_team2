# from django.urls import include, path

# from . import views
# from .views import *

# urlpatterns = [
#     path("", ProductListView.as_view(), name="product_list"),
#     path("products/<int:pk>/", ProductDetailView.as_view(), name="product_detail"),
#     path("cart/add/<int:product_id>/", views.AddToCartView.as_view(), name="add_to_cart"),
#     path("cart/", views.CartListView.as_view(), name="cart_list"),
#     path("cart/remove/<int:cart_item_id>/",views.RemoveFromCartView.as_view(),name="remove_from_cart"),
#     path('checkout/', views.CheckoutView.as_view(), name='checkout'),
#     path("order/execute/", views.OrderExecutionView.as_view(), name="order_execute"),
#     path("order/direct/<int:product_id>/",views.DirectPurchaseView.as_view(),name="direct_purchase"),
#     path("transactions/",views.TransactionHistoryView.as_view(),name="transaction_history"),
#     path('product/<int:product_id>/review/', ReviewCreateView.as_view(), name='review_create'),
#     path('review/delete/<int:review_id>/', ReviewDeleteView.as_view(), name='review_delete'),
#     path("review/update/<int:review_id>/", views.ReviewUpdateView.as_view(), name="review_update"),
#     path("consulting/", ConsultingProductListView.as_view(), name="product_consulting_list"),  # ✅ 추가
#     path('coupons/', views.CouponRegisterView.as_view(), name='register_coupon'),
    
# ]
from django.urls import path

from shop.views import (
    ProductListView,
    ProductDetailView,
    AddToCartView,
    CartListView,
    RemoveFromCartView,
    CheckoutView,
    OrderExecutionView,
    DirectPurchaseView,
    TransactionHistoryView,
    ReviewCreateView,
    ReviewDeleteView,
    ReviewUpdateView,
    ConsultingProductListView,
    CouponRegisterView,
)

urlpatterns = [
    path("", ProductListView.as_view(), name="product_list"),
    path("products/<int:pk>/", ProductDetailView.as_view(), name="product_detail"),
    path("cart/add/<int:product_id>/", AddToCartView.as_view(), name="add_to_cart"),
    path("cart/", CartListView.as_view(), name="cart_list"),
    path("cart/remove/<int:cart_item_id>/", RemoveFromCartView.as_view(), name="remove_from_cart"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("order/execute/", OrderExecutionView.as_view(), name="order_execute"),
    path("order/direct/<int:product_id>/", DirectPurchaseView.as_view(), name="direct_purchase"),
    path("transactions/", TransactionHistoryView.as_view(), name="transaction_history"),
    path("product/<int:product_id>/review/", ReviewCreateView.as_view(), name="review_create"),
    path("review/delete/<int:review_id>/", ReviewDeleteView.as_view(), name="review_delete"),
    path("review/update/<int:review_id>/", ReviewUpdateView.as_view(), name="review_update"),
    path("consulting/", ConsultingProductListView.as_view(), name="product_consulting_list"),
    path("coupons/", CouponRegisterView.as_view(), name="register_coupon"),
]

