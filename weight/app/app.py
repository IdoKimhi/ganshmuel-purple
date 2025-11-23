import os
import time
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
        "produce": row['produce'] or "na",
        "containers": row['containers'].split(',') if row['containers'] else []
    }

# Temporarily redirecting / to /weight, can be changed later as needed.
@app.route('/')
def index():
    return redirect('/weight')

@app.route('/health', methods=['GET'])
def health():
    try:
        conn = db_pool.get_connection()
        conn.close()
        return "OK", 200
    except Exception:
        return "Failure", 500

@app.route('/weight', methods=['GET'])
def get_weight():
    now = datetime.now()
    default_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    t1 = parse_date(request.args.get('from'), default_start)
    t2 = parse_date(request.args.get('to'), now)
    directions = sanitize_directions(request.args.get('filter', 'in,out,none'))

    if t1 is None or t2 is None:
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
            params = [t1, t2] + directions
            cursor.execute(query, params)
            results = [format_row(row) for row in cursor.fetchall()]
            return jsonify(results), 200

    except mysql.connector.Error as e:
        app.logger.error(f"DB Error: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected Error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/weight', methods=['POST'])
def post_weight():
    # 1. Input Parsing
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
        
    direction = data.get('direction')
    truck = data.get('truck', 'na')
    containers = data.get('containers', '')  # Example: "C-101,C-102"
    weight_input = int(data.get('weight'))
    unit = data.get('unit', 'kg')
    produce = data.get('produce', 'na')

    if direction not in ['in', 'out', 'none']:
        return jsonify({"error": "Invalid direction"}), 400

    # 2. Unit Conversion (Always store in KG)
    weight_kg = int(weight_input * 0.453592) if unit == 'lbs' else weight_input

    try:
        # We use the pool exactly like your team did in get_weight
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor(dictionary=True)) as cursor:
            
            # --- LOGIC A: Direction IN ---
            if direction == 'in':
                # Generate a unique Session ID (using integer timestamp)
                session_id = int(time.time())
                
                query = """
                    INSERT INTO transactions 
                    (direction, truck, containers, bruto, produce, datetime, session_id) 
                    VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                """
                cursor.execute(query, (direction, truck, containers, weight_kg, produce, session_id))
                conn.commit() # <--- CRITICAL: You must commit writes!
                
                return jsonify({
                    "id": cursor.lastrowid, 
                    "truck": truck, 
                    "bruto": weight_kg
                }), 201

            # --- LOGIC B: Direction OUT ---
            elif direction == 'out':
                # Find the last 'in' record for this truck
                cursor.execute("""
                    SELECT * FROM transactions 
                    WHERE truck = %s AND direction = 'in' 
                    ORDER BY datetime DESC LIMIT 1
                """, (truck,))
                last_in = cursor.fetchone()

                if not last_in:
                    return jsonify({"error": "No previous 'in' record found for truck"}), 404

                # Calculate Logic
                bruto_in = last_in['bruto']
                truck_tara = weight_kg  # Current weight is empty truck
                
                # Calculate Container Weight from DB lookup
                total_container_weight = 0
                neto = 0 
                
                if containers:
                    container_list = containers.split(',')
                    # Create placeholders based on number of containers
                    format_strings = ','.join(['%s'] * len(container_list))
                    
                    # Get sum of weights
                    cursor.execute(f"SELECT sum(weight) as total, count(*) as count FROM containers_registered WHERE container_id IN ({format_strings})", tuple(container_list))
                    result = cursor.fetchone()
                    
                    # If we found fewer containers in DB than requested, some are unknown
                    if result['count'] != len(container_list):
                        neto = None # "na"
                    else:
                        total_container_weight = result['total'] if result['total'] else 0
                        neto = bruto_in - truck_tara - total_container_weight
                else:
                    neto = bruto_in - truck_tara

                # Save OUT record linked to SAME session_id
                session_id = last_in['session_id']
                query = """
                    INSERT INTO transactions 
                    (direction, truck, containers, truckTara, neto, produce, datetime, session_id) 
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                """
                cursor.execute(query, (direction, truck, containers, truck_tara, neto, produce, session_id))
                conn.commit() # <--- CRITICAL: You must commit writes!

                return jsonify({
                    "id": cursor.lastrowid,
                    "truck": truck,
                    "bruto": bruto_in,
                    "truckTara": truck_tara,
                    "neto": neto if neto is not None else "na"
                }), 201

            # --- LOGIC C: Direction NONE ---
            else:
                session_id = int(time.time())
                cursor.execute("INSERT INTO transactions (direction, bruto, datetime, session_id) VALUES (%s, %s, NOW(), %s)", 
                             (direction, weight_kg, session_id))
                conn.commit()
                return jsonify({"id": cursor.lastrowid, "bruto": weight_kg}), 201

    except mysql.connector.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500
    
@app.route('/session', defaults={'id': None}, methods=['GET'])
@app.route('/session/<id>', methods=['GET'])
def get_session(id):
    def _serialize_session(row):
        resp = {
            "id": str(row['session_id']),
            "truck": row['truck'] or "na",
            "bruto": row['bruto']
        }
        if row['direction'] == 'out':
            resp['truckTara'] = row['truckTara']
            resp['neto'] = row['neto'] if row['neto'] is not None else "na"
        else:
             resp['status'] = 'active'
        return resp

    try:
        with closing(db_pool.get_connection()) as conn, \
             closing(conn.cursor(dictionary=True)) as cursor:
            
            if id:
                query = """
                    SELECT session_id, truck, bruto, truckTara, neto, direction 
                    FROM transactions 
                    WHERE session_id = %s 
                    ORDER BY datetime DESC 
                    LIMIT 1
                """
                cursor.execute(query, (id,))
                row = cursor.fetchone()

                if not row:
                    return jsonify({"error": "Session not found"}), 404

                return jsonify(_serialize_session(row)), 200

            else:
                query = """
                    SELECT session_id, truck, bruto, truckTara, neto, direction 
                    FROM transactions 
                    WHERE direction = 'out'
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                
                results = [_serialize_session(row) for row in rows]
                
                return jsonify(results), 200

    except Exception as e:
        app.logger.error(f"Error getting session: {e}")
        return jsonify({"error": "Internal server error"}), 500
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)