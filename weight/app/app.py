from flask import Flask
import os
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

db_pool = None

def init_db_pool():
    global db_pool
    db_config = {
        'host': os.getenv('DB_HOST'),
        'port': int(os.getenv('DB_PORT')),
        'database': os.getenv('DB_NAME'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'pool_name': 'weight_app_pool', 
        'pool_size': 5  
    }
    
    try:
        db_pool = pooling.MySQLConnectionPool(**db_config)
        print("Database pool initialized successfully")
    except mysql.connector.Error as e:
        print(f"Error creating connection pool: {e}")
        db_pool = None

@app.route('/health', methods=['GET'])
def health_check():
    if connect_to_db():
        return 'OK', 200
    else:
        return 'Database connection failed', 500

def connect_to_db():
    if db_pool is None:
        return False
    
    try:
        connection = db_pool.get_connection()
        
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
    init_db_pool()
    app.run(host='0.0.0.0')