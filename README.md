# Python 기본 캐시 및 가상환경 파일 제외
venv/
env/
__pycache__/
*.pyc
*.pyo
*.pyd

# 환경 변수 파일 (보안 중요)
.env

# 개발중에만 사용

# 데이터베이스 파일 제외 (SQLite 등)
db.sqlite3
*.sqlite3

# Django 마이그레이션 캐시 제외
# **/migrations/*.pyc
# **/migrations/*.py
# !**/migrations/__init__.py

# 로그 파일 제외
*.log
*.out
*.err

# 미디어 및 정적 파일 (수동 업로드 방지)
# media/
# staticfiles/
# static/
node_modules/

# VS Code 및 IDE 설정 파일 제외
.vscode/
.idea/
*.sublime-workspace

# Docker 관련 파일 제외 (사용할 경우)
docker-compose.override.yml


### 추가 모듈 uv pip install pillow
### dateil.html 구성 및 구현 테스트 완료 
### list.html 즉 기본 화면 구성 및 테스트 완료 

----------------------------------------------
# 2026.01.30 16:06 환경 전체 초기화.
# 2026.02.05 오전
    - 비밀번호 변경시 내정보 수정 날짜 갱신
    - 내정보 수정 -> form 필드에 DB에 저장된 주소지가 입력되어 있게 수정
    - 장바구니 -> 상품 결제 시 여러 항목을 담았을 때 한 상품의 수량을 증가시 다른 상품의 수량도 같이 증가하던 오류 수정
    - Account, Shop 작업환경 완전 분리(DB/View 파일 위치 등)
    - 거래 내역 항목에 필터링 기능 추가(카테고리, 날짜, 결제 계좌 등)

# 2026.02.06
    - 별점/리뷰 기능 구현(상품 구매자만 가능하게, 수정&삭제 가능)
        >> 포토 리뷰 구현(예정)
    - Mypage 전면 수정 (은행 계좌 등록, 주소 설정 UI 로직 변경)
