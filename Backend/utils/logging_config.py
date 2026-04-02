import logging
import json
import sys
import os


class CloudRunFormatter(logging.Formatter):
    """
    Formats log records as JSON for Cloud Logging structured log ingestion.
    When running locally, falls back to a readable plain-text format.
    """

    def format(self, record: logging.LogRecord) -> str:
        is_cloud_run = os.getenv("K_SERVICE")  # Cloud Run sets this automatically

        if is_cloud_run:
            severity_map = {
                "DEBUG": "DEBUG",
                "INFO": "INFO",
                "WARNING": "WARNING",
                "ERROR": "ERROR",
                "CRITICAL": "CRITICAL"
            }
            log_entry = {
                "severity": severity_map.get(record.levelname, "DEFAULT"),
                "message": record.getMessage(),
                "logger": record.name,
            }
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_entry)
        else:
            # Readable format for local development
            return f"[{record.levelname}] {record.name}: {record.getMessage()}"


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudRunFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)