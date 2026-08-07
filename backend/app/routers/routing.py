import sys
from app.modules.walksafe.routers import routing as _module

sys.modules[__name__] = _module
