from .base import *  # noqa: F403
from .base import env

# On by default for local work; `DJANGO_DEBUG=false` in .env turns it off (ROOT-6). Production
# forces it off whatever the environment says.
DEBUG = env.bool("DJANGO_DEBUG", default=True)
