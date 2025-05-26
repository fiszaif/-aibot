import logging
import os

def setup_logger(name='binance_tracker', log_file='app.log', level=logging.INFO):
    """
    Sets up and returns a logger.

    Args:
        name (str, optional): Name of the logger. Defaults to 'binance_tracker'.
        log_file (str, optional): Name of the log file. Defaults to 'app.log'.
                                  This will be stored in a 'logs/' directory.
        level (int, optional): Logging level. Defaults to logging.INFO.

    Returns:
        logging.Logger: Configured logger instance.
    """
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, log_file)

    # Get the logger
    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers if logger already exists with handlers
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(level)

    # Define log format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create file handler
    fh = logging.FileHandler(log_file_path)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Create console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger

if __name__ == '__main__':
    # Demonstrate usage
    # Logger for the main script/module
    main_logger = setup_logger('my_app_main', log_file='main_app.log', level=logging.DEBUG)
    main_logger.debug("This is a debug message from main_app.")
    main_logger.info("This is an info message from main_app.")
    main_logger.warning("This is a warning message from main_app.")
    main_logger.error("This is an error message from main_app.")
    main_logger.critical("This is a critical message from main_app.")

    # Logger for a specific component/module
    component_logger = setup_logger('my_component', log_file='component.log', level=logging.INFO)
    component_logger.info("Info message from my_component.")
    component_logger.error("Error message from my_component (will also go to component.log).")

    print(f"Log files should be in the '{os.path.abspath('logs')}' directory.")
    print(f"Check 'main_app.log' and 'component.log'.")
