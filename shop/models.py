import re
from django.conf import settings
from django.core.validators import MinValueValidator,MaxValueValidator
from django.db import models
from account.models import Account
import uuid
import os
from django.utils import timezone

# 회원가입 간 입력할 대부분의 정보
class Category(models.Model):
    # IN = "IN"
    # OUT = "OUT"
    # BOTH = "BOTH"

    # 이런 방식의 저장은 DB에서 "IN / OUT / BOTH" 형태로 저장됨
    # Admin이나 Form에서는 "수입 / 지출 / 공통" 으로 표시됨.
    # TYPE_CHOICES = [(IN, "수입"), (OUT, "지출"), (BOTH, "공통")]

    # 가전제품, 식료품, 청소용품 따위 등.
    name = models.CharField(max_length=200, unique=True)

    # TYPE_CHOICES를 읽어와 'choices' 기능으로 "IN / OUT / BOTH" 중 하나만 선택하게 강제함.
    # ModelForm/ 관리자에서 드롭다운으로 자동 표시됨
    # type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=BOTH)

    # (선택) user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    def __str__(self):
        return self.name

def product_image_upload_to(instance, filename):
    return f"products/{instance.pk}/{filename}"

def product_detail_image_upload_to(instance, filename):
    return f"products/desc/{instance.pk}/{filename}"

class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=120)
    price = models.DecimalField(
        max_digits=14, decimal_places=0, validators=[MinValueValidator(1)]
    )
    description = models.TextField(blank=True)
    stock = models.PositiveIntegerField(default=0)
    # 어드민에서 이미지를 추가 할 수 있게 해줌,png,jpg,jpeg,gif,webp,tiff,bmp 등 bmp는 비추천 용량 이슈 pdf,mp4는 불가능
    image1 = models.ImageField(upload_to=product_image_upload_to, help_text="대표 이미지 (필수)")
    image2 = models.ImageField(upload_to=product_image_upload_to, blank=True, null=True)
    image3 = models.ImageField(upload_to=product_image_upload_to, blank=True, null=True)
    image4 = models.ImageField(upload_to=product_image_upload_to, blank=True, null=True)
    image5 = models.ImageField(upload_to=product_image_upload_to, blank=True, null=True)

    # --- [하단 상세 설명용 데이터] ---
    description_text1 = models.TextField(blank=True, help_text="상세 설명 첫 번째 문단")
    description_image1 = models.ImageField(
        upload_to=product_detail_image_upload_to, blank=True, null=True
    )
    description_text2 = models.TextField(blank=True, help_text="상세 설명 두 번째 문단")
    description_image2 = models.ImageField(
        upload_to=product_detail_image_upload_to, blank=True, null=True
    )

    def __str__(self):
        return self.name


class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # 유저 한명이 여러개의 사품을 담을 수 있게

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    # 상품 정보 DB를 연결 받아 가져옴

    quantity = models.PositiveIntegerField(default=1)
    # 상품을 담은 갯수 양수 1부터 음수 (-1)는 들어갈수없음

    added_at = models.DateTimeField(auto_now_add=True)
    # 언제 담았는지 장바구니 생성시 생성 날짜를 적어줌

    def total_price(self):
        # 상품 개당 가격 * 장바구니 수량 곱해서 반환
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.user.username}의 장바구니 - {self.product.name}"


