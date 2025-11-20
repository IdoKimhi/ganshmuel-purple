from flask import Flask
import os
import mysql.connector
from dotenv import load_dotenv


app = Flask(__name__)
load_dotenv()

@app.route('/health', methods=['GET'])
def health_check():
    if connect_to_db():
        return 'OK', 200
    else:   
        return 'Database connection failed', 500

def connect_to_db():
    db_config = {
        'host': os.getenv('DB_HOST'),'port': int(os.getenv('DB_PORT')),'database': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'), 'password': os.getenv('DB_PASSWORD')
    }

    try:
        connection = mysql.connector.connect(**db_config)

        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()  

        cursor.close()
        connection.close()

        return True

    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        return False
    

if __name__ == '__main__':
    app.run(host='0.0.0.0')