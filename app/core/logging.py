"""
Shared logger for the whole application.
Import `logger` from here instead of calling logging.getLogger() everywhere.
"""

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("whatsapp-service")
