# real_estate_assistant/utils/web_scraper.py
import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

async def fetch_page_content(url: str) -> str:
    """Fetches the content of a given URL."""
    logger.info(f"Fetching content from: {url}")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        logger.info(f"Successfully fetched content from {url}")
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return f"Error: Could not retrieve content from {url}. {e}"

def parse_html_to_text(html_content: str) -> str:
    """Parses HTML content to extract readable text."""
    logger.info("Parsing HTML content to text.")
    soup = BeautifulSoup(html_content, "html.parser")
    # Remove script and style elements
    for script_or_style in soup(["script", "style"]):
        script_or_style.extract()
    text = soup.get_text()
    # Break into lines and remove leading/trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # Break multi-headlines into a single line
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # Drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    logger.info("HTML parsed successfully.")
    return text