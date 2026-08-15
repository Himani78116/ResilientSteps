import sys
from app.core import database as _module

sys.modules[__name__] = _module
