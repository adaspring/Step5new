import os
import json
import deepl
import argparse
import regex as re 
from pathlib import Path


def create_efficient_translatable_map(
    json_data, 
    translator, 
    target_lang="FR", 
    primary_lang=None, 
    secondary_lang=None, 
    memory_file=None,
    update_memory=False
):
    """
    Creates a translation map with language validation.
    Only translates text detected as primary_lang or secondary_lang.
    """
    # Load existing memory (unchanged)
    translation_memory = {}
    if memory_file and os.path.exists(memory_file):
        try:
            with open(memory_file, 'r', encoding='utf-8') as f:
                translation_memory = json.load(f)
            print(f"Loaded {len(translation_memory)} cached translations")
        except json.JSONDecodeError:
            print(f"⚠️ Corrupted memory - resetting {memory_file}")
            # Auto-recover by recreating
            with open(memory_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)   

    
    # Prepare translation data structures
    translatable_map = {}
    texts_to_translate = []
    token_indices = []
    original_texts = {}

    # Process all blocks and segments
    for block_id, block_data in json_data.items():
        if "text" in block_data:
            text = block_data["text"]
            token = block_id
            # Create language-aware memory key
            memory_key = f"{primary_lang or 'any'}-{target_lang}:{text}"
            if memory_key in translation_memory:
                translatable_map[token] = translation_memory[memory_key]
                print(f"Using cached: {token}")
            else:
                texts_to_translate.append(text)
                token_indices.append(token)
                original_texts[token] = (text, memory_key)

        if "segments" in block_data:
            for segment_id, segment_text in block_data["segments"].items():
                token = f"{block_id}_{segment_id}"
                memory_key = f"{primary_lang or 'any'}-{target_lang}:{segment_text}"
                if memory_key in translation_memory:
                    translatable_map[token] = translation_memory[memory_key]
                    print(f"Using cached segment: {token}")
                else:
                    texts_to_translate.append(segment_text)
                    token_indices.append(token)
                    original_texts[token] = (segment_text, memory_key)

    
    def clean_text(text):
        text = re.sub(r'^(.*?):\s*', '', text)
        text = re.sub(r'[^\p{L}\p{N}\s=+-]', ' ', text, flags=re.UNICODE)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:500]
        
    # Language-aware batch translation
    if texts_to_translate:
        print(f"Processing {len(texts_to_translate)} segments with language validation...")
        
        batch_size = 330
        for batch_idx in range(0, len(texts_to_translate), batch_size):
            batch = texts_to_translate[batch_idx:batch_idx+batch_size]
            translated_batch = []
            
            try:
                # Phase 1: Language detection with cleaned text
                detection_texts = [clean_text(text) for text in batch]
                translation_texts = batch  # Keep original texts for translation
                
                detection_results = translator.translate_text(
                    detection_texts,
                    target_lang=target_lang,
                    preserve_formatting=True
                )

                # Phase 2: Translation with original texts
                for idx, detection in enumerate(detection_results):
                    detected_lang = detection.detected_source_lang.lower()
                    allowed_langs = {lang.lower() for lang in [primary_lang, secondary_lang] if lang}
                    original_text = translation_texts[idx]

                    if allowed_langs and detected_lang in allowed_langs:
                        result = translator.translate_text(original_text, target_lang=target_lang)
                        translated_batch.append(result.text)
                    else:
                        translated_batch.append(original_text)

            except Exception as e:
                print(f"Translation skipped for batch (error: {str(e)[:50]}...)")
                translated_batch.extend(batch)
            
            # Store results
            for j in range(len(batch)):
                global_index = batch_idx + j
                token = token_indices[global_index]
                original_text, memory_key = original_texts[token]
                final_text = translated_batch[j]
                
                translatable_map[token] = final_text
                if update_memory:
                    translation_memory[memory_key] = final_text
            
            print(f"Completed batch {batch_idx//batch_size + 1}/{(len(texts_to_translate) + batch_size - 1)//batch_size}")

    # Update translation memory if enabled
    if memory_file and update_memory and translation_memory:
        os.makedirs(os.path.dirname(memory_file), exist_ok=True)
        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump(translation_memory, f, ensure_ascii=False, indent=2)
        print(f"Updated translation memory with {len(translation_memory)} entries")

    return translatable_map

def translate_json_file(
    input_file, 
    output_file, 
    target_lang="FR", 
    primary_lang=None, 
    secondary_lang=None, 
    memory_file=None,
    update_memory=False,
    segment_file=None
):
    """Main translation function with language validation"""
    # Auth check
    auth_key = os.getenv("DEEPL_AUTH_KEY")
    if not auth_key:
        raise ValueError("DEEPL_AUTH_KEY environment variable not set")

    # Initialize translator
    translator = deepl.Translator(auth_key)
    
    # Load input data
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load {input_file}: {e}")

    # Create translation map
    translatable_map = create_efficient_translatable_map(
        json_data=json_data,
        translator=translator,
        target_lang=target_lang,
        primary_lang=primary_lang,
        secondary_lang=secondary_lang,
        memory_file=memory_file,
        update_memory=update_memory
    )

    # Rebuild structure with translations
    translated_data = {}
    for block_id, block_data in json_data.items():
        translated_block = block_data.copy()
        
        if "text" in block_data:
            translated_block["text"] = translatable_map.get(block_id, block_data["text"])
        
        if "segments" in block_data:
            translated_segments = {
                seg_id: translatable_map.get(f"{block_id}_{seg_id}", seg_text)
                for seg_id, seg_text in block_data["segments"].items()
            }
            translated_block["segments"] = translated_segments
        
        translated_data[block_id] = translated_block

    # Save output
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Translation completed: {output_file}")
    
    # Export segments if requested
    if segment_file:
        segment_translations = {}
        for block_id, block_data in translated_data.items():
            if "segments" in block_data:
                for seg_id, seg_text in block_data["segments"].items():
                    segment_translations[seg_id] = seg_text

        with open(segment_file, "w", encoding="utf-8") as f:
            json.dump(segment_translations, f, indent=2, ensure_ascii=False)
        print(f"✅ Segment-only translations exported: {segment_file}")

    return translated_data

def main():
    parser = argparse.ArgumentParser(
        description="Translate JSON content with enhanced memory support"
    )
    parser.add_argument("--input", "-i", required=True, 
                       help="Input JSON file")
    parser.add_argument("--output", "-o", required=True,
                       help="Output JSON file")
    parser.add_argument("--lang", "-l", required=True,
                       help="Target language code (e.g., FR, ES)")
    parser.add_argument("--primary-lang", 
                       help="Primary source language code")
    parser.add_argument("--secondary-lang",
                       help="Secondary source language code")
    parser.add_argument("--memory", "-m", 
                       help="Path to translation memory file")
    parser.add_argument("--update-memory", action="store_true",
                       help="Update translation memory with new translations")
    parser.add_argument("--segments", "-s", 
                       help="Output file for segment-only translations")

    args = parser.parse_args()

    try:
        translate_json_file(
            input_file=args.input,
            output_file=args.output,
            target_lang=args.lang,
            primary_lang=args.primary_lang,
            secondary_lang=args.secondary_lang,
            memory_file=args.memory,
            update_memory=args.update_memory,
            segment_file=args.segments
        )
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
