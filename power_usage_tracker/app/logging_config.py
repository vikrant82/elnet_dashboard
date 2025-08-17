import logging
import sys

def setup_logging():
    """Set up basic logging to capture INFO level logs."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stdout  # Ensure logs go to stdout for Docker
    )
