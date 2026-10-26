"""Import liboqs-python without its INFO messages on stdout.

liboqs-python attaches a stdout log handler at INFO level on import, which would corrupt the
CLI output (a SUCI string). A filter on its logger, added before the import, drops records
below WARNING.
"""

import logging

logging.getLogger("oqs.oqs").addFilter(lambda record: record.levelno >= logging.WARNING)

import oqs  # noqa: E402

__all__ = ["oqs"]
