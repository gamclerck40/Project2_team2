from django.urls import include,path
from .views import ProductListView, ProductDetailView
from . import views

urlpatterns = [
    path('', ProductListView.as_view(), name='product_list'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('cart/add/<int:product_id>/', views.AddToCartView.as_view(), name='add_to_cart'),
    path('cart/', views.CartListView.as_view(), name='cart_list'),
    path('cart/remove/<int:cart_item_id>/', views.RemoveFromCartView.as_view(), name='remove_from_cart'),
    path('order/execute/', views.OrderExecutionView.as_view(), name='order_execute'),
    path('order/direct/<int:product_id>/', views.DirectPurchaseView.as_view(), name='direct_purchase'),
    path('transactions/', views.TransactionHistoryView.as_view(), name='transaction_history'),
]