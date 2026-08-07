import sys
from app.modules.walksafe.services import risk_engine as _module

sys.modules[__name__] = _module
