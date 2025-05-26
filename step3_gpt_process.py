# batch.py - Enhanced Version with Complete Block Coverage
import os
import json
import openai
import hashlib
import time
import argparse
from pathlib import Path
from json.decoder import JSONDecodeError

def validate_input_files(*files):
    """Ensure all input files exist before processing"""
    for file in files:
        if not Path(file).exists():
            raise FileNotFoundError(f"Critical file missing: {file}")

def build_gpt_friendly_input(context_file, translated_file, output_file, target_lang, primary_lang):
    """Generate GPT-ready input with language context"""
    validate_input_files(context_file, translated_file)
    
    with open(context_file, 'r', encoding='utf-8') as f:
        context_data = json.load(f)
    
    with open(translated_file, 'r', encoding='utf-8') as f:
        translated_map = json.load(f)
    
    lines = []
    for category in ['1_word', '2_words', '3_words', '4_or_more_words']:
        for entry in context_data[category]:
            tag = entry['tag']
            block_ids = []
            for key in entry.keys():
                if key != 'tag':
                    # Split merged block IDs (e.g., "BLOCK_1=BLOCK_2")
                    block_ids.extend(key.split('='))
            
            for block_id in block_ids:
                source_text = entry.get(block_id, "")
                translated_text = translated_map.get(block_id, "")
                
                lines.append(f"{block_id} | {tag}")
                lines.append(f"{primary_lang}: {source_text}")
                lines.append(f"{target_lang}: {translated_text}")
                lines.append("")  # Empty line separator
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

def count_expected_blocks(input_file):
    """Count all unique block IDs in the input file"""
    block_ids = set()
    with open(input_file, 'r', encoding='utf-8') as f:
        for entry in f.read().split("\n\n"):
            if entry.strip():
                first_line = entry.strip().split('\n')[0]
                if '|' in first_line:
                    block_id = first_line.split('|')[0].strip()
                    block_ids.add(block_id)
    return block_ids

def process_individual_entry(client, system_prompt, entry, original_translations):
    """Process a single entry and return translation dict"""
    try:
        lines = entry.strip().split('\n')
        block_id = lines[0].split('|')[0].strip()
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": entry}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        
        individual_response = response.choices[0].message.content.strip()
        
        # Try to parse as JSON first
        try:
            if individual_response.startswith('```json'):
                individual_response = individual_response.split('```json')[1].split('```')[0].strip()
            elif individual_response.startswith('```'):
                individual_response = individual_response.split('```')[1].split('```')[0].strip()
            
            result = json.loads(individual_response)
            if block_id in result:
                return result
            return {block_id: result.get(block_id, original_translations.get(block_id, ""))}
        except json.JSONDecodeError:
            return {block_id: individual_response}
        
    except Exception as e:
        print(f"❌ Individual entry failed: {str(e)[:50]}")
        return {block_id: original_translations.get(block_id, "")}

