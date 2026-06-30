# Modified: 2026-06-29T22:00:00Z
# Standalone 7-phase pipeline runtime

import logging


def init_logging(level: int = logging.INFO) -> None:
	"""Initialize pipeline logger configuration (idempotent)."""
	# Avoid reconfiguring if handlers already present
	root = logging.getLogger()
	if not root.handlers:
		logging.basicConfig(
			level=level,
			format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
		)


# Ensure logging is initialized for simple script runs
init_logging()
