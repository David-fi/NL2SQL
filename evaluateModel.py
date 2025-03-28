import json
import os
import time
import sacrebleu
import re
from dotenv import load_dotenv
load_dotenv()  # This loads environment variables from a file named .env in working directory

from openai import OpenAI
 #as per OpenAI documentation this is the key to do thinds like file uploads, and completions
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


#Configuration

MODEL_NAME = "ft:gpt-4o-mini-2024-07-18:personal::B3lHt6V9"
VALIDATION_FILE = "/Users/david/Library/Mobile Documents/com~apple~CloudDocs/Documents/Documents – David’s MacBook Pro/university/year 3/Individual Project/dataSets/test.jsonl"  
RESULTS_FILE = "/Users/david/Library/Mobile Documents/com~apple~CloudDocs/Documents/Documents – David’s MacBook Pro/university/year 3/Individual Project/dataSets/results.jsonl" 
SUMMARY_FILE = "/Users/david/Library/Mobile Documents/com~apple~CloudDocs/Documents/Documents – David’s MacBook Pro/university/year 3/Individual Project/dataSets/evaluation_summary.json" 
SLEEP_BETWEEN_CALLS = 0  # Delay in seconds between API calls 

# This is the standard set of keywords
STANDARD_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "JOIN", "ON", "GROUP", "ORDER", "LIMIT",
    "MAX", "MIN", "AVG", "COUNT", "DISTINCT", "AND", "OR", "IN", "AS"
]
# Build a regex pattern for extracting these keywords, also case sensitive
KEYWORD_PATTERN = r'\b(?:' + '|'.join(STANDARD_KEYWORDS) + r')\b'

#somr helper Functions
def clean_sql(query):
    # Remove code fences such as ```sql and ```
    query = query.replace("```sql", "").replace("```", "")
    return query.strip()

def extract_keywords(query):
    """
    Extract SQL keywords from a query string using the standard set
    The extraction is case sensitive.=
    """
    query = clean_sql(query)
    # Find all matches in order
    return re.findall(KEYWORD_PATTERN, query)

def format_prompt_from_messages(messages):
    """
    Convert a list of chat messages to a plain text prompt
    Each message is a dict with "role" and "content"
    Returns a string that concatenates messages in a readable format
    """
    prompt = ""
    for msg in messages:
        role = msg.get("role", "").capitalize()
        content = msg.get("content", "").strip()
        prompt += f"{role}: {content}\n"
    # Append the assistant's label to show model output should follow
    prompt += "Assistant:"
    return prompt

