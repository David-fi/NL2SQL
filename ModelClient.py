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
            "You are an expert SQL generator. Based on the above schema, generate a valid SQL query that answers the user's request. "
            "However, if the user's query is ambiguous or refers to data not available in the schema, instead of a SQL query, "
            "output a clarifying question asking the user for more details. ONLY output the SQL query or a clarifying question, nothing else."
            
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
        response_text = completion.choices[0].message.content.strip()
        print("Model response:")
        print(response_text)
    
        # if response starts with a phrase suggesting a clarification, treat it as ambiguous
        clarification_indicators = ["could you", "can you", "please clarify", "which", "do you mean", "ambiguous"]
        is_clarification = any(response_text.lower().startswith(ind) for ind in clarification_indicators)
    
        if is_clarification:
            return {"type": "clarification", "message": response_text}
        else:
            return {"type": "sql", "query": response_text}

    def run_query(self, sql_query, confirmed=False):
        """
        Execute the provided SQL query against the MySQL database and return the results
        parameters
        sql_query: The SQL query string
        Query results or an error message
        """
        conn = self.get_mysql_connection()
        if conn is None:
            return "MySQL connection failed."
        # Validation layer: check for dangerous keywords if not confirmed.
        if not confirmed:
            dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
            if any(keyword in sql_query.upper() for keyword in dangerous_keywords):
                return {"type": "confirmation", "message": "Warning: This query may be destructive and cause irreversible changes to your data. Please confirm if you want to proceed."}
        
        try:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            return results
        except Exception as e:
            error_message = str(e)
            # Check for common ambiguity errors 
            if "unknown column" in error_message.lower() or "ambiguous" in error_message.lower():
                return {"type": "clarification", "message": "The SQL query appears to be ambiguous. Could you please clarify which column or data element you meant?"}
            else:
                return {"type": "error", "message": error_message}

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
