"""GET-only public staging discovery; emits no credentials or business records."""
import argparse
import json
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", help="Local non-secret JSON site profile")
    args = parser.parse_args()
    with open(args.profile, encoding="utf-8") as source:
        profile = json.load(source)
    origin = profile["origin"].rstrip("/")
    url = urlsplit(origin)
    if url.scheme != "https" or not url.hostname or url.path or url.query or url.fragment or url.username or url.password:
        raise ValueError("Use an HTTPS origin without path, query or credentials.")
    result = {"http_methods": "GET_ONLY", "business_api_writes": "NONE", "credentials_modified": "NONE"}
    for name, path in [("web", "/"), ("runtime_config", "/assets/env.js"),
            ("health", "/fineract-provider/actuator/health"), ("provenance", "/fineract-provider/actuator/info")]:
        try:
            with urlopen(origin + path, timeout=20) as response:
                body = response.read(2 * 1024 * 1024)
                result[name + "_http"] = response.status
            if name == "health":
                result["health_status"] = json.loads(body).get("status")
            if name == "provenance":
                info = json.loads(body)
                git = info.get("git") or {}
                result["version"] = (git.get("build") or {}).get("version") or (info.get("build") or {}).get("version")
                result["commit"] = ((git.get("commit") or {}).get("id") or {}).get("full")
                result["git_dirty"] = git.get("dirty")
        except HTTPError as exc:
            result[name + "_http"] = exc.code
        except (ValueError, OSError):
            result[name + "_status"] = "UNVERIFIED"
    print(json.dumps(result, indent=2))
    return 0 if result.get("health_status") == "UP" and result.get("commit") else 1


if __name__ == "__main__":
    raise SystemExit(main())