def get_generated_response_chat(input_messages):
    """
    Calls the gptAPI using the provided input_messages
    Returns the generated assistant response
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=input_messages,
            temperature=0.7  
        )
        generated = response.choices[0].message.content.strip()  # Use attribute access
        return generated
    except Exception as e:
        print("Error during ChatCompletion call:", e)
        return None


def compute_set_based_metrics(gen_keywords, ref_keywords):
    """
    Compute precision, recall, and F1 score on the set of keywords.
    """
    set_gen = set(gen_keywords)
    set_ref = set(ref_keywords)
    if not set_gen or not set_ref:
        return 0.0, 0.0, 0.0

    intersection = set_gen.intersection(set_ref)
    precision = len(intersection) / len(set_gen)
    recall = len(intersection) / len(set_ref)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1

# evaluation loop
def evaluate_validation_set():
    # Load already processed example indices to avoid duplicate API calls and costing extra money
    processed_indices = set()
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r", encoding="utf-8") as rf:
            for line in rf:
                try:
                    rec = json.loads(line)
                    if "example_index" in rec:
                        processed_indices.add(rec["example_index"])
                except json.JSONDecodeError:
                    continue

    # Load the validation dataset
    validation_examples = []
    with open(VALIDATION_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                example = json.loads(line)
                validation_examples.append(example)
            except json.JSONDecodeError:
                continue

    print(f"Total validation examples: {len(validation_examples)}")
    
    # Lists to accumulate corpus-level metrics
    filtered_generated_corpus = []
    filtered_reference_corpus = []
    precision_list = []
    recall_list = []
    f1_list = []
    sentence_bleu_filtered_list = []

    # Open results file in append mode
    with open(RESULTS_FILE, "a", encoding="utf-8") as out_f:
        for idx, example in enumerate(validation_examples):
            #check if its been processed if so skip to not incur more cost
            if idx in processed_indices:
                print(f"Skipping example {idx} (already processed).")
                continue

            messages = example.get("messages", [])
            if not messages or len(messages) < 2:
                print(f"Skipping example {idx} due to insufficient messages.")
                continue

            # Use all messages except the last one as input
            input_messages = messages[:-1]
            # The last message's content is the reference
            reference = messages[-1].get("content", "").strip()

            # Prepare prompt for logging
            prompt_str = format_prompt_from_messages(input_messages)
            
            # Generate response
            generated = get_generated_response_chat(input_messages)
            if generated is None:
                print(f"Error generating response for example {idx}. Skipping.")
                continue

            # Clean generated and reference queries
            generated_clean = clean_sql(generated)
            reference_clean = clean_sql(reference)

            # Extract keywords
            gen_keywords = extract_keywords(generated_clean)
            ref_keywords = extract_keywords(reference_clean)

            # Compute sequence-based BLEU on filtered keywords
            # Join the keywords into a string for sacreBLEU
            gen_keywords_str = " ".join(gen_keywords)
            ref_keywords_str = " ".join(ref_keywords)
            try:
                filtered_sentence_bleu = sacrebleu.sentence_bleu(gen_keywords_str, [ref_keywords_str]).score
            except Exception as e:
                print(f"Error computing filtered BLEU for example {idx}: {e}")
                filtered_sentence_bleu = None

            # Compute set-based precision, recall, and F1
            precision, recall, f1 = compute_set_based_metrics(gen_keywords, ref_keywords)

            # Accumulate for corpus-level metrics
            filtered_generated_corpus.append(gen_keywords_str)
            filtered_reference_corpus.append(ref_keywords_str)
            precision_list.append(precision)
            recall_list.append(recall)
            f1_list.append(f1)
            if filtered_sentence_bleu is not None:
                sentence_bleu_filtered_list.append(filtered_sentence_bleu)

            # Build result dictionary
            result = {
                "example_index": idx,
                "prompt": prompt_str,
                "reference": reference_clean,
                "generated": generated_clean,
                "extracted_gen_keywords": gen_keywords,
                "extracted_ref_keywords": ref_keywords,
                "filtered_sentence_bleu": filtered_sentence_bleu,
                "keywords_precision": precision,
                "keywords_recall": recall,
                "keywords_f1": f1
            }

            # Write result to file
            out_f.write(json.dumps(result) + "\n")
            out_f.flush()
            print(f"Processed example {idx}.")
            time.sleep(SLEEP_BETWEEN_CALLS)

    # Compute corpus-level filtered BLEU
    corpus_filtered_bleu = (
        sacrebleu.corpus_bleu(filtered_generated_corpus, [filtered_reference_corpus]).score
        if filtered_generated_corpus else None
    )
    avg_precision = sum(precision_list) / len(precision_list) if precision_list else 0.0
    avg_recall = sum(recall_list) / len(recall_list) if recall_list else 0.0
    avg_f1 = sum(f1_list) / len(f1_list) if f1_list else 0.0
    avg_sentence_bleu_filtered = (
        sum(sentence_bleu_filtered_list) / len(sentence_bleu_filtered_list)
        if sentence_bleu_filtered_list else None
    )

    summary = {
        "corpus_filtered_bleu": corpus_filtered_bleu,
        "average_keywords_precision": avg_precision,
        "average_keywords_recall": avg_recall,
        "average_keywords_f1": avg_f1,
        "average_filtered_sentence_bleu": avg_sentence_bleu_filtered,
        "total_examples": len(validation_examples),
        "processed_examples": len(filtered_generated_corpus)
    }

    # Save summary
    with open(SUMMARY_FILE, "w", encoding="utf-8") as sf:
        json.dump(summary, sf, indent=2)
    print("Evaluation complete. Summary:")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    evaluate_validation_set()
