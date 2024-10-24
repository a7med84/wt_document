from odoo import api, fields, models, _
from hijri_converter import convert
from num2words import num2words
from odoo.exceptions import ValidationError
from odoo.http import request
import qrcode
import base64
from io import BytesIO


def generate_qr_code(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=20,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image()
    temp = BytesIO()
    img.save(temp, format="PNG")
    qr_img = base64.b64encode(temp.getvalue())
    return qr_img


def convert_to_hijri(value):
    return convert.Gregorian(value.year, value.month, value.day).to_hijri()


class CountryState(models.Model):
    _inherit = 'res.country.state'

    code = fields.Char(string='State Code', help='The state code.', required=False)


def _num2words(number):
    return num2words(number, lang='ar').title()


class WideDocuments(models.Model):
    _name = 'wide.documents'
    _description = 'Wide Documents'

    seq = fields.Char(string='Seq', default="New")
    name = fields.Char(string='رقم المعاملة', compute="compute_name")
    date = fields.Date(string='التاريخ', default=lambda self: fields.date.today())
    department_id = fields.Many2one(comodel_name='wide.department', string='الإدارة')
    document_config_id = fields.Many2one(comodel_name='document.config', string='إعداد الخطاب')
    subject = fields.Char(string='الموضوع')
    body = fields.Text(string='المحتوي')
    digital_signature = fields.Binary(string="التوقيع")
    date_hijri = fields.Char(string="التاريخ الهجري", compute="_onchange_dates")
    files = fields.Many2many(comodel_name='ir.attachment', string='المرفقات')
    filename = fields.Char('File Name')
    email_message = fields.Text(string="رسالة الإيميل", )
    received_ids = fields.Many2many(comodel_name='res.partner', string='المستلمون', copy=False)
    confirm_date = fields.Datetime(string='تاريخ الإعتماد')
    confirm_user_id = fields.Many2one(comodel_name='res.users', string='اعتمد بواسطة')
    state = fields.Selection(
        string='الحاله',
        selection=[('draft', 'مسوده'),
                   ('confirm', 'مؤكد'), ],
        default="draft", )

    editable_user_ids = fields.Many2many('res.users', 'res_users_custom_rel1', 'custom1', 'custom_rel1',
                                         string='المستخدمين المسؤلون عن التعديل')
    confirm_user_ids = fields.Many2many('res.users', 'res_users_custom_rel2', 'custom2', 'custom_rel2',
                                        string='المستخدمين المسؤلون عن التأكيد')

    @api.onchange('files')
    def onchange_files(self):
        for rec in self:
            names = []
            for line in rec.files:
                names += str(line.name)
            rec.filename = ''.join(names)

    # qr_image = fields.Binary("QR Code", compute='_generate_qr_code')
    # # qr_in_report = fields.Boolean('Show QR in Report')
    #
    # def _generate_qr_code(self):
    #     base_url = request.env['ir.config_parameter'].get_param('web.base.url')
    #     base_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
    #     self.qr_image = generate_qr_code(base_url)

    def _get_api_code(self, report_info):
        if len(report_info.split(".")) == 2:
            attach_model = report_info.split(".")[0]
            attach_type = report_info.split(".")[1]
        else:
            return False

        url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        query = "/qr/attachment/download/"
        attach_id = self.env['ir.attachment'].sudo().search([('res_id', '=', self.id),
                                                             ('attach_model', '=', attach_model),
                                                             ('attach_type', '=', attach_type)]).id
        if not attach_id:
            return False
        url += query + str(attach_id)
        self.qr_code = url
        return url

    qr_code = fields.Char(string='Qr Code', copy=False)

    @api.model
    def create(self, values):
        values['seq'] = self.env['ir.sequence'].next_by_code('wide.documents.seq') or 'New'
        result = super(WideDocuments, self).create(values)
        return result

    @api.depends("seq", "department_id.code")
    def compute_name(self):
        for rec in self:
            today = fields.Date.today()
            hijri_year = str(convert_to_hijri(today))[2:4:1]
            rec.name = str(hijri_year) + str(rec.department_id.code) + str(rec.seq)

    @api.depends("date")
    def _onchange_dates(self):
        today = fields.Date.today()
        if self.date:
            if self.date.year < 1925 or self.date > today:
                raise ValidationError("لا يمكن ادخال تاريخ قبل 1925 وبعد تاريخ اليوم")
        # Just define 12 months names:
        islamic_months = ["محرم", "صفر", "ربيع اﻷول",
                          "ربيع الثاني", "جمادى الأول",
                          "جمادى الثاني", "رجب", "شعبان",
                          "رمضان", "شوال", "ذوالقعدة", "ذو الحجة"]
        # On the next step get the right name:
        # hijri_date[2] = islamic_months[hijri_month - 1]  # 1 <= hijri_month <= 12
        for rec in self:
            if rec.date:
                # print(convert_to_hijri(rec.date))
                hijri_month = str(convert_to_hijri(rec.date))[5:7:1]
                # print(hijri_month)
                date_higri = str(convert_to_hijri(rec.date))[:5:1] + islamic_months[int(hijri_month) - 1] + str(
                    convert_to_hijri(rec.date))[7::1]
                # print(date_higri)
                rec.date_hijri = str(date_higri)

    def action_send_document(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('إرسال الخطاب'),
            'view_mode': 'form',
            'res_model': 'send.document',
            'target': 'new',
            'context': {
                'default_document_id': self.id,
                'default_document_confirmed_id': False,
            },
        }

    def confirm_document(self):
        if not self.document_config_id:
            raise ValidationError("يجب اختيار اسم الشركة (إعداد الخطاب) في الإعدادات اولا")
        return {
            'type': 'ir.actions.act_window',
            'name': _('تأكيد الخطاب'),
            'view_mode': 'form',
            'res_model': 'confirm.document',
            'target': 'new',
            'context': {
                'default_document_id': self.id,
                'default_document_confirmed_id': False,
                'default_to_draft': False,
            },
        }
    

    def unconfirm_document(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('تحويل لمسودة'),
            'view_mode': 'form',
            'res_model': 'confirm.document',
            'target': 'new',
            'context': {
                'default_document_id': self.id,
                'default_to_draft': True,
            },
        }


class WideDepartment(models.Model):
    _name = 'wide.department'
    _description = 'Wide Department'

    name = fields.Char(string="اسم الإدارة", )
    code = fields.Char(string='رقم الإدارة', copy=False)
    hr_department = fields.Boolean(
        string='شؤون الموظفين',
        required=False)

    _sql_constraints = [
        ('code_uniq', 'unique (code)', "لا يمكن تكرار رقم الإدارة"),
    ]

    # @api.onchange('code')
    # def onchange_code(self):
    #     if self.code:
    #         # for i in str(self.code):
    #         #     if i not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
    #         #         raise ValidationError("يجب أن لا يحتوي رقم الإدارة علي أي حروف ")
    #
    #         if not str(self.code).isdigit():
    #             raise ValidationError("يجب أن لا يحتوي رقم الإدارة علي أي حروف ")
    #
    #         elif len(self.code) != 2:
    #             raise ValidationError("يجب أن لا يقل أو يزيد رقم الإدارة عن رقمين ")
    #         else:
    #             pass

    def write(self, values):
        # Add code here
        if'code' in values.keys():
            if not str(values['code']).isdigit():
                raise ValidationError("يجب أن لا يحتوي رقم الإدارة علي أي حروف ")

            if len(values['code']) != 2:
                raise ValidationError("يجب أن لا يقل أو يزيد رقم الإدارة عن رقمين ")
        return super(WideDepartment, self).write(values)

    @api.model
    def create(self, values):
        # Add code here
        if not str(values['code']).isdigit():
            raise ValidationError("يجب أن لا يحتوي رقم الإدارة علي أي حروف ")

        if len(values['code']) != 2:
            raise ValidationError("يجب أن لا يقل أو يزيد رقم الإدارة عن رقمين ")
        return super(WideDepartment, self).create(values)


class DocumentConfig(models.Model):
    _name = 'document.config'
    _description = 'DocumentConfig'

    name = fields.Char(string="الاسم")
    company_id = fields.Many2one(comodel_name='res.company', string='الشركة')
    header = fields.Binary(string="الهيدر(Header)", )
    footer = fields.Binary(string="الفوتر(Footer)", )


class Attachment(models.Model):
    _inherit = 'ir.attachment'

    attach_model = fields.Char(string='Report Model', required=True)
    attach_type = fields.Char(string='Report Type', required=True)


class WideDocumentsConfirmed(models.Model):
    _name = 'wide.documents.confirmed'
    _inherit = 'wide.documents'

    editable_user_ids = fields.Many2many('res.users', 'res_users_custom_rel3', 'custom3', 'custom_rel3',
                                         string='Editable Users')
    confirm_user_ids = fields.Many2many('res.users', 'res_users_custom_rel4', 'custom4', 'custom_rel4',
                                        string='Confirm Users')

    @api.model
    def create(self, values):
        values['seq'] = self.env['ir.sequence'].next_by_code('wide.documents.confirm.seq') or 'New'
        result = super(WideDocumentsConfirmed, self).create(values)
        return result

    def action_send_document11(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('إرسال الخطاب'),
            'view_mode': 'form',
            'res_model': 'send.document',
            'target': 'new',
            'context': {
                'default_document_id': False,
                'default_document_confirmed_id': self.id,
            },
        }

    def confirm_document11(self):
        if not self.document_config_id:
            raise ValidationError("يجب اختيار اسم الشركة (إعداد الخطاب) في الإعدادات اولا")
        return {
            'type': 'ir.actions.act_window',
            'name': _('تأكيد الخطاب'),
            'view_mode': 'form',
            'res_model': 'confirm.document',
            'target': 'new',
            'context': {
                'default_document_id': False,
                'default_document_confirmed_id': self.id,
            },
        }


class WideDocumentsReceived(models.Model):
    _name = 'wide.documents.received'
    _inherit = 'wide.documents'

    destination = fields.Char(string='الجهة المرسلة', required=False)
    subject = fields.Char(string='مختصر المعاملة')
    files = fields.Many2many(comodel_name='ir.attachment', string='المرفقات', required=True)
    wide_document_id = fields.Many2one(comodel_name='wide.documents', string='رقم الصادر')

    editable_user_ids = fields.Many2many('res.users', 'res_users_custom_rel5', 'custom5', 'custom_rel5',
                                         string='Editable Users')
    confirm_user_ids = fields.Many2many('res.users', 'res_users_custom_rel6', 'custom6', 'custom_rel6',
                                        string='Confirm Users')

    @api.model
    def create(self, values):
        values['seq'] = self.env['ir.sequence'].next_by_code('wide.documents.received.seq') or 'New'
        if len(str(values['subject'])) < 300:
            raise ValidationError("يجب ان لا يقل مختصر المعاملة عن 300 حرف")
        # if not len(values['files']):
        #     raise ValidationError("يجب اضافة مرفقات")
        result = super(WideDocumentsReceived, self).create(values)
        return result

    def write(self, values):
        # Add code here
        if 'subject' in values.keys():
            print(len(str(values['subject'])))
            if len(str(values['subject'])) < 300:
                raise ValidationError("يجب ان لا يقل مختصر المعاملة عن 300 حرف")

        # if 'files' in values.keys():
        #     if not len(values['files']):
        #         raise ValidationError("يجب اضافة مرفقات")
        return super(WideDocumentsReceived, self).write(values)

    def action_send_document12(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('إرسال الخطاب'),
            'view_mode': 'form',
            'res_model': 'send.document',
            'target': 'new',
            'context': {
                'default_document_id': False,
                'default_document_confirmed_id': self.id,
            },
        }

    def confirm_document12(self):
        # if not self.document_config_id:
        #     raise ValidationError("يجب اختيار اسم الشركة (إعداد الخطاب) في الإعدادات اولا")
        return {
            'type': 'ir.actions.act_window',
            'name': _('تأكيد الخطاب'),
            'view_mode': 'form',
            'res_model': 'confirm.document',
            'target': 'new',
            'context': {
                'default_document_id': False,
                'default_document_confirmed_id': self.id,
            },
        }
