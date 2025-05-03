import logging
import logging.config
import sys

def setup_logging(
    default_level=logging.INFO,
    default_config_dict=None,
    log_file=None,
    console_output=True,
    json_log=False
):
    """
    Sets up logging configuration for the application.  This can use a dictionary
    config, a file config, or a basic config.

    Args:
        default_level (int, optional): The default logging level. Defaults to INFO.
        default_config_dict (dict, optional): A dictionary containing the logging
            configuration. If provided, overrides basic configuration.
        log_file (str, optional):  If provided, sets up a FileHandler to log to
            the specified file.
        console_output (bool, optional): Whether to include a StreamHandler
            for console output. Defaults to True.
        json_log (bool, optional): Whether to format the output as JSON.
            Defaults to False.
    """
    if default_config_dict:
        # Use dictionary configuration if provided
        logging.config.dictConfig(default_config_dict)
        return

    # Basic configuration (can be overridden by dictConfig)
    format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    if json_log:
        format_string = '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'

    handlers = []

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(default_level)
        formatter = logging.Formatter(format_string)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(default_level)
        formatter = logging.Formatter(format_string)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(level=default_level, handlers=handlers)
