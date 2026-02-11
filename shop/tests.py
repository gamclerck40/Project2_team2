from __future__ import annotations

import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from account.models import Account, Address, Bank
from shop.models import Cart, Category, Coupon, Product, Transaction, UserCoupon


User = get_user_model()


def _make_test_image(name: str = "test.png") -> SimpleUploadedFile:
    """Create a tiny valid PNG for ImageField tests."""
    try:
        from PIL import Image
    except Exception:
        # Pillow가 없는 환경을 대비: 최소 PNG 헤더(유효하지 않을 수 있음)
        return SimpleUploadedFile(name, b"\x89PNG\r\n\x1a\n", content_type="image/png")

    buf = BytesIO()
    Image.new("RGB", (1, 1)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ShopViewsAndModelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="buyer", password="pass12345")

        self.bank = Bank.objects.create(name="테스트은행", min_len=1, max_len=50, prefixes_csv="")
        self.account = Account.objects.create(
            user=self.user,
            name="구매자",
            phone="01012345678",
            bank=self.bank,
            account_number="1111",
            balance=Decimal("100000"),
            is_default=True,
        )
        self.address = Address.objects.create(
            user=self.user,
            zip_code="12345",
            address="서울시 강남구",
            detail_address="101동 101호",
            is_default=True,
            receiver_name="홍길동",
        )

        self.category = Category.objects.create(name="식료품")
        self.product = Product.objects.create(
            category=self.category,
            name="테스트상품",
            price=Decimal("10000"),
            description="desc",
            stock=10,
            image1=_make_test_image(),
        )

    def test_product_list_view_works(self):
        resp = self.client.get(reverse("product_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "테스트상품")

    def test_add_to_cart_requires_login(self):
        resp = self.client.post(reverse("add_to_cart", args=[self.product.id]), {"quantity": 1})
        self.assertEqual(resp.status_code, 302)
        # LoginView의 url name은 account.urls에서 'login'
        self.assertIn(reverse("login"), resp["Location"])

    def test_add_to_cart_increments_quantity(self):
        self.client.login(username="buyer", password="pass12345")
        url = reverse("add_to_cart", args=[self.product.id])
        self.client.post(url, {"quantity": 2})
        self.client.post(url, {"quantity": 3})
        item = Cart.objects.get(user=self.user, product=self.product)
        self.assertEqual(item.quantity, 5)

    def test_add_to_cart_blocks_over_stock(self):
        self.client.login(username="buyer", password="pass12345")
        url = reverse("add_to_cart", args=[self.product.id])
        # 첫 담기 9개
        self.client.post(url, {"quantity": 9})
        # 추가 2개는 재고(10) 초과
        resp = self.client.post(url, {"quantity": 2})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("cart_list"))
        item = Cart.objects.get(user=self.user, product=self.product)
        self.assertEqual(item.quantity, 9)

    def test_order_execution_applies_coupon_deducts_balance_creates_transactions(self):
        self.client.login(username="buyer", password="pass12345")
        # 장바구니에 2개 담기
        Cart.objects.create(user=self.user, product=self.product, quantity=2)

        # 10% 할인 쿠폰 (최소금액 0, 최대할인 없음)
        coupon = Coupon.objects.create(
            name="10퍼",
            code="tenoff",
            discount_type="percentage",
            discount_value=10,
            min_purchase_amount=0,
            max_discount_amount=None,
            valid_from=timezone.now() - timedelta(days=1),
            valid_to=timezone.now() + timedelta(days=30),
            active=True,
        )
        user_coupon = UserCoupon.objects.create(user=self.user, coupon=coupon, is_used=False)

        # 총액 20000, 할인 2000, 최종 18000
        resp = self.client.post(
            reverse("order_execute"),
            {
                "selected_account_id": str(self.account.id),
                "address_id": str(self.address.id),
                "coupon_id": str(user_coupon.id),
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("mypage"))

        # 잔액 차감(한 번만)
        self.account.refresh_from_db()
        self.assertEqual(self.account.balance, Decimal("100000") - Decimal("18000"))

        # 재고 차감
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

        # 쿠폰 사용 처리
        user_coupon.refresh_from_db()
        self.assertTrue(user_coupon.is_used)
        self.assertIsNotNone(user_coupon.used_at)

        # 장바구니 비움
        self.assertFalse(Cart.objects.filter(user=self.user).exists())

        # 거래내역 생성 (장바구니에 상품이 1종이므로 1건)
        txs = Transaction.objects.filter(user=self.user, tx_type=Transaction.OUT)
        self.assertEqual(txs.count(), 1)
        tx = txs.first()
        self.assertEqual(tx.total_price_at_pay, Decimal("20000"))
        self.assertEqual(tx.discount_amount, Decimal("2000"))
        self.assertEqual(tx.amount, Decimal("18000"))
        self.assertEqual(tx.used_coupon_id, user_coupon.id)

    def test_coupon_code_is_uppercased_on_save(self):
        c = Coupon.objects.create(
            name="welcome",
            code="welcome2026",
            discount_type="amount",
            discount_value=1000,
            min_purchase_amount=0,
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=10),
            active=True,
        )
        c.refresh_from_db()
        self.assertEqual(c.code, "WELCOME2026")
