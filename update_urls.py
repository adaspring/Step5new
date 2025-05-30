import os
import re
import zipfile
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_urls_in_file(file_path: str, language_code: str) -> None:
    """Update JSON-LD and hreflang URLs in HTML file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Update JSON-LD URLs
        def update_jsonld_url(match: re.Match) -> str:
            jsonld = match.group(1)
            patterns = [
                (r'"url": "https://artea\.netlify\.app/([^"]*?)\.html"', 
                 f'"url": "https://artea.netlify.app/\\1-{language_code}.html"'),
                (r'"mainEntityOfPage": \{.*?"@id": "https://artea\.netlify\.app/([^"]*?)\.html"',
                 f'"mainEntityOfPage": {{"@type": "WebPage", "@id": "https://artea.netlify.app/\\1-{language_code}.html"')
            ]
            for pattern, replacement in patterns:
                jsonld = re.sub(pattern, replacement, jsonld)
            return f'<script type="application/ld+json">{jsonld}</script>'

        content = re.sub(
            r'<script type="application/ld\+json">(.*?)</script>',
            update_jsonld_url,
            content,
            flags=re.DOTALL
        )

        # Update BreadcrumbList
        content = re.sub(
            r'"item": "https://artea\.netlify\.app/([^"]*?)\.html"',
            f'"item": "https://artea.netlify.app/\\1-{language_code}.html"',
            content
        )

        # Update hreflang URLs
        content = re.sub(
            r'(<link rel="alternate" hreflang="[^"]*" href="https://artea\.netlify\.app/)([^"]*?)\.html"',
            f'\\1\\2-{language_code}.html"',
            content
        )

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Successfully processed {file_path}")
        
    except Exception as e:
        logger.error(f"Error processing {file_path}: {str(e)}")
        raise

def process_files(input_folder: str = 'upload', output_folder: str = 'processed') -> None:
    """Process all HTML files in input folder"""
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    for filename in os.listdir(input_folder):
        if not filename.endswith('.html'):
            continue
            
        try:
            # Extract language code (e.g., "es" from "nok-terracottas-es.html")
            match = re.search(r'-([a-z]{2}(?:-[A-Z]{2})?)\.html$', filename)
            if not match:
                logger.warning(f"Skipping {filename} - no language code detected")
                continue
                
            language_code = match.group(1)
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)
            
            # Copy file to output folder
            with open(input_path, 'r', encoding='utf-8') as src, \
                 open(output_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            
            # Update URLs
            update_urls_in_file(output_path, language_code)
            
            # Create zip file
            zip_filename = os.path.join(output_folder, f'{os.path.splitext(filename)[0]}.zip')
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(output_path, arcname=filename)
            logger.info(f"Created {zip_filename}")
            
        except Exception as e:
            logger.error(f"Failed to process {filename}: {str(e)}")
            continue

if __name__ == '__main__':
    process_files()
