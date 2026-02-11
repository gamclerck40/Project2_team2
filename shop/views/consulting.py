from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.urls import reverse
from django.views.generic import *
from datetime import date
from ..models import *
from account.models import Account, Address
from decimal import Decimal  # ✅ Decimal*float 에러 방지용
# ✅ 다계좌(기본 계좌) 대응: 결제/체크아웃은 항상 기본 계좌를 사용
from account.utils.common import get_default_account
from django.db.models import Sum, Case, When, Value, DecimalField, Q
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from urllib.parse import urlencode


class ConsultingProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = "shop/product_consulting_list.html"
    context_object_name = "products"
    paginate_by = 8

    def _month_range(self):
        today = timezone.localdate()
        start = today.replace(day=1)
        return start, today

    def _to_decimal(self, v):
        if v is None:
            return Decimal("0")
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    def _calc_month_in(self, account=None):
        """이번 달 입금(IN) 합계
        - account가 주어지면 해당 계좌 기준
        - account가 None이면 ✅ 계좌 상관없이(전체) 기준
        """
        start, end = self._month_range()
        qs = Transaction.objects.filter(
            user=self.request.user,
            occurred_at__date__gte=start,
            occurred_at__date__lte=end,
        )
        if account is not None:
            qs = qs.filter(account=account)

        total_in = qs.filter(tx_type=Transaction.IN).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        return self._to_decimal(total_in).quantize(Decimal("1"))

    def _calc_month_out(self, account=None):
        """이번 달 출금(OUT) 합계
        - account가 주어지면 해당 계좌 기준
        - account가 None이면 ✅ 계좌 상관없이(전체) 기준
        """
        start, end = self._month_range()
        qs = Transaction.objects.filter(
            user=self.request.user,
            occurred_at__date__gte=start,
            occurred_at__date__lte=end,
        )
        if account is not None:
            qs = qs.filter(account=account)

        total_out = qs.filter(tx_type=Transaction.OUT).aggregate(s=Sum("amount"))["s"] or Decimal("0")
        return self._to_decimal(total_out).quantize(Decimal("1"))

    def _calc_total_in(self, account=None):
        """누적 입금(IN) 합계(가입 이후 전체)
        - account=None이면 ✅ 계좌 상관없이(전체)
        """
        qs = Transaction.objects.filter(user=self.request.user, tx_type=Transaction.IN)
        if account is not None:
            qs = qs.filter(account=account)

        total_in = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        return self._to_decimal(total_in).quantize(Decimal("1"))

    def _calc_total_out(self, account=None):
        """누적 출금(OUT) 합계: 가입 이후 전체
        - account=None이면 ✅ 계좌 상관없이(전체)
        """
        qs = Transaction.objects.filter(user=self.request.user, tx_type=Transaction.OUT)
        if account is not None:
            qs = qs.filter(account=account)

        total_out = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        return self._to_decimal(total_out).quantize(Decimal("1"))

    def _calc_asset_base(self, total_in, total_out):
        """✅ Runway+SWR 모델 계산용 자산(순자산)
        = 누적입금 - 누적출금 (0 미만은 0 처리)
        """
        total_in = self._to_decimal(total_in)
        total_out = self._to_decimal(total_out)
        net = total_in - total_out
        if net < 0:
            net = Decimal("0")
        return net.quantize(Decimal("1"))

    def _recommend_budget(self, asset_base, month_out):
        asset_base = self._to_decimal(asset_base)
        month_out = self._to_decimal(month_out)

        if asset_base <= 0:
            return Decimal("0")

        # 1) runway (months)
        denom = month_out if month_out > 0 else Decimal("1")
        runway = asset_base / denom

        # 2) base monthly safe spending rate (월 1%)
        base_rate = Decimal("0.01")

        # 3) risk multiplier by runway
        if runway >= Decimal("24"):
            mult = Decimal("1.6")
        elif runway >= Decimal("12"):
            mult = Decimal("1.2")
        elif runway >= Decimal("6"):
            mult = Decimal("0.9")
        else:
            mult = Decimal("0.6")

        budget = asset_base * base_rate * mult
        budget = min(budget, asset_base)

        return budget.quantize(Decimal("1"))

    def get_queryset(self):
        qs = Product.objects.all()

        q = (self.request.GET.get("search") or "").strip()
        category_id = self.request.GET.get("category")
        sort_option = self.request.GET.get("sort", "newest")

        if q:
            qs = qs.filter(name__icontains=q)
        if category_id:
            qs = qs.filter(category_id=category_id)

        # ✅ 예산 산정(모델 계산)은 "누적 순자산"을 기반으로,
        # ✅ 분모(소비속도)는 "이번 달 지출"로 유지하는 구성이 가장 자연스러움
        month_out = self._calc_month_out(account=None)
        total_in = self._calc_total_in(account=None)
        total_out = self._calc_total_out(account=None)
        asset_base = self._calc_asset_base(total_in, total_out)
        budget = self._recommend_budget(asset_base, month_out)

        qs = qs.filter(price__lte=budget)

        if sort_option == "price_low":
            qs = qs.order_by("price")
        elif sort_option == "price_high":
            qs = qs.order_by("-price")
        else:
            qs = qs.order_by("-id")

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all()

        # 월 라벨 ("N월")
        today = timezone.localdate()
        context["month_label"] = f"{today.month}월"

        # 기본계좌(표시용 유지)
        default_account = get_default_account(self.request.user)
        balance = self._to_decimal(default_account.balance if default_account else 0).quantize(Decimal("1"))
        context["default_account"] = default_account
        context["balance"] = balance

        # ✅ 이번 달 기준
        month_in = self._calc_month_in(account=None)
        month_out = self._calc_month_out(account=None)

        # ✅ 누적(전체) 기준
        total_in = self._calc_total_in(account=None)
        total_out = self._calc_total_out(account=None)

        # ✅ 모델 계산(예산/런웨이)용 자산: 누적 순자산
        asset_base = self._calc_asset_base(total_in, total_out)
        budget = self._recommend_budget(asset_base, month_out)

        # -----------------------------------------
        # ✅ 컨텍스트 키 구성 (기존 키 + 신규 키 공존)
        # -----------------------------------------

        # 1) 이번 달 표기용(신규)
        context["month_total_in"] = month_in
        context["month_total_out"] = month_out  # (이번 달 지출)

        # 2) 누적(전체) 표기용(신규)
        context["total_in_all"] = total_in
        context["total_out_all"] = total_out

        # 3) 기존 템플릿 호환용(유지)
        # - 기존에 current_asset을 "총 누적 수익"으로 쓰던 흐름을 깨지 않기 위해 유지
        context["current_asset"] = total_in

        # 추천 예산
        context["recommended_budget"] = budget

        # 런웨이 메시지 (누적 순자산 / 이번 달 지출)
        denom = month_out if month_out > 0 else Decimal("1")
        runway = asset_base / denom

        if runway >= Decimal("24"):
            context["consult_msg"] = "지출 속도 대비 자산 런웨이가 충분합니다. 기준 예산보다 한 단계 적극적으로 제안할게요."
        elif runway >= Decimal("12"):
            context["consult_msg"] = "런웨이가 안정 구간입니다. 무리 없는 범위에서 예산을 제안할게요."
        elif runway >= Decimal("6"):
            context["consult_msg"] = "지출 속도가 자산 대비 빠른 편입니다. 예산을 보수적으로 조정했어요."
        elif month_out == 0:
            context["consult_msg"] = "이번 달 지출이 없어 런웨이가 매우 깁니다. 예산은 자산 대비 보수적으로 제안했어요."
        else:
            context["consult_msg"] = "런웨이가 짧습니다. 당분간은 필수 소비 중심으로 예산을 강하게 제한하는 걸 권합니다."

        return context
