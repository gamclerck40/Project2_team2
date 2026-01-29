from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator

class Account(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accounts")
    
    name = models.CharField(max_length=50)  # a_name -> name
    bank_name = models.CharField(max_length=50)
    account_number = models.CharField(max_length=50)  # 원본 저장
    balance = models.DecimalField(max_digits=14, decimal_places=0, default=0)  # 원 단위 정수처럼 사용
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def masked_account_number(self) -> str:
        # 예: 110-****-1234 (형식이 다양할 수 있으니 단순 규칙)
        s = self.account_number or ""
        if len(s) <= 4:
            return "****"
        return "****-" + s[-4:]

    def __str__(self):
        return f"{self.name} ({self.bank_name}) {self.masked_account_number()}"


class Category(models.Model):
    IN = "IN"
    OUT = "OUT"
    BOTH = "BOTH"
    TYPE_CHOICES = [(IN, "수입"), (OUT, "지출"), (BOTH, "공통")]

    name = models.CharField(max_length=200, unique=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=BOTH)
    # (선택) user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Transaction(models.Model):
    IN = "IN"
    OUT = "OUT"
    TX_TYPE_CHOICES = [(IN, "입금"), (OUT, "출금")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="transactions")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)

    tx_type = models.CharField(max_length=3, choices=TX_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=0, validators=[MinValueValidator(1)])
    occurred_at = models.DateTimeField()

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
        return f"{self.user} {self.tx_type} {self.amount} @ {self.occurred_at}"