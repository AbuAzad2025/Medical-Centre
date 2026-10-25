import sys

sys.path.insert(0, r'D:\recovers\data\medical')
from app.core.tenant.models import _PRODUCT_PROFILE_SEED

for slug, prof in _PRODUCT_PROFILE_SEED.items():
    if 'doctor' in slug or 'small_clinic' in slug:
        print(slug + ': ' + str(prof['modules']))
