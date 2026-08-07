import sys
from app.core import rate_limiter as _module

sys.modules[__name__] = _module
