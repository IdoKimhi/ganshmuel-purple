from flask import Flask, request, jsonify
import json

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

if __name__ == '__main__':
    # Flask app will run on port 8000 (standard for a simple server process)
    app.run(host='0.0.0.0', port=8000)