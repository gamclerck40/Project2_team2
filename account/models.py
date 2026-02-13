import re
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
# Create your models here.
class Bank(models.Model):
    name = models.CharField(max_length=50, unique=True)  # 예: 국민은행
    min_len = models.PositiveSmallIntegerField()
    max_len = models.PositiveSmallIntegerField()
    prefixes_csv = models.CharField(max_length=200, blank=True, default="")  
    # 예: "351,352,356"

    def prefixes(self):
        return [p.strip() for p in (self.prefixes_csv or "").split(",") if p.strip()]

    def __str__(self):
        return self.name


class Account(models.Model):
    # 해당 함수에 대해서는 더 공부가 필요함.
    # USER는 대체 왜 쓰는가? -> User는 단순히 데이터를 다르게 저장하기 위한 객체가 아니라, 서비스 내에서 정체성·소유권·권한·행위의 기준점 역할을 한다.
    # User는 ‘데이터를 담는 객체’가 아니라 ‘모든 데이터가 연결되는 중심 좌표’다.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accounts"
    )
    # "사용자 이름" >>
    name = models.CharField(max_length=50)
    # a_name -> name
    phone = models.CharField(max_length=11)
    bank = models.ForeignKey(Bank, on_delete=models.PROTECT, related_name="accounts")
    # masked_account_number >> 로 마스킹을 하고 원본 데이터만 저장.
    account_number = models.CharField(max_length=50)

    # 잔액(충전 방식으로 해당 앱에서 구매할 때 적용되도록)
    balance = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    # 원 단위 정수처럼 사용

    # 아직 잘 해석이 안됨.
    is_active = models.BooleanField(default=True)

    # (추천) 결제에 사용할 기본 계좌 개념이 필요하면 추가
    is_default = models.BooleanField(default=False)

    # 생성시 생성 당일 날짜에 맞게 DB에 저장.
    created_at = models.DateTimeField(auto_now_add=True)

    # "내 정보 수정" 따위의 기능을 넣을 때 수정 날짜가 저장 되도록.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # “같은 은행 + 같은 계좌번호”는 딱 1번만 존재 가능 (유저가 누구든)
            models.UniqueConstraint(
                fields=["bank", "account_number"],
                name="uniq_bank_account_number",
            ),
        ]
        
    def save(self, *args, **kwargs):
        # 계좌번호는 DB에 숫자만 저장 (중복판정 정확도 ↑)
        self.account_number = re.sub(r"[^0-9]", "", self.account_number or "")
        super().save(*args, **kwargs)

    def masked_account_number(self) -> str:
        s = re.sub(r"[^0-9]", "", self.account_number or "")
        if len(s) <= 4:
            return "****"
        return "****" + s[-4:]

    def phone_number_alignment(self) -> str:
        p = self.phone or ""
        if len(p) == 11:
            return p[:3] + "-" + p[3:7] + "-" + p[7:]

    def __str__(self):
        return f"{self.name} ({self.bank}) {self.masked_account_number()}|{self.phone_number_alignment()} "


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    alias = models.CharField(max_length=20,default="기본 배송지")
    zip_code = models.CharField(max_length=10)        # 우편번호
    address = models.CharField(max_length=255)         # 기본 주소
    detail_address = models.CharField(max_length=255)  # 상세 주소
    is_default = models.BooleanField(default=False)     # 기본 배송지 여부
    created_at = models.DateTimeField(auto_now_add=True)
    receiver_name = models.CharField(max_length=20, blank=True, null=True, verbose_name="수령인")    

    def __str__(self):
        return f"[{self.zip_code}] {self.address}"