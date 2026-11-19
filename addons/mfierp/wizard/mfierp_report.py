# SPDX-License-Identifier: LGPL-3.0-or-later
import re
from urllib.parse import quote

from markupsafe import Markup, escape

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from ..services.fineract import FineractError


class MfierpReport(models.TransientModel):
    _name = "mfierp.report"
    _description = "Run a Fineract Report"
    _check_company_auto = True

    backend_id = fields.Many2one("mfierp.backend", string="Fineract Connection", required=True, check_company=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    report_id = fields.Many2one("mfierp.record", required=True, check_company=True,
        domain="[('backend_id', '=', backend_id), ('kind', '=', 'report')]")
    office_id = fields.Many2one("mfierp.record", check_company=True,
        domain="[('backend_id', '=', backend_id), ('kind', '=', 'office')]")
    client_id = fields.Many2one("mfierp.record", check_company=True,
        domain="[('backend_id', '=', backend_id), ('kind', '=', 'client')]")
    start_date = fields.Date()
    end_date = fields.Date()
    currency_code = fields.Char()
    result_html = fields.Html(readonly=True, sanitize=True)

    def action_run(self):
        self.ensure_one()
        self.check_access("read")
        if not self.env.user.has_group("mfierp.group_reader"):
            raise AccessError(_("An MFIERP reader role is required."))
        self.backend_id.check_access("read")
        self.report_id.check_access("read")
        if self.report_id.backend_id != self.backend_id or self.report_id.kind != "report":
            raise UserError(_("Select a report from this connection."))
        data = self.report_id.sudo().raw_data or {}
        report_name = data.get("reportName") or data.get("name")
        if not report_name or not re.fullmatch(r"[A-Za-z0-9 _()-]{1,150}", report_name):
            raise UserError(_("This report name is unsupported. Use Fineract for this report."))
        if data.get("reportType") not in {"Table", None}:
            raise UserError(_("This screen supports Fineract table reports. Other formats require the upstream report viewer."))
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise UserError(_("Start date must be on or before end date."))
        params = {}
        for record, kind, key in [(self.office_id, "office", "R_officeId"), (self.client_id, "client", "R_clientId")]:
            if record:
                record.check_access("read")
                if record.backend_id != self.backend_id or record.kind != kind:
                    raise UserError(_("Report parameters must belong to the selected connection."))
                params[key] = record.remote_id
        for key, value in [("R_startDate", self.start_date), ("R_endDate", self.end_date)]:
            if value:
                params[key] = fields.Date.to_string(value)
        if self.currency_code:
            if not re.fullmatch(r"[A-Z]{3}", self.currency_code):
                raise UserError(_("Use a three-letter currency code."))
            params["R_currencyId"] = self.currency_code
        try:
            result = self.backend_id._client().request("GET", "runreports/" + quote(report_name, safe=""), params=params)
        except FineractError as exc:
            raise UserError(str(exc)) from exc
        if not isinstance(result, dict) or not isinstance(result.get("columnHeaders"), list) or not isinstance(result.get("data"), list):
            raise UserError(_("Fineract did not return a supported table report."))
        if len(result["data"]) > 5000:
            raise UserError(_("Report exceeds 5,000 rows. Narrow the date range or office."))
        header = Markup("").join(Markup("<th>%s</th>") % escape(col.get("columnName", "")) for col in result["columnHeaders"])
        body = Markup("").join(Markup("<tr>%s</tr>") % Markup("").join(
            Markup("<td>%s</td>") % escape("" if value is None else str(value)) for value in row.get("row", [])) for row in result["data"])
        self.result_html = Markup('<table class="table table-striped"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>') % (header, body)
        return {"type": "ir.actions.act_window", "name": _("Fineract Report"), "res_model": self._name,
            "res_id": self.id, "view_mode": "form", "target": "current"}
