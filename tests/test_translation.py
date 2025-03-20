import pytest

def normalize_sql(sql):
    """Simple normalization: lowercase and collapse whitespace."""
    return " ".join(sql.strip().lower().split())

@pytest.mark.unit
@pytest.mark.parametrize("user_query, expected_sql", [
    (
      "List the names and emails of all employees in the Human Resources department",
      "SELECT first_name, last_name, email FROM employees WHERE department_id = (SELECT department_id FROM departments WHERE department_name = 'Human Resources');"
    ),
    (
      "Show all customers",
      "SELECT * FROM customers;"
    )
])
def test_simple_select_translation(nl_to_sql_model, user_query, expected_sql):
    """
    Test that the NL2SQL model client correctly translates natural language to SQL,
    based on the actual schema from WorkplaceTest.json.
    """
    import io
    # Create a dummy schema file from WorkplaceTest.json
    with open("WorkplaceTest.json", "r", encoding="utf-8") as f:
        schema_content = f.read()
    dummy_file = io.StringIO(schema_content)
    response = nl_to_sql_model.query(dummy_file, user_query, filename="WorkplaceTest.json")
    assert response.get("type") == "sql"
    generated_sql = response.get("query")
    assert normalize_sql(generated_sql) == normalize_sql(expected_sql)