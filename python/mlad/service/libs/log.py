import logging
from fastapi.logger import logger

def init_logger(name):
    formatter = logging.Formatter(
        '%(levelname)s: [%(filename)s:%(lineno)d] %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    #logger.info('Logger Start')
    return logger