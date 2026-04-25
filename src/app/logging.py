import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    # Processors safe for both PrintLogger (native structlog) and stdlib bridge.
    # Note: add_logger_name requires stdlib Logger (.name attr), so we keep it
    # only in the foreign_pre_chain used by the stdlib handler.
    base_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.EventRenamer("message"),
        structlog.processors.format_exc_info,
    ]

    # For the stdlib ProcessorFormatter bridge, we can safely add logger name.
    foreign_pre_chain = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.EventRenamer("message"),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[*base_processors, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=foreign_pre_chain,
        processors=[structlog.processors.JSONRenderer()],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
