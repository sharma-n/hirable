from docling.document_converter import DocumentConverter
from mcp.server.fastmcp import FastMCP
import logging

from src.utils import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

mcp = FastMCP('Hirable')

@mcp.tool()
def ingest_resume(resume_path) -> str:
    """
    Ingest a resume from a PDF file and return its content as a Markdown string.

    Args:
        resume_path (str): The path to the PDF file containing the resume.
    Returns:
        str: The content of the resume as a Markdown string.
    """
    logger.info(f"Loading resume from {resume_path}")
    converter = DocumentConverter()
    result = converter.convert(resume_path)
    return result.document.export_to_markdown()


# Run the MCP server locally
if __name__ == '__main__':
    mcp.run()