from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from account.views import (
    SignUpView,
    FindAccountView,
    PasswordResetView,
    PasswordResetVerifyView,
    PasswordResetSetView,
    MypageView,
    MypageUpdateView,
    PasswordVerifyView,
    PasswordChangeAfterVerifyView,
    AddressDeleteView,
    ReceiptPDFView,
    SetDefaultAddressView,
)

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="account_signup"),

    # ✅ Django 기본 로그인/로그아웃
    path("login/", LoginView.as_view(template_name="account/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    path("found/", FindAccountView.as_view(), name="found_account"),
    path("find/password/", PasswordResetView.as_view(), name="password_reset"),

    path("password-reset/verify/", PasswordResetVerifyView.as_view(), name="pw_reset_verify"),
    path("password-reset/set/", PasswordResetSetView.as_view(), name="pw_reset_set"),

    path("mypage/", MypageView.as_view(), name="mypage"),
    path("mypage/update/", MypageUpdateView.as_view(), name="mypage_update"),
    path('mypage/set-default/', SetDefaultAddressView.as_view(), name='set_default_address'),

    path("mypage/password/verify/", PasswordVerifyView.as_view(), name="pw_verify"),
    path("mypage/password/change/", PasswordChangeAfterVerifyView.as_view(), name="pw_change"),

    path("address/delete/<int:address_id>/", AddressDeleteView.as_view(), name="address_delete"),
    path("receipts/<int:tx_id>.pdf", ReceiptPDFView.as_view(), name="receipt_pdf"),
]
