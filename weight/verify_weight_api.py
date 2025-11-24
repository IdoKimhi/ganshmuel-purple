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

    # --- ADDITIONAL EDGE CASES ---
    print("\n--- Additional Edge Cases ---")
    
    # Use unique truck IDs to avoid session ID collisions (since app uses int(time.time()))
    ts = int(time.time())

    # 1. Unknown Tara Logic
    # Scenario: Container ID not in DB. Expect 'neto': 'na'.
    time.sleep(1.5) # Wait for unique session ID
    truck_unknown = f"T-UNKNOWN-{ts}"
    # IN (Use force=True to ensure clean state)
    make_request("POST", "/weight", {"direction": "in", "truck": truck_unknown, "containers": "C-UNKNOWN-1", "weight": 5000, "unit": "kg", "produce": "mystery", "force": True})
    # OUT
    code, body = make_request("POST", "/weight", {"direction": "out", "truck": truck_unknown, "containers": "C-UNKNOWN-1", "weight": 2000, "unit": "kg", "produce": "mystery", "force": False})
    
    is_na = False
    if code in [200, 201] and isinstance(body, dict):
        if body.get("neto") == "na":
            is_na = True
    print_result("Unknown Tara (neto='na')", is_na, f"Code: {code}, Neto: {body.get('neto') if isinstance(body, dict) else 'N/A'}")
    if not is_na:
        print(f"   Response Body: {body}")

    # 3. Container Swapping (IN vs OUT)
    # Scenario: Truck IN with C-35434 (296kg), OUT with C-73281 (273kg).
    time.sleep(1.5) # Wait for unique session ID
    truck_swap = f"T-SWAP-{ts}"
    # IN with C-35434
    make_request("POST", "/weight", {"direction": "in", "truck": truck_swap, "containers": "C-35434", "weight": 10000, "unit": "kg", "produce": "swap_test", "force": True})
    # OUT with C-73281
    code, body = make_request("POST", "/weight", {"direction": "out", "truck": truck_swap, "containers": "C-73281", "weight": 2000, "unit": "kg", "produce": "swap_test", "force": False})
    
    print_result("Container Swapping (IN!=OUT)", code in [200, 201], f"Code: {code}")
    if code in [200, 201]:
        print(f"   Neto with swapped container: {body.get('neto')}")
    else:
        print(f"   Response Body: {body}")

    # 4. Zero Net Weight
    # Scenario: Neto = Bruto(IN) - Weight(OUT) - Tara(Containers) = 0
    # C-35434 Tara = 296kg.
    # Weight(OUT) [Truck Tara] = 1000kg.
    # Bruto(IN) = 1000 + 296 = 1296kg.
    # Neto = 1296 - 1000 - 296 = 0.
    time.sleep(1.5) # Wait for unique session ID
    truck_zero = f"T-ZERO-{ts}"
    # IN - Use force=True
    make_request("POST", "/weight", {"direction": "in", "truck": truck_zero, "containers": "C-35434", "weight": 1296, "unit": "kg", "produce": "nothing", "force": True})
    # OUT
    code, body = make_request("POST", "/weight", {"direction": "out", "truck": truck_zero, "containers": "C-35434", "weight": 1000, "unit": "kg", "produce": "nothing", "force": False})
    
    is_zero = False
    if code in [200, 201] and isinstance(body, dict):
        neto = body.get("neto")
        if neto == 0 or neto == "0":
            is_zero = True
    print_result("Zero Net Weight", is_zero, f"Code: {code}, Neto: {body.get('neto') if isinstance(body, dict) else 'N/A'}")
    if not is_zero:
        print(f"   Response Body: {body}")

    # --- DEEP DIVE TESTS (GET /item & GET /unknown) ---
    print("\n--- Deep Dive Tests ---")

    # Deep Dive 1: GET /unknown Format
    # Verifies that /unknown returns a list (not just 200 OK).
    code, body = make_request("GET", "/unknown")
    is_list = isinstance(body, list)
    print_result("GET /unknown returns List", is_list, f"Type: {type(body)}")

    # Deep Dive 2: GET /item Non-existent ID
    # Verifies that querying a non-existent ID returns 404.
    fake_id = "NON_EXISTENT_ID_99999"
    code, body = make_request("GET", f"/item/{fake_id}")
    print_result("GET /item (Non-existent) returns 404", code == 404, f"Code: {code}")

    # Deep Dive 3: GET /item Valid Keys
    # Verifies that a valid response contains 'id', 'tara', and 'sessions' keys.
    # Using 'truck_id' from earlier tests (T-12345).
    code, body = make_request("GET", f"/item/{truck_id}")
    has_keys = False
    if code == 200 and isinstance(body, dict):
        has_keys = all(k in body for k in ["id", "tara", "sessions"])
    print_result("GET /item Response Keys", has_keys, f"Keys: {list(body.keys()) if isinstance(body, dict) else 'Not Dict'}")

    # Deep Dive 4: GET /item Date Filter (Future)
    # Verifies that filtering for a future date range returns an empty sessions list.
    future_t1 = (datetime.now() + timedelta(days=300)).strftime("%Y%m%d%H%M%S")
    future_t2 = (datetime.now() + timedelta(days=301)).strftime("%Y%m%d%H%M%S")
    code, body = make_request("GET", f"/item/{truck_id}?from={future_t1}&to={future_t2}")
    sessions_empty = False
    if isinstance(body, dict):
        sessions = body.get("sessions")
        if isinstance(sessions, list) and len(sessions) == 0:
            sessions_empty = True
    print_result("GET /item Date Filter (Future)", sessions_empty, f"Sessions: {body.get('sessions') if isinstance(body, dict) else body}")

    # Deep Dive 5: GET /item Invalid Date Format
    # Verifies that invalid date format returns 400 Bad Request.
    code, body = make_request("GET", f"/item/{truck_id}?from=INVALID_DATE")
    print_result("GET /item Invalid Date Format", code >= 400, f"Code: {code}")

    # Deep Dive 6: GET /item Impossible Range
    # Verifies that from > to is handled gracefully (returns error).
    t1_late = "20251231235959"
    t2_early = "20200101000000"
    code, body = make_request("GET", f"/item/{truck_id}?from={t1_late}&to={t2_early}")
    print_result("GET /item Impossible Range", code >= 400, f"Code: {code}")

    # Deep Dive 7: GET /item Unknown Container
    # Verifies that an unknown container (in transactions but not registered) returns 200 with tara='na'.
    code, body = make_request("GET", "/unknown")
    unknown_container = None
    if isinstance(body, list) and len(body) > 0:
        unknown_container = body[0]
    
    if unknown_container:
        code, body = make_request("GET", f"/item/{unknown_container}")
        is_valid = False
        if code == 200 and isinstance(body, dict):
            if body.get("tara") == "na" and "sessions" in body:
                is_valid = True
        print_result("GET /item Unknown Container", is_valid, f"Container: {unknown_container}, Tara: {body.get('tara') if isinstance(body, dict) else 'N/A'}")
    else:
        print("[SKIP] GET /item Unknown Container - No unknown containers found")

    # Deep Dive 8: GET /item Registered Container
    # Verifies that a registered container returns 200 with numeric tara.
    registered_container = "C-35434"  # From containers1.csv
    code, body = make_request("GET", f"/item/{registered_container}")
    is_valid = False
    if code == 200 and isinstance(body, dict):
        tara = body.get("tara")
        if tara != "na" and isinstance(tara, (int, float)):
            is_valid = True
    print_result("GET /item Registered Container", is_valid, f"Container: {registered_container}, Tara: {body.get('tara') if isinstance(body, dict) else 'N/A'}")

    # Deep Dive 9: GET /item Default Dates
    # Verifies that omitting from/to uses defaults (1st of month -> now).
    code, body = make_request("GET", f"/item/{truck_id}")
    has_sessions = False
    if code == 200 and isinstance(body, dict):
        sessions = body.get("sessions")
        if isinstance(sessions, list):
            has_sessions = True
    print_result("GET /item Default Dates", has_sessions, f"Code: {code}, Sessions: {body.get('sessions') if isinstance(body, dict) else 'N/A'}")

    # Deep Dive 10: GET /item Partial Filter (only 'from')
    # Verifies that providing only 'from' uses default 'to' (now).
    past_date = "20200101000000"
    code, body = make_request("GET", f"/item/{truck_id}?from={past_date}")
    has_sessions = False
    if code == 200 and isinstance(body, dict):
        sessions = body.get("sessions")
        if isinstance(sessions, list):
            has_sessions = True
    print_result("GET /item Partial Filter (from)", has_sessions, f"Code: {code}")

    # Deep Dive 11: GET /item Partial Filter (only 'to')
    # Verifies that providing only 'to' uses default 'from' (1st of month).
    future_date = "20300101000000"
    code, body = make_request("GET", f"/item/{truck_id}?to={future_date}")
    has_sessions = False
    if code == 200 and isinstance(body, dict):
        sessions = body.get("sessions")
        if isinstance(sessions, list):
            has_sessions = True
    print_result("GET /item Partial Filter (to)", has_sessions, f"Code: {code}")

    # Deep Dive 12: GET /item Past Date Range (No Sessions)
    # Verifies that a valid date range with no sessions returns empty list.
    old_t1 = "19900101000000"
    old_t2 = "19910101000000"
    code, body = make_request("GET", f"/item/{truck_id}?from={old_t1}&to={old_t2}")
    sessions_empty = False
    if code == 200 and isinstance(body, dict):
        sessions = body.get("sessions")
        if isinstance(sessions, list) and len(sessions) == 0:
            sessions_empty = True
    print_result("GET /item Past Range (Empty)", sessions_empty, f"Sessions: {body.get('sessions') if isinstance(body, dict) else 'N/A'}")

    # Deep Dive 13: GET /unknown Empty Check
    # Verifies that /unknown returns an empty list when no unknown containers exist (or non-empty if they do).
    code, body = make_request("GET", "/unknown")
    is_list = isinstance(body, list)
    print_result("GET /unknown List Type", is_list, f"Type: {type(body)}, Length: {len(body) if is_list else 'N/A'}")

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
