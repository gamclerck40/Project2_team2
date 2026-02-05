from django.db import migrations

def seed_banks(apps, schema_editor):
    Bank = apps.get_model("account", "Bank")

    banks = [
        {"name": "국민은행", "prefixes_csv": "110, 111", "min_len": 12, "max_len": 14},
        {"name": "신한은행", "prefixes_csv": "101, 102", "min_len": 11, "max_len": 13},
        {"name": "우리은행", "prefixes_csv": "1002, 1005", "min_len": 12, "max_len": 14},
        {"name": "하나은행", "prefixes_csv": "356, 357", "min_len": 12, "max_len": 14},
        {"name": "카카오뱅크", "prefixes_csv": "3333", "min_len": 12, "max_len": 14},
        {"name": "토스뱅크", "prefixes_csv": "1001", "min_len": 12, "max_len": 14},
        {"name": "농협", "prefixes_csv": "301, 302", "min_len": 11, "max_len": 13},
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
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_banks, reverse_code=unseed_banks),
    ]