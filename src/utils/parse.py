from pathlib import Path
from docx import Document
import logging
import re

from docling.document_converter import DocumentConverter
from bs4 import BeautifulSoup
import requests

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