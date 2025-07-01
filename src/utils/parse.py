from pathlib import Path
from docx import Document
import logging
import re
import io
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import DocumentStream
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)

def parse_file(file_input) -> str:
    '''
    Parse a file into text data. Accepts .txt, .docx or .pdf formats.
    Can accept either a file path (str) or a file-like object (e.g., from Streamlit's file_uploader).

    Args:
       file_input: The path to the file (str) or the file-like object to be parsed.
    Returns:
       str: The text data from the file. If the file is not found, a FileNotFoundError will be raised.
    '''
    text = ''

    # If file_input is a path, open it as a file-like object
    is_filepath = isinstance(file_input, str)

    if is_filepath:
        filepath = Path(file_input)
        if not filepath.exists():
            logger.error(f"File {filepath} does not exist.")
            raise FileNotFoundError(f"File {filepath} does not exist.")
        file_extension = filepath.suffix.lower()
        file_obj = open(filepath, 'rb')
    else:
        # For Streamlit UploadedFile, read its content into BytesIO
        file_extension = Path(getattr(file_input, 'name', '')).suffix.lower()
        file_obj = io.BytesIO(file_input.read())

    if file_extension == '.pdf':
        source = DocumentStream(name='resume.pdf', stream=file_obj)
        converter = DocumentConverter()
        result = converter.convert(source)
        text = result.document.export_to_markdown()
    elif file_extension == '.docx':
        doc = Document(file_obj)
        for para in doc.paragraphs:
            text += para.text + '\n'
    elif file_extension == '.txt':
        # If file_obj is already opened in binary mode, decode
        content = file_obj.read()
        if isinstance(content, bytes):
            text = content.decode('utf-8')
        else:
            text = content
    else:
        logger.error(f"Unsupported file format: {file_extension}")
        raise NotImplementedError
    
    if is_filepath:
        file_obj.close()
    
    return text

def parse_url(url):
    """
    Parses a URL to extract text data from the HTML content.

    Args:
    url (str): The URL of the webpage to be parsed.
    Returns:
    content (str): The extracted text data from the HTML content.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')

        # Identify and remove common unwanted elements
        for script in soup.find_all('script'):
            script.decompose()
        for style in soup.find_all('style'):
            style.decompose()
        for nav in soup.find_all('nav'):
            nav.decompose()
        for aside in soup.find_all('aside'):
            aside.decompose()
        for footer in soup.find_all('footer'):
            footer.decompose()
        for header in soup.find_all('header'):
            header.decompose()
        for form in soup.find_all('form'):
            form.decompose()

        # Attempt to find the main content area (you might need to adjust selectors)
        main_content = soup.find('main')
        if not main_content:
            main_content = soup.find('article')
        if not main_content:
            # Fallback to extracting all text if no specific main content is found
            text = soup.get_text(separator='\n', strip=True)
        else:
            text = main_content.get_text(separator='\n', strip=True)

        # Remove unicode characters
        cleaned_text = re.sub(r'[^\x00-\x7F]+', '', text)

        # Remove extra whitespace
        cleaned_text = '\n'.join(line.strip() for line in cleaned_text.splitlines() if line.strip())

        return cleaned_text
    except requests.RequestException as e:
        logger.error(f"Error fetching URL: {e}")
        raise e