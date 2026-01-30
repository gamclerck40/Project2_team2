from django.contrib import admin
from django.urls import include,path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/shop/", permanent=False)),
    path('admin/', admin.site.urls),
    path('shop/', include('shop.urls')),

    # ✅ Django 기본 로그인/로그아웃/비번변경 등 제공
    path("accounts/", include("django.contrib.auth.urls")),

    # ✅ 우리가 만든 회원가입(계좌 Account 생성 포함)
    path("accounts/", include("account.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,document_root = settings.MEDIA_ROOT)