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
the two following are the dataset i created with the sql code to test the system
    WorkplaceTest.json        #this file is used in the pytests, it is a json file of one of the test datasets defined in the SQLCode module
    LibraryManagement.json
--

## Running the Project Locally (via Docker)

This project is Dockerised for reproducibility. To install and run:

- [Docker](https://www.docker.com/) installed and running

OPENAI_API_KEY= (in the environment file)

In the root of the project (where docker-compose.yml is), run:

docker-compose up --build

	•	Frontend: http://localhost:3000

## Run down of the system:

Once you have everythin running, you will first see a crenditals screen, this can be simply skipped and countinue going forward with the default setting.

You should then upload a dataset in the provided area, and subsquently clicking to upload the dataset as stated in the area.

Once the successful upload confimation has appered you can either proceed with a question, or apply filters through the schema over view.

from there, once all pop up (clarrification or warning) you can explore your results and export if desired.

potential questions for either provided dataset:

WorkplaceTest.json:

    List every department and its location

    What is employee John Doe’s email address and phone number?

    For every department, show the total number of employees it currently has, sorted from the largest staff to the smallest (Result doesnt acturally sort because the number in both is one but the sql generated is (in my tests) accurate)

    List the departments that do not have any employees assigned yet

    (to get a clarrification model): what is bobs number 

LibraryManagement.json (more complex questions):

    Show me a list of every book the library owns

    Which books were written by George Orwell?

    What is Alice Brown’s email address?

    Give me all books published after the year 2000

    Show me how many total copies are currently available for each genre, arranged from the genre with the most copies to the least

    Find the titles and authors of all books that have never been borrowed

    Which books were borrowed by ‘Alice Brown’ but not yet returned? I’d like to see the book title, the loan date, and the due date

    For each author, please list their latest published book. I’d like the author’s name, the book’s title, and its publication date