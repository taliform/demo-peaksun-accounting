# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

from werkzeug.datastructures import FileStorage

from odoo import http, fields
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.tools.translate import _
from odoo.http import request
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.osv.expression import OR

from datetime import datetime
from dateutil.relativedelta import relativedelta


class DriverPortal(http.Controller):
    _items_per_page = 20

    @http.route('/driver_portal', type='http', auth='public')
    def _driver_portal_home(self, **kw):
        employee = request.env.user.sudo().employee_id

        values = {
            'employee': employee,
            'title': "Driver Portal - Home"
        }
        values.update(kw)
        return request.render("tf_peec_portal.driver_portal_home", values)

    @http.route(['/driver_portal/attendance', '/driver_portal/attendance/page/<int:page>'], type='http', auth='public')
    def _driver_portal_attendance(self, page=1, **kw):
        employee = request.env.user.sudo().employee_id
        attendances = pager = False
        domain = [('employee_id', '=', employee.id)]
        DHAttendance = request.env['tf.hr.dh.attendance']
        if employee:
            # attendances = DHAttendance.search(domain)
            # count for pager
            attendance_count = DHAttendance.search_count(domain)
            # pager
            pager = portal_pager(
                url="/driver_portal/attendance",
                total=attendance_count,
                page=page,
                step=self._items_per_page
            )
            # content according to pager and archive selected
            attendances = DHAttendance.search(domain, order='from_date desc', limit=self._items_per_page, offset=pager['offset'])

        values = {
            'employee': employee,
            'attendances': attendances,
            'pager': pager,
            'title': "Driver Portal - Attendance",
            'success': kw.get('success', ''),
            'error': kw.get('error', '')
        }
        return request.render("tf_peec_portal.driver_portal_attendance", values)

    def _driver_portal_attendance_update(self, kw, state):
        employee = request.env.user.sudo().employee_id
        pin = kw.get('employee_pin', False)
        values = {}

        if employee:
            temp_employee = employee
        elif not employee and pin:
            temp_employee = request.env['hr.employee'].sudo().search([('pin_user', '=', pin)])
            if not temp_employee:
                values['error'] = 'Employee cannot be found.'
                return http.local_redirect("/driver_portal/attendance", query=values)
        else:
            values['error'] = 'Employee cannot be found.'
            return http.local_redirect("/driver_portal/attendance", query=values)

        if temp_employee:
            from_date = kw.get('from_date')
            if not from_date:
                values['error'] = "From Date is required."
                return http.local_redirect("/driver_portal/attendance", query=values)

            to_date = kw.get('to_date')
            if not to_date:
                values['error'] = "To Date is required."
                return http.local_redirect("/driver_portal/attendance", query=values)

            attendance_vals = {
                'employee_id': temp_employee.id,
                'from_date': from_date,
                'to_date': to_date,
                'state': state,
            }

            if temp_employee.user_id:
                try:
                    attendance = request.env['tf.hr.dh.attendance'].with_user(temp_employee.user_id) \
                        .create(attendance_vals)
                except ValidationError as e:
                    values['error'] = e
                    return http.local_redirect("/driver_portal/attendance", query=values)
                    # return self._driver_portal_attendance(**values)
            else:
                try:
                    attendance = request.env['tf.hr.dh.attendance'].sudo().create(attendance_vals)
                except ValidationError as e:
                    values['error'] = e
                    return http.local_redirect("/driver_portal/attendance", query=values)
                    # return self._driver_portal_attendance(**values)

            if attendance:
                if state == 'available':
                    state_display = 'Available'
                elif state == 'leave':
                    state_display = 'On Leave'
                elif state == 'meeting':
                    state_display = 'In Meeting'
                else:
                    state_display = 'Unavailable'

                values['success'] = "Marked dates from %s to %s as <strong>%s</strong> for %s." % \
                                    (from_date, to_date, state_display, temp_employee.display_name)

        if employee:
            attendances = request.env['tf.hr.dh.attendance'].search([('employee_id', '=', employee.id)])
            values['attendances'] = attendances

        values.update({
            'employee': employee,
            'title': "Driver Portal - Attendance"
        })

        return http.local_redirect("/driver_portal/attendance", query=values)

    @http.route('/driver_portal/attendance/available', type='http', auth='public', methods=['POST'])
    def _driver_portal_attendance_available(self, **kw):
        return self._driver_portal_attendance_update(kw, 'available')

    @http.route('/driver_portal/attendance/leave', type='http', auth='public', methods=['POST'])
    def _driver_portal_attendance_leave(self, **kw):
        return self._driver_portal_attendance_update(kw, 'leave')

    @http.route('/driver_portal/attendance/meeting', type='http', auth='public', methods=['POST'])
    def _driver_portal_attendance_meeting(self, **kw):
        return self._driver_portal_attendance_update(kw, 'meeting')

    @http.route('/driver_portal/attendance/delete', type='http', auth='public', methods=['POST'])
    def _driver_portal_attendance_delete(self, **kw):
        employee = request.env.user.sudo().employee_id
        attendance_id = kw.get('attendance_id')
        values = {}
        DHAttendance = request.env['tf.hr.dh.attendance']
        if not employee:
            values['error'] = 'Employee must be logged in to delete attendance records.'
            return http.local_redirect("/driver_portal/attendance", query=values)
        if not attendance_id:
            values['error'] = 'Attendance ID not found.'
            return http.local_redirect("/driver_portal/attendance", query=values)
        attendance = DHAttendance.browse([int(attendance_id)])

        from_date = attendance.from_date
        to_date = attendance.to_date
        today = fields.Date.today()
        yesterday = today + relativedelta(days=-1)
        state = attendance.state

        if today > to_date:
            values['error'] = 'Cannot delete attendance records that have already passed.'
            return http.local_redirect("/driver_portal/attendance", query=values)

        attendance.unlink()

        if to_date >= today > from_date:
            # SPLIT: If Today is after from date but is less than to date, split from from_date to yesterday
            DHAttendance.create({
                'employee_id': employee.id,
                'from_date': from_date,
                'to_date': yesterday,
                'state': state,
            })
            values['success'] = 'Attendance record from %s to %s of %s has been deleted.\n' \
                                'A new attendance record was created from %s to %s to retain past attendances.' \
                                % (from_date, to_date, employee.display_name, from_date, yesterday)
        else:
            values['success'] = 'Attendance record from %s to %s of %s has been deleted.' \
                                % (from_date, to_date, employee.display_name)
        return http.local_redirect("/driver_portal/attendance", query=values)

    @http.route('/driver_portal/delivery_order', type='http', auth='user')
    def _driver_portal_delivery_order(self, **kw):
        employee = request.env.user.sudo().employee_id
        delivery_unit = employee.delivery_unit_id
        values = {
            'employee': employee,
            'delivery_unit': delivery_unit,
            'title': "Driver Portal - Delivery Orders"
        }

        if delivery_unit:
            delivery_orders = request.env['logistics.delivery.order'].search([
                ('delivery_unit_id', '=', delivery_unit.id), ('state', '!=', 'closed')
            ])
            values['delivery_orders'] = delivery_orders

        values.update(kw)
        return request.render("tf_peec_portal.driver_portal_delivery_order_list", values)

    def _get_delivery_order_values(self, order_id):
        employee = request.env.user.sudo().employee_id

        delivery_order = False
        delivery_unit = False
        values = {}

        delivery_order = request.env['logistics.delivery.order'].search([('id', '=', order_id)])
        delivery_unit = delivery_order.delivery_unit_id
        if not delivery_order:
            values['error'] = "Deliver Order does not exist."

        if delivery_unit and employee.id not in delivery_unit.driver_ids.ids + delivery_unit.helper_ids.ids:
            values['error'] = "Current user does not have access to the Delivery Order."

        checkers = request.env['res.partner'].sudo().search([('is_weight_checker', '=', True)])

        values.update({
            'employee': employee,
            'delivery_order': delivery_order,
            'delivery_unit': delivery_unit,
            'checkers': checkers,
        })

        return delivery_order, delivery_unit, values

    @http.route('/driver_portal/delivery_order/<int:order_id>', type='http', auth='user')
    def _delivery_order_main(self, order_id=None, **kw):
        delivery_order, delivery_unit, values = self._get_delivery_order_values(order_id)
        if 'error' in values:
            return self._driver_portal_main(**values)
        values['title'] = "Driver Portal - Delivery Order %s" % (delivery_order.name,)

        last_weight_log = request.env['logistics.log.weight'].search([
            ('delivery_order_id', '=', delivery_order.id),
        ], order='weighing_date desc', limit=1)

        for document in delivery_order.document_ids:
            document._portal_ensure_token()

        # Get last weight log for its tare weight in case it was logging for an empty vehicle
        tare_weight = 0
        load_state = 'empty'
        if last_weight_log and last_weight_log.load_state == 'empty':
            tare_weight = last_weight_log.tare_weight
            load_state = 'loaded'

        values['tare_weight'] = tare_weight
        values['load_state'] = load_state

        if 'success' in kw:
            values['success'] = kw.get('success')
        if 'error' in kw:
            values['error'] = kw.get('error')

        return request.render("tf_peec_portal.driver_portal_delivery_order_main", values)

    @http.route('/driver_portal/delivery_order/start_trip', type='http', auth='user', methods=['POST'])
    def _delivery_order_start_trip(self, **kw):
        delivery_order_id = int(kw.get('delivery_order_id'))
        departure_date = kw.get('manual_date')
        if not departure_date:
            departure_date = fields.Datetime.now()
        else:
            # TODO: better localization function instead of direct subtracting of 8 hours
            departure_date = datetime.strptime(departure_date, '%Y-%m-%dT%H:%M') + relativedelta(hours=-8)

        StartWizard = request.env['logistics.delivery.order.start.trip']
        values = {
            'delivery_order_id': delivery_order_id,
            'delivery_unit_id': int(kw.get('delivery_unit_id')),
            'is_inspection_done': True if kw.get('inspection_done') == 'on' else False,
            'odometer_reading': float(kw.get('odometer_reading')),
            'is_manual_date': True if kw.get('is_manual') == '1' else False,
            'departure_date': departure_date,
            'manual_reason': kw.get('manual_reason')
        }
        temp_wizard = StartWizard.create(values)
        temp_wizard.with_context({'start_trip_type': kw.get('start_trip_type')}).action_start_trip()

        return_values = {
            'success': 'Trip has started.'
        }

        return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=return_values)

    @http.route('/driver_portal/delivery_order/end_trip', type='http', auth='user', methods=['POST'])
    def _delivery_order_end_trip(self, **kw):
        delivery_order_id = int(kw.get('delivery_order_id'))
        arrival_date = kw.get('manual_date')
        if not arrival_date:
            arrival_date = fields.Datetime.now()
        else:
            # TODO: better localization function instead of direct subtracting of 8 hours
            arrival_date = datetime.strptime(arrival_date, '%Y-%m-%dT%H:%M') + relativedelta(hours=-8)

        EndWizard = request.env['logistics.delivery.order.end.trip']
        values = {
            'delivery_order_id': delivery_order_id,
            'delivery_unit_id': int(kw.get('delivery_unit_id')),
            'trip_log_id': int(kw.get('trip_log_id')),
            'odometer_reading': float(kw.get('odometer_reading')),
            'is_manual_date': True if kw.get('is_manual') == '1' else False,
            'arrival_date': arrival_date,
            'manual_reason': kw.get('manual_reason')
        }
        temp_wizard = EndWizard.create(values)
        temp_wizard.with_context({'end_trip_type': kw.get('end_trip_type')}).action_end_trip()

        return_values = {
            'success': 'Trip has ended.'
        }

        return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=return_values)

    @http.route('/driver_portal/delivery_order/log_weight', type='http', auth='user', methods=['POST'])
    def _delivery_order_log_weight(self, **kw):
        delivery_order_id = int(kw.get('delivery_order_id'))
        delivery_unit_id = int(kw.get('delivery_unit_id'))
        load_state = kw.get('load_state')
        tare_weight = float(kw.get('tare_weight'))

        if 'cp_load' in kw:
            cp_load = True
        else:
            cp_load = False

        if 'bp_unload' in kw:
            bp_unload = True
        else:
            bp_unload = False

        if 'gross_weight' in kw:
            gross_weight = float(kw.get('gross_weight'))
        else:
            gross_weight = False

        if kw.get('checker_id') == 'new':
            checker_id = False
            checker_name = kw.get('new_checker')
        else:
            checker_id = int(kw.get('checker_id'))
            checker_name = request.env['res.partner'].browse([checker_id]).display_name

        context = dict(request._context)
        if cp_load:
            context.update({'cp_load': True})
        if bp_unload:
            context.update({'bp_unload': True})

        request.env['logistics.log.weight'].with_context(context).create({
            'delivery_order_id': delivery_order_id,
            'delivery_unit_id': delivery_unit_id,
            'checker_id': checker_id,
            'checker_name': checker_name,
            'tare_weight': tare_weight,
            'gross_weight': gross_weight,
            'load_state': load_state,
        })

        values = {
            'success': "Weight Log successfully created."
        }

        return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

    @http.route('/driver_portal/delivery_order/start_loading', type='http', auth='user', methods=['POST'])
    def _delivery_order_start_loading(self, **kw):
        delivery_order_id = int(kw.get('delivery_order_id'))
        delivery_unit_id = int(kw.get('delivery_unit_id'))

        delivery_order = request.env['logistics.delivery.order'].browse([delivery_order_id])

        values = {}

        try:
            delivery_order.action_start_loading()
        except ValidationError as e:
            values['error'] = e
            return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

        values['success'] = 'Loading has started.'

        return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

    @http.route('/driver_portal/delivery_order/end_loading', type='http', auth='user', methods=['POST'])
    def _delivery_order_end_loading(self, **kw):
        delivery_order_id = int(kw.get('delivery_order_id'))
        delivery_unit_id = int(kw.get('delivery_unit_id'))

        delivery_order = request.env['logistics.delivery.order'].browse([delivery_order_id])

        values = {}

        try:
            delivery_order.action_end_loading()
        except ValidationError as e:
            values['error'] = e
            return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

        values['success'] = 'Loading has ended.'

        return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

    @http.route('/driver_portal/delivery_order/start_unloading', type='http', auth='user', methods=['POST'])
    def _delivery_order_start_unloading(self, **kw):
        delivery_order_id = int(kw.get('delivery_order_id'))
        delivery_unit_id = int(kw.get('delivery_unit_id'))

        delivery_order = request.env['logistics.delivery.order'].browse([delivery_order_id])

        values = {}

        try:
            delivery_order.action_start_unloading()
        except ValidationError as e:
            values['error'] = e
            return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

        values['success'] = 'Unloading has started.'

        return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

    @http.route('/driver_portal/delivery_order/end_unloading', type='http', auth='user', methods=['POST'])
    def _delivery_order_end_unloading(self, **kw):
        delivery_order_id = int(kw.get('delivery_order_id'))
        delivery_unit_id = int(kw.get('delivery_unit_id'))

        delivery_order = request.env['logistics.delivery.order'].browse([delivery_order_id])

        values = {}

        try:
            delivery_order.action_end_unloading()
        except ValidationError as e:
            values['error'] = e
            return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

        values['success'] = 'Unloading has ended.'

        return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

    @http.route('/driver_portal/delivery_order/for_validation', type='http', auth='user', methods=['POST'])
    def _delivery_order_for_validation(self, **kw):
        delivery_order_id = int(kw.get('delivery_order_id'))
        delivery_unit_id = int(kw.get('delivery_unit_id'))

        delivery_order = request.env['logistics.delivery.order'].browse([delivery_order_id])

        values = {}

        try:
            delivery_order.action_for_validation()
        except ValidationError as e:
            values['error'] = e
            return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

        values['success'] = 'Delivery Order sent for validation.'

        return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

    @http.route('/driver_portal/delivery_order/submit_documents', type='http', auth='user', methods=['POST'])
    def _delivery_order_submit_documents(self, **kw):
        delivery_order_id = int(kw.get('delivery_order_id'))
        delivery_unit_id = int(kw.get('delivery_unit_id'))
        delivery_order = request.env['logistics.delivery.order'].browse([delivery_order_id])

        for doc in delivery_order.document_ids:
            # FileStorage
            file = kw.get("document-%s" % (doc.id))
            # for file in files:
            # file = FileStorage(file)
            files = request.httprequest.files.getlist('document-%d' % (doc.id,))

            for file in files:
                if not doc.picture1:
                    field = 'picture1'
                elif doc.picture2:
                    field = 'picture2'
                else:
                    field = 'picture3'
                # attachment_value = {
                #     'name': file.filename,
                #     'datas': base64.encodestring(file.read()),
                #     # 'datas_fname': file.filename,
                #     'res_model': 'logistics.delivery.order.document',
                #     'res_id': doc.id,
                #     'res_field': field
                # }
                # attachment_id = request.env['ir.attachment'].sudo().create(attachment_value)
                if not doc.picture1:
                    doc.write({'picture1': base64.encodestring(file.read())})
                elif not doc.picture2:
                    doc.write({'picture2': base64.encodestring(file.read())})
                else:
                    doc.write({'picture3': base64.encodestring(file.read())})

        values = {}
        values['success'] = 'Documents submitted.'

        return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

        # delivery_order = request.env['logistics.delivery.order'].browse([delivery_order_id])
        #
        # values = {}
        #
        # try:
        #     delivery_order.action_for_validation()
        # except ValidationError as e:
        #     values['error'] = e
        #     return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)
        #
        # values['success'] = 'Delivery Order sent for validation.'
        #
        # return http.local_redirect("/driver_portal/delivery_order/%s" % delivery_order_id, query=values)

    @http.route('/driver_portal/delivery_order/<int:order_id>/messenger', type='http', auth='user')
    def _delivery_order_messenger(self, order_id=None, **kw):
        delivery_order, delivery_unit, values = self._get_delivery_order_values(order_id)
        values['title'] = "Driver Portal - Delivery Order %s - Messenger" % (delivery_order.name,)
        return request.render("tf_peec_portal.driver_portal_delivery_order_messenger", values)

    @http.route('/driver_portal/delivery_order/<int:order_id>/expense', type='http', auth='user')
    def _delivery_order_expenses(self, order_id=None, **kw):
        delivery_order, delivery_unit, values = self._get_delivery_order_values(order_id)
        if 'error' in values:
            return http.local_redirect("/delivery_order/%s/expense" % (delivery_order,), query=values)
        values['title'] = "Driver Portal - Delivery Order %s - Expenses" % (delivery_order.name,)
        values['expenses'] = delivery_order.expense_ids
        values['products'] = request.env['product.product'].search([('is_trip_expense', '=', True)])

        if 'success' in kw:
            values['success'] = kw.get('success')
        if 'error' in kw:
            values['error'] = kw.get('error')

        return request.render("tf_peec_portal.driver_portal_delivery_order_expenses", values)

    @http.route('/driver_portal/delivery_order/add_expense', type='http', auth='user')
    def _delivery_order_expense_add(self, order_id=None, **kw):
        # delivery_order, delivery_unit, values = self._get_delivery_order_values(order_id)
        # if 'error' in values:
        #     return http.local_redirect("/delivery_order/%s/expense" % (delivery_order,), query=values)

        if 'trip_log_id' in kw:
            trip_log_id = int(kw.get('trip_log_id'))
        else:
            trip_log_id = False

        if 'delivery_order_id' in kw:
            delivery_order_id = int(kw.get('delivery_order_id'))
        else:
            delivery_order_id = False

        expense_date = datetime.strptime(kw.get('expense_date'), '%Y-%m-%dT%H:%M') + relativedelta(hours=-8)

        request.env['logistics.log.expense'].create({
            'trip_log_id': trip_log_id,
            'delivery_order_id': delivery_order_id,
            'product_id': int(kw.get('product_id')),
            'name': kw.get('description'),
            'expense_date': expense_date,
            'amount': float(kw.get('amount')),
        })

        values = {'success': 'Expense has been added.'}

        return http.local_redirect("/driver_portal/delivery_order/%s/expense" % (delivery_order_id,), query=values)

    @http.route('/driver_portal/delivery_order/delete_expense', type='http', auth='user')
    def _delivery_order_expense_delete(self, order_id=None, **kw):
        delivery_order_id = int(kw.get('delivery_order_id'))
        expense_id = int(kw.get('expense_id'))
        expense = request.env['logistics.log.expense'].browse([expense_id])
        expense.unlink()

        values = {'success': 'Expense has been deleted.'}

        return http.local_redirect("/driver_portal/delivery_order/%s/expense" % (delivery_order_id,), query=values)

    @http.route('/driver_portal/delivery_order/<int:order_id>/maintenance', type='http', auth='user')
    def _delivery_order_maintenance(self, order_id=None, **kw):
        delivery_order, delivery_unit, values = self._get_delivery_order_values(order_id)

        if 'error' in values:
            return http.local_redirect("/delivery_order/%s/maintenance" % (delivery_order,), query=values)

        values['title'] = "Driver Portal - Delivery Order %s - Maintenance" % (delivery_order.name,)
        values['maintenances'] = delivery_order.maintenance_ids
        values['vehicles'] = delivery_order.delivery_unit_id.tractor_head_id + delivery_order.delivery_unit_id.trailer_id
        if 'success' in kw:
            values['success'] = kw.get('success')
        if 'error' in kw:
            values['error'] = kw.get('error')

        return request.render("tf_peec_portal.driver_portal_delivery_order_maintenance", values)

    @http.route('/driver_portal/delivery_order/add_maintenance', type='http', auth='user')
    def _delivery_order_maintenance_add(self, order_id=None, **kw):
        if 'trip_log_id' in kw:
            trip_log_id = int(kw.get('trip_log_id'))
        else:
            trip_log_id = False

        if 'delivery_order_id' in kw:
            delivery_order_id = int(kw.get('delivery_order_id'))
        else:
            delivery_order_id = False

        request.env['maintenance.request'].create({
            'trip_log_id': trip_log_id,
            'delivery_order_id': delivery_order_id,
            'name': kw.get('description'),
            'to_maintain': 'vehicle',
            'vehicle_id': int(kw.get('vehicle_id')),
            'description': kw.get('description'),
        })

        values = {'success': 'Maintenance Request has been added.'}

        return http.local_redirect("/driver_portal/delivery_order/%s/maintenance" % (delivery_order_id,), query=values)

    @http.route('/driver_portal/maintenance_request/<int:request_id>', type='http', auth='user')
    def _delivery_order_maintenance_main(self, request_id=None, **kw):
        values = {
            'maintenance': request.env['maintenance.request'].browse([request_id])
        }
        return request.render('tf_peec_portal.driver_portal_delivery_order_maintenance_main', values)
