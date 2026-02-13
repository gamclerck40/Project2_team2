# (teamsquare_shoppingmole)

## 시작하기 앞서

- 본 프로젝트는 기저기반을 해당 앱을 사용하는 사용자가 "모두" 설정해서 시험 해 보는 어디까지나 테스트 환경을 전제로 만든 프로젝트입니다.
- Product, Account, Coupon, Category 등 모든 데이터 셋은 사용자가 직접 세팅을 해야 합니다.

### 기본적으로 세팅 되어 있는 부분

1. 기본 BANK 추가

### 사용자가 직접 처음부터 해야 할 것들(관리자 Page)

1. Category 항목 추가
2. Product 상품 (사진, 상품 설명, 상세 페이지 이미지 등)
3. 계정 생성 필요 (사용자 본인 기준대로 계정을 만들 것.)
4. Coupon도 직접 만들어야 함.

사용자의 가용 예산을 실시간으로 분석하여 구매 가이드를 제안하는 데이터 연동형 이커머스
쇼핑몰입니다. 단순한 물건 구매를 넘어,
사용자의 계좌 잔액에 맞춘 **'구매 가능 상품 품목'**을
제공하는 사용자 중심 쇼핑 플랫폼을 지향합니다.

# 🚀 주요 기능

### 사용자 인증 및 접근 제어 (Authentication & Access Control)

- 세션 기반 인증 시스템: Django의 기본 User 모델과 Session 메커니즘을 활용한 로그인/로그아웃 구현.
- 접근 제한 (LoginRequiredMixin): 비인증 사용자의 자산 데이터 접근을 원천 차단하고 로그인 페이지로 리다이렉션.

---

### ▸ 자산 및 계좌 관리 (Account CRUD)

- 계좌 생성/수정/삭제: 은행별, 용도별(예적금, 입출금 등) 다중 계좌 등록 및 관리.
- 실시간 잔액 동기화: 거래 내역 입력에 따른 계좌별 가용 잔액 자동 계산.

---

### ▸ 거래 내역 관리 (Transaction CRUD)

- 거래 기록 생성: 수입·지출 내역의 일시, 금액, 카테고리, 메모 입력.
- 영수증 파일 업로드: 각 거래 건당 이미지/PDF 파일을 직접 첨부하여 데이터의 객관성 확보.
- 내역 수정 및 삭제: 오기입된 데이터의 사후 관리 기능.

---

### ▸ 데이터 탐색 및 조회 (Search & Discovery)

- 다차원 필터링: 기간별, 계좌별, 카테고리별 내역 분류.
- 검색 및 정렬: 거래처명이나 메모 키워드 검색, 금액순/최신순 정렬을 통한 데이터 추적.

---

### ▸ 자산 대시보드 (Dashboard Summary)

- 요약 정보 제공: 총자산 현황, 당월 수입/지출 합계 시각화.
- 증빙 현황 체크: 전체 거래 대비 영수증 첨부 비율 등 관리 상태 브리핑.

---

### ▸ [추가기능] 전문 분석 기능 (Fund Manager Preview)

- 소비 가이드라인: MVP 기록 데이터를 바탕으로 한 기초적인 소비 상한선 가이드 제시.
- 맞춤형 필터링 연동: 자산 상태에 따른 쇼핑 상품의 우선순위 노출 맛보기 기능.

# 🛠 기술 스택

Backend: Django 6.0.1 (Python)

Database: PostgreSQL (Production), SQLite (Development)

Frontend: Django Template Engine (SSR), CSS3, HTML5

Library: ReportLab (PDF 생성), Pillow (이미지 처리), psycopg2-binary (DB 연결)

Deployment: render.com

# ⚙ 로컬 실행 방법

# 1. 가상환경 활성화

source venv/bin/activate

# 2. 패키지 설치 (PostgreSQL 연결용 라이브러리 포함)

pip install -r requirements.txt

# 3. 환경 변수 설정

# 프로젝트 루트에 .env 파일을 생성하고 아래 형식을 참고하세요.

touch .env

# 4. 마이그레이션

python manage.py migrate

# 5. 서버 실행

python manage.py runserver

# 🔐 환경 변수 (.env) 예시

POSTGRES_DB=DBNAME
POSTGRES_USER=USER
POSTGRES_PASSWORD=STRONG_PASSWORD
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5432
SECRETKEY=your_secret_key_here

# 📂 디렉토리 구조

PROJECT2_TEAM2/
├─ accountbook/ # 프로젝트 설정 및 공통 미들웨어
├─ account/ # 계좌 관리, 주소록, 프로필 및 PDF 영수증
├─ shop/ # 상품, 장바구니, 결제, 쿠폰 및 리뷰
├─ templates/ # SSR 구현을 위한 HTML 템플릿
├─ static/ # CSS 및 정적 리소스
└─ media/

# 화면 예시

메인 대시보드(비인증 사용자): 현재 등록된 상품의 목록 및 회원가입 로그인

메인 대시보드(인증된 사용자): 현재 등록된 상품의 목록 및 내 정보(수정,영수증 등),
컨설팅 모드 토글 버튼, 장바구니, 로그아웃 , 거래내역

컨설팅 모드(스마트) 쇼핑: 예산 내 추천 상품 목록을 보여줌으로 사용자의 편의성 강조

디지털 영수증: 상품 구매 후 내정보란 영수증 탭에서 발급된 PDF 영수증 미리보기

# 🌍 배포 주소

<https://project2-team2.onrender.com/shop/>

# ## 📌 프로젝트 성격

본 프로젝트는 학습 및 포트폴리오 목적의 MVP 구현 버전입니다.  
운영 환경 수준의 확장 기능 및 고급 보안 기능은 포함하지 않습니다.

# 📄 라이선스

본 프로젝트는 개인 학습 및 포트폴리오 용도로 제작되었습니다.

---
