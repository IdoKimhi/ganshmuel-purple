import os
import time
import csv
import json
from datetime import datetime
from contextlib import closing
from flask import Flask, request, jsonify, redirect, send_from_directory
from flask_cors import CORS
import mysql.connector
from mysql.connector import pooling

app = Flask(__name__)

# Enable CORS for frontend access
CORS(app)

# Enable pretty-printed JSON responses for better readability
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
app.json.sort_keys = False

# Database connection pool for efficient connection reuse
db_pool = pooling.MySQLConnectionPool(
    pool_name="weight_pool",
    pool_size=5,
    pool_reset_session=True,
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD'),
    host=os.environ.get('DB_HOST'),
    database=os.environ.get('DB_NAME'),
    port=int(os.environ['DB_PORT'])
)

def parse_date(date_str, default):
    """Parse date string (YYYYMMDDHHMMSS format) or return default."""
    if not date_str:
        return default
    try:
        return datetime.strptime(date_str, "%Y%m%d%H%M%S")
    except ValueError:
        return None

def sanitize_directions(filter_str):
    """Validate and filter directions to only allowed values."""
    if not filter_str:
        return []
    raw_dirs = [d.strip() for d in filter_str.split(',')]
    return [d for d in raw_dirs if d in {'in', 'out', 'none'}]

def validate_mandatory_fields(data, required_fields):
    """Verify all required fields are present in request data."""
    for field in required_fields:
        if field not in data:
            return False, f"Missing mandatory field: {field}"
    return True, None

def normalize_and_validate_containers(containers, direction):
    
    #Normalize containers string -> (container_list, containers_norm_str)
    #IN/OUT require at least one container id, NONE may be empty
    
    containers_norm = (containers or "").replace(" ", "")
    container_list = [c for c in containers_norm.split(',') if c]
    containers_norm_str = ",".join(container_list)

    if direction in ['in', 'out'] and not container_list:
        return None, None, jsonify({"error": "Containers required for direction 'in' or 'out'"}), 400

    return container_list, containers_norm_str, None, None


def validate_weight_input(data):
    
    # Validate POST /weight input fields, normalize containers,convert weight to kg, force rules
    # Returns:(direction, truck, container_list, containers_norm_str, weight_kg, produce, force),
    # error_response, status_code
    

    direction = data['direction']
    truck = data.get('truck', 'na')
    containers = data.get('containers', '')
    weight_input = data['weight']
    unit = (data.get('unit', 'kg') or 'kg').lower()
    produce = data.get('produce', 'na')
    force = data.get('force', False)

    # direction
    if direction not in ['in', 'out', 'none']:
        return None, jsonify({"error": "Invalid direction"}), 400

    # force must be real boolean
    if not isinstance(force, bool):
        return None, jsonify({"error": "Force must be a boolean (true/false)"}), 400

    if unit not in ['kg', 'lbs']:
        return None, jsonify({"error": "Unit must be 'kg' or 'lbs'"}), 400

    # weight positive int
    if not isinstance(weight_input, int) or weight_input <= 0:
        return None, jsonify({"error": "Weight must be a positive integer"}), 400

    # normalize + validate containers
    container_list, containers_norm_str, err_resp, code = normalize_and_validate_containers(containers, direction)
    if err_resp:
        return None, err_resp, code

    # NONE must be standalone -> truck='na'
    if direction == 'none' and truck != 'na':
        return None, jsonify({"error": "Direction 'none' must use truck='na'"}), 400

    # truck required only for IN/OUT
    if direction in ['in', 'out']:
        if not truck or not isinstance(truck, str) or truck.strip() == "":
            return None, jsonify({"error": "Truck cannot be empty or whitespace"}), 400

    # produce normalize to "na" if empty
    if not produce or not isinstance(produce, str) or produce.strip() == "":
        produce = "na"

    # convert lbs to kg
    weight_kg = int(weight_input * 0.453592) if unit == 'lbs' else weight_input

    return (direction, truck, container_list, containers_norm_str, weight_kg, produce, force), None, None


def calculate_neto(cursor, bruto_in, truck_tara, containers):
    """Calculate net weight: neto = bruto - truck_tara - sum(container_weights).
    Returns None if any container has unknown weight.
    """
    if not containers:
        return bruto_in - truck_tara

    container_list = containers.split(',')
    placeholders = ','.join(['%s'] * len(container_list))

    cursor.execute(
        f"SELECT sum(weight) as total, count(*) as count FROM containers_registered WHERE container_id IN ({placeholders})",
        tuple(container_list)
    )
    result = cursor.fetchone()

    # If any container is not registered, we can't calculate neto
    if result['count'] != len(container_list):
        return None

    total_container_weight = result['total'] if result['total'] else 0
    return bruto_in - truck_tara - total_container_weight

