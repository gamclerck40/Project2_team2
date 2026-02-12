# “로그인한 사용자의 공통 데이터(예: 잔고)를
# 모든 템플릿에서 자동으로 쓸 수 있게 해주는 역할”
from account.utils.setdefault import get_default_account

def inject_account(request):
    if request.user.is_authenticated:
        return {"account": get_default_account(request.user)}
    return {"account": None}
