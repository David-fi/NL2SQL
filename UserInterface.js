import React, { useState, useEffect } from "react";
import Downshift from 'downshift';
import {matchSorter} from 'match-sorter';

function App() {
  // initialises a bunch of states 
  const [dataset, setDataset] = useState(null); //for the dataset upload
  const [question, setQuestion] = useState(""); // the question the user asks is stored here
  const [generatedSQL, setGeneratedSQL] = useState(""); //the models query 
  const [results, setResults] = useState(""); //the results from running the query 
  const [loading, setLoading] = useState(false); // boolean for if the api request is in progress
  const [error, setError] = useState(""); //to display the error message
  // some states for clarrification handling
  const [showClarificationModal, setShowClarificationModal] = useState(false);
  const [clarificationMessage, setClarificationMessage] = useState("");
  const [clarificationInput, setClarificationInput] = useState("");

  // State for dangerous query confirmation modal
  const [showConfirmationModal, setShowConfirmationModal] = useState(false);
  const [confirmationMessage, setConfirmationMessage] = useState("");

  // States for phpMyAdmin credentials and controlling the credentials 
  const [phpHost, setPhpHost] = useState("localhost");
  const [phpUser, setPhpUser] = useState("root");
  const [phpPassword, setPhpPassword] = useState("");
  const [showCredentialsModal, setShowCredentialsModal] = useState(true);
  
  // State to store the newDatabaseCreated flag from dataset upload
  const [newDatabaseCreated, setNewDatabaseCreated] = useState(false);
  const [selectedSchemaFilters, setSelectedSchemaFilters] = useState([]);

  const [enableFormatting, setEnableFormatting] = useState(true);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: "asc" });
  const [columnFilters, setColumnFilters] = useState({});

  const [schemaPreview, setSchemaPreview] = useState({});
  const [showSchemaSidebar, setShowSchemaSidebar] = useState(true);
  const [autocompleteEnabled, setAutocompleteEnabled] = useState(true);
  
  // event handles
  const handleDatasetChange = (e) => {
    setDataset(e.target.files[0]); //updata the dataset state with the file which is uploaed in the upload section
  };

  const handleSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
  };

  // Upload dataset by calling the /api/upload-dataset endpoint
  const handleDatasetUpload = async () => {
    if (!dataset) {
      setError("Please select a dataset file to upload.");
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("dataset", dataset);
      formData.append("host", phpHost);
      formData.append("user", phpUser);
      formData.append("password", phpPassword);
      
      const response = await fetch("/api/upload-dataset", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || "Dataset upload failed.");
        setDataset(null); // Clear the invalid dataset
        return;
      } else {
        setError("");
        setNewDatabaseCreated(data.newDatabaseCreated);
        const schemaForm = new FormData();
        schemaForm.append("dataset", dataset);
        const previewResponse = await fetch("/api/schema-preview", {
          method: "POST",
          body: schemaForm
        });
        const previewData = await previewResponse.json();
        setSchemaPreview(previewData);
        alert(data.message);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Remove dataset by calling the /api/remove-dataset endpoint
  const handleRemoveDataset = async () => {
    if (!dataset) {
      setError("No dataset to remove.");
      return;
    }
    if (!window.confirm("Are you sure you want to remove the dataset? This will drop the database if it was created by this system.")) {
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("dataset", dataset);
      formData.append("host", phpHost);
      formData.append("user", phpUser);
      formData.append("password", phpPassword);
      formData.append("newDatabaseCreated", newDatabaseCreated);
      
      const response = await fetch("/api/remove-dataset", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || "Dataset removal failed.");
      } else {
        setError("");
        alert(data.message);
        setDataset(null);
        setSchemaPreview({});
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleQuestionChange = (e) => {
    setQuestion(e.target.value); //by setting the question state to the input in the text area
  };

  const handleSubmit = async (e) => { //asynchronous function handles the form submission
    e.preventDefault(); //to prevent refreshing of the page i stop the default form submission behaviour
    //reset following states
    setError("");
    setGeneratedSQL("");
    setResults("");
    //as a dataset and question is needed to work, send an error if these are not present
    if (!dataset) {
      setError("Please upload a dataset file.");
      return;
    }
    if (!question) {
      setError("Please enter a question.");
      return;
    }
    setLoading(true); //indicating the process has started
    try {
      // Prepare form data with the persisted dataset and the question
      const formData = new FormData(); 
      //appedning the file and question to the formdata obeject so that it can be sent together to the server
      formData.append("dataset", dataset);
      formData.append("question", question);

      // Call API to generate SQL query
      const genResponse = await fetch("/api/generate-query", {
        method: "POST", //send a post request to the generate query api endepoint 
        body: formData,
      });
      if (!genResponse.ok) {//throw an error if response is not ok
        let errorMsg = "";
        try {
          const errorJson = await genResponse.json();
          // If the server returned { "type": "error", "message": "..."},
          // we can grab that message directly
          errorMsg = errorJson.message || "Unknown error occurred.";
        } catch (jsonParseError) {
          // If parsing fails (not valid JSON), fall back to plain text
          errorMsg = await genResponse.text();
        }
        throw new Error(`Execute Query Error: ${errorMsg}`);
      }
      //update the generateSQL state to the response from the api
      const genData = await genResponse.json();
      // Check if the response is a clarification prompt
      if (genData.type === "clarification") {
        // Display clarifying question to the user
        setClarificationMessage(genData.message);
        setShowClarificationModal(true);
      } else if (genData.type === "sql") {
        const sqlQuery = genData.query;
        setGeneratedSQL(sqlQuery);
  
        // Call API to execute the generated SQL query
        const execResponse = await fetch("/api/execute-query", {
          method: "POST", //send a post to the execute query endpoint woth the generated sql 
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ query: sqlQuery }),
        });
        if (!execResponse.ok) { //throw error if response is not ok
          const errorMsg = await execResponse.text();
          throw new Error(`Execute Query Error: ${errorMsg}`);
        }
        const execData = await execResponse.json();
        if (execData.results && execData.results.type === "confirmation") {
          setConfirmationMessage(execData.results.message);
          setShowConfirmationModal(true);
        } else {
          setResults(execData.results);
        }
      }
    } catch (err) {
      setError(err.message); //if error happens in the api call its caught 
    } finally {
      setLoading(false);
    }
  };

  // called when the user clicks "Apply Clarification"
  const applyClarification = () => {
    // append the user’s clarification input to the original question
    const updatedQuestion = question + " " + clarificationInput;
    setQuestion(updatedQuestion);
    setShowClarificationModal(false);
    setClarificationInput("");
    resubmitQuery(updatedQuestion);
  };

  // function to resubmit the query with the updated question
  const resubmitQuery = async (updatedQuestion) => {
    setError("");
    setGeneratedSQL("");
    setResults("");
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append("dataset", dataset);
      formData.append("question", updatedQuestion);

      const genResponse = await fetch("/api/generate-query", {
        method: "POST",
        body: formData,
      });
      if (!genResponse.ok) {
        const errorMsg = await genResponse.text();
        throw new Error(`Generate Query Error: ${errorMsg}`);
      }
      const genData = await genResponse.json();

      if (genData.type === "clarification") {
        setClarificationMessage(genData.message);
        setShowClarificationModal(true);
      } else if (genData.type === "sql") {
        const sqlQuery = genData.query;
        setGeneratedSQL(sqlQuery);

        const execResponse = await fetch("/api/execute-query", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ query: sqlQuery }),
        });
                if (!execResponse.ok) {
                    let errorMsg = "";
                    try {
                      const errorJson = await execResponse.json();
                      errorMsg = errorJson.message || "Unknown error occurred.";
                    } catch (jsonParseError) {
                      errorMsg = await execResponse.text();
                    }
                    throw new Error(`Execute Query Error: ${errorMsg}`);
                  }
        const execData = await execResponse.json();
        if (execData.results && execData.results.type === "confirmation") {
          setConfirmationMessage(execData.results.message);
          setShowConfirmationModal(true);
        } else {
          setResults(execData.results);
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

   // Execute dangerous query after user confirms.
   const executeConfirmedQuery = async () => {
    setError("");
    setLoading(true);
    try {
      const execResponse = await fetch("/api/execute-query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: generatedSQL, confirmed: true }),
      });
      if (!execResponse.ok) {
        const errorMsg = await execResponse.text();
        throw new Error(`Execute Query Error: ${errorMsg}`);
      }
      const execData = await execResponse.json();
      setResults(execData.results);
      setShowConfirmationModal(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

   // Save credentials and close the modal
   const saveCredentials = () => {
    setShowCredentialsModal(false);
  };

  useEffect(() => {
    const savedSort = localStorage.getItem("sortConfig");
    if (savedSort) {
      setSortConfig(JSON.parse(savedSort));
    }
  }, []);
  
  useEffect(() => {
    localStorage.setItem("sortConfig", JSON.stringify(sortConfig));
  }, [sortConfig]);

  const handleColumnClick = (col, table) => {
    const filterText = `In the column ${col} of table ${table}`;
    const updated = selectedSchemaFilters.includes(filterText)
      ? selectedSchemaFilters
      : [...selectedSchemaFilters, filterText];
    setSelectedSchemaFilters(updated);
    setQuestion(prev => {
      const stripped = prev.replace(/^(From table .*?\.\s*)*(In the column .*?\.\s*)*/g, "").trim();
      return `${updated.join(". ").replace(/\.\s/g, ". and ")}. ${stripped}`;
    });
  };

  return (
    <div style={{ 
      maxWidth: "1000px", 
      margin: "40px auto", 
      padding: "30px", 
      fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif", 
      backgroundColor: "#f9f9fb", 
      borderRadius: "10px", 
      boxShadow: "0 2px 10px rgba(0,0,0,0.1)" 
    }}>
      <h1 style={{
        color: "#333",
        borderBottom: "2px solid #ddd",
        paddingBottom: "10px",
        marginBottom: "20px"
      }}>
        NL2SQL Interface
      </h1>
      {/* Credentials Modal */}
      {showCredentialsModal && (
        <div style={{
          position: "fixed",
          top: 0, left: 0, width: "100%", height: "100%",
          backgroundColor: "rgba(0,0,0,0.5)",
          display: "flex", justifyContent: "center", alignItems: "center",
          zIndex: 3000
        }}>
          <div style={{ backgroundColor: "#fff", padding: "20px", borderRadius: "8px", width: "400px" }}>
            <h2>phpMyAdmin Credentials</h2>
            <p>Please enter your phpMyAdmin login details. For default values, simply continue.</p>
            <div>
              <label>Host:</label>
              <input type="text" value={phpHost} onChange={(e) => setPhpHost(e.target.value)} style={{ width: "100%", marginBottom: "10px" }} />
            </div>
            <div>
              <label>User:</label>
              <input type="text" value={phpUser} onChange={(e) => setPhpUser(e.target.value)} style={{ width: "100%", marginBottom: "10px" }} />
            </div>
            <div>
              <label>Password:</label>
              <input type="password" value={phpPassword} onChange={(e) => setPhpPassword(e.target.value)} style={{ width: "100%", marginBottom: "10px" }} />
            </div>
            <button onClick={saveCredentials}
              style={{
                backgroundColor: "#1976d2",
                color: "white",
                border: "none",
                borderRadius: "6px",
                padding: "8px 16px",
                fontSize: "14px",
                fontWeight: "500",
                cursor: "pointer",
                boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
                transition: "all 0.2s ease-in-out"
              }}
              onMouseOver={(e) => (e.target.style.backgroundColor = "#1565c0")}
              onMouseOut={(e) => (e.target.style.backgroundColor = "#1976d2")}
            >Save</button>
          </div>
        </div>
      )}

      {/* left Credentials Button */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        //alignItems: "flex-start",
        marginBottom: "10px"
      }}>
      <div> 
        <button onClick={() => setShowCredentialsModal(true)}
              style={{
                backgroundColor: "#1976d2",
                color: "white",
                border: "none",
                borderRadius: "6px",
                padding: "8px 16px",
                fontWeight: "500",
                cursor: "pointer",
                boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
                transition: "all 0.2s ease-in-out"
              }}
              onMouseOver={(e) => (e.target.style.backgroundColor = "#1565c0")}
              onMouseOut={(e) => (e.target.style.backgroundColor = "#1976d2")}
          >Edit phpMyAdmin Credentials</button>
      </div>      
      
      {/* Dataset Upload Section */}
      <div
        style={{
      flex: "1",
      border: "1px solid #e0e0e0",
      padding: "15px",
      borderRadius: "10px",
      backgroundColor: "#ffffff",
      maxWidth: "280px",
      boxShadow: "0 2px 6px rgba(0,0,0,0.05)",
      fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
        }}
      >
        <h3 style={{ fontSize: "16px", fontWeight: "600", color: "#333", marginBottom: "12px" }}>
          Dataset Upload (json file)
        </h3>
        {dataset ? (
          <div>
            <p>
              <strong>Uploaded File:</strong> {dataset.name}
            </p>
            <p style={{ fontStyle: "italic", color: "#333" }}>
              Remember to click "Upload Dataset".
            </p>
            <button onClick={handleRemoveDataset}
                style={{
                  backgroundColor: "#1976d2",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  padding: "8px 16px",
                  fontWeight: "500",
                  cursor: "pointer",
                  boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
                  transition: "all 0.2s ease-in-out"
                }}
                onMouseOver={(e) => (e.target.style.backgroundColor = "#1565c0")}
                onMouseOut={(e) => (e.target.style.backgroundColor = "#1976d2")}
            >Remove Dataset</button>
          </div>
        ) : (
          <div>
            <input type="file" accept=".json,.jsonl,.csv" onChange={handleDatasetChange} />
            <p style={{ fontStyle: "italic", color: "#333", marginTop: "10px" }}>
              After selecting your file, click "Upload Dataset".
            </p>
          </div>
        )}
        <div style={{ marginTop: "10px" }}>
          <button onClick={handleDatasetUpload} disabled={!dataset || loading}
          style={{
            backgroundColor: "#1976d2",
            color: "white",
            border: "none",
            borderRadius: "6px",
            padding: "8px 16px",
            fontWeight: "500",
            cursor: "pointer",
            boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
            transition: "all 0.2s ease-in-out"
          }}
          onMouseOver={(e) => (e.target.style.backgroundColor = "#1565c0")}
          onMouseOut={(e) => (e.target.style.backgroundColor = "#1976d2")}
          >
            {loading ? "Uploading..." : "Upload Dataset"}
          </button>
        </div>
      </div>
    </div>

      <div>
      <button
        onClick={() => setShowSchemaSidebar(!showSchemaSidebar)}
        style={{
          marginBottom: "10px",
          backgroundColor: "#e0f7fa",
          border: "1px solid #b2ebf2",
          borderRadius: "20px",
          padding: "6px 12px",
          fontSize: "13px",
          fontWeight: "500",
          color: "#00796b",
          cursor: "pointer",
          transition: "background-color 0.2s ease-in-out"
        }}
        onMouseOver={(e) => (e.target.style.backgroundColor = "#b2ebf2")}
        onMouseOut={(e) => (e.target.style.backgroundColor = "#e0f7fa")}
      >
        {showSchemaSidebar ? "Hide Schema Overview" : "Show Schema Overview"}
      </button>
      {selectedSchemaFilters.length > 0 && (
        <button
          onClick={() => {
            setSelectedSchemaFilters([]);
            setQuestion(prev => {
              const allFilterPatterns = selectedSchemaFilters.map(f => f.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
              const combinedRegex = new RegExp(`\\b(${allFilterPatterns.join('|')})\\.\\s*`, "g");
              return prev.replace(combinedRegex, "").trim();
            });
          }}
          style={{
            marginBottom: "10px",
            backgroundColor: "#ffebee",
            border: "1px solid #ef9a9a",
            borderRadius: "20px",
            padding: "6px 12px",
            fontSize: "13px",
            fontWeight: "500",
            color: "#c62828",
            cursor: "pointer",
            transition: "background-color 0.2s ease-in-out"
          }}
          onMouseOver={(e) => (e.target.style.backgroundColor = "#ffcdd2")}
          onMouseOut={(e) => (e.target.style.backgroundColor = "#ffebee")}
        >
          Clear Schema Filters
        </button>
      )}
        {showSchemaSidebar && (
          <div style={{
            border: "1px solid #ddd",
            borderRadius: "10px",
            padding: "15px",
            backgroundColor: "#fff",
            marginBottom: "20px",
            maxHeight: "300px",
            overflowY: "auto"
          }}>
            <h3 style={{ marginTop: 0 }}>📊 Schema Overview</h3>
            {Object.keys(schemaPreview).length === 0 ? (
              <p style={{ fontStyle: "italic", color: "#555" }}>
                Please upload a dataset to view its structure.
              </p>
            ) : (
              Object.entries(schemaPreview).map(([table, columns]) => (
                <div key={table} style={{ marginBottom: "15px" }}>
                  <h4
                    style={{ marginBottom: "6px", color: "#1976d2", cursor: "pointer" }}
                    onClick={() => {
                      const filterText = `From table ${table}`;
                    const updated = selectedSchemaFilters.includes(filterText)
                      ? selectedSchemaFilters
                      : [...selectedSchemaFilters, filterText];
                      setSelectedSchemaFilters(updated);
                      setQuestion(prev => {
                        const stripped = prev.replace(/^(From table .*?\.\s*)*(In the column .*?\.\s*)*/g, "").trim();
                        return `${updated.join(". ").replace(/\.\s/g, ". and ")}. ${stripped}`;
                      });
                    }}
                  >
                    📁 {table}
                  </h4>
                  <table style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    marginBottom: "10px"
                  }}>
                    <thead>
                      <tr>
                        <th style={{
                          textAlign: "left",
                          padding: "6px",
                          borderBottom: "1px solid #ccc"
                        }}>Column</th>
                        <th style={{
                          textAlign: "left",
                          padding: "6px",
                          borderBottom: "1px solid #ccc"
                        }}>Examples</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(columns).map(([col, vals], idx) => (
                        <tr key={idx}>
                          <td
                            style={{ padding: "6px", borderBottom: "1px solid #eee", cursor: "pointer", color: "#1976d2" }}
                            onClick={() => handleColumnClick(col, table)}
                          >
                            {col}
                          </td>
                          <td
                            style={{ padding: "6px", borderBottom: "1px solid #eee", color: "#555", cursor: "pointer" }}
                            onClick={() => handleColumnClick(col, table)}
                          >
                            {vals.length > 0 ? vals.join(", ") : "No examples"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))
            )}
          </div>
        )}
      </div>
      {/* Question Form Section */}
      <form onSubmit={handleSubmit} style={{ marginTop: "10px" }}>
      <div>
        <label>Ask your question about the data bellow:</label>
        <div style={{ position: "relative" }}>
          {selectedSchemaFilters.length > 0 && (
            <div style={{ marginBottom: "10px", display: "flex", flexWrap: "wrap", gap: "8px" }}>
              {selectedSchemaFilters.map((filter, index) => (
                <span key={index} style={{
                  display: "inline-flex",
                  alignItems: "center",
                  backgroundColor: "#e0f7fa",
                  borderRadius: "16px",
                  padding: "6px 10px",
                  fontSize: "13px",
                  color: "#00796b",
                  border: "1px solid #b2ebf2"
                }}>
              <span dangerouslySetInnerHTML={{ __html: filter }} />
                  <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                      const updated = selectedSchemaFilters.filter(f => f !== filter);
                      setSelectedSchemaFilters(updated);
                    setQuestion(prev => {
                        const escaped = filter.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                        const filterRegex = new RegExp(`\\b${escaped}\\.\\s*`, "g");
                        return prev.replace(filterRegex, "").trim();
                    });
                    }}
                    style={{
                      marginLeft: "8px",
                      backgroundColor: "transparent",
                      border: "none",
                      color: "#00796b",
                      fontWeight: "bold",
                      cursor: "pointer"
                    }}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          <Downshift
            onChange={selection => {
              const words = question.trim().split(" ");
              words[words.length - 1] = selection;
              setQuestion(words.join(" "));
            }}
            itemToString={item => (item ? item : "")}
          >
            {({
              getInputProps,
              getItemProps,
              getLabelProps,
              getMenuProps,
              isOpen,
              inputValue,
              highlightedIndex,
              selectedItem,
            }) => {
              const flatSuggestions = Object.entries(schemaPreview).flatMap(([table, columns]) => {
                const tableName = table.replace(/_/g, " ");
                const columnsAndValues = Object.entries(columns).flatMap(([col, vals]) => {
                  const colName = col.replace(/_/g, " ");
                  const valueSuggestions = vals.map(val => `${colName} of ${val}`);
                  return [colName, ...valueSuggestions];
                });
                return [tableName, ...columnsAndValues];
              });
              const lastWord = inputValue.trim().split(" ").pop();
              const suggestions = autocompleteEnabled && lastWord
                ? matchSorter(flatSuggestions, lastWord, { threshold: matchSorter.rankings.CONTAINS })
                : [];

              return (
                <div>
                  <textarea
                    {...getInputProps({
                      placeholder: "Enter your natural language query here...",
                      value: question,
                      onChange: (e) => setQuestion(e.target.value),
                      onKeyDown: (e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          handleSubmit(e);
                        }
                      },
                      rows: 4,
                      style: {
                        width: "90%",
                        padding: "10px",
                        fontSize: "14px",
                        fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
                        border: "1px solid #ccc",
                        borderRadius: "6px",
                        marginTop: "6px"
                      },
                      required: true
                    })}
                  />
                  <ul {...getMenuProps()} style={{
                  position: "absolute",
                    top: "100%",
                    left: 0,
                    zIndex: 2000,
                    backgroundColor: "white",
                    border: "1px solid #ccc",
                    width: "90%",
                    maxHeight: "150px",
                    overflowY: "auto",
                    margin: 0,
                    padding: 0,
                    listStyle: "none",
                    pointerEvents: "auto",
                    boxShadow: "0 2px 8px rgba(0,0,0,0.15)"
                  }}>
                    {isOpen && suggestions.map((item, index) => (
                      <li
                        {...getItemProps({
                          key: item + index,
                          index,
                          item,
                          style: {
                            backgroundColor: highlightedIndex === index ? '#bde4ff' : 'white',
                            padding: '5px',
                            cursor: 'pointer'
                          }
                        })}
                      >
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            }}
          </Downshift>
        </div>
      </div>
        <button type="submit" disabled={loading} style={{
                  backgroundColor: "#1976d2",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  padding: "8px 16px",
                  fontWeight: "500",
                  cursor: "pointer",
                  boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
                  transition: "all 0.2s ease-in-out"
                }}
                onMouseOver={(e) => (e.target.style.backgroundColor = "#1565c0")}
                onMouseOut={(e) => (e.target.style.backgroundColor = "#1976d2")}>
          {loading ? "Loading..." : "Generate & Execute"}
        </button>
      </form>
      <div style={{ display: "flex", gap: "10px", marginTop: "10px" }}>
        <button
          type="button"
          onClick={() => setAutocompleteEnabled(!autocompleteEnabled)}
          style={{
            padding: "8px 12px",
            borderRadius: "4px",
            border: "1px solid #ccc",
            backgroundColor: autocompleteEnabled ? "#e0f7fa" : "#fff",
            cursor: "pointer"
          }}
        >
          {autocompleteEnabled ? "✓ Autocomplete Enabled" : "Enable Autocomplete"}
        </button>
        <button
          type="button"
          onClick={() => setEnableFormatting(!enableFormatting)}
          style={{
            padding: "8px 12px",
            borderRadius: "4px",
            border: "1px solid #ccc",
            backgroundColor: enableFormatting ? "#e0f7fa" : "#fff",
            cursor: "pointer"
          }}
        >
          {enableFormatting ? "✓ Friendly Formatting On" : "Enable Friendly Formatting"}
        </button>
      </div>
      
      {error && (
        <div style={{ color: "red", marginTop: "10px" }}>
          <strong>Error:</strong> {error}
          <p>Please review your dataset file (must be json file) or query input and try again.</p>
        </div>
      )}
      {generatedSQL && (
        <div style={{ marginTop: "10px" }}>
          <h3>Generated SQL:</h3>
          <pre>{generatedSQL}</pre>
        </div>
      )}
      {results && Array.isArray(results) && results.length > 0 && (        
        <div style={{ marginTop: "10px" }}>
          <div style={{ marginBottom: "10px" }}>
            <button onClick={() => setSortConfig({ key: null, direction: "asc" })}
             style={{
              backgroundColor: "#e0f7fa",
              border: "1px solid #b2ebf2",
              borderRadius: "20px",
              padding: "6px 12px",
              fontSize: "13px",
              fontWeight: "500",
              color: "#00796b",
              cursor: "pointer",
              marginRight: "10px",
              marginTop: "10px",
              transition: "background-color 0.2s ease-in-out"
            }}
            onMouseOver={(e) => (e.target.style.backgroundColor = "#b2ebf2")}
            onMouseOut={(e) => (e.target.style.backgroundColor = "#e0f7fa")}
              >
              Reset Sort
            </button>
          </div>
          <h3>Query Results:</h3>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {Object.keys(results[0]).map((key, index) => (
                <th
                  key={index}
                  onClick={() => handleSort(key)}
                  title={`Click to sort by ${key}`}
                  style={{
                    border: "1px solid #ccc",
                    padding: "8px",
                    backgroundColor: "#f9f9f9",
                    textAlign: "left",
                    cursor: "pointer"
                  }}
                >
                  <div>
                    {key
                      .replace(/_/g, " ")
                      .replace(/\w\S*/g, (txt) =>
                        txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase()
                      )}
                    {sortConfig.key === key ? (sortConfig.direction === "asc" ? " 🔼" : " 🔽") : ""}
                  </div>
                  <input
                    type="text"
                    placeholder="Filter..."
                    value={columnFilters[key] || ""}
                    onChange={(e) =>
                      setColumnFilters({ ...columnFilters, [key]: e.target.value })
                    }
                    style={{ width: "90%", marginTop: "4px", fontSize: "10px" }}
                  />
                </th>
              ))}
            </tr>
          </thead>
            <tbody>
            {[...results]
              .filter((row) =>
                Object.entries(columnFilters).every(([key, value]) =>
                  String(row[key] ?? "").toLowerCase().includes(value.toLowerCase())
                )
              ).sort((a, b) => {
                if (!sortConfig.key) return 0;
                const valA = a[sortConfig.key];
                const valB = b[sortConfig.key];
                if (valA < valB) return sortConfig.direction === "asc" ? -1 : 1;
                if (valA > valB) return sortConfig.direction === "asc" ? 1 : -1;
                return 0;
              }).map((row, idx) => (
                <tr key={idx}>
                  {Object.keys(results[0]).map((col, colIdx) => {
                    const value = row[col];
                    let formatted = value;
                    if (enableFormatting) {
                      if (typeof value === "number") {
                        formatted = value.toLocaleString(undefined, { maximumFractionDigits: 2 });
                      } else if (typeof value === "string" && !/^\d+$/.test(value) && Date.parse(value)) {
                        const date = new Date(value);
                        if (!isNaN(date)) {
                          formatted = date.toLocaleDateString(undefined, {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                          });
                        }
                      } else if (typeof value === "string") {
                        formatted = value.charAt(0).toUpperCase() + value.slice(1);
                      }
                    }
                    return (
                      <td key={colIdx} style={{ border: "1px solid #ccc", padding: "8px" }}>{formatted}</td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <button
            onClick={() => {
              const csvContent = [
                Object.keys(results[0]).join(","),
                ...results.map((row) => Object.values(row).map((val) => `"${String(val).replace(/"/g, '""')}"`).join(","))
              ].join("\n");
              const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
              const url = URL.createObjectURL(blob);
              const link = document.createElement("a");
              link.setAttribute("href", url);
              link.setAttribute("download", "query_results.csv");
              link.click();
            }}
            style={{
              backgroundColor: "#1976d2",
              color: "white",
              border: "none",
              borderRadius: "6px",
              padding: "8px 16px",
              fontWeight: "500",
              cursor: "pointer",
              boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
              transition: "all 0.2s ease-in-out"
            }}
            onMouseOver={(e) => (e.target.style.backgroundColor = "#1565c0")}
            onMouseOut={(e) => (e.target.style.backgroundColor = "#1976d2")}
          >
            Export to CSV
          </button>
        </div>
      )}

      {/* Clarification Modal */}
      {showClarificationModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            backgroundColor: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 3000,
          }}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "20px",
              borderRadius: "8px",
              width: "400px",
              boxShadow: "0 2px 10px rgba(0, 0, 0, 0.1)",
            }}
          >
            <h2>Clarification Needed</h2>
            <p>
              Your query appears ambiguous.<br />
              <strong style={{ display: "block", margin: "10px 0", fontSize: "16px" }}>
                {clarificationMessage}
              </strong>
              Please add any additional details in the field below. After entering the details, click "Apply Clarification" to proceed.
            </p>
            <input
              type="text"
              value={clarificationInput}
              onChange={(e) => setClarificationInput(e.target.value)}
              placeholder="Enter additional details..."
              style={{ width: "90%", padding: "8px", marginBottom: "10px" }}
            />
            <div style={{ display: "flex", gap: "12px", marginTop: "10px" }}>
              <button onClick={applyClarification} 
                style={{
                  backgroundColor: "#1976d2",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  padding: "8px 16px",
                  fontWeight: "500",
                  cursor: "pointer",
                  boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
                  transition: "all 0.2s ease-in-out"
                }}
                onMouseOver={(e) => (e.target.style.backgroundColor = "#1565c0")}
                onMouseOut={(e) => (e.target.style.backgroundColor = "#1976d2")}
              >
                Apply Clarification
              </button>
              <button onClick={() => setShowClarificationModal(false)}
                style={{
                  backgroundColor: "#1976d2",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  padding: "8px 16px",
                  fontWeight: "500",
                  cursor: "pointer",
                  boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
                  transition: "all 0.2s ease-in-out"
                }}
                onMouseOver={(e) => (e.target.style.backgroundColor = "#1565c0")}
                onMouseOut={(e) => (e.target.style.backgroundColor = "#1976d2")}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal for Dangerous Query */}
      {showConfirmationModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            backgroundColor: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 3000,
          }}
        >
          <div
            style={{
              backgroundColor: "#fff",
              padding: "20px",
              borderRadius: "8px",
              width: "400px",
              boxShadow: "0 2px 10px rgba(0, 0, 0, 0.1)",
            }}
          >
            <h2>Dangerous Query Confirmation</h2>
            <p>{confirmationMessage}</p>
            <div style={{ marginTop: "10px" }}>
              <button onClick={executeConfirmedQuery} style={{
                  backgroundColor: "#1976d2",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  padding: "8px 16px",
                  fontWeight: "500",
                  cursor: "pointer",
                  boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
                  transition: "all 0.2s ease-in-out"
                }}
                onMouseOver={(e) => (e.target.style.backgroundColor = "#1565c0")}
                onMouseOut={(e) => (e.target.style.backgroundColor = "#1976d2")}>
                Execute Query
              </button>
              <button onClick={() => setShowConfirmationModal(false)}
                style={{
                  backgroundColor: "#1976d2",
                  color: "white",
                  border: "none",
                  borderRadius: "6px",
                  padding: "8px 16px",
                  fontWeight: "500",
                  cursor: "pointer",
                  boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
                  transition: "all 0.2s ease-in-out"
                }}
                onMouseOver={(e) => (e.target.style.backgroundColor = "#1565c0")}
                onMouseOut={(e) => (e.target.style.backgroundColor = "#1976d2")}
                >Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;