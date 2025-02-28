from schemaExtract import extract_schema
import mysql.connector

class ModelClient:
    def __init__(self, client, model, mysql_config):
        """
        Initialise
        parameters:
        client: he OpenAI client
        model: name of fine-tuned model 
        mysql_config: dictionary with MySQL connection parameters
                    
        """
        self.client = client
        self.model = model
        self.mysql_config = mysql_config

    def get_mysql_connection(self):
        """Establish and return a MySQL connection using the given configuration"""
        try:
            conn = mysql.connector.connect(
                host=self.mysql_config["host"],
                user=self.mysql_config["user"],
                password=self.mysql_config["password"],
                database=self.mysql_config["database"]
            )
            return conn
        except mysql.connector.Error as err:
            print("MySQL connection error:", err)
            return None

    def query(self, dataset, user_question, max_tokens=150, temperature=0.0, stop=None, filename=None):
        """
        Extract the schema from the dataset (file path or uploaded file), append it to the system message to give context 
        then ask the model for a SQL query based on the user's question.
        parameters:
        dataset: File path OR uploaded file object
        user_question: The natural language question the user asks 
        max_tokens: max tokens in the response
        temperature: temp for the API call
        stop: stop tokens
        filename: The name of the uploaded file (needed for file objects)
    
        returns the created SQL query
        """
        # Extract schema from either file path or file object
        schema_context = (
            f"{extract_schema(dataset, filename=filename)}\n\n"
            "You are an expert SQL generator. Based on the above schema, generate a valid SQL query "
            "that answers the user's request. ONLY output the SQL query, nothing else."
        )

        # Create the messages list for the chat API
        messages = [
            {"role": "system", "content": schema_context},
            {"role": "user", "content": user_question}
        ]
    
        # Print the full prompt for debugging
        print("Full prompt sent to the model:")
        for msg in messages:
            print(f"{msg['role'].upper()}: {msg['content']}\n")

        # Query the fine-tuned model
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop
        )
    
        # Extract the SQL query from the response
        generated_sql = completion.choices[0].message.content  # this assumes the possibility of a list of choices so take the first
        print("Generated SQL Query:")
        print(generated_sql)
        return generated_sql

    def run_query(self, sql_query):
        """
        Execute the provided SQL query against the MySQL database and return the results
        parameters
        sql_query: The SQL query string
        Query results or an error message
        """
        conn = self.get_mysql_connection()
        if conn is None:
            return "MySQL connection failed."
        try:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            return results
        except Exception as e:
            return str(e)

if __name__ == "__main__":
    import os
    from openai import OpenAI

    # initialise the OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # name of fine tuned model
    fine_tuned_model = "ft:gpt-4o-mini-2024-07-18:personal::B3lHt6V9"
    
    # MySQL connection config
    mysql_config = {
        "host": "localhost",
        "user": "root",
        "password": "",
        "database": "WorkplaceTest"
    }
    
    # instantiate the ModelClient
    inference_client = ModelClient(client, fine_tuned_model, mysql_config)
    
    # dataset path
    dataset_path = "/Users/david/Downloads/WorkplaceTest.json"  # or "your_dataset.jsonl"
    
    # an example of a question
    user_question = "Find the first and last names and email of employees working in the human resources department"
    
    # make the SQL query using the fine-tuned model
    sql_query = inference_client.query(dataset_path, user_question)
    print("Generated SQL Query:")
    print(sql_query)
    
    # Execute and print the results
    results = inference_client.run_query(sql_query)
    print("MySQL Query Results:")
    print(results)
