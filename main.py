from src.utils import setup_logging
setup_logging()

from src.hirable_server import mcp


if __name__ == "__main__":
    mcp.run()
