import os
import logging
import requests
import fitz  # PyMuPDF
import tempfile
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

def download_elsevier(doi: str, output_dir: Path) -> str:
    """Download full text from Elsevier using ScienceDirect API."""
    api_key = os.getenv("ELSEVIER_API_KEY")
    inst_token = os.getenv("ELSEVIER_INST_TOKEN")
    
    if not api_key:
        logger.error("ELSEVIER_API_KEY environment variable not set.")
        return None
        
    url = f"https://api.elsevier.com/content/article/doi/{doi}"
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "text/plain" # or application/json for structured data
    }
    if inst_token:
        headers["X-ELS-Insttoken"] = inst_token
        
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Save as text file
        safe_doi = doi.replace('/', '_')
        output_file = output_dir / f"{safe_doi}.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
            
        logger.info(f"Successfully downloaded Elsevier paper {doi} to {output_file}")
        return str(output_file)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (400, 404, 406):
            logger.info(f"text/plain failed for {doi}, attempting application/json fallback...")
            headers["Accept"] = "application/json"
            try:
                fallback_resp = requests.get(url, headers=headers, timeout=30)
                fallback_resp.raise_for_status()
                data = fallback_resp.json().get('full-text-retrieval-response', {})
                
                content = data.get('originalText', '')
                if not content:
                    # Fallback to abstract if full text isn't in JSON
                    content = data.get('coredata', {}).get('dc:description', 'No content available.')
                    
                safe_doi = doi.replace('/', '_')
                output_file = output_dir / f"{safe_doi}.txt"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    # Write title and content
                    title = data.get('coredata', {}).get('dc:title', 'Unknown Title')
                    f.write(f"Title: {title}\\n\\n{content}")
                    
                logger.info(f"Successfully downloaded Elsevier paper {doi} (JSON fallback) to {output_file}")
                return str(output_file)
            except Exception as inner_e:
                logger.error(f"Failed Elsevier JSON fallback for {doi}: {inner_e}")
                return None
                
        logger.error(f"Failed to download Elsevier paper {doi}: {e}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response: {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error downloading Elsevier paper {doi}: {e}")
        return None

def download_springer(doi: str, output_dir: Path) -> str:
    """Download full text from Springer API."""
    api_key = os.getenv("SPRINGER_API_KEY")
    
    if not api_key:
        logger.error("SPRINGER_API_KEY environment variable not set.")
        return None
        
    safe_doi = doi.replace('/', '_')
    output_file = output_dir / f"{safe_doi}.txt"
    
    # 1. Attempt the TDM / Full-Text API first (Returns XML)
    tdm_url = "https://spdi.public.springernature.app/xmldata/jats"
    params = {"q": f"doi:{doi}", "api_key": api_key}
    
    try:
        response = requests.get(tdm_url, params=params, timeout=30)
        if response.status_code == 200 and len(response.text.strip()) > 500:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info(f"Successfully downloaded Springer TDM full XML for {doi} to {output_file}")
            return str(output_file)
    except requests.exceptions.RequestException as e:
        logger.debug(f"Springer TDM full-text fetch failed for {doi}: {e}")

    # 2. Fallback: Meta API v2 which returns JSON with abstract
    meta_url = "https://api.springernature.com/meta/v2/json"
    
    try:
        response = requests.get(meta_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        records = data.get("records", [])
        if not records:
            logger.warning(f"No records found in Springer Meta API for DOI {doi}")
            return None
            
        record = records[0]
        title = record.get("title", "Unknown Title")
        abstract = record.get("abstract", "")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Title: {title}\\n\\n")
            f.write(f"DOI: {doi}\\n\\n")
            f.write(f"Content (Abstract only - Full Text access restricted):\\n{abstract}")
            
        logger.info(f"Successfully downloaded Springer abstract for {doi} to {output_file}")
        return str(output_file)
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download Springer paper {doi}: {e}")
        return None

def download_unpaywall(doi: str, output_dir: Path) -> str:
    """Download full text or preprint via Unpaywall API using DOI."""
    email = os.getenv("UNPAYWALL_EMAIL") or os.getenv("OPENALEX_EMAIL")
    if not email:
        logger.error("UNPAYWALL_EMAIL or OPENALEX_EMAIL environment variable not set. It is required by Unpaywall.")
        return None

    safe_doi = doi.replace('/', '_')
    output_file = output_dir / f"{safe_doi}.txt"
    
    url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        oa_location = data.get("best_oa_location")
        if not oa_location:
            logger.warning(f"No Open Access location found for DOI {doi} on Unpaywall.")
            return None
            
        pdf_url = oa_location.get("url_for_pdf")
        if not pdf_url:
            pdf_url = oa_location.get("url") # Fallback to general URL if PDF specifically isn't marked
            if not pdf_url:
                 logger.warning(f"No valid URL found in OA location for DOI {doi}.")
                 return None

        # Download the content
        logger.info(f"Fetching OA content from {pdf_url}")
        
        # We need headers mimicking a browser as some institutional repos block bare requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        pdf_resp = requests.get(pdf_url, headers=headers, stream=True, timeout=60)
        pdf_resp.raise_for_status()
        
        content_type = pdf_resp.headers.get('Content-Type', '')
        
        if 'application/pdf' in content_type.lower() or pdf_url.lower().endswith('.pdf'):
            # It's a PDF, save temporarily and parse with PyMuPDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                for chunk in pdf_resp.iter_content(chunk_size=8192):
                    tmp_pdf.write(chunk)
                tmp_pdf_path = tmp_pdf.name
                
            try:
                text_content = ""
                with fitz.open(tmp_pdf_path) as doc:
                    for page in doc:
                        text_content += page.get_text() + "\\n"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                    
                logger.info(f"Successfully extracted text from OA PDF for {doi} to {output_file}")
                return str(output_file)
            finally:
                if os.path.exists(tmp_pdf_path):
                    os.remove(tmp_pdf_path)
                    
        else:
            # Not a PDF, maybe raw text or HTML. Try to save directly
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(pdf_resp.text)
            logger.info(f"Downloaded non-PDF OA content for {doi} to {output_file}")
            return str(output_file)
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch Unpaywall data or download OA link for {doi}: {e}")
        return None

def download_paper_by_publisher(doi: str, publisher: str, output_dir: Path) -> str:
    """Download a paper based on the specified publisher."""
    publisher = publisher.lower().strip()
    if publisher == "elsevier":
        return download_elsevier(doi, output_dir)
    elif publisher == "springer":
        return download_springer(doi, output_dir)
    elif publisher in ["unpaywall", "preprint", "oa"]:
        return download_unpaywall(doi, output_dir)
    else:
        logger.warning(f"Unsupported publisher: {publisher} for DOI: {doi}. Attempting generic unpaywall fallback.")
        return download_unpaywall(doi, output_dir)