def check_session_closed(cursor, session_id):
    """Check if a session has been closed (has an OUT record)."""
    cursor.execute("SELECT 1 FROM transactions WHERE session_id = %s AND direction = 'out' LIMIT 1", (session_id,))
    return cursor.fetchone() is not None

def format_transaction_row(row):
    """Format a transaction DB row for API response."""
    return {
        "id": row['id'],
        "direction": row['direction'],
        "truck": row['truck'] or "na",
        "bruto": row['bruto'],
        "neto": row['neto'] if row['neto'] is not None else "na",
        "produce": row['produce'] or "na",
        "containers": row['containers'].split(',') if row['containers'] else []
    }

@app.route('/')
def index():
    """Serve the frontend application."""
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files (CSS, JS)."""
    return send_from_directory('static', path)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint - tests DB connectivity."""
    try:
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor()) as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return "OK", 200
    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return "Failure", 500

@app.route('/unknown', methods=['GET'])
def get_unknown():
    """Return list of containers used in transactions but not registered."""
    try:
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor(dictionary=True)) as cursor:
            cursor.execute("SELECT container_id FROM containers_registered WHERE weight IS NOT NULL")
            known_containers = {row['container_id'] for row in cursor.fetchall()}

            cursor.execute("SELECT containers FROM transactions WHERE containers IS NOT NULL AND containers != ''")

            unknown_containers = set()
            for row in cursor.fetchall():
                cons = row['containers'].split(',')
                for c in cons:
                    c = c.strip()
                    if c and c not in known_containers:
                        unknown_containers.add(c)

            return jsonify(list(unknown_containers)), 200

    except mysql.connector.Error as e:
        app.logger.error(f"DB Error in /unknown: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected Error in /unknown: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/item/<id>', methods=['GET'])
def get_item(id):
    """Get truck or container info with session history."""
    now = datetime.now()
    default_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    t1 = parse_date(request.args.get('from'), default_start)
    t2 = parse_date(request.args.get('to'), now)

    if t1 is None or t2 is None:
        return jsonify({"error": "Invalid date format. Use YYYYMMDDHHMMSS"}), 400
    if t1 > t2:
        return jsonify({"error": "'from' must be earlier than 'to'"}), 400
    try:
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor(dictionary=True)) as cursor:
            cursor.execute("SELECT 1 FROM transactions WHERE truck = %s LIMIT 1", (id,))
            is_truck = cursor.fetchone() is not None

            cursor.execute("SELECT weight FROM containers_registered WHERE container_id = %s LIMIT 1", (id,))
            container_row = cursor.fetchone()
            is_registered_container = container_row is not None

            cursor.execute("SELECT 1 FROM transactions WHERE FIND_IN_SET(%s, REPLACE(containers, ' ', '')) > 0 LIMIT 1", (id,))
            is_container_in_transactions = cursor.fetchone() is not None

            is_container = is_registered_container or is_container_in_transactions

            if not is_truck and not is_container:
                return jsonify({"error": "Item not found"}), 404

            tara_val = "na"

            if is_truck:
                cursor.execute("SELECT truckTara FROM transactions WHERE truck = %s AND truckTara IS NOT NULL ORDER BY datetime DESC LIMIT 1", (id,))
                last_tara = cursor.fetchone()
                tara_val = last_tara["truckTara"] if last_tara else "na"

                cursor.execute("SELECT DISTINCT session_id FROM transactions WHERE truck = %s AND datetime BETWEEN %s AND %s ORDER BY session_id DESC", (id, t1, t2))
            else:
                tara_val = container_row["weight"] if container_row and container_row["weight"] is not None else "na"

                cursor.execute("SELECT DISTINCT session_id FROM transactions WHERE FIND_IN_SET(%s, REPLACE(containers, ' ', '')) > 0 AND datetime BETWEEN %s AND %s ORDER BY session_id DESC", (id, t1, t2))

            sessions = [row["session_id"] for row in cursor.fetchall()]

            return jsonify({"id": id, "tara": tara_val, "sessions": sessions}), 200

    except mysql.connector.Error as e:
        app.logger.error(f"DB Error in /item/{id}: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected Error in /item/{id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/weight', methods=['GET'])
def get_weight():
    """Query weight transactions with optional date/direction filters."""
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
        SELECT id, direction, truck, bruto, neto, produce, containers 
        FROM transactions 
        WHERE datetime BETWEEN %s AND %s AND direction IN ({placeholders})
        ORDER BY datetime DESC
    """
    try:
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor(dictionary=True)) as cursor:
            params = [t1, t2] + directions
            cursor.execute(query, params)
            results = [format_transaction_row(row) for row in cursor.fetchall()]
            return jsonify(results), 200

    except mysql.connector.Error as e:
        app.logger.error(f"DB Error: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected Error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/weight', methods=['POST'])
def post_weight():
    """Record a weight transaction (IN/OUT/NONE) according to spec."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    required_fields = ['direction', 'truck', 'containers', 'weight', 'unit', 'produce', 'force']
    valid, error_msg = validate_mandatory_fields(data, required_fields)
    if not valid:
        return jsonify({"error": error_msg}), 400

    validated, err_resp, code = validate_weight_input(data)
    if err_resp:
        return err_resp, code

    direction, truck, container_list, containers_norm_str, weight_kg, produce, force = validated

    try:
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor(dictionary=True)) as cursor:

            # ---------------------------
            # DIRECTION: IN
            # ---------------------------
            if direction == 'in':
                # last IN for truck
                cursor.execute("""
                    SELECT id, session_id
                    FROM transactions
                    WHERE truck=%s AND direction='in'
                    ORDER BY datetime DESC, id DESC
                    LIMIT 1
                """, (truck,))
                last_in = cursor.fetchone()

                # if last IN is still open => IN after IN
                if last_in and not check_session_closed(cursor, last_in['session_id']):
                    if not force:
                        return jsonify({"error": "Truck already in. Use force=true to overwrite."}), 409

                    # overwrite by UPDATE (keep same session)
                    cursor.execute("""
                        UPDATE transactions
                        SET containers=%s, bruto=%s, produce=%s, datetime=NOW()
                        WHERE id=%s
                    """, (containers_norm_str, weight_kg, produce, last_in['id']))
                    conn.commit()

                    return jsonify({
                        "id": str(last_in['id']),
                        "truck": truck,
                        "bruto": weight_kg
                    }), 200

                # else create new session
                session_id = int(time.time())
                cursor.execute("""
                    INSERT INTO transactions
                    (direction, truck, containers, bruto, produce, datetime, session_id)
                    VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                """, (direction, truck, containers_norm_str, weight_kg, produce, session_id))
                conn.commit()

                return jsonify({
                    "id": str(cursor.lastrowid),
                    "truck": truck,
                    "bruto": weight_kg
                }), 201

            # ---------------------------
            # DIRECTION: OUT
            # ---------------------------
            elif direction == 'out':
                # must have previous IN
                cursor.execute("""
                    SELECT *
                    FROM transactions
                    WHERE truck=%s AND direction='in'
                    ORDER BY datetime DESC, id DESC
                    LIMIT 1
                """, (truck,))
                last_in = cursor.fetchone()

                if not last_in:
                    return jsonify({"error": "No previous 'in' record found for truck"}), 409

                session_id = last_in['session_id']
                bruto_in = last_in['bruto']
                truck_tara = weight_kg

                # check existing OUT for that session
                cursor.execute("""
                    SELECT id
                    FROM transactions
                    WHERE session_id=%s AND truck=%s AND direction='out'
                    LIMIT 1
                """, (session_id, truck))
                existing_out = cursor.fetchone()

                if existing_out and not force:
                    return jsonify({"error": "OUT already exists for this session. Use force=true to overwrite."}), 409

                # containers in OUT must match IN or be empty (unless force)
                in_containers_norm = (last_in['containers'] or "").replace(" ", "")
                in_list = [c for c in in_containers_norm.split(',') if c]

                if container_list and container_list != in_list and not force:
                    return jsonify({"error": "OUT containers must match IN containers"}), 409

                # tara validations
                if truck_tara > bruto_in and not force:
                    return jsonify({"error": "Truck tara exceeds bruto"}), 409

                # neto: None if some containers unknown
                neto = calculate_neto(cursor, bruto_in, truck_tara, containers_norm_str)

                # extra validation vs known container weights
                if container_list:
                    placeholders = ','.join(['%s'] * len(container_list))
                    cursor.execute(
                        f"SELECT SUM(weight) as total, COUNT(*) as count "
                        f"FROM containers_registered WHERE container_id IN ({placeholders})",
                        tuple(container_list)
                    )
                    res = cursor.fetchone() or {"total": 0, "count": 0}
                    known_weight = int(res["total"] or 0)

                    if truck_tara > bruto_in - known_weight and not force:
                        return jsonify({"error": "Tara too high vs known containers"}), 409

                if existing_out:
                    # overwrite OUT by UPDATE (keep id)
                    cursor.execute("""
                        UPDATE transactions
                        SET containers=%s, truckTara=%s, neto=%s, produce=%s, datetime=NOW()
                        WHERE id=%s
                    """, (containers_norm_str, truck_tara, neto, produce, existing_out['id']))
                    conn.commit()
                    out_id = existing_out['id']
                    status = 200
                else:
                    cursor.execute("""
                        INSERT INTO transactions
                        (direction, truck, containers, truckTara, neto, produce, datetime, session_id)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                    """, (direction, truck, containers_norm_str, truck_tara, neto, produce, session_id))
                    conn.commit()
                    out_id = cursor.lastrowid
                    status = 201

                return jsonify({
                    "id": str(out_id),
                    "truck": truck,
                    "bruto": bruto_in,
                    "truckTara": truck_tara,
                    "neto": neto if neto is not None else "na"
                }), status

            # ---------------------------
            # DIRECTION: NONE
            # ---------------------------
            else:
                session_id = int(time.time())
                cursor.execute("""
                    INSERT INTO transactions
                    (direction, bruto, datetime, session_id)
                    VALUES (%s, %s, NOW(), %s)
                """, (direction, weight_kg, session_id))
                conn.commit()

                return jsonify({
                    "id": str(cursor.lastrowid),
                    "truck": "na",
                    "bruto": weight_kg
                }), 201

    except mysql.connector.Error as e:
        app.logger.error(f"Database error in POST /weight: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        app.logger.error(f"Server error in POST /weight: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route('/session', defaults={'id': None}, methods=['GET'])
@app.route('/session/<id>', methods=['GET'])
def get_session(id):
    """Get session details by session ID."""
    def serialize_session(row):
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
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor(dictionary=True)) as cursor:

            if id:
                query = """
                    SELECT session_id, MAX(truck) as truck, MAX(bruto) as bruto, 
                           MAX(truckTara) as truckTara, MAX(neto) as neto, 
                           MAX(direction) as direction 
                    FROM transactions 
                    WHERE session_id = %s 
                    GROUP BY session_id
                """
                cursor.execute(query, (id,))
                row = cursor.fetchone()

                if not row:
                    return jsonify({"error": "Session not found"}), 404

                return jsonify(serialize_session(row)), 200
            else:
                query = """
                    SELECT session_id, MAX(truck) as truck, MAX(bruto) as bruto, 
                           MAX(truckTara) as truckTara, MAX(neto) as neto, 
                           MAX(direction) as direction 
                    FROM transactions 
                    GROUP BY session_id
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                return jsonify([serialize_session(row) for row in rows]), 200

    except Exception as e:
        app.logger.error(f"Error getting session: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/batch-weight', methods=['POST'])
def batch_weight():
    """Upload container weights from CSV or JSON file in /in folder."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    filename = data.get('file')
    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    filepath = os.path.join('/in', filename)
    if not os.path.exists(filepath):
        return jsonify({"error": f"File {filename} not found in /in folder"}), 404

    success_count = 0

    try:
        with closing(db_pool.get_connection()) as conn, closing(conn.cursor()) as cursor:
            file_ext = filename.split('.')[-1].lower()

            if file_ext == 'json':
                with open(filepath, 'r') as f:
                    records = json.load(f)
                    for item in records:
                        c_id = item.get('id')
                        w = int(item.get('weight'))
                        u = item.get('unit', 'kg')
                        final_w = int(w * 0.453592) if u == 'lbs' else w
                        cursor.execute("REPLACE INTO containers_registered (container_id, weight, unit) VALUES (%s, %s, 'kg')", (c_id, final_w))
                        success_count += 1

            elif file_ext == 'csv':
                with open(filepath, 'r') as f:
                    reader = csv.reader(f)
                    rows = list(reader)

                    start_idx = 0
                    if rows and rows[0][0].lower() in ['id', 'container_id', 'unit', 'weight']:
                        start_idx = 1

                    for row in rows[start_idx:]:
                        if len(row) < 2:
                            continue

                        c_id = row[0]
                        w = int(row[1])
                        u = row[2].lower() if len(row) > 2 else 'kg'
                        final_w = int(w * 0.453592) if u == 'lbs' else w
                        cursor.execute("REPLACE INTO containers_registered (container_id, weight, unit) VALUES (%s, %s, 'kg')", (c_id, final_w))
                        success_count += 1

            conn.commit()
            return jsonify({"accepted": success_count}), 200

    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Data format error: {str(e)}"}), 400
    except mysql.connector.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0')