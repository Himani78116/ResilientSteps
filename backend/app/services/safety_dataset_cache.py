import sys
from app.modules.walksafe.services import safety_dataset_cache as _module

sys.modules[__name__] = _module
