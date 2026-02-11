from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, DecimalField, Sum, Value, When, Q
from django.db.models.functions import TruncMonth
from django.views.generic import ListView

from account.models import Account
from shop.models import Category, Transaction
from shop.utils.tx_summary import (
    aggregate_in_out,
    month_start,
    next_month_start,
    parse_month_range,
)



class TransactionHistoryView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "shop/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 10   # ✅ 추가: 페이지당 10개 (원하면 20 등으로 변경)

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

        context["categories"] = Category.objects.all()
        context["accounts"] = Account.objects.filter(user=self.request.user)

        context["start_date"] = self.request.GET.get("start_date") or ""
        context["end_date"] = self.request.GET.get("end_date") or ""
        context["selected_account"] = self.request.GET.get("account") or ""
        context["selected_category"] = self.request.GET.get("category") or ""
        context["discounted"] = self.request.GET.get("discounted") or ""

        if tab == "summary":
            sum_start = self.request.GET.get("sum_start") or ""
            sum_end = self.request.GET.get("sum_end") or ""
            sum_category = self.request.GET.get("sum_category") or ""

            chart_tab = self.request.GET.get("chart_tab", "monthly")
            context["chart_tab"] = chart_tab

            reset = (self.request.GET.get("reset") == "1")
            if reset:
                sum_start, sum_end, sum_category = "", "", ""

            context["sum_start"] = sum_start
            context["sum_end"] = sum_end
            context["sum_category"] = sum_category

            base = Transaction.objects.filter(user=self.request.user)

            # ✅ 열린 구간 필터링: 시작만/끝만/둘 다
            if sum_start and sum_end:
                start, end = parse_month_range(sum_start, sum_end)
                base = base.filter(occurred_at__date__gte=start, occurred_at__date__lt=end)

            elif sum_start and not sum_end:
                # 시작월부터 "현재"까지 (열린 끝)
                start = month_start(sum_start)
                base = base.filter(occurred_at__date__gte=start)

            elif sum_end and not sum_start:
                # "최초 거래"부터 끝월까지 (열린 시작)
                end = next_month_start(sum_end)
                base = base.filter(occurred_at__date__lt=end)            

            # ✅ 요약 수치
            total_in, total_out = aggregate_in_out(base, self.IN_TYPES, self.OUT_TYPES)
            context["total_in"] = total_in
            context["total_out"] = total_out
            context["net_total"] = total_in - total_out
            context["has_summary_data"] = (total_in != 0 or total_out != 0)

            # =========================
            # ✅ 그래프 데이터
            # =========================
            if chart_tab == "monthly":
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

                labels, ins, outs = [], [], []
                for row in monthly:
                    if not row["m"]:
                        continue
                    labels.append(row["m"].strftime("%Y-%m"))
                    ins.append(str(row["income"] or 0))
                    outs.append(str(row["expense"] or 0))

                # ✅ 템플릿(txMonthlyChart)이 기대하는 키로 넣기
                context["chart_labels"] = "|".join(labels)
                context["chart_in"] = "|".join(ins)
                context["chart_out"] = "|".join(outs)

            else:
                # 카테고리별 지출 통계 (기존 유지)
                base_for_cat = base.filter(tx_type__in=self.OUT_TYPES)
                if sum_category:
                    base_for_cat = base_for_cat.filter(category_id=sum_category)

                by_cat = (
                    base_for_cat.values("category__name")
                    .annotate(total=Sum("amount"))
                    .order_by("-total")
                )

                labels, values = [], []
                for row in by_cat:
                    labels.append(row["category__name"] or "미분류")
                    values.append(str(row["total"] or 0))

                context["has_category_data"] = len(labels) > 0
                context["cat_chart_labels"] = "|".join(labels)
                context["cat_chart_values"] = "|".join(values)

        return context
