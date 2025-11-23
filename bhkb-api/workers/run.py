import logging
import time


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.info("Worker placeholder started (no tasks defined). Sleeping indefinitely.")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