# MyPage 내 정보 확인에서 접속하는 거래내역, 계좌정보 확인 등
class Transaction(models.Model):
    # 계좌 선택 -> 원하는 금액만큼 Account.balance 추가.
    # 보여주기식으로 구현하는것을 목표로.
    IN = "IN"
    OUT = "OUT"
    TX_TYPE_CHOICES = [(IN, "입금"), (OUT, "출금")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions"
    )
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="transactions"
    )

    # on_delete=CASCADE -> 부모-자식 모두 삭제됨, models.SET_NULL -> 부모가 삭제되지만, 자식은 남기되 FK값은 NULL로 변경.
    # Category 객체 하나가 삭제 되더라도, 거래 '기록' 그 자체는 남겨야 하기 때문에 CASCADE를 쓰지 않음.
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL
    )
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL
    )

    # 💡 [에이스님 추가분] 구매 수량을 기록하는 테이블 역할 필드
    quantity = models.PositiveIntegerField(default=1, verbose_name="구매 수량")
    product_name = models.CharField(
        max_length=200, null=True, blank=True, verbose_name="결제시 상품명"
    )  # TX_TYPE_CHOICES를 읽어와 "IN / OUT" 중 하나를 저장
    tx_type = models.CharField(max_length=3, choices=TX_TYPE_CHOICES)

    # 입금/거래량
    amount = models.DecimalField(
        max_digits=14, decimal_places=0, validators=[MinValueValidator(1)]
    )

    # 거래일(날짜/시간)
    occurred_at = models.DateTimeField()

    # 가맹점/거래처(선택)
    merchant = models.CharField(max_length=50, null=True, blank=True)
    memo = models.CharField(max_length=600, null=True, blank=True)

    # ✅ 영수증 탭에서만 "삭제"(숨김) 처리를 하기 위한 플래그
    # - 거래(Transaction) 기록은 남기되, 마이페이지 영수증 탭/영수증 PDF 접근만 차단하려면 True
    # - 실제 DB 삭제(delete())는 하지 않음
    receipt_hidden = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

        #주소 필드
    shipping_address = models.CharField(max_length=255, null=True, blank=True, verbose_name="배송지 주소")
    shipping_detail_address = models.CharField(max_length=255, null=True, blank=True, verbose_name="배송지 상세주소")
    shipping_zip_code = models.CharField(max_length=10, null=True, blank=True, verbose_name="우편번호")
    receiver_name = models.CharField(max_length=50, null=True, blank=True, verbose_name="수령인")

    total_price_at_pay = models.DecimalField(
        max_digits=14, decimal_places=0, default=0, verbose_name="할인 전 원가"
    )
    discount_amount = models.DecimalField(
        max_digits=14, decimal_places=0, default=0, verbose_name="할인 금액"
    )
    # 어떤 쿠폰을 썼는지 기록 (쿠폰이 삭제되어도 내역은 남도록 SET_NULL)
    used_coupon = models.ForeignKey(
        'UserCoupon', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="사용된 쿠폰"
    )

    def clean(self):
        # **무결성 핵심: 거래 user와 계좌 user 일치 강제**
        if self.account_id and self.user_id and self.account.user_id != self.user_id:
            from django.core.exceptions import ValidationError

            raise ValidationError("본인 계좌로만 거래를 생성할 수 있습니다.")

    def __str__(self):
        # 영수증처럼 보이도록 수량 정보도 포함
        product_name = self.product.name if self.product else "삭제된 상품"
        return f"{self.user} | {product_name}({self.quantity}개) | {self.tx_type} {self.amount}원"

class Review(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    # 별점 1~5점 제한
    rating = models.PositiveSmallIntegerField(
        default=5, 
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="평점"
    )
    content = models.TextField(verbose_name="리뷰 내용")

    # 리뷰에도 이미지를 넣고 싶다면 추가 (선택사항)
    # image = models.ImageField(upload_to="reviews/%Y/%m/%d/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # 한 사용자가 한 상품에 대해 리뷰를 하나만 남기게 제한하려면 활성화
        # unique_together = ('product', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}의 리뷰 - {self.product.name} ({self.rating}점)"
# 현재 이 상태에서 product(Product FK), quantity(주문량)등의 정보가 더 필요할 것.

def review_image_upload_to(instance, filename):
    # 1. 확장자 추출 (.jpg, .png 등)
    ext = filename.split('.')[-1]
    
    # 2. UUID를 사용해 무작위 파일명 생성
    # 이렇게 하면 파일명이 겹치지 않아 여러 장 업로드 시 덮어쓰기를 방지합니다.
    new_filename = f"{uuid.uuid4()}.{ext}"
    
    # 3. 리뷰 ID가 아직 없을 경우를 대비 (새로 생성 중일 때)
    review_id = instance.review.id if instance.review.id else "new_post"

    # ✅ 이 줄이 반드시 있어야 합니다! 실제 저장 경로를 반환합니다.
    return f"reviews/{review_id}/{new_filename}"

class ReviewImage(models.Model):
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(
        upload_to=review_image_upload_to,  # 수정된 함수 사용
        verbose_name="리뷰 이미지"
    )

    def __str__(self):
        # ID가 없을 때 에러 방지
        review_display = self.review.id if self.review.id else "생성 중"
        return f"{review_display}번 리뷰의 사진"

class Coupon(models.Model):
    # 쿠폰 종류: 정액 할인(원), 정률 할인(%)
    DISCOUNT_CHOICES = (
        ('amount', '정액 할인 (원)'),
        ('percentage', '정률 할인 (%)'),
    )

    name = models.CharField(max_length=50)  # 쿠폰 이름 (예: 신규가입 축하 쿠폰)
    code = models.CharField(max_length=20, unique=True) # 쿠폰 코드 (예: WELCOME2026)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_CHOICES, default='amount')
    discount_value = models.PositiveIntegerField() # 할인 금액 또는 할인율
    
    min_purchase_amount = models.PositiveIntegerField(default=0) # 최소 주문 금액 제한
    max_discount_amount = models.PositiveIntegerField(null=True, blank=True) # 정률 할인 시 최대 할인 금액 제한
    
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField()
    
    active = models.BooleanField(default=True) # 관리자가 쿠폰을 중단할 수 있게 함

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.code}] {self.name}"

class UserCoupon(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='my_coupons')
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.coupon.name}"

    # 쿠폰이 유효한지 확인하는 프로퍼티
    @property
    def is_valid(self):
        now = timezone.now()
        return not self.is_used and self.coupon.active and self.coupon.valid_from <= now <= self.coupon.valid_to