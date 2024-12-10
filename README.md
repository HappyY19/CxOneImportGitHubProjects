# CxOneImportGitHubProjects

This python script aims to import all GitHub repos from one GitHub Organization into CxOne.

## Prerequisites for the script, you need to set the following environment variables
    a. GITHUB_ORG: your GitHub organization name, which is case-sensitive
    b. GITHUB_TOKEN: your GitHub personal access token
    c. CX_ONE_SCANNERS: comma separated value, for example: sast,sca,apisec,kics

## Notice
Please use Python3!

## How to run the script
1. create a python virtual environment: python -m venv .venv
2. activate the virtual environment: 
   a. on Windows: .\.venv\Scripts\activate
   b. on Linux/MacOS: source .venv/bin/activate
3. install the dependencies: pip install -r requirements.txt 
4. run the python script: python main.py