# Automation steps
* tox
  * `tox`
* poetry
  * `poetry add <package name>` - add package to the poetry manager
  * `poetry add <package name> --group dev` - add package to dev
  * `poetry build` to generate package
* pytest
  * `pytest`

# MongoDB
* Need to add IP access for access the database

# Planning
* [Notion site](https://www.notion.so/panzoto/12d889efe8c280d98b68ef6c6ce2293a?v=12d889efe8c281a1a45a000c80a63373)

# Folder Structure
```
├── data               # Storing data for entire app
├── api                # all api folder
    ├── backend        # backend api folder
        ├── api.py     # backend fast api file
├── backend            # backend code 
    ├── config         # config folder for pydantic structure
        ├── config.py  # pydantic settings for backend
    ├── data           # scripts to get decision stories data
        ├── reddit.py  # web scrapping to get data from reddit
        ├── mongodb_client.py       # save data to mongodb
        ├── save_reddit_posts.py    # save reddit data to mongodb
    ├── transcribe     # scripts to transcribe data on S3
        ├── aws_s3.py  # functions to download/upload files on S3
        ├── whipser.py # using openai whipser service to transcribe audio
    ├── utils          # utility scripts for all backend code
        ├── logger.py  # logging setup
        ├── dynamo.py  # using AWS dynamo db as key value pair storage
    ├── workflow       # workflow to generate results
        ├── daily_summary.py    # generate the daily summary from transcription
    ├── services       # automatic servies
        ├── controller.service
        ├── controller.py
├── data_structure     # pydantic models for data structures
    ├── models.py      # pydantic models
├── ui                 # frontend code folder
    ├── email
        ├── email.py  # sending email to the user
    ├── workflow
├── tests              # tests for repo
    ├── backend 
        ├── data
            ├── test_mongodb_client.py
            ├── test_reddit.py
        ├── transcribe
            ├── test_aws_s3.py
            ├── test_whisper.py
    ├── ui 
        ├── email
            ├── test_email.py
├── .env               # enviornment variables
├── flake8             # flake8 settings
├── .gitignore         # gitignore file
├── LICENSE            # license file
├── mypy.ini           # mypy settings
├── poetry.lock        # poetry lock file
├── pyproject.toml     # poetry setting file
├── pytest.ini         # pytest setting file
├── README.md          # readme file for entire repo
├── tox.ini            # tox setting file
```

# Services
The following services are automatically started in cloud server
* `decision_data/backend/transcribe/whipser.py`

# API
* api.backend.api  
`http://127.0.0.1:8000/api/stories?source=reddit&subreddit=decisions&limit=5`
* get stories from reddit and save to mongo db
`curl -X POST "http://127.0.0.1:8000/api/save_stories?num_posts=1000"`

# Bug list
Datetime object wasn't saving to the mongo db as date object. Filtering it with string format have weird results. 