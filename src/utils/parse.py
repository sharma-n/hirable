from pathlib import Path
from docx import Document
import logging
from docling.document_converter import DocumentConverter


logger = logging.getLogger(__name__)

def parse_file(filepath):
    '''
    Parse a file into text data. Accepts .txt, .docx or .pdf formats.

    Args:
       filepath (str): The path to the file to be parsed.
    Returns:
       str: The text data from the file. If the file is not found, a FileNotFoundError will be raised.
    '''
    filepath = Path(filepath)
    text = ''
    if filepath.exists():
        logger.info(f"Loading resume from {filepath}")
        if filepath.suffix == '.pdf':
            converter = DocumentConverter()
            result = converter.convert(filepath)
            text = result.document.export_to_markdown()
        elif filepath.suffix == '.docx':
            doc = Document(filepath)
            for para in doc.paragraphs:
                text += para.text + '\n'
        elif filepath.suffix == '.txt':
            with open(filepath, 'r') as f:
                text = f.read()
        else:
            logger.error(f"Unsupported file format: {filepath.suffix}")
            raise NotImplementedError
    else:
        logger.error(f"File {filepath} does not exist.")
        raise FileNotFoundError(f"File {filepath} does not exist.")
    
    return text