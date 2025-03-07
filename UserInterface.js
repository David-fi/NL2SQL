
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

  // event handles
  const handleDatasetChange = (e) => {
    setDataset(e.target.files[0]); //updata the dataset state with the file which is uploaed in the upload section
  };

  const handleRemoveDataset = () => {
    setDataset(null); //by putting the dataset state back to null it clears the dataset
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
        const errorMsg = await genResponse.text();
        throw new Error(`Generate Query Error: ${errorMsg}`);
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
        setResults(execData.results);
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
          const errorMsg = await execResponse.text();
          throw new Error(`Execute Query Error: ${errorMsg}`);
        }
        const execData = await execResponse.json();
        setResults(execData.results);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: "600px", margin: "auto", padding: "20px" }}>
      <h1>NL2SQL Interface</h1>

      {/* Dataset Upload Section (fixed in the top-right corner) */}
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
            <button onClick={handleRemoveDataset}>Remove Dataset</button>
          </div>
        ) : (
          <input
            type="file"
            accept=".json,.jsonl,.csv"
            onChange={handleDatasetChange}
          />
        )}
      </div>

      {/* Question Form Section */}
      <form onSubmit={handleSubmit} style={{ marginTop: "100px" }}>
        <div>
          <label>User Question:</label>
          <textarea
            value={question}
            onChange={handleQuestionChange}
            rows="4"
            style={{ width: "100%" }}
            placeholder="Enter your natural language query here..."
            required
          />
        </div>
        <button type="submit" disabled={loading} style={{ marginTop: "10px" }}>
          {loading ? "Loading..." : "Generate & Execute"}
        </button>
      </form>

      {error && (
        <div style={{ color: "red", marginTop: "10px" }}>Error: {error}</div>
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
+             After entering the details, click "Apply Clarification" to proceed..
            </p>
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
            <button onClick={() => setShowClarificationModal(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;