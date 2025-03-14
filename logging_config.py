import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('minecraft_bot.log')
        ]
    )
    
    # Create logger
    logger = logging.getLogger('minecraft_bot')
    return logger

logger = setup_logging()
