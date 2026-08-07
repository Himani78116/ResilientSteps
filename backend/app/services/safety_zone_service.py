import sys
from app.modules.walksafe.services import safety_zone_service as _module

sys.modules[__name__] = _module
