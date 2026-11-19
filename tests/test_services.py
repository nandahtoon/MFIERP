# SPDX-License-Identifier: LGPL-3.0-or-later
"""Run with `py -m unittest discover -s tests -v`; no Odoo installation needed."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "addons/mfierp/services" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


operations = load_module("operations")
fineract = load_module("fineract")


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.payload = {"transactionDate": "2026-11-18", "transactionAmount": 10.25, "dateFormat": "yyyy-MM-dd", "locale": "en"}

    def test_repayment_endpoint_and_command(self):
        self.assertEqual(operations.build_request("repay_loan", 17, self.payload),
            ("loans/17/transactions", {"command": "repayment"}))

    def test_reject_unreviewed_parameters_and_arbitrary_operations(self):
        for op, payload in [("repay_loan", dict(self.payload, command="disburse")), ("arbitrary", self.payload)]:
            with self.assertRaises(ValueError):
                operations.build_request(op, 17, payload)

    def test_reject_invalid_amounts_identifiers_dates(self):
        for value in [0, -10, "NaN", "Infinity"]:
            with self.assertRaises(ValueError):
                operations.build_request("repay_loan", 17, dict(self.payload, transactionAmount=value))
        for value in [0, -1, True, "17"]:
            with self.assertRaises(ValueError):
                operations.build_request("repay_loan", value, self.payload)
        with self.assertRaises(ValueError):
            operations.build_request("repay_loan", 17, dict(self.payload, transactionDate="2026-02-30"))

    def test_every_registered_operation_has_a_valid_route(self):
        for operation, (_, _kind, _command, _tx, required, _optional) in operations.OPERATIONS.items():
            payload = {key: 1 if key.endswith("Id") or key in {"principal", "transactionAmount"} else
                "2026-11-18" if key.endswith("Date") else "test" for key in required}
            payload.update(dateFormat="yyyy-MM-dd", locale="en")
            operations.build_request(operation, 0 if operation.startswith("create_") else 1, payload)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.client = fineract.FineractClient("https://fineract.example/fineract-provider/api/v1", "default", "svc", "secret")

    def test_secure_url_required(self):
        for url in ["http://example.com/fineract-provider/api/v1", "https://u:p@example.com/fineract-provider/api/v1",
                "https://example.com/elsewhere", "https://example.com/fineract-provider/api/v1?password=x"]:
            with self.assertRaises(ValueError):
                fineract.validate_url(url)

    @patch.object(fineract.requests, "request")
    def test_transport_uses_tenant_tls_timeout_and_idempotency(self, request):
        response = MagicMock(status_code=200)
        response.iter_content.return_value = [b'{"resourceId": 7}']
        request.return_value.__enter__.return_value = response
        result = self.client.request("POST", "loans/7/transactions", payload={"x": 1}, idempotency_key="unique")
        self.assertEqual(result["resourceId"], 7)
        args = request.call_args.kwargs
        self.assertTrue(args["verify"])
        self.assertFalse(args["allow_redirects"])
        self.assertEqual(args["headers"]["Fineract-Platform-TenantId"], "default")
        self.assertEqual(args["headers"]["Idempotency-Key"], "unique")
        self.assertEqual(args["timeout"], (5, 30))

    @patch.object(fineract.requests, "request")
    def test_timeout_marks_post_uncertain_and_redacts_secret(self, request):
        request.side_effect = fineract.requests.Timeout("secret account and password")
        with self.assertRaises(fineract.FineractError) as caught:
            self.client.request("POST", "clients", payload={})
        self.assertTrue(caught.exception.uncertain)
        self.assertNotIn("secret", str(caught.exception))

    @patch.object(fineract.requests, "request")
    def test_remote_errors_redacted_and_5xx_uncertain(self, request):
        for status, uncertain in [(400, False), (401, False), (429, True), (500, True)]:
            request.return_value.__enter__.return_value = MagicMock(status_code=status)
            with self.assertRaises(fineract.FineractError) as caught:
                self.client.request("POST", "clients", payload={})
            self.assertEqual(caught.exception.uncertain, uncertain)

    def test_pagination_and_bounds(self):
        with patch.object(self.client, "request", side_effect=[
                {"pageItems": [{"id": 1}, {"id": 2}], "totalFilteredRecords": 3},
                {"pageItems": [{"id": 3}], "totalFilteredRecords": 3}]) as request:
            self.assertEqual(sum(list(self.client.pages("clients", page_size=2)), []), [{"id": 1}, {"id": 2}, {"id": 3}])
            self.assertEqual(request.call_args.kwargs["params"]["offset"], 2)
        with patch.object(self.client, "request", return_value={"pageItems": [{"id": 1}]}):
            with self.assertRaises(fineract.FineractError):
                list(self.client.pages("clients", page_size=1, max_pages=2))

    @patch.object(fineract.requests, "request")
    def test_invalid_success_body_is_uncertain_for_writes(self, request):
        response = MagicMock(status_code=200)
        response.iter_content.return_value = [b'not json']
        request.return_value.__enter__.return_value = response
        with self.assertRaises(fineract.FineractError) as caught:
            self.client.request("POST", "clients", payload={})
        self.assertTrue(caught.exception.uncertain)

    def test_reference_array_and_invalid_list_shape(self):
        with patch.object(self.client, "request", return_value=[{"id": 1}]):
            self.assertEqual(list(self.client.pages("offices")), [[{"id": 1}]])
        with patch.object(self.client, "request", return_value={"unexpected": []}):
            with self.assertRaises(fineract.FineractError):
                list(self.client.pages("clients"))

    def test_path_validation_rejects_arbitrary_destinations(self):
        for path in ["https://attacker.example", "../users", "clients?command=delete", "clients/1#fragment"]:
            with self.assertRaises(ValueError):
                self.client.request("GET", path)

    @patch.object(fineract.requests, "request")
    def test_multipart_upload_and_empty_delete_response(self, request):
        response = MagicMock(status_code=204)
        response.iter_content.return_value = []
        request.return_value.__enter__.return_value = response
        self.assertEqual(self.client.request("DELETE", "clients/1/identifiers/2", allow_empty=True), {})
        files = [("file", ("synthetic.pdf", b"synthetic", "application/pdf"))]
        self.client.request("POST", "clients/1/documents", payload={"name": "Synthetic"}, files=files, allow_empty=True)
        self.assertEqual(request.call_args.kwargs["files"], files)
        self.assertNotIn("json", request.call_args.kwargs)

    @patch.object(fineract.requests, "request")
    def test_bounded_binary_download_remains_authenticated(self, request):
        response = MagicMock(status_code=200, headers={"Content-Type": "application/pdf"})
        response.iter_content.return_value = [b"synthetic pdf"]
        request.return_value.__enter__.return_value = response
        result = self.client.request("GET", "clients/1/documents/2/attachment", binary=True)
        self.assertEqual(result["data"], "c3ludGhldGljIHBkZg==")
        self.assertEqual(request.call_args.kwargs["auth"], ("svc", "secret"))

    @patch.object(fineract.requests, "request")
    def test_v2_stays_on_the_configured_host_and_api_root(self, request):
        response = MagicMock(status_code=200)
        response.iter_content.return_value = [b'{"pageItems":[]}']
        request.return_value.__enter__.return_value = response
        self.client.request("GET", "groups", api_version="v2")
        self.assertTrue(request.call_args.args[1].endswith("/fineract-provider/api/v2/groups"))
        with self.assertRaises(ValueError):
            self.client.request("GET", "groups", api_version="../other")


if __name__ == "__main__":
    unittest.main()
