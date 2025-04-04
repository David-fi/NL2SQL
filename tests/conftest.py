import pytest
import mysql.connector
import logging
import json

# Configure structured logging to file
logger = logging.getLogger("nl2sql_tests")
logger.setLevel(logging.INFO) #record info, warning, error and critical messages
file_handler = logging.FileHandler("test_results.log") #write the reports in this file
logger.addHandler(file_handler)

# Global list to store test results for later insertion into the DB
test_results = []

#pytest hook to add custom command line option, so that i can configure the tests
#using this i can override the database configurations when running the tests, if nothing is entered go to the defaults entered
def pytest_addoption(parser):
    parser.addoption("--db_host", action="store", default="localhost", help="MySQL database host")
    parser.addoption("--db_user", action="store", default="root", help="MySQL database user")
    parser.addoption("--db_password", action="store", default="", help="MySQL database password")
    parser.addoption("--db_name", action="store", default="nl2sql_tests", help="MySQL database name")


@pytest.fixture(scope="session") #only create one fixture per session
def db_connection(request): #connect to databse
    #use the command lines for the db configuration
    host = request.config.getoption("--db_host")
    user = request.config.getoption("--db_user")
    password = request.config.getoption("--db_password")
    db_name = request.config.getoption("--db_name")
    conn = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=db_name
    )
    yield conn
    conn.close() #close the connection after all the tests 

#to save costs from the api call i made this class to simulates the behavior of an API for generating sql queries
class DummyChatCompletions:
    def create(self, **kwargs): #simulate sending a request to the api
        # hold the message content 
        class DummyMessage:
            def __init__(self, content):
                self.content = content
        #wraps the message
        class DummyChoice:
            def __init__(self, message):
                self.message = message
        #contains a list of the dummychoice objects
        class DummyResponse:
            def __init__(self, message):
                self.choices = [DummyChoice(DummyMessage(message))]
                
        messages = kwargs.get("messages", [])
        #mimic what it would be like to receive the response sql from the ai model
        user_message = messages[1].get("content", "").lower() if len(messages) > 1 else ""
        if "orders" in user_message:
            response_message = "SELECT COUNT(*) FROM Orders WHERE YEAR(order_date) = 2020;"
        elif "human resources" in user_message:
            response_message = (
                "SELECT first_name, last_name, email FROM employees "
                "WHERE department_id = (SELECT department_id FROM departments WHERE department_name = 'Human Resources');"
            )
        elif "customers" in user_message:
            response_message = "SELECT * FROM customers;"
        else:
            response_message = "SELECT * FROM dummy;"
        return DummyResponse(response_message)

class DummyChat:
    def __init__(self):
        self.completions = DummyChatCompletions()

class DummyOpenAIForIntegration:
    def __init__(self):
        self._chat = DummyChat()  # create an instance of DummyChat

    @property
    def chat(self):
        return self._chat


@pytest.fixture(scope="session") #session scoped fixture again
def dummy_openai_client():
    return DummyOpenAIForIntegration()

@pytest.fixture(scope="session")
def nl_to_sql_model(dummy_openai_client):
    from backend.ModelClient import ModelClient #imports the model client class where i connect the functions to translate nl to sql 
    fake_model = "dummy-model" #dummy model identifier
    #some dummy mysql configurations
    dummy_mysql_config = {
        "host": "localhost",
        "user": "root",
        "password": "",
        "database": "WorkplaceTest"
    }
    return ModelClient(dummy_openai_client, fake_model, dummy_mysql_config)

# Pytest hook to record test outcome after each test call
def pytest_runtest_logreport(report):
    if report.when == "call": #check if the report and the call correspond
        outcome = "passed" if report.passed else "failed" #the determiner for fail or pass
        test_results.append({
            "test_case_id": report.nodeid,
            "outcome": outcome,
            "duration": report.duration
        })

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    host = config.getoption("--db_host")
    user = config.getoption("--db_user")
    password = config.getoption("--db_password")
    db_name = config.getoption("--db_name")
    try:
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=db_name
        )
        cursor = conn.cursor()
        insert_sql = """
        INSERT INTO test_results 
        (test_case_id, input_query, expected_sql, generated_sql, execution_success, bleu_score, error_message) 
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        #loop over results, 
        for result in test_results: 
            test_case_id = result["test_case_id"] 
            input_query = ""
            expected_sql = ""
            generated_sql = ""
            execution_success = 1 if result["outcome"] == "passed" else 0
            bleu_score = None
            error_message = ""
            #executes the insert statements for each of the test results with its values
            cursor.execute(insert_sql, (
                test_case_id,
                input_query,
                expected_sql,
                generated_sql,
                execution_success,
                bleu_score,
                error_message
            ))
        conn.commit() #store in the dataset
        cursor.close()
        conn.close()
        logger.info("Test results successfully logged to MySQL.")
    except Exception as e:
        logger.error("Error logging test results to MySQL: " + str(e))