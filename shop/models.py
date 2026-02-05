import re
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from account.models import Account

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # **무결성 핵심: 거래 user와 계좌 user 일치 강제**
        if self.account_id and self.user_id and self.account.user_id != self.user_id:
            from django.core.exceptions import ValidationError

            raise ValidationError("본인 계좌로만 거래를 생성할 수 있습니다.")

    def __str__(self):
        # 영수증처럼 보이도록 수량 정보도 포함
        product_name = self.product.name if self.product else "삭제된 상품"
        return f"{self.user} | {product_name}({self.quantity}개) | {self.tx_type} {self.amount}원"


# 현재 이 상태에서 product(Product FK), quantity(주문량)등의 정보가 더 필요할 것.
