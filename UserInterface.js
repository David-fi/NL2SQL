
import React, { useState } from "react";

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

  // event handles
  const handleDatasetChange = (e) => {
    setDataset(e.target.files[0]); //updata the dataset state with the file which is uploaed in the upload section
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
      } else {
        setError("");
        setNewDatabaseCreated(data.newDatabaseCreated);
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

  return (
    <div style={{ maxWidth: "600px", margin: "auto", padding: "20px" }}>
      <h1>NL2SQL Interface</h1>
      {/* Credentials Modal */}
      {showCredentialsModal && (
        <div style={{
          position: "fixed",
          top: 0, left: 0, width: "100%", height: "100%",
          backgroundColor: "rgba(0,0,0,0.5)",
          display: "flex", justifyContent: "center", alignItems: "center",
          zIndex: 1000
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
            <button onClick={saveCredentials}>Save</button>
          </div>
        </div>
      )}

      {/* Top-left Credentials Button */}
      <div style={{
        position: "fixed",
        top: "20px",
        left: "20px",
        border: "1px solid #ccc",
        padding: "10px",
        borderRadius: "4px",
        backgroundColor: "#fff",
      }}>
        <button onClick={() => setShowCredentialsModal(true)}>Edit phpMyAdmin Credentials</button>
      </div>

      {/* Dataset Upload Section */}
      <div
        style={{
          position: "fixed",
          top: "20px",
          right: "20px",
          border: "1px solid #ccc",
          padding: "10px",
          borderRadius: "4px",
          backgroundColor: "#fff",
        }}
      >
        <h3>Dataset Upload</h3>
        {dataset ? (
          <div>
            <p>
              <strong>Uploaded File:</strong> {dataset.name}
            </p>
            <p style={{ fontStyle: "italic", color: "#333" }}>
              Remember to click "Upload Dataset".
            </p>
            <button onClick={handleRemoveDataset}>Remove Dataset</button>
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
          <button onClick={handleDatasetUpload} disabled={!dataset || loading}>
            {loading ? "Uploading..." : "Upload Dataset"}
          </button>
        </div>
      </div>

      {/* Question Form Section */}
      <form onSubmit={handleSubmit} style={{ marginTop: "100px" }}>
        <div>
          <label>User Question:</label>
          <textarea
            value={question}
            onChange={handleQuestionChange}
            rows="4"
            style={{ width: "90%" }}
            placeholder="Enter your natural language query here..."
            required
          />
        </div>
        <button type="submit" disabled={loading} style={{ marginTop: "10px" }}>
          {loading ? "Loading..." : "Generate & Execute"}
        </button>
      </form>

      {error && (
        <div style={{ color: "red", marginTop: "10px" }}>
          <strong>Error:</strong> {error}
          <p>Please review your dataset file or query input and try again.</p>
        </div>
      )}
      {generatedSQL && (
        <div style={{ marginTop: "10px" }}>
          <h3>Generated SQL:</h3>
          <pre>{generatedSQL}</pre>
        </div>
      )}
      {results && (
        <div style={{ marginTop: "10px" }}>
          <h3>Query Results:</h3>
          <pre>{JSON.stringify(results, null, 2)}</pre>
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
              Your query appears ambiguous. {clarificationMessage}
              <br />
              Please add any additional details in the field below.
                           After entering the details, click "Apply Clarification" to proceed..            </p>
            <input
              type="text"
              value={clarificationInput}
              onChange={(e) => setClarificationInput(e.target.value)}
              placeholder="Enter additional details..."
              style={{ width: "100%", padding: "8px", marginBottom: "10px" }}
            />
            <button onClick={applyClarification} style={{ marginRight: "10px" }}>
              Apply Clarification
            </button>
            <button onClick={() => setShowClarificationModal(false)}>Cancel</button>
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
              <button onClick={executeConfirmedQuery} style={{ marginRight: "10px" }}>
                Execute Query
              </button>
              <button onClick={() => setShowConfirmationModal(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;