import os
import json
import random
import logging
import mysql.connector

from openai import OpenAI
 #as per OpenAI documentation this is the key to do thinds like file uploads, fine-tuning jobs, and completions.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
from nltk.translate.bleu_score import sentence_bleu

logging.basicConfig(
    level=logging.DEBUG, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("model_development.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

#the base of themodel i am going to fine tune 
MODEL_NAME = "gpt-4o-mini-2024-07-18"

# Directories and file paths
DATA_DIR = '/Users/david/Library/Mobile Documents/com~apple~CloudDocs/Documents/Documents – David’s MacBook Pro/university/year 3/Individual Project/dataSets'
PREPROCESSED_FILE = os.path.join(DATA_DIR, "preprocessed_data.jsonl")
TRAIN_SPLIT_FILE = os.path.join(DATA_DIR, "train.jsonl")
VAL_SPLIT_FILE = os.path.join(DATA_DIR, "dev.jsonl")
TEST_SPLIT_FILE = os.path.join(DATA_DIR, "test.jsonl")
OUTPUT_TRAINING_FILE = os.path.join(DATA_DIR, "openai_train.jsonl")  # File for fine-tuning

def load_preprocessed_data(filepath):
    """
    Loads examples from a JSONL file
    logs if it does not exist or parse error
    returns list of example objects 
    """
    examples = []
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return examples
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            try:
                ex = json.loads(line)
                examples.append(ex)
            except Exception as e:
                logger.error(f"Error parsing line: {e}")
    return examples

def split_dataset(examples, train_ratio=0.8, dev_ratio=0.1, test_ratio=0.1, seed=42):
    """
    Randomly splits examples into train, dev, and test sets
    used a seed to be able to reproduce the split
    """
    if seed is not None:
        random.seed(seed)
    random.shuffle(examples)
    n = len(examples)
    train = examples[:int(train_ratio * n)]
    dev = examples[int(train_ratio * n):int((train_ratio + dev_ratio) * n)]
    test = examples[int((train_ratio + dev_ratio) * n):]
    return train, dev, test

def write_jsonl(data, filepath):
    '''
    write data to a jsonl file, each objecct new line 
    '''
    with open(filepath, "w", encoding="utf-8") as f:
        for ex in data:
            f.write(json.dumps(ex) + "\n")
    logger.info(f"Wrote {len(data)} examples to {filepath}")

def compute_bleu(reference, hypothesis):
    """
    Compute BLEU score between generated and knowncorrect SQL strings
    """
    ref_tokens = reference.split()
    hyp_tokens = hypothesis.split()
    return sentence_bleu([ref_tokens], hyp_tokens)

def execute_sql(query, connection):
    """
    Execute a SQL query in the database i set up in phpmyadmin.
    fetch the results and handle errors 
    """
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        return results
    except Exception as e:
        return str(e)

def get_mysql_connection():
    """
    Establish a MySQL connection
    """
    try:
        conn = mysql.connector.connect(
            host="localhost",         
            user="root",              
            password="",              
            database="WorkplaceTest"  
        )
        logger.info("MySQL connection established.")
        return conn
    except mysql.connector.Error as err:
        logger.error(f"MySQL connection error: {err}")
        return None

def main():
    logger.info("Starting model development pipeline...")

    # Load preprocessed examples from the file created in the data prep
    all_examples = load_preprocessed_data(PREPROCESSED_FILE)
    logger.info(f"Loaded {len(all_examples)} examples from preprocessed data.")

    # Split the dataset
    train_examples, dev_examples, test_examples = split_dataset(all_examples)
    logger.info(f"Dataset split: {len(train_examples)} train, {len(dev_examples)} dev, {len(test_examples)} test examples.")
    write_jsonl(train_examples, TRAIN_SPLIT_FILE)
    write_jsonl(dev_examples, VAL_SPLIT_FILE)
    write_jsonl(test_examples, TEST_SPLIT_FILE)

    # Use the training examples directly as the fine-tuning file
    write_jsonl(train_examples, OUTPUT_TRAINING_FILE)

    try:
        '''
        upload the training file to openai's server recordnig the file id 
        '''
        logger.info("Uploading training file to OpenAI...")
        training_file_resp = client.files.create(
            file=open(OUTPUT_TRAINING_FILE, "rb"),
            purpose="fine-tune"
        )
        training_file_id = training_file_resp.id
        logger.info(f"Uploaded training file: {training_file_id}")
    except Exception as e:
        logger.error(f"Failed to upload training file: {e}")
        return

    try:
        logger.info("Starting fine-tuning job...")
        # Create a supervised fine-tuning job with hyperparameters i chose from the openai docs
        fine_tune_resp = client.fine_tuning.jobs.create(
            training_file=training_file_id,
            model=MODEL_NAME,
            method={
                "type": "supervised",
                "supervised": {
                    "hyperparameters": {"n_epochs": 3, "learning_rate_multiplier": 0.1}
                }
            }
        )
        fine_tune_id = fine_tune_resp.id
        logger.info(f"Fine-tuning job started: {fine_tune_id}")
    except Exception as e:
        logger.error(f"Failed to start fine-tuning job: {e}")
        return

    def generate_sql(prompt):
        try:
            # Use the fine-tuned model if available, otherwise fallback to base model
            model_to_use = getattr(fine_tune_resp, "fine_tuned_model", MODEL_NAME)
            response = client.completions.create(
                model=model_to_use,
                prompt=prompt,
                max_tokens=150,
                temperature=0.0,
                stop=[""]
            )
            generated = response.choices[0].text.strip()
            return generated
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return ""

if __name__ == "__main__":
    main()
