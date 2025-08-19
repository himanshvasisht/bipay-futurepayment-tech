import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


def post(path, payload):
    url = BASE + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            status = r.getcode()
            body = r.read().decode("utf-8")
            print(f"POST {path} -> STATUS {status}")
            try:
                print(json.dumps(json.loads(body), indent=2))
            except Exception:
                print(body)
            return status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp is not None else ""
        print(f"POST {path} -> HTTP_ERROR {e.code}")
        try:
            print(json.dumps(json.loads(body), indent=2))
        except Exception:
            print(body)
        return e.code, body
    except Exception as e:
        print(f"POST {path} -> ERROR {e}")
        return None, str(e)


if __name__ == '__main__':
    print('Running backend smoke tests against', BASE)

    register_payload = {
        "first_name": "Test",
        "last_name": "User",
        "email": "smoketest+1@example.com",
        "phone_number": "1234567890",
        "password": "password123",
        "fingerprint_data": "simulated-fingerprint-data-1"
    }

    status, body = post('/api/v1/auth/register', register_payload)

    # attempt to extract user_id from response
    user_id = None
    try:
        j = json.loads(body)
        if isinstance(j, dict):
            user_id = j.get('user_id') or (j.get('user') and j.get('user').get('user_id'))
    except Exception:
        user_id = None

    if user_id:
        print('\nAttempting login for user_id:', user_id)
        login_payload = {
            "user_id": user_id,
            "fingerprint_data": "simulated-fingerprint-data-1"
        }
        post('/api/v1/auth/login', login_payload)
    else:
        print('\nCould not determine user_id from register response; skipping login.')
