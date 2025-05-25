#!/usr/bin/env python3
"""
Step 4: Merge translations back into HTML
Creates final translated HTML files using either DeepL or OpenAI translations
"""

import argparse
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
import sys

def load_json(file_path):
    """Load JSON file with error handling"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}")
        sys.exit(1)

def merge_translations_into_html(html_file, translations, output_file):
    """
    Merge translations back into the HTML file by replacing BLOCK_X_SX placeholders
    """
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: HTML file {html_file} not found")
        sys.exit(1)
    
    # Replace each placeholder with its translation
    replaced_count = 0
    for block_id, translation in translations.items():
        if translation and translation.strip():  # Only replace if translation exists and is not empty
            # Use regex to replace the exact placeholder
            pattern = re.escape(block_id)
            if re.search(pattern, html_content):
                html_content = re.sub(pattern, translation, html_content)
                replaced_count += 1
    
    # Parse and prettify the HTML
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Write the final HTML
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        
        print(f"Successfully merged {replaced_count} translations into {output_file}")
        
    except Exception as e:
        print(f"Error processing HTML: {e}")
        # If BeautifulSoup fails, write raw content
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Warning: HTML parsing failed, wrote raw content with {replaced_count} replacements to {output_file}")

def validate_translations(translations, translation_source):
    """Validate translation data and report statistics"""
    if not translations:
        print(f"Warning: No translations found in {translation_source}")
        return False
    
    total_keys = len(translations)
    non_empty_translations = sum(1 for v in translations.values() if v and v.strip())
    empty_translations = total_keys - non_empty_translations
    
    print(f"\n{translation_source} Statistics:")
    print(f"  Total translation keys: {total_keys}")
    print(f"  Non-empty translations: {non_empty_translations}")
    print(f"  Empty/missing translations: {empty_translations}")
    
    if empty_translations > 0:
        print(f"  Warning: {empty_translations} translations are empty or missing")
    
    return non_empty_translations > 0

def main():
    parser = argparse.ArgumentParser(description="Merge translations back into HTML file")
    parser.add_argument("--html", required=True, help="Path to non_translatable.html file")
    parser.add_argument("--deepl", help="Path to segments_only.json (DeepL translations)")
    parser.add_argument("--openai", help="Path to openai_translations.json (OpenAI translations)")
    parser.add_argument("--output-deepl", default="final_deepl.html", help="Output file for DeepL version")
    parser.add_argument("--output-openai", default="final_openai.html", help="Output file for OpenAI version")
    parser.add_argument("--both", action="store_true", help="Process both translation sources")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.deepl and not args.openai and not args.both:
        print("Error: Must specify at least one translation source (--deepl, --openai, or --both)")
        sys.exit(1)
    
    if args.both and (not args.deepl or not args.openai):
        print("Error: --both requires both --deepl and --openai paths")
        sys.exit(1)
    
    html_file = Path(args.html)
    if not html_file.exists():
        print(f"Error: HTML file {html_file} does not exist")
        sys.exit(1)
    
    print(f"Processing HTML file: {html_file}")
    print("=" * 50)
    
    # Process DeepL translations
    if args.deepl:
        print("\nProcessing DeepL translations...")
        deepl_translations = load_json(args.deepl)
        
        if validate_translations(deepl_translations, "DeepL (segments_only.json)"):
            merge_translations_into_html(args.html, deepl_translations, args.output_deepl)
        else:
            print("Skipping DeepL merge due to validation failure")
    
    # Process OpenAI translations
    if args.openai:
        print("\nProcessing OpenAI translations...")
        openai_translations = load_json(args.openai)
        
        if validate_translations(openai_translations, "OpenAI (openai_translations.json)"):
            merge_translations_into_html(args.html, openai_translations, args.output_openai)
        else:
            print("Skipping OpenAI merge due to validation failure")
    
    print("\n" + "=" * 50)
    print("Merge process completed successfully!")
    
    # Show output files created
    created_files = []
    if args.deepl and Path(args.output_deepl).exists():
        created_files.append(args.output_deepl)
    if args.openai and Path(args.output_openai).exists():
        created_files.append(args.output_openai)
    
    if created_files:
        print(f"\nOutput files created:")
        for file in created_files:
            file_size = Path(file).stat().st_size
            print(f"  - {file} ({file_size:,} bytes)")

if __name__ == "__main__":
    main()
