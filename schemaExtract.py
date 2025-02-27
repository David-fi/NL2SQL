import os
import json
import pandas as pd

def extract_schema_from_json(file_path):
    """
    if the file is json:
    first read a JSON file containing multiple objects
    for each of the objects with "type": "table", take the table name and
    infer the schema from the first record in the "data" list.
    Returns a dictionary mapping table names to their schema dictionaries.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    schema_dict = {} #where the schema will be stored
    for record in data:
        if isinstance(record, dict) and record.get("type") == "table": #running the loop if the type in the directory is a table
            table_name = record.get("name") #get the name of the table
            table_data = record.get("data", []) #and then all the data too, if there inst any just an empty list
            if table_data:
                '''
                get the first element in the table which will in this case represent the schema
                then make a dictionary to go through the key value paris in the first row ^ 
                then maps each of the column names ti the type of the corresponding value
                then store and once all the records have been iterated through, return the complete dictionary
                '''
                first_row = table_data[0]
                table_schema = { key: type(value).__name__ for key, value in first_row.items() }
                schema_dict[table_name] = table_schema
    return schema_dict

def extract_schema_from_jsonl(file_path):
    """
    if the file is JSONL:
    Reads a JSONL file
    For each JSON object with "type": "table", it extracts the table name and
    infers the schema from the first record in the "data" list
    Returns a dictionary mapping table names to their schema dictionaries
    """
    schema_dict = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                if isinstance(record, dict) and record.get("type") == "table": #checks for table in the line 
                    table_name = record.get("name")
                    table_data = record.get("data", [])
                    if table_data:
                        first_row = table_data[0]
                        table_schema = { key: type(value).__name__ for key, value in first_row.items() }
                        schema_dict[table_name] = table_schema
    return schema_dict

def extract_schema_from_csv(file_path):
    """
    if the file is CSV:
    Reads a CSV file into a DataFrame
    Assumes the entire CSV is one table; the table name is derived from the file name
    It infers the schema by mapping pandas dtypes to simplified type names
    Returns a dictionary with a single key (the table name) and its column schema
    """
    table_name = os.path.splitext(os.path.basename(file_path))[0]
    df = pd.read_csv(file_path)
    schema = {}
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_integer_dtype(dtype):
            schema[col] = "int"
        elif pd.api.types.is_float_dtype(dtype):
            schema[col] = "float"
        else:
            schema[col] = "str"
    return {table_name: schema}

def extract_schema(file_path):
    """
    Determines the file type based on the extension and extracts the schema based on that 
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return extract_schema_from_csv(file_path)
    elif ext == ".jsonl":
        return extract_schema_from_jsonl(file_path)
    elif ext == ".json":
        return extract_schema_from_json(file_path)
    else:
        raise ValueError("Unsupported file format. Please use a CSV, JSONL, or JSON file.")

if __name__ == "__main__":
    # Replace with the path to your dataset file (CSV, JSONL, or JSON)
    dataset_path = "/Users/david/Downloads/WorkplaceTest.json"
    schema = extract_schema(dataset_path)
    print(json.dumps(schema, indent=2))
