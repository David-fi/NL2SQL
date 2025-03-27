from flask import Flask, request, jsonify
import os
from ModelClient import ModelClient, SchemaMismatchError, InvalidQueryError
from openai import OpenAI
from dotenv import load_dotenv
import logging
logging.basicConfig(level=logging.ERROR)
load_dotenv()
import mysql.connector
from mysql.connector import errorcode
import json

app = Flask(__name__)

# Initialise open ai client 
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# the name of the model i fine tuned adn the paremeters to connect to a databsae server
fine_tuned_model = "ft:gpt-4o-mini-2024-07-18:personal::B3lHt6V9"
#fine_tuned_model = "o3-mini-2025-01-31"

default_mysql_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "WorkplaceTest"
}

# Instantiate model client class which integrates the schema extraction and MySQL execution logic
model_client = ModelClient(openai_client, fine_tuned_model, default_mysql_config)

@app.route('/api/generate-query', methods=['POST'])
def generate_query():
    print("Received request at /api/generate-query")
    # Check if the dataset file is uploaded
    if 'dataset' not in request.files:
        return "No dataset file provided", 400
    dataset_file = request.files['dataset']

    # Also check for a question
    question = request.form.get('question')
    if not question:
        return "No question provided", 400
    try:
        sql_query = model_client.query(dataset_file, question, filename=dataset_file.filename)
        print("SQL Query generated:", sql_query)
        return jsonify(sql_query)
    except SchemaMismatchError as sme:
        logging.error("Schema mismatch error during query generation", exc_info=True)
        return jsonify({"type": "error", "message": str(sme)}), 400
    except Exception as e:
        logging.error("Unhandled error during query generation", exc_info=True)
        return f"Generate Query Error: {str(e)}", 500


@app.route('/api/execute-query', methods=['POST'])
def execute_query():
    data = request.get_json()
    if not data or "query" not in data:
        return "No query provided", 400
    query = data["query"]
    confirmed = data.get("confirmed", False)
    try:
        #execute the sql query made by my model 
        results = model_client.run_query(query, confirmed)
        return jsonify({"results": results})
    except InvalidQueryError as iqe:
        logging.error("Invalid query error during execution", exc_info=True)
        return jsonify({"type": "error", "message": str(iqe)}), 400
    except Exception as e:
        logging.error("Unhandled error during query execution", exc_info=True)
        return f"Execute Query Error: {str(e)}", 500
    
