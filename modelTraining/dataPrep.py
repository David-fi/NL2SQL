import json
import os
import logging

# Directories for the datasets
SPIDER_DIR = "/Users/david/Library/Mobile Documents/com~apple~CloudDocs/Documents/Documents – David’s MacBook Pro/university/year 3/Individual Project/dataSets/spider_data"
WIKISQL_DIR = "/Users/david/Library/Mobile Documents/com~apple~CloudDocs/Documents/Documents – David’s MacBook Pro/university/year 3/Individual Project/dataSets/wikiSQL"

# Output location for preprocessed data
OUTPUT_DATA_PATH = "/Users/david/Library/Mobile Documents/com~apple~CloudDocs/Documents/Documents – David’s MacBook Pro/university/year 3/Individual Project/dataSets/preprocessed_data.jsonl"

# Set up logging to help debugginh and tracking the script process 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

def load_public_dataset(dataset_dir):
    """
    Loads examples from all JSON files
    """
    examples = []
    #check if directory hasa dataset 
    if not os.path.exists(dataset_dir):
        logger.error(f"Directory not found: {dataset_dir}") 
        return examples
    for filename in os.listdir(dataset_dir): #iterate over the files 
        if filename.endswith(".json"): #check for json file 
            file_path = os.path.join(dataset_dir, filename)
            try:
                '''
                open and read the json file
                if the data is a list, extends exanpks with the whole list
                if its a directory look for data or examples keys and pulls out those values
                '''
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        examples.extend(data)
                    elif isinstance(data, dict):
                        for key in ["data", "examples"]:
                            if key in data:
                                examples.extend(data[key])
                                break
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}") #log errors 
    return examples

def main():
    logger.info("Starting preprocessing pipeline...")
    
    # Load examples from Spider and WikiSQL datasets.
    spider_examples = load_public_dataset(SPIDER_DIR)
    wikisql_examples = load_public_dataset(WIKISQL_DIR)
    logger.info(f"Loaded {len(spider_examples)} examples from Spider.") #so i know the number of examples loaded from each dataset
    logger.info(f"Loaded {len(wikisql_examples)} examples from WikiSQL.")
    
    all_examples = spider_examples + wikisql_examples #make one big list 

    # Add augmented examples.
    augmented_examples = [
        {
            "question": "List all departments located in New York.",
            "query": "SELECT department_name FROM departments WHERE location = 'New York';"
        },
        {
            "question": "Find the first and last names and email of employees working in the Sales department.",
            "query": ("SELECT e.first_name, e.last_name, e.email FROM employees e JOIN departments d "
                      "ON e.department_id = d.department_id WHERE d.department_name = 'Sales';")
        },
        {
            "question": "What is the total salary paid per department?",
            "query": ("SELECT d.department_name, SUM(s.amount) AS total_salary FROM salaries s JOIN employees e "
                      "ON s.employee_id = e.employee_id JOIN departments d ON e.department_id = d.department_id "
                      "GROUP BY d.department_name;")
        },
        {
            "question": "Retrieve order details and customer names for orders with a total amount greater than 500.",
            "query": ("SELECT o.order_id, c.first_name, c.last_name, o.total_amount FROM orders o JOIN customers c "
                      "ON o.customer_id = c.customer_id WHERE o.total_amount > 500;")
        },
        {
            "question": "Show all products in the Electronics category that are in stock.",
            "query": "SELECT product_name FROM products WHERE category = 'Electronics' AND stock > 0;"
        }
    ]
    
    all_examples.extend(augmented_examples)
    '''
    go trough all the examples
    extract teh question, and then either the query of an answer if the query isnt ther e
    skip examples which dont have a question answer combo, if so log it 
    then format the data to be put into the preprocessed dataset in the format that openAI api accepts 
    put these new datapoints in output data path and log if all is good 
    '''
    output_examples = []
    for idx, ex in enumerate(all_examples):
        question = ex.get("question", "").strip()
        query = ex.get("query", "").strip() or ex.get("answer", "").strip()
        if not question or not query:
            logger.warning(f"Example index {idx} missing question or query. Skipping.")
            continue
        output_examples.append({
            "messages": [
                {
                    "role": "system",
                    "content": "write an sql statement which will access the data requested by the users question without any extra conversation"
                },
                {"role": "user", "content": question},
                {"role": "assistant", "content": query}
            ]
        })
    
    logger.info(f"Processed {len(output_examples)} examples.")
    
    try:
        with open(OUTPUT_DATA_PATH, "w", encoding="utf-8") as outfile:
            for ex in output_examples:
                outfile.write(json.dumps(ex) + "\n")
        logger.info(f"Preprocessed data saved to {OUTPUT_DATA_PATH}")
    except Exception as e:
        logger.error(f"Failed to write preprocessed data: {e}")

if __name__ == "__main__":
    main() #execute 
