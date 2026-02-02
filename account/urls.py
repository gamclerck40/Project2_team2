from django.urls import include,path
from .views import SignUpView, MypageView, FindIDView
from django.contrib.auth.views import LoginView,LogoutView

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="account_signup"),
    # ✅ Django 기본 로그인/로그아웃/비번변경 등 제공
    path("login/", 
         LoginView.as_view(template_name='account/login.html'), 
         name='login'),
    path("findid/",
         FindIDView.as_view(), name="find_id"),
    path("logout/", 
         LogoutView.as_view(), 
         name='logout'),
    path("mypage/",MypageView.as_view(), name='mypage'),
    # ✅ 우리가 만든 회원가입(계좌 Account 생성 포함)
]