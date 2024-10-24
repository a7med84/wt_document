from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import base64


class ConfirmDocument(models.TransientModel):
    _name = 'confirm.document'
    _description = 'Confirm Document'

    document_id = fields.Many2one(comodel_name='wide.documents', string='الخطاب')
    document_confirmed_id = fields.Many2one(comodel_name='wide.documents.confirmed', string='الخطاب المعتمد')
    to_draft = fields.Boolean()

    def confirm_document(self):
        if self.document_id:
            if self.to_draft:
                self.document_id.state = 'draft'
                self.document_id.confirm_date = False
                self.document_id.confirm_user_id = False
            else:
                self.document_id.state = 'confirm'
                self.document_id.confirm_date = fields.Datetime.now()
                self.document_id.confirm_user_id = self.env.user
        if self.document_confirmed_id:
            if self.to_draft:
                self.document_confirmed_id.state = 'draft'
                self.document_confirmed_id.confirm_date = False
                self.document_confirmed_id.confirm_user_id = False
            else:
                self.document_confirmed_id.state = 'confirm'
                self.document_confirmed_id.confirm_date = fields.Datetime.now()
                self.document_confirmed_id.confirm_user_id = self.env.user


class SendDocument(models.TransientModel):
    _name = 'send.document'
    _description = 'Send Document'

    partner_id = fields.Many2many(comodel_name='res.partner', string='العملاء')
    document_id = fields.Many2one(comodel_name='wide.documents', string='الخطاب')
    document_confirmed_id = fields.Many2one(comodel_name='wide.documents.confirmed', string='الخطاب المعتمد')

    def send_email_with_attachment(self):
        if self.document_id:
            report_template_id = self.env.ref('wt_documents.wide_documents_report').sudo()._render_qweb_pdf(
                self.document_id.id)
            data_record = base64.b64encode(report_template_id[0])
            ir_values = {
                'name': f'{self.document_id.subject} {self.document_id.name} {self.document_id.date_hijri}.pdf',
                'type': 'binary',
                'datas': data_record,
                'store_fname': data_record,
                'mimetype': 'application/x-pdf',
            }
            data_id = self.env['ir.attachment'].create(ir_values)

            # lines = [(6, 0, [self.document_id.files.ids]), (4, data_id.id)]
            # print("lineslineslines", lines)
            attachments = []
            for rec in self.document_id.files:
                attachments.append(rec.id)
            attachments.append(data_id.id)
            for paetner in self.partner_id:
                values = {
                    'subject': self.document_id.document_config_id.company_id.partner_id.name,
                    'author_id': self.env.company.partner_id.id,
                    'email_to': paetner.email,
                    'email_from': 'no-reply@wtsaudi.com',
                    'state': 'outgoing',
                    'body_html': self.document_id.email_message,
                    # 'recipient_ids': self.partner_id,
                    'attachment_ids': [(6, 0, [x for x in attachments])],
                }
                template = self.env['mail.mail'].create(values)
                template.send()
                self.document_id.received_ids = [(4, paetner.id)]
            return True
        if self.document_confirmed_id:
            attachments = []
            for rec in self.document_confirmed_id.files:
                attachments.append(rec.id)
            for paetner in self.partner_id:
                values = {
                    'subject': self.document_confirmed_id.document_config_id.company_id.partner_id.name,
                    'author_id': self.env.company.partner_id.id,
                    'email_to': paetner.email,
                    'email_from': 'no-reply@wtsaudi.com',
                    'state': 'outgoing',
                    'body_html': self.document_confirmed_id.email_message,
                    # 'recipient_ids': self.partner_id,
                    'attachment_ids': [(6, 0, [x for x in attachments])],
                }
                template = self.env['mail.mail'].create(values)
                template.send()
                self.document_id.received_ids = [(4, paetner.id)]
            return True

    def send_email(self):
        if self.partner_id.email:
            body_html = _(
                '''Hello,<br><br>Property called %s<br>
                Property location is (%s)<br>''') \
                        % (self.property_id.name,
                           self.property_id.url1)

            self.env['mail.mail'].create({
                'body_html': body_html,
                'state': 'outgoing',
                'email_from': self.env.user.email_formatted or '',
                'email_to': self.customer_id.email,
                'subject': 'Property Location'
            }).send()

        else:
            raise ValidationError(_("يرجي إضافة الايميل الخاص بالعميل"))
