from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from account.views import *

urlpatterns = [
    # 회원가입 페이지
    path("signup/", SignUpView.as_view(), name="account_signup"),

    # ✅ Django 기본 로그인/로그아웃
    path("login/", LoginView.as_view(template_name="account/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # 아이디 찾기 / 계정 찾기
    path("found/", FindAccountView.as_view(), name="found_account"),

    # 비밀번호 재설정(이메일 또는 인증 시작 단계)
    path("find/password/", PasswordResetView.as_view(), name="password_reset"),

    # 비밀번호 재설정 인증(코드/토큰 검증 단계)
    path("password-reset/verify/", PasswordResetVerifyView.as_view(), name="pw_reset_verify"),

    # 비밀번호 재설정 최종 변경(새 비밀번호 설정)
    path("password-reset/set/", PasswordResetSetView.as_view(), name="pw_reset_set"),

    # 내정보 메인 페이지 (마이페이지)
    path("mypage/", MypageView.as_view(), name="mypage"),

    # 내정보 수정(전화번호, 계좌 정보 등 프로필 수정 처리)
    path("mypage/update/", MypageUpdateView.as_view(), name="mypage_update"),

    # 마이페이지에서 기본 배송지 설정
    path('mypage/set-default/', SetDefaultAddressView.as_view(), name='set_default_address'),

    # 내 정보 수정 진입 전 비밀번호 재확인
    path("mypage/password/verify/", PasswordVerifyView.as_view(), name="pw_verify"),

    # 비밀번호 재확인 후 실제 비밀번호 변경
    path("mypage/password/change/", PasswordChangeAfterVerifyView.as_view(), name="pw_change"),

    # 배송지 삭제
    path("address/delete/<int:address_id>/", AddressDeleteView.as_view(), name="address_delete"),

    # 거래 내역 영수증 PDF 보기/다운로드
    path("receipts/<int:tx_id>.pdf", ReceiptPDFView.as_view(), name="receipt_pdf"),

    # 계좌 추가 (다계좌 구조)
    path("accounts/add/", AccountAddView.as_view(), name="account_add"),

    # 계좌 삭제 (기본 계좌는 삭제 불가)
    path("accounts/delete/<int:account_id>/", AccountDeleteView.as_view(), name="account_delete"),

    # 기본 계좌 변경 (다계좌 중 하나를 기본으로 설정)
    path("accounts/default/<int:account_id>/", SetDefaultAccountView.as_view(), name="account_set_default"),

    # 계좌 충전 페이지 (현재는 더미 페이지 / 추후 잔액 충전 기능 구현 예정)
    path("accounts/charge/", AccountChargeView.as_view(), name="account_charge"),
]