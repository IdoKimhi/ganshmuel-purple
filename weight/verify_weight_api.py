import urllib.request
import urllib.error
import json
import time
import sys
import os
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8086"
# Ensure IN_DIR is always relative to this script's location (weight/in)
IN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "in")

# Global stats
STATS = {"passed": 0, "failed": 0}

def print_result(test_name, success, message=""):
    if success:
        STATS["passed"] += 1
        status = "PASS"
    else:
        STATS["failed"] += 1
        status = "FAIL"
    print(f"[{status}] {test_name}: {message}")

def make_request(method, endpoint, data=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}
    
    req = urllib.request.Request(url, method=method, headers=headers)
    
    if data:
        json_data = json.dumps(data).encode('utf-8')
        req.data = json_data
        
    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            response_body = response.read().decode('utf-8')
            try:
                json_body = json.loads(response_body)
            except:
                json_body = response_body
            return status_code, json_body
    except urllib.error.HTTPError as e:
        response_body = e.read().decode('utf-8')
        try:
            json_body = json.loads(response_body)
        except:
            json_body = response_body
        return e.code, json_body
    except Exception as e:
        return 0, str(e)

def run_tests():
    print(f"Starting E2E tests against {BASE_URL}...")
    
    # --- 1. Health Check ---
    # Verifies that the API is up and running (returns 200 OK).
    code, body = make_request("GET", "/health")
    print_result("Health Check", code == 200, f"Code: {code}")
    if code != 200:
        print("Health check failed. Aborting tests.")
        return

    # --- 2. GET /unknown ---
    # Verifies that /unknown endpoint exists and returns 200 OK (list of unknown containers).
    code, body = make_request("GET", "/unknown")
    print_result("GET /unknown", code == 200, f"Code: {code}")

    # --- 3. POST /weight (IN) ---
    # Verifies standard IN transaction for a truck. Expects 201 Created.
    truck_id = "T-12345"
    data_in = {
        "direction": "in",
        "truck": truck_id,
        "containers": "C-1,C-2",
        "weight": 1000,
        "unit": "kg",
        "produce": "apples",
        "force": False
    }
    code, body = make_request("POST", "/weight", data_in)
    print_result("POST /weight (IN)", code == 201, f"Code: {code}, Body: {body}")
    
    # Note: The body returns the Transaction ID, not the Session ID directly.
    # We will fetch the Session ID later via /item/<id>

    # --- 4. POST /weight (IN) Duplicate Force=False ---
    # Verifies that trying to weigh IN again without force=true fails (400 Bad Request).
    code, body = make_request("POST", "/weight", data_in)
    print_result("POST /weight (IN) Duplicate Force=False", code != 201, f"Code: {code} (Expected Error)")

    # --- 5. POST /weight (IN) Duplicate Force=True ---
    # Verifies that force=true allows overwriting an existing IN transaction.
    data_in_force = data_in.copy()
    data_in_force["force"] = True
    data_in_force["weight"] = 1100
    code, body = make_request("POST", "/weight", data_in_force)
    print_result("POST /weight (IN) Duplicate Force=True", code in [200, 201], f"Code: {code}")
    
    # --- 6. POST /weight (NONE) after IN ---
    # Verifies that a truck cannot perform a NONE transaction while currently IN.
    data_none = {
        "direction": "none",
        "truck": truck_id,
        "containers": "C-3",
        "weight": 500,
        "unit": "kg",
        "produce": "pears",
        "force": False
    }
    code, body = make_request("POST", "/weight", data_none)
    print_result("POST /weight (NONE) after IN", code != 201, f"Code: {code} (Expected Error)")

    # --- 7. POST /weight (OUT) ---
    # Verifies standard OUT transaction to close the session. Expects 201 Created.
    data_out = {
        "direction": "out",
        "truck": truck_id,
        "containers": "C-1,C-2", 
        "weight": 200, 
        "unit": "kg",
        "produce": "apples",
        "force": False
    }
    code, body = make_request("POST", "/weight", data_out)
    print_result("POST /weight (OUT)", code == 201, f"Code: {code}")
    if code == 201:
         print(f"   Response Body: {body}")

    # --- 8. POST /weight (OUT) without IN ---
    # Verifies that trying to weigh OUT for a truck not currently IN fails (404/400).
    data_out_bad = data_out.copy()
    data_out_bad["truck"] = "T-99999"
    code, body = make_request("POST", "/weight", data_out_bad)
    print_result("POST /weight (OUT) without IN", code in [400, 404], f"Code: {code} (Expected 400/404)")

    # --- 9. GET /weight (Filter) ---
    # Verifies retrieving transactions with default filters works (200 OK).
    code, body = make_request("GET", "/weight?filter=in,out")
    print_result("GET /weight", code == 200, f"Code: {code}")

    # --- 10. GET /item/<id> (Truck) ---
    # Verifies retrieving history for a specific truck. Used to find valid Session ID.
    code, body = make_request("GET", f"/item/{truck_id}")
    print_result(f"GET /item/{truck_id}", code == 200, f"Code: {code}")
    
    session_id = None
    if code == 200 and isinstance(body, dict):
        sessions = body.get('sessions', [])
        if sessions:
            session_id = sessions[0]
            print(f"   Found Session ID from history: {session_id}")

    # --- 11. GET /session/<id> ---
    # Verifies retrieving a specific session by ID (using ID found in previous step).
    if session_id:
        code, body = make_request("GET", f"/session/{session_id}")
        print_result(f"GET /session/{session_id}", code == 200, f"Code: {code}")
    else:
        print("[SKIP] GET /session/<id> - No session ID found in item history")

    # --- 12. POST /batch-weight (CSV) ---
    # Verifies batch upload using existing mock file 'containers1.csv'.
    csv_file = "containers1.csv"
    if os.path.exists(os.path.join(IN_DIR, csv_file)):
        batch_data = {"file": csv_file} 
        code, body = make_request("POST", "/batch-weight", batch_data)
        print_result("POST /batch-weight (CSV)", code == 200, f"Code: {code}")
    else:
        print(f"[SKIP] POST /batch-weight (CSV) - {csv_file} not found in {IN_DIR}")

    # --- 13. POST /batch-weight (JSON) ---
    # Verifies batch upload using existing mock file 'containers3.json'.
    json_file = "containers3.json"
    if os.path.exists(os.path.join(IN_DIR, json_file)):
        batch_data = {"file": json_file} 
        code, body = make_request("POST", "/batch-weight", batch_data)
        print_result("POST /batch-weight (JSON)", code == 200, f"Code: {code}")
    else:
        print(f"[SKIP] POST /batch-weight (JSON) - {json_file} not found in {IN_DIR}")

    # --- 14. GET /weight (Specific Filter) ---
    # Verifies that ?filter=in returns ONLY 'in' direction transactions.
    code, body = make_request("GET", "/weight?filter=in")
    is_only_in = True
    if code == 200 and isinstance(body, list):
        for item in body:
            if item.get('direction') != 'in':
                is_only_in = False
                break
    print_result("GET /weight?filter=in", code == 200 and is_only_in, f"Code: {code}")

    # --- 15. GET /weight (Date Filter) ---
    # Verifies filtering transactions by date range (from/to).
    now = datetime.now()
    t1 = (now - timedelta(days=1)).strftime("%Y%m%d%H%M%S")
    t2 = (now + timedelta(days=1)).strftime("%Y%m%d%H%M%S")
    
    code, body = make_request("GET", f"/weight?from={t1}&to={t2}&filter=in,out,none")
    print_result("GET /weight (Date Filter)", code == 200, f"Code: {code}")

    # --- 16. GET /weight (Invalid Date) ---
    # Verifies that invalid date formats return 400 Bad Request.
    code, body = make_request("GET", "/weight?from=INVALID&to=INVALID")
    print_result("GET /weight (Invalid Date)", code == 400, f"Code: {code} (Expected 400)")

    # --- EDGE CASES ---
    print("\n--- Edge Case Tests ---")
    
    required_fields = ['direction', 'truck', 'containers', 'weight', 'unit', 'produce', 'force']
    base_data = {
        "direction": "in",
        "truck": "T-EDGE",
        "containers": "C-EDGE",
        "weight": 100,
        "unit": "kg",
        "produce": "test",
        "force": False
    }
    
    # Missing Fields
    # Verifies that omitting any mandatory field results in 400 Bad Request.
    for field in required_fields:
        bad_data = base_data.copy()
        del bad_data[field]
        code, body = make_request("POST", "/weight", bad_data)
        print_result(f"Missing Field: {field}", code == 400, f"Code: {code} (Expected 400)")

    # Invalid Values
    # Verifies various invalid input values (negative weight, bad unit, empty strings, etc.)
    edge_cases = [
        ("Invalid Weight (Negative)", "weight", -100),
        ("Invalid Unit", "unit", "tons"),
        ("Empty Truck", "truck", ""),
        ("Weight as String", "weight", "100"),
        ("Float Weight", "weight", 100.5),
        ("Zero Weight", "weight", 0),
        ("Whitespace Truck", "truck", "   "),
        ("Whitespace Produce", "produce", "   "),
        ("Empty Containers (IN)", "containers", ""),
        ("Force as String", "force", "true")
    ]

    for name, field, value in edge_cases:
        bad_data = base_data.copy()
        bad_data[field] = value
        code, body = make_request("POST", "/weight", bad_data)
        print_result(name, code == 400, f"Code: {code} (Expected 400)")

    # --- STATE TRANSITION TESTS ---
    print("\n--- State Transition Tests ---")
    
    # OUT -> OUT (force=false)
    # Verifies that weighing OUT twice for the same session fails without force=true.
    truck_state = "T-STATE-1"
    make_request("POST", "/weight", {"direction": "in", "truck": truck_state, "containers": "C-X", "weight": 1000, "unit": "kg", "produce": "test", "force": False})
    make_request("POST", "/weight", {"direction": "out", "truck": truck_state, "containers": "C-X", "weight": 200, "unit": "kg", "produce": "test", "force": False})
    
    code, body = make_request("POST", "/weight", {"direction": "out", "truck": truck_state, "containers": "C-X", "weight": 250, "unit": "kg", "produce": "test", "force": False})
    print_result("OUT -> OUT (force=false)", code == 400, f"Code: {code} (Expected 400)")

    # OUT -> OUT (force=true)
    # Verifies that force=true allows updating an existing OUT transaction.
    code, body = make_request("POST", "/weight", {"direction": "out", "truck": truck_state, "containers": "C-X", "weight": 300, "unit": "kg", "produce": "test", "force": True})
    print_result("OUT -> OUT (force=true)", code in [200, 201], f"Code: {code}")

    # NONE -> NONE
    # Verifies that standalone NONE transactions are allowed and don't affect state.
    code, body = make_request("POST", "/weight", {"direction": "none", "truck": "na", "containers": "", "weight": 100, "unit": "kg", "produce": "standalone", "force": False})
    print_result("NONE -> NONE", code == 201, f"Code: {code}")

    # OUT -> IN (New Session)
    # Verifies that after weighing OUT, a truck can start a fresh IN session.
    truck_cycle = "T-CYCLE"
    make_request("POST", "/weight", {"direction": "in", "truck": truck_cycle, "containers": "C-Y", "weight": 1000, "unit": "kg", "produce": "apples", "force": False})
    make_request("POST", "/weight", {"direction": "out", "truck": truck_cycle, "containers": "C-Y", "weight": 200, "unit": "kg", "produce": "apples", "force": False})
    code, body = make_request("POST", "/weight", {"direction": "in", "truck": truck_cycle, "containers": "C-Z", "weight": 1100, "unit": "kg", "produce": "oranges", "force": False})
    print_result("OUT -> IN (New Session)", code == 201, f"Code: {code}")

    # Multiple Different Trucks IN Simultaneously
    # Verifies that multiple trucks can be IN at the same time without interference.
    truck_a = "T-MULTI-A"
    truck_b = "T-MULTI-B"
    
    data_a = {"direction": "in", "truck": truck_a, "containers": "C-A", "weight": 500, "unit": "kg", "produce": "apples", "force": False}
    code_a, body_a = make_request("POST", "/weight", data_a)
    
    data_b = {"direction": "in", "truck": truck_b, "containers": "C-B", "weight": 600, "unit": "kg", "produce": "oranges", "force": False}
    code_b, body_b = make_request("POST", "/weight", data_b)
    
    print_result("Multiple Trucks IN Simultaneously", code_a == 201 and code_b == 201, f"Truck A: {code_a}, Truck B: {code_b}")

    print("\n" + "="*30)
    print("TEST RESULTS SUMMARY")
    print("="*30)
    print(f"Total Tests: {STATS['passed'] + STATS['failed']}")
    print(f"Passed:      {STATS['passed']}")
    print(f"Failed:      {STATS['failed']}")
    print("="*30)

if __name__ == "__main__":
    try:
        run_tests()
    except KeyboardInterrupt:
        print("\nAborted.")
