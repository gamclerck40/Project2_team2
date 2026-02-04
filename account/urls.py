from django.urls import include,path
from .views import SignUpView, MypageView, FindAccountView, MypageUpdateView, PasswordVerifyView, PasswordChangeAfterVerifyView, PasswordResetView, PasswordResetVerifyView, PasswordResetSetView
from django.contrib.auth.views import LoginView,LogoutView

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="account_signup"),
     # ✅ Django 기본 로그인/로그아웃/비번변경 등 제공
    path("login/", 
         LoginView.as_view(template_name='account/login.html'), 
         name='login'),
    path("logout/",LogoutView.as_view(), name='logout'),
    path("found/", FindAccountView.as_view(), name="found_account"),
    path("find/password/", PasswordResetView.as_view(), name="password_reset"),

    path("password-reset/verify/", PasswordResetVerifyView.as_view(), name="pw_reset_verify"),
    path("password-reset/set/", PasswordResetSetView.as_view(), name="pw_reset_set"),
     # ✅ 우리가 만든 회원가입(계좌 Account 생성 포함)
    path("mypage/",MypageView.as_view(), name='mypage'),
     # ✅ 내정보 수정 POST 처리
    path("mypage/update/", MypageUpdateView.as_view(), name="mypage_update"),
     
     # ✅ 비밀번호 변경 플로우
    path("mypage/password/verify/", PasswordVerifyView.as_view(), name="pw_verify"),
    path("mypage/password/change/", PasswordChangeAfterVerifyView.as_view(), name="pw_change"),
    
]