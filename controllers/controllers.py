from odoo.http import content_disposition, route, request, Controller
from odoo import http, _
from odoo.addons.web.controllers.main import Binary
from odoo.http import content_disposition, dispatch_rpc, request, serialize_exception as _serialize_exception, Response
from odoo.exceptions import AccessError, UserError, AccessDenied, ValidationError
import base64
import functools
import io
import json
import logging
import werkzeug
import unicodedata

_logger = logging.getLogger(__name__)


def clean(name): return name.replace('\x3c', '')


def serialize_exception(f):
    @functools.wraps(f)
    def wrap(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            _logger.exception("An exception occured during an http request")
            se = _serialize_exception(e)
            error = {
                'code': 200,
                'message': "Odoo Server Error",
                'data': se
            }
            return werkzeug.exceptions.InternalServerError(json.dumps(error))

    return wrap


#class BinaryInherit(Binary):
    #@http.route('/web/binary/upload_attachment', type='http', auth="user")
    #@serialize_exception
    #def upload_attachment(self, model, id, ufile, callback=None):
    #    files = request.httprequest.files.getlist('ufile')
    #    Model = request.env['ir.attachment']
    #    out = """<script language="javascript" type="text/javascript">
    #    args = []
    #    for ufile in files:

    #        if len(ufile.read()) > 5 * 1024 * 1024:
    #            args.append({'error': _("The selected file exceed the maximum file size of 5MB")})
    #        else:
    #            filename = ufile.filename
    #            if request.httprequest.user_agent.browser == 'safari':
                    # Safari sends NFD UTF-8 (where é is composed by 'e' and [accent])
                    # we need to send it the same stuff, otherwise it'll fail
    #                filename = unicodedata.normalize('NFD', ufile.filename)
    #            try:
    #                attachment = Model.create({
    #                    'name': filename,
    #                    'datas': base64.encodebytes(ufile.read()),
    #                    'res_model': model,
    #                    'res_id': int(id)
    #                })
    #                attachment._post_add_create()
    #            except AccessError:
    #                args.append({'error': _("You are not allowed to upload an attachment here.")})
    #            except Exception:
    #                args.append({'error': _("Something horrible happened")})
    #                _logger.exception("Fail to upload attachment %s" % ufile.filename)
    #            else:
    #                args.append({
    #                    'filename': clean(filename),
    #                    'mimetype': ufile.content_type,
    #                    'id': attachment.id,
    #                    'size': attachment.file_size
    #                })
    #    return out % (json.dumps(clean(callback)), json.dumps(args)) if callback else json.dumps(args)


class ApiController(Controller):
    @route('/qr/<int:idit>', auth='public')  # not used
    def index(self, idit):
        invoices = request.env['wide.documents']
        return request.render('wt_documents.qr_scanned_document', {
            'o': invoices.search([('id', '=', idit)])
        })

    @route('/qr/attachment/download/<int:attach_id>', type='http', auth='public')
    def qr_scanned_download(self, attach_id):
        invoice = request.env['ir.attachment'].sudo().search([('id', '=', attach_id)])
        print(invoice)
        data = io.BytesIO(base64.standard_b64decode(invoice["datas"]))
        print(data)
        filename = invoice.name + '.pdf'
        print(filename)
        return http.send_file(data, filename=filename, as_attachment=True)
