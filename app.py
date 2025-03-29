from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import time
import threading
import random
import requests
from functools import wraps
from dotenv import load_dotenv
import os


load_dotenv()

app = Flask(__name__)

# Configuration
SCORING_TIME_RANGE = (5, 15)  # Min/max seconds scoring takes
TOKEN_EXPIRY = os.getenv('TOKEN_EXPIRY')  # 5 minutes in seconds

pending_scores = {}
completed_scores = {}
registered_clients = {}
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
users = {
    USERNAME: generate_password_hash(PASSWORD)
}


# Authentication decorator
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_credentials(auth.username, auth.password):
            return jsonify({
                "error": "Unauthorized",
                "message": "Please provide valid credentials"
            }), 401, {'WWW-Authenticate': 'Basic realm="Scoring API"'}
        return f(*args, **kwargs)

    return decorated


def check_credentials(username, password):
    return username in users and check_password_hash(users[username], password)


def verify_client_token(token):
    """Verify client registration token"""
    return any(client['token'] == token for client in registered_clients.values())


# Endpoint to initiate scoring
@app.route('/api/v1/scoring/initiateQueryScore/<customerNumber>', methods=['GET'])
@requires_auth
def initiate_scoring(customerNumber):
    if not customerNumber:
        return jsonify({"error": "customer_number is required"}), 400

    # client_token = request.headers.get('X-Client-Token')
    # if not client_token or client_token not in registered_clients:
    #     return jsonify({"error": "Valid X-Client-Token header is required"}), 400

    try:
        token = registered_clients[1]['token']
    except KeyError:
        return jsonify({
            "error": "No registred clients"
        }), 400

    pending_scores[token] = {
        "customer_number": customerNumber,
        "timestamp": time.time(),
        "status": "processing"
    }

    # Start background scoring simulation
    threading.Thread(
        target=perform_scoring,
        args=(customerNumber, token)
    ).start()

    return jsonify({
        "token": token
    })


# Endpoint to check score
@app.route('/api/v1/scoring/queryScore/<token>', methods=['GET'])
@requires_auth
def check_score(token):
    id = random.randint(1, 100)
    # Check if score is ready
    if token in completed_scores:
        result = completed_scores[token]
        if result['status'] == 'failed':
            return jsonify({
                "id": id,
                "customerNumber": result['customer_number'],
                "error": "Scoring Failed!"
            }), 400
        return jsonify({
            "id": id,
            "customerNumber": result["customer_number"],
            "limitAmount": 30000,
            "score": result["score"],
            "exclusion": "No Exclusion",
            "exclusionReason": "No Exclusion"
        })

    # Check if still processing
    if token in pending_scores:
        # Calculate estimated time remaining
        started = pending_scores[token]["timestamp"]
        elapsed = time.time() - started
        avg_duration = sum(SCORING_TIME_RANGE) / 2

        return jsonify({
            "id": id,
            "status": "processing",
            "progress": min(99, int((elapsed / avg_duration) * 100))
        })

    # Check if token expired
    if token not in pending_scores and token not in completed_scores:
        return jsonify({
            "error": "Invalid or expired token"
        }), 404


# Client registration
@app.route('/api/v1/client/createClient', methods=['POST'])
@requires_auth
def register_client():
    data = request.get_json()

    required_fields = ['url', 'name', 'username', 'password']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    client_id = len(registered_clients) + 1
    client_token = str(uuid.uuid4())

    registered_clients[client_id] = {
        "id": client_id,
        "url": data['url'],
        "name": data['name'],
        "username": data['username'],
        "password": data['password'],
        "token": client_token
    }

    return jsonify(registered_clients[client_id])


def calculate_score(transactions):
    """Calculate score based on transaction data"""
    if not transactions:
        return 300  # Minimum score if no transactions

    # Example scoring logic
    total_value = sum(t.get('transactionValue', 0) for t in transactions)
    avg_value = total_value / len(transactions)

    # Base score + weighted factors
    score = 500  # Base score
    score += min(200, avg_value / 1000)  # Up to 200 points for transaction size
    score += min(150, len(transactions) * 5)  # Up to 150 points for activity

    # Ensure score stays within bounds
    return max(300, min(850, int(score)))


# Background scoring with middleware integration
def perform_scoring(customer_number, token):
    try:
        # Get middleware client info
        client = next((item for item in registered_clients.values() if item.get('token') == token), None)

        if not client:
            raise Exception("Invalid client token")

        # Query middleware for transactions
        middleware_url = f"{client['url']}/api/v1/transactions/{customer_number}"
        response = requests.get(
            middleware_url,
            auth=(client['username'], client['password'])
        )

        if response.status_code != 200:
            raise Exception(f"Middleware error: {response.text}")

        transactions = response.json().get('transactions', [])

        # Calculate score based on transactions
        score = calculate_score(transactions)

        # Store completed score
        completed_scores[token] = {
            "customer_number": customer_number,
            "score": score,
            "timestamp": time.time(),
            "status": "completed",
        }

    except Exception as e:
        completed_scores[token] = {
            "customer_number": customer_number,
            "error": str(e),
            "timestamp": time.time(),
            "status": "failed"
        }
    finally:
        # Remove from pending
        pending_scores.pop(token, None)


# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "pending_requests": len(pending_scores),
        "completed_requests": len(completed_scores)
    })


# Cleanup expired tokens periodically
def cleanup_expired_tokens():
    while True:
        time.sleep(60)
        now = time.time()
        expired = [t for t, data in completed_scores.items()
                   if now - data['timestamp'] > float(TOKEN_EXPIRY)]
        for t in expired:
            completed_scores.pop(t, None)


# Start cleanup thread
threading.Thread(target=cleanup_expired_tokens, daemon=True).start()


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


if __name__ == '__main__':
    app.run(port=5001, debug=True)
