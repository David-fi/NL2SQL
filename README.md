# NL2SQL Natural Language to SQL Interface

the project allows users to upload a json dataset and ask questions in plain English. Using a fine-tuned OpenAI model, it generates corresponding SQL queries and executes them on a live MySQL database. The project includes schema previewing, query clarification, and execution safety features. 

(the web application is reachable through this url but the whole system does not function as paying for the hosting Mysql database was out of my budget) 
link: https://nl2sql-frontend.onrender.com

---

## Main project structure Structure

The following folders and files are included in the submission package:

NL2SQL/
    backend/                  # flask API logic and OpenAI integration
        api.py                # main entry point for backend API
        ModelClient.py        # class for schema extraction, SQL generation and execution
        schemaExtract.py      # utility for extracting JSON/CSV schema
        requirements.txt      # python dependencies
        config.py             # holds all of the sql default values 
    frontend/                 # react frontend application
        package.json          # Node.js dependencies
        src 
            App.js                # main React component
            index.js              # entry point for React app
            UserInterface.js      # all of the react code written here

      
    tests/                    # all pytest testing scripts
        test_execution.py     # tests SQL execution logic
        test_translation.py   # tests language-to-SQL mapping
        test_integration.py   # end to end testing across modules
        conftest.py           # test environment config

    modelTraining/
        dataPrep.py           #pre precessing of the data
        evaluateModel.py      #evaluating the models performance
        modelDevelopment.py   #where training hte model with a fine tuning job is done 

    docker-compose.yml        # launches MySQL, backend, and frontend as services
    README.md                 # this file
    SQLCode         # containing the sql for test schema setup
    WorkplaceTest.json        #this file is used in the pytests, it is a json file of one of the test datasets defined in the SQLCode module

--

## Running the Project Locally (via Docker)

This project is Dockerised for reproducibility. To install and run:

- [Docker](https://www.docker.com/) installed and running

OPENAI_API_KEY= (in the environment file)

In the root of the project (where docker-compose.yml is), run:

docker-compose up --build

	•	Frontend: http://localhost:3000

