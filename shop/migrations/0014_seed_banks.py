# shop/migrations/000Y_seed_banks.py
from django.db import migrations

def seed_banks(apps, schema_editor):
    Bank = apps.get_model("shop", "Bank")

    banks = [
        # name, min_len, max_len, prefixes_csv
        ("국민은행", 12, 14, ""),
        ("신한은행", 11, 12, ""),
        ("우리은행", 11, 14, ""),
        ("하나은행", 12, 14, ""),
        ("농협은행", 13, 13, "351,352,356"),
        ("기업은행", 10, 14, ""),
        ("우체국", 12, 13, ""),
        ("산업은행", 11, 15, ""),
    ]

    for name, mn, mx, pre in banks:
        Bank.objects.get_or_create(
            name=name,
            defaults={"min_len": mn, "max_len": mx, "prefixes_csv": pre}
        )

def unseed_banks(apps, schema_editor):
    Bank = apps.get_model("shop", "Bank")
    Bank.objects.filter(
        name__in=["국민은행","신한은행","우리은행","하나은행","농협은행","기업은행","우체국","산업은행"]
    ).delete()

class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0013_bank_remove_account_bank_name_account_bank"),  # ← 여기 X는 실제 파일에 맞춰 수정
    ]

    operations = [
        migrations.RunPython(seed_banks, reverse_code=unseed_banks),
    ]