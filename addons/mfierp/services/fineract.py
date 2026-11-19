# SPDX-License-Identifier: LGPL-3.0-or-later
"""Small, bounded HTTP adapter. Never expose response bodies or credentials in errors."""

import json
import base64
import re
from urllib.parse import unquote, urlsplit

import requests


class FineractError(Exception):
    def __init__(self, message, *, uncertain=False, status=None):
        super().__init__(message)
        self.uncertain = uncertain
        self.status = status


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Use an HTTPS API base URL without credentials, query or fragment.")
    if parsed.path.rstrip("/") != "/fineract-provider/api/v1":
        raise ValueError("API URL must end in /fineract-provider/api/v1.")
    return url.rstrip("/")


class FineractClient:
    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self, url, tenant, username, password, timeout=30):
        self.url = validate_url(url)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", tenant):
            raise ValueError("Invalid tenant identifier.")
        if not username or not password:
            raise ValueError("Fineract service credentials are missing.")
        self.tenant = tenant
        self.auth = (username, password)
        self.timeout = timeout

    def request(self, method, path, *, params=None, payload=None, idempotency_key=None, allow_empty=False,
            files=None, binary=False, api_version="v1"):
        if api_version not in {"v1", "v2"}:
            raise ValueError("Unsupported Fineract API version.")
        regular_path = bool(re.fullmatch(r"[A-Za-z0-9_/%().,-]+", path)) and all(
            unquote(part) not in {".", ".."} and not any(char in unquote(part) for char in "/\\?#\r\n")
            for part in path.split("/"))
        report_path = method == "GET" and bool(re.fullmatch(r"runreports/[A-Za-z0-9_%()-]+", path))
        if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"} or not (regular_path or report_path):
            raise ValueError("Invalid request route.")
        base = self.url.removesuffix("/v1") + "/" + api_version
        return self._request(method, f"{base}/{path}", params=params, payload=payload,
            idempotency_key=idempotency_key, allow_empty=allow_empty, files=files, binary=binary)

    def info(self):
        return self._request("GET", self.url.removesuffix("/api/v1") + "/actuator/info")

    def _request(self, method, url, *, params=None, payload=None, idempotency_key=None, allow_empty=False,
            files=None, binary=False):
        headers = {"Fineract-Platform-TenantId": self.tenant, "Accept": "application/json"}
        if binary:
            headers["Accept"] = "*/*"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            # No redirects, no implicit retries, TLS verification always enabled.
            body_args = {"data": payload, "files": files} if files is not None else {"json": payload}
            with requests.request(
                method, url, params=params, **body_args,
                headers=headers, auth=self.auth, timeout=(5, self.timeout),
                verify=True, allow_redirects=False, stream=True,
            ) as response:
                status = response.status_code
                if not 200 <= status < 300:
                    raise FineractError(
                        f"Fineract returned HTTP {status}.",
                        uncertain=method != "GET" and (status >= 500 or status in {408, 429}),
                        status=status,
                    )
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > self.MAX_BYTES:
                        raise FineractError("Fineract response exceeds the size limit.", uncertain=method != "GET")
                    chunks.append(chunk)
                data = b"".join(chunks)
                if binary:
                    return {"data": base64.b64encode(data).decode("ascii"),
                        "content_type": response.headers.get("Content-Type", "application/octet-stream")}
                if not data and allow_empty:
                    return {}
                try:
                    return json.loads(data)
                except (ValueError, UnicodeError) as exc:
                    raise FineractError("Fineract returned invalid JSON.", uncertain=method != "GET") from exc
        except requests.RequestException as exc:
            raise FineractError("Fineract transport failed; check connectivity and TLS.", uncertain=method != "GET") from exc

    def pages(self, path, page_size=200, max_pages=50):
        """Handle both paginated portfolio APIs and array reference APIs."""
        for page in range(max_pages):
            result = self.request("GET", path, params={
                "paged": "true", "offset": page * page_size, "limit": page_size,
                "orderBy": "id", "sortOrder": "ASC",
            })
            if isinstance(result, list):
                yield result
                return
            if not isinstance(result, dict) or not isinstance(result.get("pageItems"), list):
                raise FineractError("Unexpected Fineract list response.")
            rows = result["pageItems"]
            yield rows
            if len(rows) < page_size or (page + 1) * page_size >= result.get("totalFilteredRecords", float("inf")):
                return
        raise FineractError("Sync page limit reached. Narrow the portfolio or increase the reviewed limit.")
