
import os
import sys
import django

sys.path.append("/home/hojechun/ssd_mnt/repos/htvs")
sys.path.append("/home/hojechun/ssd_mnt/repos/htvs/djangochem")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangochem.settings.toy")
django.setup()

from pgmols.models import Method

print("Available Methods:")
for m in Method.objects.all()[:10]:
    print(f"- {m.name} (id: {m.id})")
