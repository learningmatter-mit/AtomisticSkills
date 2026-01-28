
import os
import sys
import django

sys.path.append("/home/hojechun/ssd_mnt/repos/htvs")
sys.path.append("/home/hojechun/ssd_mnt/repos/htvs/djangochem")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangochem.settings.toy")
django.setup()

from jobs.models import JobConfig

print("Available JobConfigs:")
for c in JobConfig.objects.all():
    print(f"- {c.name}")
