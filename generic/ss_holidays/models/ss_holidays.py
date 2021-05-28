# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2020 Taliform Inc.
#
# Author: Allen Guarnes <allen@taliform.com>
# V13 Porting: Martin Perez <martin@taliform.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsibility of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.    
#
# You should have received a copy of the GNU Affero General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import calendar
from datetime import datetime, timedelta

from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class HolidayCalendar(models.Model):
    _name = 'ss.holiday.calendar'
    _description = 'Holiday Calendar'
    _order = 'year desc'

    name = fields.Char()
    year = fields.Char('Year', size=4, default=datetime.now().year, required=True)
    holiday_ids = fields.One2many('ss.holiday', 'calendar_id', 'Holidays')
    last_sync = fields.Datetime('Last Synced', readonly=True)

    _sql_constraints = [
        ('year_uniq', 'unique(name)', "The Holiday Calendar's year has already been used.")
    ]

    def isNumber(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    @api.model
    def create(self, vals):
        res = super(HolidayCalendar, self).create(vals)
        res.update({'name': '%s Holidays' % (str(res.year),)})
        return res

    def write(self, vals):
        res = super(HolidayCalendar, self).write(vals)
        # if type(self.year) != int or len(str(self.year)) != 4:
        if not self.isNumber(self.year):
            raise exceptions.ValidationError(_("The specified year is not valid!"))
        return res

    def sync_calendar_events(self):
        for rec in self:
            for holiday in rec.holiday_ids:
                holiday.sync_calendar_event()


class Holiday(models.Model):
    _name = 'ss.holiday'
    _description = 'Holiday'

    calendar_id = fields.Many2one('ss.holiday.calendar', 'Holiday Calendar', ondelete='cascade', required=True)
    event_id = fields.Many2one('calendar.event', 'Calendar Event')
    name = fields.Char(required=True)
    year = fields.Char(related='calendar_id.year', store=True)
    date = fields.Date('Date', required=True)
    type = fields.Many2one('ss.holiday.type', 'Type', required=True)
    weekday = fields.Char()
    tocorrect = fields.Boolean(default=True)
    weekday = fields.Char(compute='_compute_weekday', store=True)
    last_sync = fields.Datetime('Last Synced', readonly=True)

    @api.depends('date')
    def _compute_weekday(self):
        for rec in self:
            if not rec.tocorrect and 'default_name' in self._context:
                rec.date = rec.date + timedelta(days=1)

            if rec.date:
                date = rec.date
                if date:
                    rec.weekday = calendar.day_name[date.weekday()]

    @api.model
    def create(self, values):
        if len(values['date']) != 10:
            values.update({'date': datetime.strptime(values['date'][:10], '%Y-%m-%d') + timedelta(days=1)})
        else:
            values.update({'tocorrect': True})
        res = super(Holiday, self).create(values)
        res.calendar_id = res.calendar_id.id or False
        # res.calendar_id = self._context['active_id'] or False
        return res

    @api.model
    def get_holiday_code(self, date):
        holiday_id = self.search([('date', '=', date)])
        code = holiday_id.type.code
        return code if code else False

    def sync_calendar_event(self):
        holiday_model = self.env['ir.model'].search([('model', '=', self._name)], limit=1)
        current_dt = fields.Datetime.now()
        for rec in self:
            date = rec.date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            holiday_data = {
                'name': rec.name,
                'start_date': rec.date,
                'stop_date': rec.date,
                'start': date,
                'stop': date,
                'allday': True,
                'privacy': 'public',
                'partner_ids': [],
                'holiday_id': rec.id,
                'res_model_id': holiday_model.id,
                'res_id': rec.id,
            }
            if not rec.event_id:
                rec.event_id = self.env['calendar.event'].create(holiday_data)
            else:
                rec.event_id.write(holiday_data)

            rec.calendar_id.last_sync = current_dt
            rec.last_sync = current_dt


class HolidayType(models.Model):
    _name = 'ss.holiday.type'
    _description = 'Holiday Type'

    name = fields.Char(required=True)
    code = fields.Char()

    @api.constrains('code')
    def _check_code_unique(self):
        """
        @note: This function checks for lower case and upper case alpha characters
        """
        if self.code:
            code = self.code.lower()
            existing_code = self.search([("code", "!=", False)]).filtered(lambda x: x.code.lower() == code)
            if len(existing_code) > 1:
                raise exceptions.ValidationError(_("The Holiday Type's code has already been used."))
