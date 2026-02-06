from django.db import migrations

def seed_banks(apps, schema_editor):
    Bank = apps.get_model("account", "Bank")

    banks = [
        {"name": "국민은행", "prefixes_csv": "", "min_len": 12, "max_len": 14},
        {"name": "신한은행", "prefixes_csv": "", "min_len": 11, "max_len": 13},
        {"name": "우리은행", "prefixes_csv": "", "min_len": 12, "max_len": 14},
        {"name": "하나은행", "prefixes_csv": "", "min_len": 12, "max_len": 14},
        {"name": "카카오뱅크", "prefixes_csv": "", "min_len": 12, "max_len": 14},
        {"name": "토스뱅크", "prefixes_csv": "", "min_len": 12, "max_len": 14},
        {"name": "농협", "prefixes_csv": "", "min_len": 11, "max_len": 13},
    ]

    for data in banks:
        Bank.objects.update_or_create(
            name=data["name"],
            defaults={
                "prefixes_csv": data["prefixes_csv"],
                "min_len": data["min_len"],
                "max_len": data["max_len"],
            },
        )

def unseed_banks(apps, schema_editor):
    Bank = apps.get_model("account", "Bank")
    names = ["국민은행", "신한은행", "우리은행", "하나은행", "카카오뱅크", "토스뱅크", "농협"]
    Bank.objects.filter(name__in=names).delete()

class Migration(migrations.Migration):

    dependencies = [
        ("account", "0003_account_is_default_alter_bank_prefixes_csv_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_banks, reverse_code=unseed_banks),
    ]