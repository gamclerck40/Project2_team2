import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url  # ✅ DB 설정을 위해 필수

# 1. 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# 2. 보안 설정
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-fallback-key")
DEBUG = os.environ.get("DEBUG", "False") == "True"  # 배포 시 False 권장 

ALLOWED_HOSTS = [
    "project2-team2.onrender.com", 
    "localhost", 
    "127.0.0.1"
]

# CSRF 보안 설정 (로그인 에러 방지)
CSRF_TRUSTED_ORIGINS = ["https://project2-team2.onrender.com"]

# 3. 앱 정의
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 커스텀 앱들
    "accountbook",
    "shop",
    "account",
    "django.contrib.humanize",
    "whitenoise.runserver_nostatic",  # ✅ 정적 파일 서빙용 
]

# 4. 미들웨어 (WhiteNoise 추가 필수)
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # ✅ 정적 파일 서빙 미들웨어 
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "accountbook.urls"

# 5. 템플릿 설정 (에러 수정됨)
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "account.context_processors.inject_account",  # ✅ 커스텀 프로세서
            ],
        },
    },
]

WSGI_APPLICATION = "accountbook.wsgi.application"

# 6. 데이터베이스 설정 (Render DB 자동 연결)
# DATABASE_URL 환경변수가 있으면 Render DB를 쓰고, 없으면 로컬 DB를 씁니다. 
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
    )
}

# 7. 정적 파일 및 미디어 설정 (배포 최적화)
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")  # ✅ collectstatic 경로 
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

# WhiteNoise: 정적 파일 압축 및 캐싱 기능 활성화 
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# 8. 언어 및 시간 설정
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 로그인 관련 경로
LOGIN_REDIRECT_URL = "/shop/"
LOGOUT_REDIRECT_URL = "/shop/"
LOGIN_URL = "/accounts/login/"