from account.utils.setdefault import get_default_account

def inject_account(request):
    if request.user.is_authenticated:
        return {"account": get_default_account(request.user)}
    return {"account": None}
