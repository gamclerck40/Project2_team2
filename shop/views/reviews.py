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


class ReviewCreateView(LoginRequiredMixin, View):
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)

        # 1. 구매 여부 확인
        OUT_TYPES = ["OUT", "buy"]

        has_purchased = Transaction.objects.filter(
            user=request.user,
            tx_type__in=OUT_TYPES,
        ).filter(
            Q(product=product) | Q(product_name=product.name)
        ).exists()

        if not has_purchased:
            messages.error(request, "해당 상품을 구매하신 분만 리뷰를 남길 수 있습니다.")
            return redirect("product_detail", pk=product.id)
        # 2. 리뷰 데이터 가져오기        
        rating = request.POST.get('rating')
        content = request.POST.get('content')

        # 3. 리뷰 본문 생성 (먼저 생성해야 review 객체의 ID가 생김)
        review = Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            content=content
        )

        # 4. 🔥 여러 장의 이미지 처리 (핵심 부분)
        # request.FILES.getlist를 사용하여 선택된 모든 파일을 리스트로 가져옵니다.
        images = request.FILES.getlist('review_images') 

        for img in images:
        # 파일이 실제로 존재할 때만(빈 칸이 아닐 때만) 저장
            if img:
                ReviewImage.objects.create(review=review, image=img)
        messages.success(request, "리뷰가 성공적으로 등록되었습니다.")
        return redirect("product_detail", pk=product.id)

class ReviewDeleteView(LoginRequiredMixin, View):
    def post(self, request, review_id):
        # 1. 내 리뷰인지 확인하며 가져오기 (보안)
        review = get_object_or_404(Review, id=review_id, user=request.user)
        product_id = review.product.id

        # 2. 삭제 처리
        review.delete()

        # 3. 메시지 남기기
        messages.success(request, "리뷰가 성공적으로 삭제되었습니다.")

        # 4. 상품 상세 페이지의 '리뷰 섹션' 위치로 바로 이동하도록 주소 생성
        # 결과 예시: /shop/products/5/#review-section
        return redirect(reverse('product_detail', kwargs={'pk': product_id}) + '#review-section')

class ReviewUpdateView(LoginRequiredMixin, View):
    def post(self, request, review_id):
        # 1. 내 리뷰인지 확인하며 가져오기 (보안)
        review = get_object_or_404(Review, id=review_id, user=request.user)
        product_id = review.product.id

        # 2. 수정 데이터 가져오기
        content = request.POST.get("content")
        rating = request.POST.get("rating")

        # ✅ 추가된 데이터: 삭제할 이미지 ID 리스트와 새로 등록할 파일들
        delete_image_ids = request.POST.getlist("delete_images")
        new_images = request.FILES.getlist("review_images")

        # 3. 데이터 업데이트 및 저장
        if content and rating:
            review.content = content
            review.rating = int(rating)
            review.save()

            # ✅ [추가] 이미지 삭제 로직
            if delete_image_ids:
                # 선택된 이미지들을 찾아서 한꺼번에 삭제
                # (이때 review.images는 ReviewImage 모델과의 관계 이름입니다)
                review.images.filter(id__in=delete_image_ids).delete()

            # ✅ [추가] 새 이미지 저장 로직
            for img in new_images:
                # ReviewImage 모델을 사용하여 새 객체 생성
                # (모델명이 다를 경우 본인의 모델명에 맞게 수정하세요)
                ReviewImage.objects.create(review=review, image=img)            
            messages.success(request, "리뷰가 성공적으로 수정되었습니다.")
        else:
            messages.error(request, "내용과 평점을 모두 입력해주세요.")

        # 4. 상세 페이지의 리뷰 섹션으로 다시 리다이렉트
        return redirect(reverse('product_detail', kwargs={'pk': product_id}) + '#review-section')
