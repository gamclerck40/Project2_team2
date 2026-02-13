#!/usr/bin/env bash
# 에러 발생 시 즉시 중단
set -o errexit

# 1. 패키지 설치
pip install -r requirements.txt

# 2. 정적 파일 모으기 (CSS, 이미지 등)
python manage.py collectstatic --no-input

# 3. 데이터베이스 테이블 생성 및 업데이트
python manage.py migrate --no-input

python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='normalframe1094').exists() or User.objects.create_superuser('normalframe1094', 'kapol2990@gmail.com', 'csw13158297!')"