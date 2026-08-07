import sys
from app.modules.walksafe.services import reporting_service as _module

sys.modules[__name__] = _module