@app.route('/api/upload-dataset', methods=['POST'])
def upload_dataset():
    # Get credentials from form data (or fallback to defaults)
    host = request.form.get("host", default_mysql_config["host"])
    user = request.form.get("user", default_mysql_config["user"])
    password = request.form.get("password", default_mysql_config["password"])
    
    if 'dataset' not in request.files:
        return jsonify({"error": "No dataset file provided"}), 400
    dataset_file = request.files['dataset']
    
    # Read the dataset file and pull the database name
    try:
        dataset_content = dataset_file.read().decode('utf-8')
        dataset_file.seek(0)  # Reset pointer for more processing if needed
        data = json.loads(dataset_content)
        db_name = None
        # Look for the line with "type": "database" to extract the name
        for line in data:
            if line.get("type") == "database":
                db_name = line.get("name")
                break
        if not db_name:
            return jsonify({"error": "Database name not found in dataset"}), 400
    except Exception as e:
        logging.error("Error parsing dataset file", exc_info=True)
        return jsonify({"error": "Failed to parse dataset"}), 400

    newDatabaseCreated = False
    #create the database
    try:
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        create_db_query = f"CREATE DATABASE {db_name};"
        cursor.execute(create_db_query)
        conn.commit()
        newDatabaseCreated = True
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_DB_CREATE_EXISTS:
            # Database already exists so flag remains False
            newDatabaseCreated = False
            # Update the model client's configuration to use the existing database
            model_client.mysql_config = {
                "host": host,
                "user": user,
                "password": password,
                "database": db_name
            }
            return jsonify({
                "message": f"Database '{db_name}' is already present and did not need to be uploaded. Continue with your question.",
                "database": db_name,
                "newDatabaseCreated": newDatabaseCreated
            })
        else:
            logging.error("MySQL error during database creation", exc_info=True)
            return jsonify({"error": f"MySQL error: {err}"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

    # Update the model client's configuration to use the new (or existing) database
    model_client.mysql_config = {
        "host": host,
        "user": user,
        "password": password,
        "database": db_name
    }
    
    # Process dataset to generate and execute CREATE TABLE and INSERT queries so i can populate the database 
    if newDatabaseCreated:
        try:
            conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=db_name
            )
            cursor = conn.cursor()
            # Iterate through each record in the dataset JSON
            for record in data:
                if record.get("type") == "table":
                    table_name = record.get("name")
                    table_data = record.get("data", [])
                    if not table_name or not table_data:
                        continue
                    # get schema from the first row
                    first_row = table_data[0]
                    columns_definitions = []
                    for col, val in first_row.items():
                        if isinstance(val, int):
                            col_type = "INT"
                        elif isinstance(val, float):
                            col_type = "DOUBLE"
                        else:
                            col_type = "VARCHAR(255)"
                        columns_definitions.append(f"`{col}` {col_type}")
                    columns_sql = ", ".join(columns_definitions)
                    create_table_query = f"CREATE TABLE IF NOT EXISTS `{table_name}` ({columns_sql});"
                    cursor.execute(create_table_query)

                    # Insert data rows
                    for row in table_data:
                        columns = ", ".join(f"`{col}`" for col in row.keys())
                        values_list = []
                        for val in row.values():
                            if isinstance(val, str):
                                escaped_val = val.replace("'", "''")
                                values_list.append(f"'{escaped_val}'")
                            elif val is None:
                                values_list.append("NULL")
                            else:
                                values_list.append(str(val))
                        values = ", ".join(values_list)
                        insert_query = f"INSERT INTO `{table_name}` ({columns}) VALUES ({values});"
                        cursor.execute(insert_query)
            conn.commit()
        except mysql.connector.Error as err:
            conn.rollback()
            return jsonify({"error": f"MySQL error during table creation/insertion: {err}"}), 500
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        return jsonify({
            "message": "Dataset processed successfully.",
            "database": db_name,
            "newDatabaseCreated": newDatabaseCreated
        })

@app.route('/api/remove-dataset', methods=['POST'])
def remove_dataset():
    # Get credentials from form data
    host = request.form.get("host", default_mysql_config["host"])
    user = request.form.get("user", default_mysql_config["user"])
    password = request.form.get("password", default_mysql_config["password"])
    
    # Get the flag indicating if the database was newly created
    new_db_flag = request.form.get("newDatabaseCreated", "false").lower() == "true"
    
    if 'dataset' not in request.files:
        return jsonify({"error": "No dataset file provided"}), 400
    dataset_file = request.files['dataset']
    
    try:
        dataset_content = dataset_file.read().decode('utf-8')
        data = json.loads(dataset_content)
        db_name = None
        for line in data:
            if line.get("type") == "database":
                db_name = line.get("name")
                break
        if not db_name:
            return jsonify({"error": "Database name not found in dataset"}), 400
    except Exception as e:
        logging.error("Error parsing dataset file during removal", exc_info=True)
        return jsonify({"error": "Failed to parse dataset"}), 400

    # Instead of erroring out if the database already existed, just skip removal
    if not new_db_flag:
        return jsonify({"message": "No removal needed: the database was not created by this system."})
    
    try:
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        drop_db_query = f"DROP DATABASE {db_name};"
        cursor.execute(drop_db_query)
        conn.commit()
    except mysql.connector.Error as err:
        logging.error("MySQL error during DROP DATABASE", exc_info=True)
        return jsonify({"error": f"MySQL error during DROP DATABASE: {err}"}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
    
    return jsonify({"message": f"Database {db_name} has been dropped successfully."})

@app.route('/api/schema-preview', methods=['POST'])
def schema_preview():
    if 'dataset' not in request.files:
        return jsonify({"error": "No dataset file provided"}), 400
    dataset_file = request.files['dataset']
    try:
        dataset_content = dataset_file.read().decode('utf-8')
        data = json.loads(dataset_content)
        preview = {}
        for record in data:
            if record.get("type") == "table":
                table_name = record["name"]
                table_data = record.get("data", [])
                if table_data:
                    column_samples = {}
                    for col in table_data[0].keys():
                        unique_vals = list({row[col] for row in table_data if row.get(col) is not None})
                        column_samples[col] = unique_vals[:3]
                    preview[table_name] = column_samples
        return jsonify(preview)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    app.run(debug=True, port = 5001)