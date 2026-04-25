import urllib.request
import json
import base64

def run():
    auth = base64.b64encode(b"admin:admin").decode("utf-8")
    req = urllib.request.Request("http://localhost:3000/api/datasources")
    req.add_header("Authorization", f"Basic {auth}")

    correct_uid = None
    with urllib.request.urlopen(req) as resp:
        datasources = json.loads(resp.read().decode())
        for ds in datasources:
            if ds['type'] == 'cloudwatch':
                if '1' in ds['name'] or 'working' in ds['name'] or ds['name'].lower() == 'cloudwatch-1':
                    correct_uid = ds['uid']
                    print(f"Found perfectly configured Data Source: {ds['name']} (UID: {correct_uid})")
                else:
                    print(f"Found broken default Data Source: {ds['name']}. Deleting...")
                    del_req = urllib.request.Request(f"http://localhost:3000/api/datasources/uid/{ds['uid']}", method="DELETE")
                    del_req.add_header("Authorization", f"Basic {auth}")
                    try:
                        urllib.request.urlopen(del_req)
                    except Exception as e:
                        print("Could not delete:", e)

    if not correct_uid:
        print("WARNING: Could not identify 'cloudwatch-1'. Attempting fallback.")
        with urllib.request.urlopen(req) as resp:
            datasources = json.loads(resp.read().decode())
            for ds in datasources:
                if ds['type'] == 'cloudwatch':
                    correct_uid = ds['uid']
                    break

    # Patch dashboard JSON
    with open("grafana/dashboard.json") as f:
        dash_str = f.read()
    
    dash = json.loads(dash_str)
    for p in dash.get('panels', []):
        if 'datasource' in p and type(p['datasource']) == dict and p['datasource'].get('type') == 'cloudwatch':
            p['datasource']['uid'] = correct_uid

    # Safely push it 
    payload = json.dumps({
        "dashboard": dash,
        "overwrite": True
    }).encode("utf-8")

    req2 = urllib.request.Request("http://localhost:3000/api/dashboards/db", data=payload, method="POST")
    req2.add_header("Content-Type", "application/json")
    req2.add_header("Authorization", f"Basic {auth}")
    try:
        with urllib.request.urlopen(req2) as resp:
            print("✅ Successfully forced the dashboard to use the working credentials!")
    except urllib.error.HTTPError as e:
        print(f"❌ Error uploading dashboard: {e.read().decode()}")

if __name__ == "__main__":
    run()
