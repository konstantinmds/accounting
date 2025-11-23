import logging, os, json

def setup_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # example JSON handler if you prefer:
    # logging.getLogger().handlers[0].setFormatter(
    #     logging.Formatter('%(message)s')
    # )
