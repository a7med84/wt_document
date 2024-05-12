from odoo.http import content_disposition, route, request, Controller
from odoo.addons.web.controllers import main as report
from odoo import http
import base64
import io


class CustomController(report.ReportController):
    @route(['/report/download'], type='http', auth="user")
    def report_download(self, data, token):
        res = super(CustomController, self).report_download(data, token)
        print("datadatadata", data)
        if len(data.split('/')) == 5:  # means it's in the form --> /report/pdf/model/id
            model = data.split('/')[3].split(".")[0]
            report_type = data.split('/')[3].split(".")[1]
            activeId = data.split('/')[4].split("\"")[0]
        else:
            return res

        # Customizable according to the required reports and models
        if model in ['wt_documents'] and report_type in ['wide_documents_temp'] and activeId:
            move = request.env['wide.documents'].sudo().search([('id', '=', int(activeId))])  # Check existence of move
        # Customizable according to the required reports and models
        elif model in ['wt_hr_custom'] and report_type in ['job_offer_temp'] and activeId:
            move = request.env['wide.job.offer'].sudo().search([('id', '=', int(activeId))])  # Check existence of move
        else:
            return res

        if not move:
            return res

        attachment = {
            'datas': base64.encodebytes(res.data),
            'type': 'binary',
            'name': str(move.name),
            'res_model': 'ir.attachment',
            'res_id': int(activeId),
            'attach_model': model,
            'attach_type': report_type
        }
        current_attachment = request.env['ir.attachment'].sudo().search([('res_id', '=', int(activeId)),
                                                                         ('attach_model', '=', model),
                                                                         ('attach_type', '=', report_type)])
        if current_attachment:
            current_attachment.sudo().write(attachment)
        else:
            request.env['ir.attachment'].create(attachment)
        res = super(CustomController, self).report_download(data, token)
        return res
