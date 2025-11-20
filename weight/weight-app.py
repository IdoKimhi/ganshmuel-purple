import os
from datetime import datetime
from flask import Flask, request, jsonify, redirect
from contextlib import closing
import mysql.connector
from mysql.connector import pooling

app = Flask(__name__)

# Database connection configuration, Dev's, Please set .env variables accordingly :)
db_pool = pooling.MySQLConnectionPool(
    pool_name="weight_pool",
    pool_size=5,
    pool_reset_session=True,
    user=os.environ.get('DB_USER'),          
    password=os.environ.get('DB_PASSWORD'),  
    host=os.environ.get('DB_HOST'),          
    database=os.environ.get('DB_NAME'), 
    port=int(os.environ.get('DB_PORT', 3306))
)

def parse_date(date_str, default):
    if not date_str:
        return default
    try:
        return datetime.strptime(date_str, "%Y%m%d%H%M%S")
    except ValueError:
        return None

def sanitize_directions(filter_str):
    if not filter_str:
        return []
    raw_dirs = [d.strip() for d in filter_str.split(',')]
    return [d for d in raw_dirs if d in {'in', 'out', 'none'}]

def format_row(row):
    return {
        "id": row['id'],
        "direction": row['direction'],
        "bruto": row['bruto'],
        "neto": row['neto'] if row['neto'] is not None else "na",
        "produce": row['produce'],
        "containers": row['containers'].split(',') if row['containers'] else []
    }

# Temporarily redirecting / to /weight
@app.route('/')
def index():
    return redirect('/weight')

@app.route('/weight', methods=['GET'])
def get_weight():
    now = datetime.now()
    default_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = parse_date(request.args.get('from'), default_start)
    end_date = parse_date(request.args.get('to'), now)
    directions = sanitize_directions(request.args.get('filter', 'in,out,none'))

    if start_date is None or end_date is None:
        return jsonify({"error": "Invalid date format. Use YYYYMMDDHHMMSS"}), 400
    if not directions:
        return jsonify({"error": "Invalid filter values"}), 400

    placeholders = ','.join(['%s'] * len(directions))
    query = f"""
        SELECT id, direction, bruto, neto, produce, containers 
        FROM transactions 
        WHERE datetime BETWEEN %s AND %s AND direction IN ({placeholders})
        ORDER BY datetime DESC
    """
    try:
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor(dictionary=True)) as cursor:           
            params = [start_date, end_date] + directions
            cursor.execute(query, params)
            results = [format_row(row) for row in cursor.fetchall()]
            return jsonify(results), 200

    except mysql.connector.Error as e:
        app.logger.error(f"DB Error: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected Error: {e}")
        return jsonify({"error": "Internal server error"}), 500
   
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)