def process_with_api_direct_json(input_file, api_key, args, max_retries=3, batch_size=10):
    """Process translations with batch processing and complete coverage"""
    validate_input_files(input_file, args.translated)
    
    # Load all original translations
    with open(args.translated, 'r', encoding='utf-8') as f:
        original_translations = json.load(f)
    
    # Get all expected blocks
    expected_blocks = count_expected_blocks(input_file)
    print(f"ℹ️ Expecting {len(expected_blocks)} translation blocks in total")
    
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = [entry.strip() for entry in f.read().split("\n\n") if entry.strip()]
    
    # Build system prompt
    system_prompt = f"""You are a professional translator. 

You will receive entries with:

   -BLOCK_ID | tag_name
   - Original text: Original text in {args.primary_lang}{f" or {args.secondary_lang}" if args.secondary_lang else ""}
   - Current translation: {args.target_lang} translation

2. For EACH block, you MUST return:
   - The IMPROVED translation if needed
   - The Current translation if no        improvement is needed
- Never omit any block from your response!


3. TRANSLATION SCOPE AND LANGUAGE IDENTIFICATION:
-Compare the original text with the current translation to determine if improvement is needed.
-Only translate text if the original text is in:
- **{args.primary_lang}**: Translate to {args.target_lang}
{f"- **{args.secondary_lang}**: Translate to {args.target_lang}" if args.secondary_lang else ""}
- **For Any other language**: Return the original text unchanged.

4. EVALUATION OF THE TRANSLATION PROCESS:**
4.1. Compare the original text with the current {args.target_lang} translation
4.2. Identify if the current translation has issues:
   - **Accuracy**: Wrong meaning, missing information, mistranslations
   - **Naturalness**: Awkward phrasing, overly literal translation
   - **Grammar**: Incorrect verb forms, word order, agreement errors
   - **Terminology**: Inconsistent or inappropriate word choices
   - **Context**: Doesn't fit UI/web context appropriately
   - **Special cases**: 
        --Common Descriptive Words:
            Everyday adjectives and nouns in descriptive context → TRANSLATE
            Examples: "Height", "Width", "Material", "Color", "Size" → Always translate
4.3.DECISION CRITERIA:
- **Do IMPROVE**: If current translation has any of the above issues
- **Do not IMPROVE**: If current translation is accurate, natural, and appropriate
- **EXAMPLES:**
Input format you'll receive:
```
BLOCK_123 | tag_name
en: Log in to your account
fr: Connecter à votre compte
```

✓Do  IMPROVE (grammatical error): `fr: Se connecter à votre compte`
✓Do not  IMPROVE (already good): If current translation was already `Se connecter à votre compte`

4. Output MUST be JSON with ALL received BLOCK_IDs:
   {{
     "BLOCK_X": "improved_or_current_translation",
     "BLOCK_Y": "improved_or_current_translation",
   }}
   """
  
    # Process in batches
    batches = [content[i:i+batch_size] for i in range(0, len(content), batch_size)]
    final_translations = {}
    
    for batch_idx, batch in enumerate(batches):
        print(f"Processing batch {batch_idx+1}/{len(batches)} ({len(batch)} entries)")
        batch_input = "\n\n".join(batch)
        
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": batch_input}
                    ],
                    temperature=0.2,
                    max_tokens=4000,
                    response_format={"type": "json_object"}
                )
                
                batch_response = response.choices[0].message.content.strip()
                
                try:
                    # Clean JSON response
                    if batch_response.startswith('```json'):
                        batch_response = batch_response.split('```json')[1].split('```')[0].strip()
                    elif batch_response.startswith('```'):
                        batch_response = batch_response.split('```')[1].split('```')[0].strip()
                    
                    batch_translations = json.loads(batch_response)
                    
                    # Validate we got all expected blocks from this batch
                    batch_block_ids = {e.split('\n')[0].split('|')[0].strip() for e in batch}
                    missing_in_batch = batch_block_ids - set(batch_translations.keys())
                    
                    if missing_in_batch:
                        print(f"⚠️ Batch {batch_idx+1} missing {len(missing_in_batch)} blocks - filling with originals")
                        for block_id in missing_in_batch:
                            batch_translations[block_id] = original_translations.get(block_id, "")
                    
                    final_translations.update(batch_translations)
                    print(f"✅ Batch {batch_idx+1} processed ({len(batch_translations)} entries)")
                    break
                    
                except JSONDecodeError as json_error:
                    print(f"⚠️ Batch {batch_idx+1} JSON error: {str(json_error)[:100]}")
                    if attempt == max_retries - 1:
                        print(f"🔄 Processing batch {batch_idx+1} individually as fallback")
                        for entry in batch:
                            final_translations.update(process_individual_entry(
                                client, system_prompt, entry, original_translations
                            ))
                    else:
                        time.sleep(2 ** attempt)
                        continue
                        
            except Exception as e:
                print(f"❌ Batch {batch_idx+1} attempt {attempt+1} failed: {str(e)[:100]}")
                if attempt == max_retries - 1:
                    print(f"🔄 Processing batch {batch_idx+1} individually as fallback")
                    for entry in batch:
                        final_translations.update(process_individual_entry(
                            client, system_prompt, entry, original_translations
                        ))
                else:
                    time.sleep(2 ** attempt)
        
        time.sleep(1)  # Rate limit buffer
    
    # Final verification
    missing_blocks = expected_blocks - set(final_translations.keys())
    if missing_blocks:
        print(f"⚠️ Filling {len(missing_blocks)} missing blocks with original translations")
        for block_id in missing_blocks:
            final_translations[block_id] = original_translations.get(block_id, "")
    
    # Calculate improvement statistics
    improved_count = sum(
        1 for block_id in expected_blocks 
        if final_translations.get(block_id, "") != original_translations.get(block_id, "")
    )
    
    print("\n📊 Final Statistics:")
    print(f"- Total blocks processed: {len(expected_blocks)}")
    print(f"- Blocks improved: {improved_count}")
    print(f"- Blocks unchanged: {len(expected_blocks) - improved_count}")
    
    return final_translations



def normalize_text(text, length=50):
    """Normalize and truncate text for hashing/grouping"""
    return ' '.join(text.lower().strip().split())[:length]

