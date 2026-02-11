from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.models import Account, Address, Bank
from account.utils.common import get_default_account, set_default_account
from shop.models import Transaction


User = get_user_model()


class AccountModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pass12345")
        self.bank = Bank.objects.create(
            name="테스트은행",
            min_len=10,
            max_len=14,
            prefixes_csv="351,352",
        )

    def test_account_save_strips_non_digits(self):
        acc = Account.objects.create(
            user=self.user,
            name="홍길동",
            phone="01012345678",
            bank=self.bank,
            account_number="351-12-3456-7890",
            balance=0,
            is_default=True,
        )
        acc.refresh_from_db()
        self.assertEqual(acc.account_number, "3511234567890")

    def test_masked_account_number_last4(self):
        acc = Account.objects.create(
            user=self.user,
            name="홍길동",
            phone="01012345678",
            bank=self.bank,
            account_number="3511234567890",
            balance=0,
        )
        self.assertEqual(acc.masked_account_number(), "****7890")

    def test_unique_constraint_bank_account_number_global(self):
        Account.objects.create(
            user=self.user,
            name="홍길동",
            phone="01012345678",
            bank=self.bank,
            account_number="3511234567890",
        )
        other = User.objects.create_user(username="u2", password="pass12345")
        with self.assertRaises(IntegrityError):
            Account.objects.create(
                user=other,
                name="김철수",
                phone="01099998888",
                bank=self.bank,
                account_number="351-123-456-7890",  # save()에서 숫자만 남긴 뒤 중복
            )

    def test_phone_number_alignment(self):
        acc = Account.objects.create(
            user=self.user,
            name="홍길동",
            phone="01012345678",
            bank=self.bank,
            account_number="3511234567890",
        )
        self.assertEqual(acc.phone_number_alignment(), "010-1234-5678")


class AccountUtilsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pass12345")
        self.bank = Bank.objects.create(name="테스트은행", min_len=1, max_len=50, prefixes_csv="")

    def test_get_default_account_returns_default(self):
        a1 = Account.objects.create(
            user=self.user,
            name="a1",
            phone="01012345678",
            bank=self.bank,
            account_number="1111",
            is_default=False,
        )
        a2 = Account.objects.create(
            user=self.user,
            name="a2",
            phone="01012345679",
            bank=self.bank,
            account_number="2222",
            is_default=True,
        )
        self.assertEqual(get_default_account(self.user).id, a2.id)

    def test_get_default_account_creates_one_if_none(self):
        acc = get_default_account(self.user)
        self.assertIsNotNone(acc)
        self.assertTrue(acc.is_default)
        self.assertEqual(acc.user, self.user)

    def test_set_default_account_switches_flag_only(self):
        a1 = Account.objects.create(
            user=self.user,
            name="a1",
            phone="01012345678",
            bank=self.bank,
            account_number="1111",
            balance=Decimal("1000"),
            is_default=True,
        )
        a2 = Account.objects.create(
            user=self.user,
            name="a2",
            phone="01012345679",
            bank=self.bank,
            account_number="2222",
            balance=Decimal("2000"),
            is_default=False,
        )
        set_default_account(self.user, a2.id)
        a1.refresh_from_db()
        a2.refresh_from_db()
        self.assertFalse(a1.is_default)
        self.assertTrue(a2.is_default)
        # 잔액 이관을 하지 않는 정책
        self.assertEqual(a1.balance, Decimal("1000"))
        self.assertEqual(a2.balance, Decimal("2000"))


class AccountSignupViewTests(TestCase):
    def setUp(self):
        self.bank = Bank.objects.create(
            name="테스트은행",
            min_len=10,
            max_len=14,
            prefixes_csv="351",
        )

    def test_signup_creates_user_account_address_and_init_transaction(self):
        url = reverse("account_signup")
        payload = {
            "username": "newuser",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
            "name": "홍길동",
            "phone": "01012345678",
            "bank": str(self.bank.id),
            "account_number": "351-1234-5678",
            "balance": "5000",
            "zip_code": "12345",
            "address": "서울시 강남구",
            "detail_address": "101동 101호",
        }
        resp = self.client.post(url, payload, follow=False)
        # 성공 시 product_list로 redirect
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("product_list"))

        user = User.objects.get(username="newuser")
        acc = Account.objects.get(user=user)
        self.assertTrue(acc.is_default)
        self.assertEqual(acc.balance, Decimal("5000"))
        self.assertEqual(acc.account_number, "35112345678")

        addr = Address.objects.get(user=user)
        self.assertTrue(addr.is_default)
        self.assertEqual(addr.zip_code, "12345")

        # 회원가입 초기 충전은 IN 거래로 기록
        tx = Transaction.objects.get(user=user, tx_type=Transaction.IN)
        self.assertEqual(tx.amount, Decimal("5000"))
        self.assertEqual(tx.product_name, "회원가입 충전")


class TransactionValidationTests(TestCase):
    def setUp(self):
        self.bank = Bank.objects.create(name="테스트은행", min_len=1, max_len=50, prefixes_csv="")
        self.u1 = User.objects.create_user(username="u1", password="pass12345")
        self.u2 = User.objects.create_user(username="u2", password="pass12345")
        self.a1 = Account.objects.create(
            user=self.u1,
            name="a1",
            phone="01012345678",
            bank=self.bank,
            account_number="1111",
            is_default=True,
        )

    def test_transaction_clean_prevents_other_users_account(self):
        tx = Transaction(
            user=self.u2,
            account=self.a1,
            tx_type=Transaction.IN,
            amount=Decimal("100"),
            occurred_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            tx.full_clean()
