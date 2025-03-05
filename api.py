from flask import Flask, request, jsonify
import os
import tempfile
from ModelClient import ModelClient
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Initialise open ai client 
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# the name of the model i fine tuned adn the paremeters to connect to a databsae server
fine_tuned_model = "ft:gpt-4o-mini-2024-07-18:personal::B3lHt6V9"
mysql_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "WorkplaceTest"
}

# Instantiate model client class which integrates the schema extraction and MySQL execution logic
model_client = ModelClient(openai_client, fine_tuned_model, mysql_config)

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
        # Directly pass the file object and filename to query
        sql_query = model_client.query(dataset_file, question, filename=dataset_file.filename)
        print("SQL Query generated:", sql_query)
        return jsonify({"query": sql_query})
    except Exception as e:
        print("Error during query generation:", e)
        return f"Generate Query Error: {str(e)}", 500

@app.route('/api/execute-query', methods=['POST'])
def execute_query():
    data = request.get_json()
    if not data or "query" not in data:
        return "No query provided", 400
    query = data["query"]

    try:
        # Execute the SQL query created by my model on the MySQL database
        results = model_client.run_query(query)
        return jsonify({"results": results})
    except Exception as e:
        return f"Execute Query Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, port = 5001)