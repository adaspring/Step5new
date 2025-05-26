#!/usr/bin/env python3
"""
Step 4: Merge translations back into HTML for multiple files
Creates final translated HTML files using either DeepL or OpenAI translations
"""

import argparse
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
import sys
import os

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
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
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

def process_single_file(html_file, deepl_path, openai_path, output_dir):
    """Process a single HTML file with both translation sources"""
    filename = os.path.splitext(os.path.basename(html_file))[0]
    
    # Create output filenames
    deepl_output = os.path.join(output_dir, f"{filename}_deepl.html")
    openai_output = os.path.join(output_dir, f"{filename}_openai.html")
    
    # Process DeepL translations if available
    if deepl_path and os.path.exists(deepl_path):
        print(f"\nProcessing DeepL translations for {filename}...")
        deepl_translations = load_json(deepl_path)
        
        if validate_translations(deepl_translations, "DeepL (segments_only.json)"):
            merge_translations_into_html(html_file, deepl_translations, deepl_output)
        else:
            print(f"Skipping DeepL merge for {filename} due to validation failure")
    
    # Process OpenAI translations if available
    if openai_path and os.path.exists(openai_path):
        print(f"\nProcessing OpenAI translations for {filename}...")
        openai_translations = load_json(openai_path)
        
        if validate_translations(openai_translations, "OpenAI (openai_translations.json)"):
            merge_translations_into_html(html_file, openai_translations, openai_output)
        else:
            print(f"Skipping OpenAI merge for {filename} due to validation failure")

def main():
    parser = argparse.ArgumentParser(description="Merge translations back into HTML files")
    parser.add_argument("--input-dir", required=True, help="Directory containing non_translatable.html files")
    parser.add_argument("--output-dir", required=True, help="Output directory for final HTML files")
    parser.add_argument("--deepl-dir", help="Directory containing segments_only.json files")
    parser.add_argument("--openai-dir", help="Directory containing openai_translations.json files")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.input_dir):
        print(f"Error: Input directory {args.input_dir} does not exist")
        sys.exit(1)
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Processing HTML files from: {args.input_dir}")
    print("=" * 50)
    
    # Process each HTML file in the input directory
    processed_files = 0
    for root, _, files in os.walk(args.input_dir):
        for file in files:
            if file == "non_translatable.html":
                html_path = os.path.join(root, file)
                filename = os.path.basename(os.path.dirname(root))
                
                # Determine paths to translation files
                deepl_path = None
                openai_path = None
                
                if args.deepl_dir:
                    deepl_path = os.path.join(args.deepl_dir, filename, "segments_only.json")
                
                if args.openai_dir:
                    openai_path = os.path.join(args.openai_dir, filename, "openai_translations.json")
                
                print(f"\nProcessing file: {filename}")
                process_single_file(html_path, deepl_path, openai_path, args.output_dir)
                processed_files += 1
    
    print("\n" + "=" * 50)
    print(f"Merge process completed! Processed {processed_files} files.")
    print(f"Output files saved to: {args.output_dir}")

if __name__ == "__main__":
    main()
