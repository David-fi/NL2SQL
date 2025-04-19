from flask import Flask, request, jsonify
from flask_cors import CORS
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
from config import MySQLConfig

app = Flask(__name__) #create a flask instance, name being the same as the current module
CORS(app, origins=["http://localhost:3000"]) #enable cross origin resource, to let the react frontend call the flask api

# Initialise open ai client, creating an openai object
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# the name of the model i fine tuned adn the paremeters to connect to a databsae server
fine_tuned_model = "ft:gpt-4o-mini-2024-07-18:personal::B3lHt6V9"
#alternative of using the better (more expensive model)
#fine_tuned_model = "o3-mini-2025-01-31"

#default param for mysql connection to the database host, pulls from env
default_mysql_config = {
    "host": os.environ.get("DB_HOST", "mysql"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "root"),
    "database": os.environ.get("DB_NAME", "nl2sql_db")
}

# Instantiate model client class which integrates the schema extraction and MySQL execution logic
model_client = ModelClient(openai_client, fine_tuned_model)

@app.route('/api/generate-query', methods=['POST'])
def generate_query():
    print("Received request at /api/generate-query") #debugginf line
    # Check if the dataset file is uploaded
    if 'dataset' not in request.files:
        return "No dataset file provided", 400
    dataset_file = request.files['dataset'] #get the uploaded file from the request

    # Also check for a question
    question = request.form.get('question')
    if not question:
        return "No question provided", 400 #error if no question is present 
    try:
        sql_query = model_client.query(dataset_file, question, filename=dataset_file.filename)
        print("SQL Query generated:", sql_query) #ask the modelclient to produce an sql query using the model, the file for schema and query to know waht to translate
        return jsonify(sql_query) #generated query is returned in json format to display
    except SchemaMismatchError as sme:
    #known errorrs are logged and return an error response 
        logging.error("Schema mismatch error during query generation", exc_info=True)
        return jsonify({"type": "error", "message": str(sme)}), 400
    except Exception as e:
        logging.error("Unhandled error during query generation", exc_info=True)
        return jsonify({"type": "error", "message": f"Generate Query Error: {str(e)}"}), 500


@app.route('/api/execute-query', methods=['POST'])
def execute_query():
    data = request.get_json()
    if not data or "query" not in data: #ready the json and check for a key "query"
        return "No query provided", 400
    query = data["query"]
    #extract the query string and potentially a boolean which indicated the user confirms 
    confirmed = data.get("confirmed", False) 
    try:
        #execute the sql query made by my model 
        results = model_client.run_query(query, confirmed)
        #return the results of the query as a json
        return jsonify({"results": results})
    #log errors and respond to errors
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
    if host in ["localhost", "127.0.0.1"]:
        host = "mysql" #as in docker based environments, if the host is local host, default to mysql
    user = request.form.get("user", default_mysql_config["user"])
    password = request.form.get("password", default_mysql_config["password"])
    #check if the file with name "dataset" is in the request, if so retrieve it 
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

    newDatabaseCreated = False #used to run the drop dataset command or not 
    #create the database
    try:
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        #create the database in teh file in our host, so we can fetch results and search the data within the files 
        create_db_query = f"CREATE DATABASE {db_name};"
        cursor.execute(create_db_query)
        conn.commit()
        newDatabaseCreated = True
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_DB_CREATE_EXISTS:
            # Database already exists so flag remains False
            newDatabaseCreated = False
            # Update MySQLConfig with the existing database credentials
            MySQLConfig.update_config(host=host, user=user, password=password, database=db_name)
            return jsonify({
                "message": f"Database '{db_name}' is already present and did not need to be uploaded. Continue with your question.",
                "database": db_name,
                "newDatabaseCreated": newDatabaseCreated
            })
        else:
            logging.error("MySQL error during database creation", exc_info=True)
            return jsonify({"error": f"MySQL error: {err}"}), 500
        #if the databse already exists, skip the creation
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        #all scenarios close the DB connection to avoid resource leaks

    # Update the model client's configuration to use the new (or existing) database
    MySQLConfig.update_config(host=host, user=user, password=password, database=db_name)
    
    # Process dataset to generate and execute CREATE TABLE and INSERT queries so i can populate the database 
    if newDatabaseCreated:
        try:
            conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=db_name
            )
            if not conn.is_connected():
                return jsonify({"error": f"Failed to connect to MySQL database '{db_name}'. Please verify the server and database."}), 500
            cursor = conn.cursor()
            # Iterate through each record in the dataset JSON
            #reconned to the created databsae, then creating the tables within if it is accessible
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
                    #for each table in the schema, i build a CREATE TABLE statment, inferring the collumn types from the first row
                    # then inserting each row of data
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
            conn.commit() #all the create and insert operations go to the database
        except mysql.connector.Error as err:
            #in case of error when creating the tabls or inserting tthe data, roll back and output error
            conn.rollback()
            return jsonify({"error": f"MySQL error during table creation/insertion: {err}"}), 500
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
                #when done close the cursor and connection
        return jsonify({
            "message": "Dataset processed successfully.",
            "database": db_name,
            "newDatabaseCreated": newDatabaseCreated
        }) #pop up a massage telling the user that the database is ready

@app.route('/api/remove-dataset', methods=['POST'])
def remove_dataset():
    # Get credentials from form data
    host = request.form.get("host", default_mysql_config["host"])
    if host in ["localhost", "127.0.0.1"]:
        host = "mysql"
    user = request.form.get("user", default_mysql_config["user"])
    password = request.form.get("password", default_mysql_config["password"])
    
    # Get the flag indicating if the database was newly created
    new_db_flag = request.form.get("newDatabaseCreated", "false").lower() == "true"
    
    if 'dataset' not in request.files:
        return jsonify({"error": "No dataset file provided"}), 400
    dataset_file = request.files['dataset'] #read the credentials, check if the dataset was created, retrieve the dataset file
    
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
    
    #to drop the dataset, get the name from the db, check if it was created, if it was then safe to drop without comprimising data
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
    #tell the user that the db was removed
    return jsonify({"message": f"Database {db_name} has been dropped successfully."})

@app.route('/api/schema-preview', methods=['POST'])
def schema_preview():
    if 'dataset' not in request.files:
        return jsonify({"error": "No dataset file provided"}), 400
    dataset_file = request.files['dataset'] #check and retrieve the db file
    try:
        dataset_content = dataset_file.read().decode('utf-8')
        data = json.loads(dataset_content)
        preview = {}
        #for each table within the db, gather a few examples to user in the preview from each collumn
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
        return jsonify(preview) #return the data for preview, including the few samples per column
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) #start the flask development server on all the interfaces at port 5001
