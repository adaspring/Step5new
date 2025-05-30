import os
import re
import zipfile
from pathlib import Path

def update_urls_in_file(file_path, language_code):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update JSON-LD URLs
    def update_jsonld_url(match):
        jsonld = match.group(1)
        # Update main URL
        jsonld = re.sub(
            r'"url": "https://artea\.netlify\.app/([^"]*?)\.html"',
            f'"url": "https://artea.netlify.app/\\1-{language_code}.html"',
            jsonld
        )
        # Update mainEntityOfPage
        jsonld = re.sub(
            r'"mainEntityOfPage": \{.*?"@id": "https://artea\.netlify\.app/([^"]*?)\.html"',
            f'"mainEntityOfPage": {{"@type": "WebPage", "@id": "https://artea.netlify.app/\\1-{language_code}.html"',
            jsonld
        )
        # Update collection URLs
        jsonld = re.sub(
            r'"url": "https://artea\.netlify\.app/([^"]*?)\.html"',
            f'"url": "https://artea.netlify.app/\\1-{language_code}.html"',
            jsonld
        )
        return f'<script type="application/ld+json">{jsonld}</script>'

    content = re.sub(
        r'<script type="application/ld\+json">(.*?)</script>',
        update_jsonld_url,
        content,
        flags=re.DOTALL
    )

    # Update BreadcrumbList
    def update_breadcrumb_url(match):
        breadcrumb = match.group(1)
        breadcrumb = re.sub(
            r'"item": "https://artea\.netlify\.app/([^"]*?)\.html"',
            f'"item": "https://artea.netlify.app/\\1-{language_code}.html"',
            breadcrumb
        )
        return f'<script type="application/ld+json">{breadcrumb}</script>'

    content = re.sub(
        r'<script type="application/ld\+json">(\{"@context": "https://schema\.org".*?"BreadcrumbList".*?)</script>',
        update_breadcrumb_url,
        content,
        flags=re.DOTALL
    )

    # Update hreflang URLs
    def update_hreflang_url(match):
        return match.group(0).replace('.html"', f'-{language_code}.html"')

    content = re.sub(
        r'<link rel="alternate" hreflang="[^"]*" href="https://artea\.netlify\.app/[^"]*\.html"',
        update_hreflang_url,
        content
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def process_files(input_folder, output_folder):
    for filename in os.listdir(input_folder):
        if filename.endswith('.html'):
            # Extract language code from filename (e.g., "es" from "nok-terracottas-es.html")
            match = re.search(r'-([a-z]{2}(?:-[A-Z]{2})?)\.html$', filename)
            if not match:
                continue
                
            language_code = match.group(1)
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)
            
            # Copy file to output folder
            Path(output_folder).mkdir(parents=True, exist_ok=True)
            with open(input_path, 'r', encoding='utf-8') as src, open(output_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            
            # Update URLs in the copied file
            update_urls_in_file(output_path, language_code)
            
            # Create zip file with the same name
            zip_filename = os.path.join(output_folder, f'{os.path.splitext(filename)[0]}.zip')
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(output_path, arcname=filename)

if __name__ == '__main__':
    input_folder = 'upload'
    output_folder = 'processed'
    process_files(input_folder, output_folder)
