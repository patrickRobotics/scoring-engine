# Loan Scoring Service
## Introduction and Setup
1. Create a **.env** file to store secret variables for your environment and populate values for the keys listed below:
```
TOKEN_EXPIRY=           # Token expiry duration in seconds, e.g. 300
USERNAME=               # username for basic authentication on this service
PASSWORD=               # password for basic auth on this service
```
## Create & Activate a Python virtualenvironment to install the needed dependencies.
`python3 -m venv .venv`

`source .venv/bin/activate`

## Insall project dependencies
`pip install -r requirements.txt`

## Start the service
`flask run --host=0.0.0.0 --port=8001`

## Testing Scoring APIs
1: Scoring Engine requires the transaction data to process the scoring and limits. It will therefore need another service, 
middleware, to consume the transaction API, and expose a RESTful API to the Scoring Engine.

The scoring engine would then need to be aware of this middleware's endpoint. For this to work, this service allows
you to register your middleware's endpoint. Send a POST request to the following endpoint to register your endpoint:
`<SCORING_HOST>>/api/v1/client/createClient`
Payload: 
```json
{
    "url": "http://localhost:5000",
    "name": "middleware-service",
    "username": "admin",
    "password": "pwd123"
}
```
Successful registration returns
```json
{
    "id": 1,
    "name": "middleware-service",
    "password": "pwd123",
    "token": "d10e23ac-bcc4-4c80-917a-2e2c9bc84e9b",
    "url": "http://localhost:5000",
    "username": "admin"
}
```
The Scoring Engine will then be able to call your RESTful endpoint, with the credentials to retrieve the transactional data.

2: Initiate Query Score
GET `<SCORING_HOST>/api/v1/scoring/initiateQueryScore/{customerNumber}` including Basic Auth credentials.
Response:
```json
{
    "token": "d10e23ac-bcc4-4c80-917a-2e2c9bc84e9b"
}
```

3: Query the score.
GET `<SCORING_HOST>/api/v1/scoring/queryScore/{token}` including Basic Auth credentials.
Response: 
```json
{
    "customerNumber": "234774784",
    "exclusion": "No Exclusion",
    "exclusionReason": "No Exclusion",
    "id": 48,
    "limitAmount": 30000,
    "score": 508
}
```

