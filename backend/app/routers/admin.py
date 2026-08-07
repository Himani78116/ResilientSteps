import sys
from app.modules.walksafe.routers import admin as _module

sys.modules[__name__] = _module
