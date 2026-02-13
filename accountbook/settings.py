import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# 보안 설정
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-fallback-key")
DEBUG = os.environ.get("DEBUG", "True") == "True"

# 불필요한 [cite] 텍스트를 모두 제거했습니다. 
ALLOWED_HOSTS = ["project2-team2.onrender.com", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["https://project2-team2.onrender.com"]

# 앱 정의
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accountbook",
    "shop",
    "account",
    "django.contrib.humanize",
    "whitenoise.runserver_nostatic",
]

# 미들웨어 (WhiteNoise 순서 확인) [cite: 12]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# 이 줄이 빠지면 AttributeError: 'Settings' object has no attribute 'ROOT_URLCONF' 에러가 납니다.
ROOT_URLCONF = "accountbook.urls"

# 템플릿 설정
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
                "django.template.context_processors.media", # 미디어를 위해 추가 [cite: 14]
                "account.context_processors.inject_account",
            ],
        },
    },
]

WSGI_APPLICATION = "accountbook.wsgi.application"

# 데이터베이스 설정 (Render와 로컬 자동 전환) [cite: 15]
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
    )
}

# 로컬 DB 설정 (DATABASE_URL이 없을 때 작동)
if not os.environ.get("DATABASE_URL"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "team_square_db",
        "USER": "teamsquare_user",
        "PASSWORD": "csw13158297!", # 여기에 실제 로컬 비번을 넣으세요.
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }

# 정적 파일 및 미디어 설정
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# 언어 및 시간 설정
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 로그인 관련 경로
LOGIN_REDIRECT_URL = "/shop/"
LOGOUT_REDIRECT_URL = "/shop/"
LOGIN_URL = "/accounts/login/"