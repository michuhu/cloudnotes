import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("azure").setLevel(logging.WARNING)

enabled = bool(os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"))

if enabled:
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(logger_name="cloudnotes")
