"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include,path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('shop/', include('shop.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,document_root = settings.MEDIA_ROOT)
=======
# Admin 관리자 '웹사이트를 생성하고 관리할 수 있게 해주는 기능'
# DB모델 데이터를 시각적으로 편리하게 추가/편집/삭제할 수 있는 기능 제공.
# from django.conf.urls.static import static
# from django.urls import include, path
# from django.conf import settings
# from django.views.generic import RedirectView

# urlpatterns = [
#     path("", RedirectView.as_view(url="/shop/", permanent=False)),
#     # http://127.0.0.1:8000/poll/ << polls 이름을 뒤에 붙여주는 로직
#     path("admin/", admin.site.urls),
#     # http://127.0.0.1:8000/admin/
    
#     path("shop/", include("shop.urls")),
#     # http://127.0.0.1:8001/shop shop호출.

#     ]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

