from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Case, When, Value, DecimalField, Q
from django.db.models.functions import TruncMonth
from django.views.generic import ListView
from django.utils import timezone  # (지금 코드에선 안 쓰면 제거해도 됨)

from account.models import Account
from ..models import Transaction, Category  # ⭐ * 대신 필요한 것만 명시
from ..utils.tx_summary import parse_month_range, aggregate_in_out


class TransactionHistoryView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "shop/transaction_list.html"
    context_object_name = "transactions"

    # ✅ tx_type 호환(데이터가 IN/OUT 이든 income/buy 든 모두 대응)
    IN_TYPES = ["IN", "income"]
    OUT_TYPES = ["OUT", "buy"]

    def get_queryset(self):
        qs = Transaction.objects.filter(user=self.request.user).order_by("-occurred_at")

        tab = self.request.GET.get("tab", "in")  # 템플릿 탭과 동일

        # ✅ 템플릿 탭 기준으로 DB tx_type 매핑 (호환)
        if tab == "in":
            qs = qs.filter(tx_type__in=self.IN_TYPES)
        elif tab == "out":
            qs = qs.filter(tx_type__in=self.OUT_TYPES)
        # summary는 리스트가 아니라 요약이므로, 목록은 기본 qs 유지해도 됨.

        # ✅ 공통 필터
        start_date = self.request.GET.get("start_date") or ""
        end_date = self.request.GET.get("end_date") or ""
        category = self.request.GET.get("category") or ""
        account = self.request.GET.get("account") or ""
        discounted = self.request.GET.get("discounted") or ""

        if start_date:
            qs = qs.filter(occurred_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(occurred_at__date__lte=end_date)
        if category:
            qs = qs.filter(category_id=category)
        if account:
            qs = qs.filter(account_id=account)

        if discounted == "1":
            qs = qs.filter(Q(used_coupon=True) | Q(discount_amount__gt=0))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tab = self.request.GET.get("tab", "in")
        context["active_tab"] = tab

        # ✅ 템플릿이 쓰는 공통 키
        context["categories"] = Category.objects.all()
        context["accounts"] = Account.objects.filter(user=self.request.user)

        context["start_date"] = self.request.GET.get("start_date") or ""
        context["end_date"] = self.request.GET.get("end_date") or ""
        context["selected_account"] = self.request.GET.get("account") or ""
        context["selected_category"] = self.request.GET.get("category") or ""
        context["discounted"] = self.request.GET.get("discounted") or ""

        # =========================
        # ✅ summary 탭(요약/통계)
        # =========================
        if tab == "summary":
            sum_start = self.request.GET.get("sum_start") or ""
            sum_end = self.request.GET.get("sum_end") or ""
            sum_category = self.request.GET.get("sum_category") or ""

            chart_tab = self.request.GET.get("chart_tab", "monthly")
            context["chart_tab"] = chart_tab

            reset = (self.request.GET.get("reset") == "1")
            if reset:
                # ✅ 입력칸은 빈칸으로 보여주기
                sum_start, sum_end, sum_category = "", "", ""

            context["sum_start"] = sum_start
            context["sum_end"] = sum_end
            context["sum_category"] = sum_category

            # ✅ base: 기본은 전체기간
            base = Transaction.objects.filter(user=self.request.user)

            # ✅ 월 범위가 둘 다 있을 때만 기간 필터 적용
            if sum_start and sum_end:
                start, end = parse_month_range(sum_start, sum_end)
                base = base.filter(
                    occurred_at__date__gte=start,
                    occurred_at__date__lt=end,
                )

            # ✅ 요약 숫자 (전체기간 / 기간필터 공통)
            total_in, total_out = aggregate_in_out(base, self.IN_TYPES, self.OUT_TYPES)
            context["total_in"] = total_in
            context["total_out"] = total_out
            context["net_total"] = total_in - total_out
            context["has_summary_data"] = (total_in != 0 or total_out != 0)

            # =========================================================
            # ✅ 그래프 데이터 (HTML은 txCategoryChart만 제대로 렌더하는 구조)
            #    → View가 chart_tab에 따라 cat_chart_labels/values를 "맞춰서" 공급
            # =========================================================
            if chart_tab == "monthly":
                # ✅ 월별(월단위)로 단일 시리즈를 만들어 txCategoryChart로 출력되게 함
                # (HTML/JS 수정 없이 그래프가 나오게 하는 View-only 우회 방식)
                monthly = (
                    base.annotate(m=TruncMonth("occurred_at"))
                    .values("m")
                    .annotate(
                        income=Sum(
                            Case(
                                When(tx_type__in=self.IN_TYPES, then="amount"),
                                default=Value(0),
                                output_field=DecimalField(),
                            )
                        ),
                        expense=Sum(
                            Case(
                                When(tx_type__in=self.OUT_TYPES, then="amount"),
                                default=Value(0),
                                output_field=DecimalField(),
                            )
                        ),
                    )
                    .order_by("m")
                )

                labels = []
                values = []

                for row in monthly:
                    if not row["m"]:
                        continue
                    labels.append(row["m"].strftime("%Y-%m"))

                    # ✅ 단일 시리즈 선택:
                    # 1) 월별 지출만 보여주고 싶으면 아래로 교체:
                    # v = row["expense"] or 0
                    # 2) 월별 순이익(수익-지출)
                    v = (row["income"] or 0) - (row["expense"] or 0)

                    values.append(str(v))

                context["has_category_data"] = len(labels) > 0
                context["cat_chart_labels"] = "|".join(labels)
                context["cat_chart_values"] = "|".join(values)

            else:
                # ✅ 카테고리별 지출 통계(기존 의도 유지)
                if sum_category:
                    base_for_cat = base.filter(tx_type__in=self.OUT_TYPES, category_id=sum_category)
                else:
                    base_for_cat = base.filter(tx_type__in=self.OUT_TYPES)

                by_cat = (
                    base_for_cat.values("category__name")
                    .annotate(total=Sum("amount"))
                    .order_by("-total")
                )

                labels = []
                values = []
                for row in by_cat:
                    labels.append(row["category__name"] or "미분류")
                    values.append(str(row["total"] or 0))

                context["has_category_data"] = len(labels) > 0
                context["cat_chart_labels"] = "|".join(labels)
                context["cat_chart_values"] = "|".join(values)

        return context
