import sys
from app.modules.walksafe.services import routing_service as _module

sys.modules[__name__] = _module
