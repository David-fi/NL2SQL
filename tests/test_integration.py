import pytest
import io
import mysql.connector

# Fixture to set up a test Orders table with known data.
@pytest.fixture(scope="module")
def setup_test_db():
    conn = mysql.connector.connect(host="localhost", user="root", password="", database="WorkplaceTest")
    cursor = conn.cursor()
    # set up a clean test table
    cursor.execute("DROP TABLE IF EXISTS Orders;")
    cursor.execute("""
        CREATE TABLE Orders (
            order_id INT PRIMARY KEY,
            order_date DATE
        );
    """)
    # Insert some known test data: one order in 2020 and one in 2021
    cursor.execute("INSERT INTO Orders (order_id, order_date) VALUES (1, '2020-05-15');")
    cursor.execute("INSERT INTO Orders (order_id, order_date) VALUES (2, '2021-07-20');")
    conn.commit()
    yield conn
    # drop the test table
    cursor.execute("DROP TABLE Orders;")
    conn.commit()
    cursor.close()
    conn.close()

def test_end_to_end_query_execution(nl_to_sql_model, setup_test_db):
    """
    End-to-end test so given a natural language query, the model returns SQL,
    which is then executed on the test Orders table
    """
    # Create a dummy JSON schema file for the Orders table
    dummy_schema_json = '[{"type": "table", "name": "Orders", "data": [{"order_id": 1, "order_date": "2020-05-15"}]}]'
    dummy_file = io.StringIO(dummy_schema_json)
    user_query = "How many orders were placed in 2020?"
    response = nl_to_sql_model.query(dummy_file, user_query, filename="dummy.json")
    assert response.get("type") == "sql"
    generated_sql = response.get("query")
    
    # Execute the generated SQL against the test database
    cursor = setup_test_db.cursor()
    cursor.execute(generated_sql)
    results = cursor.fetchall()
    #expect a count of 1 (only one order in 2020)
    assert results == [(1,)]
    cursor.close()