"""Compare a source-derived Mifos endpoint inventory with the pinned Fineract catalog.

The result is contract coverage evidence, not a feature-parity or UAT certificate.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path


def pattern(path):
    path = path.split("?", 1)[0].strip("/")
    if path.startswith("v1/"):
        path = path[3:]
    path = re.sub(r"\$\{[^}]+\}", "{}", path)
    path = re.sub(r"\{[^}]*\}", "{}", path)
    return path


def inventory(calls, catalog, repo, revision):
    rows = []
    for call in calls:
        source_pattern = pattern(call["path"])
        def compatible(api_path, source_pattern=source_pattern):
            left, right = source_pattern.split("/"), pattern(api_path.removeprefix("/v1/")).split("/")
            return len(left) == len(right) and all(a == b or a == "{}" or b == "{}" for a, b in zip(left, right, strict=True))
        matches = [entry for entry in catalog["capabilities"] if entry["method"] == call["method"] and compatible(entry["path"])]
        ready = [entry for entry in matches if not entry["blocked"]]
        dynamic = source_pattern.split("/")[0] == "{}"
        state = "DYNAMIC_RESOURCE_REQUIRES_REVIEW" if dynamic else "TYPED_CONTRACT_CANDIDATE" if ready else "CONTRACT_REQUIRES_SOURCE_WORK" if matches else "NOT_IN_DEPLOYED_OPENAPI"
        rows.append({**call, "area": call["source"].split("/")[2], "status": state,
            "dynamic_resource_segment": dynamic,
            "source_url": f"https://github.com/{repo}/blob/{revision}/{call['source']}#L{call['line']}",
            "capabilities": [entry["key"] for entry in matches],
            "remaining_contract_issues": sorted({entry["blocked"] for entry in matches if entry["blocked"]}),
            "operator_workflow_verified": False, "live_uat_verified": False})
    return {"source_repository": repo, "source_revision": revision, "fineract_api_version": catalog["api_version"],
        "api_source_sha256": catalog["source_sha256"], "inventory_scope": "Literal HTTP calls in Mifos service files; computed URLs and component workflows require separate review.",
        "counts": dict(Counter(row["status"] for row in rows)), "calls": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("calls")
    parser.add_argument("catalog")
    parser.add_argument("output")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    result = inventory(json.loads(Path(args.calls).read_text(encoding="utf-8")),
        json.loads(Path(args.catalog).read_text(encoding="utf-8")), args.repo, args.revision)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["counts"])
