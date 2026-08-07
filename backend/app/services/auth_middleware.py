import sys
from app.core import auth_middleware as _module

sys.modules[__name__] = _module