def create_text_hash_map(flat_sentences_file):
    """Create a mapping from normalized text to list of block IDs"""
    with open(flat_sentences_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    hash_map = {}
    for category in data:
        for entry in data[category]:
            for key, value in entry.items():
                if key == "tag":
                    continue
                norm = normalize_text(value)
                hash_map.setdefault(norm, []).append((key, value))
    
    return hash_map

def group_blocks_by_text(flat_sentences_file, translations):
    """Create a dict of grouped blocks with shared source text"""
    hash_map = create_text_hash_map(flat_sentences_file)
    grouped_entries = {}

    for norm, block_list in hash_map.items():
        source_text = block_list[0][1]
        block_ids = [block_id for block_id, _ in block_list]
        translations_set = {translations.get(block_id, '') for block_id in block_ids}
        
        # Only reprocess same origin 
            grouped_entries[source_text] = {
                "block_ids": block_ids,
                "translations": {block_id: translations.get(block_id, '') for block_id in block_ids}
            }

    return grouped_entries

def prepare_post_gpt_input(grouped_entries):
    """Format grouped entries into GPT-readable input string"""
    blocks = []
    for source_text, data in grouped_entries.items():
        header = '='.join(data['block_ids']) + f" = {source_text} {{"
        body = '\n'.join(f"{bid} = \"{text}\"" for bid, text in data['translations'].items())
        block = f"{header}\n{body}\n}}\n"
        blocks.append(block)
    return '\n'.join(blocks)

def run_postprocess_consistency(client, grouped_entries, system_prompt):
    """Call GPT to harmonize translations and return new translation map"""
    input_text = prepare_post_gpt_input(grouped_entries)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_text}
        ],
        temperature=0.2,
        max_tokens=4000
    )

    content = response.choices[0].message.content.strip()
    if content.startswith('```json'):
        content = content.split('```json')[1].split('```')[0].strip()
    elif content.startswith('```'):
        content = content.split('```')[1].split('```')[0].strip()

    try:
        patch = json.loads(content)
        return patch
    except json.JSONDecodeError:
        print("⚠️ Failed to parse GPT postprocess response.")
        return {}
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPT Translation Processor")
    parser.add_argument("--context", required=True, help="translatable_flat_sentences.json")
    parser.add_argument("--translated", required=True, help="segments_only.json")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--primary-lang", required=True)
    parser.add_argument("--secondary-lang")
    parser.add_argument("--target-lang", required=True)
    parser.add_argument("--batch-size", type=int, default=10, help="Number of entries per batch")
    parser.add_argument("--output", required=True, help="Output file path for translations")  # Changed from --output-dir

    args = parser.parse_args()
    client = openai.OpenAI(api_key=args.api_key)
    
    # Validate input files first
    validate_input_files(args.context, args.translated)
    
    # Generate GPT-ready input
    intermediate_file = "gpt_input.txt"
    build_gpt_friendly_input(
        args.context,
        args.translated,
        intermediate_file,
        args.target_lang,
        args.primary_lang
    )
    
    # Process with API and get final translations
    final_translations = process_with_api_direct_json(
        intermediate_file,
        args.api_key,
        args,
        batch_size=args.batch_size
    )

    # Normalize and prepare output path
    args.output = os.path.normpath(args.output)  # Clean up path
    output_dir = os.path.dirname(args.output)
    if output_dir:  # Only create directories if path contains them
        os.makedirs(output_dir, exist_ok=True)

    # Save final translations
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(final_translations, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(final_translations)} translations to {args.output}")

    # Step 4: Harmonization begins here
    try:
        print("\n🔄 Running post-GPT consistency harmonization...")
        flat_sentences_path = args.context  # translatable_flat_sentences.json
        translations_path = args.output    # openai_translations.json

        with open(translations_path, 'r', encoding='utf-8') as f:
            original_translations = json.load(f)

        grouped = group_blocks_by_text(flat_sentences_path, original_translations)

        if grouped:
            post_prompt = """
You will receive groups of block IDs that share similar original English texts.

For each group, review the translations.

If they differ, choose the most appropriate and natural translation.
--Date-related abbreviations (like BCE, CE, AD, 5th c.): 
             Are translated consistently and remain in abbreviated form.
             Avoid expanding the abbreviations unnecessarily.
             Example for French translations:
               BCE → av. notre ère
                CE → de notre ère
                c. → v.
                for "century" → use "s.” or "siècle" (e.g., 5e s. = 5th century)

Apply that translation to all block IDs in the group.

If they are already consistent, keep them unchanged.

Return a single JSON object like this: { "BLOCK_24": "Grande figure d'homme", "BLOCK_134": "Grande figure d'homme", ... }"""
            # Save GPT harmonization input file
            post_input_text = prepare_post_gpt_input(grouped)
            post_input_path = os.path.join(os.path.dirname(args.output), "gpt_post_input.txt")
            with open(post_input_path, "w", encoding="utf-8") as f:
                f.write(post_input_text)
            print(f"📝 Saved harmonization input to {post_input_path}")
    
            patch = run_postprocess_consistency(client, grouped, post_prompt)

            if patch:
                updated_count = 0
                for block_id, new_text in patch.items():
                    if block_id in original_translations and original_translations[block_id] != new_text:
                        original_translations[block_id] = new_text
                        updated_count += 1

                with open(translations_path, "w", encoding="utf-8") as f:
                    json.dump(original_translations, f, indent=2, ensure_ascii=False)
                print(f"✅ Harmonization complete. {updated_count} translations updated.")
            else:
                print("ℹ️ No changes returned from GPT postprocess step.")
        else:
            print("✔️ All translations already consistent. No harmonization needed.")

    except Exception as e:
        print(f"❌ Postprocess harmonization failed: {e}")
