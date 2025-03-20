import pytest
from modelDevelopment import execute_sql, get_mysql_connection

def test_execute_valid_sql():
    """
    Test executing a valid SQL query on a temporary table.
    """
    conn = get_mysql_connection()
    cursor = conn.cursor()
    # Create a temporary table and insert one record
    cursor.execute("CREATE TEMPORARY TABLE test_table (id INT, name VARCHAR(50));")
    cursor.execute("INSERT INTO test_table (id, name) VALUES (1, 'Alice');")
    conn.commit()
    query = "SELECT * FROM test_table;"
    results = execute_sql(query, conn)
    # Assert that the returned results match the expected data a list with one tuple containing (1, 'Alice')
    assert results == [(1, 'Alice')]
    cursor.close()
    conn.close()

def test_execute_invalid_sql():
    """
    Test executing an invalid SQL query that should be caught and returned as an error string.
    """
    conn = get_mysql_connection()
    query = "SELECT * FROM non_existent_table;"
    result = execute_sql(query, conn)
    # The function should return a string with an error message
    assert isinstance(result, str) and "non_existent_table" in result.lower()
    conn.close() 