import os
import time
from datetime import datetime
from flask import Flask, request, jsonify, redirect
from contextlib import closing
import mysql.connector
from mysql.connector import pooling
import csv
import json

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
    return "OK", 200
    
    
@app.route('/item/<id>', methods=['GET'])
def get_item(id):
    now = datetime.now()
    default_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    t1 = parse_date(request.args.get('from'), default_start)
    t2 = parse_date(request.args.get('to'), now)
    print(t1, t2)

    if t1 is None or t2 is None:
        return jsonify({"error": "Invalid date format. Use YYYYMMDDHHMMSS"}), 400
    

    if t1 > t2:
        return jsonify({"error": "'from' must be earlier than 'to'"}), 400

    
    try:
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor(dictionary=True)) as cursor:

            cursor.execute(
                "SELECT 1 FROM transactions WHERE truck = %s LIMIT 1",
                (id,))
            is_truck = cursor.fetchone() is not None

            cursor.execute(
                "SELECT weight FROM containers_registered WHERE container_id = %s LIMIT 1",
                (id,))
            container_row = cursor.fetchone()
            is_registered_container = container_row is not None

            cursor.execute("""SELECT 1 FROM transactions WHERE FIND_IN_SET(%s, REPLACE(containers, ' ', '')) > 0 LIMIT 1""", (id,))
            is_container_in_transactions = cursor.fetchone() is not None

            is_container = is_registered_container or is_container_in_transactions

            if not is_truck and not is_container:
                return jsonify({"error": "Item not found"}), 404

            tara_val = "na"

            if is_truck:
                cursor.execute("""SELECT truckTara FROM transactions WHERE truck = %s AND truckTara IS NOT NULL
                                ORDER BY datetime DESC LIMIT 1""", (id,))
                last_tara = cursor.fetchone()
                tara_val = last_tara["truckTara"] if last_tara else "na"

                cursor.execute("""
                    SELECT DISTINCT session_id FROM transactions WHERE truck = %s AND datetime BETWEEN %s AND %s
                    ORDER BY session_id DESC""", (id, t1, t2))

            else:
                tara_val = container_row["weight"] if container_row and container_row["weight"] is not None else "na"

                cursor.execute("""
                    SELECT DISTINCT session_id FROM transactions WHERE FIND_IN_SET(%s, REPLACE(containers, ' ', '')) > 0
                      AND datetime BETWEEN %s AND %s ORDER BY session_id DESC""", (id, t1, t2))

            sessions = [row["session_id"] for row in cursor.fetchall()]

            return jsonify({
                "id": id,
                "tara": tara_val,
                "sessions": sessions
            }), 200

    except mysql.connector.Error as e:
        app.logger.error(f"DB Error in /item/{id}: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected Error in /item/{id}: {e}")
        return jsonify({"error": "Internal server error"}), 500
    


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


@app.route('/batch-weight', methods=['POST'])
def batch_weight():
    # Get the filename from the request
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
        
    filename = data.get('file')
    if not filename:
        return jsonify({"error": "No filename provided"}), 400
    
    # Locate the file in the /in folder (Mapped Volume)
    filepath = os.path.join('/in', filename)
    if not os.path.exists(filepath):
        return jsonify({"error": f"File {filename} not found in /in folder"}), 404

    success_count = 0
    
    try:
        # Connect to DB
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor()) as cursor:
            
            # Determine file type
            file_ext = filename.split('.')[-1].lower()
            
            if file_ext == 'json':
                with open(filepath, 'r') as f:
                    records = json.load(f)
                    for item in records:
                        # Extract fields
                        c_id = item.get('id')
                        w = int(item.get('weight'))
                        u = item.get('unit', 'kg')
                        
                        # Convert to KG if needed
                        final_w = int(w * 0.453592) if u == 'lbs' else w
                        
                        # Save to DB (REPLACE prevents duplicates)
                        cursor.execute("REPLACE INTO containers_registered (container_id, weight, unit) VALUES (%s, %s, 'kg')", (c_id, final_w))
                        success_count += 1

            elif file_ext == 'csv':
                with open(filepath, 'r') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    
                    # Skip header if present
                    start_idx = 0
                    if rows and rows[0][0].lower() in ['id', 'container_id', 'unit', 'weight']:
                        start_idx = 1
                    
                    for row in rows[start_idx:]:
                        if len(row) < 2: continue # Skip empty rows
                        
                        # CSV Format expected: id, weight, [unit]
                        c_id = row[0]
                        w = int(row[1])
                        
                        # Default to kg, check 3rd column if it exists
                        u = 'kg'
                        if len(row) > 2:
                            u = row[2].lower()
                        
                        # Convert to KG
                        final_w = int(w * 0.453592) if u == 'lbs' else w
                        
                        cursor.execute("REPLACE INTO containers_registered (container_id, weight, unit) VALUES (%s, %s, 'kg')", (c_id, final_w))
                        success_count += 1

            # commit the transaction
            conn.commit()
            return jsonify({"accepted": success_count}), 200

    except ValueError as e:
        return jsonify({"error": f"Data format error: {str(e)}"}), 400
    except mysql.connector.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500



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
