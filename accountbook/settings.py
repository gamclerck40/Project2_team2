import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url  # ✅ 추가: DB URL 파싱용

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# --- 보안 관련 ---
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-secret-key-for-dev") # 로컬 대비

# 배포 시 False로 바꿔야 하지만, 우선 확인을 위해 환경변수로 조절 권장
DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = ["project2-team2.onrender.com", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["https://project2-team2.onrender.com"] # ✅ Render 접속 허용

# --- 애플리케이션 정의 ---
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
    "whitenoise.runserver_nostatic", # ✅ 추가: 정적 파일 최적화
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware", # ✅ 추가: (Security 바로 다음 위치)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# --- 데이터베이스 설정 (배포/로컬 자동 전환) ---
# Render의 DATABASE_URL이 있으면 그걸 쓰고, 없으면 로컬 Postgres를 씁니다.
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
    )
}

# 만약 Render DB 주소가 없으면 기존 로컬 설정을 기본값으로 사용
if not os.environ.get("DATABASE_URL"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "team_square_db",
        "USER": "teamsquare_user",
        "PASSWORD": "csw13158297!",
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }

# --- 정적 파일 및 미디어 설정 ---
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles") # ✅ 배포 시 필수
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

# WhiteNoise 설정 (압축 및 캐싱)
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# --- 기타 설정 ---
ROOT_URLCONF = "accountbook.urls"
WSGI_APPLICATION = "accountbook.wsgi.application"
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True