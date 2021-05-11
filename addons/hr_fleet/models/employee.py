# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Employee(models.Model):
    _inherit = 'hr.employee'

    employee_cars_count = fields.Integer(compute="_compute_employee_cars_count", string="Cars", groups="fleet.fleet_group_manager")
    mobility_card = fields.Char(groups="fleet.fleet_group_user")

    def action_open_employee_cars(self):
        self.ensure_one()
        cars = self.env['fleet.vehicle.assignation.log'].search([
            ('driver_id', 'in', (self.user_id.partner_id | self.sudo().address_home_id).ids)]).mapped('vehicle_id')

        return {
            "type": "ir.actions.act_window",
            "res_model": "fleet.vehicle",
            "views": [[False, "kanban"], [False, "form"], [False, "tree"]],
            "domain": [("id", "in", cars.ids)],
            "context": dict(self._context, create=False),
            "name": "History Employee Cars",
        }

    def _compute_employee_cars_count(self):
        driver_ids = (self.mapped('user_id.partner_id') | self.sudo().mapped('address_home_id')).ids
        fleet_data = self.env['fleet.vehicle.assignation.log'].read_group(
            domain=[('driver_id', 'in', driver_ids)], fields=['vehicle_id:array_agg'], groupby=['driver_id'])
        mapped_data = {
            group['driver_id'][0]: len(set(group['vehicle_id']))
            for group in fleet_data
        }
        for employee in self:
            drivers = employee.user_id.partner_id | employee.sudo().address_home_id
            employee.employee_cars_count = sum(mapped_data.get(pid, 0) for pid in drivers.ids)

    def action_get_claim_report(self):
        self.ensure_one()
        return {
            'name': 'Claim Report',
            'type': 'ir.actions.act_url',
            'url': '/fleet/print_claim_report/%(employee_id)s' % {'employee_id': self.id},
        }

    @api.constrains('address_home_id')
    def _check_address_home_id(self):
        no_address = self.filtered(lambda r: not r.address_home_id)
        car_ids = self.env['fleet.vehicle'].sudo().search([
            ('driver_employee_id', 'in', no_address.ids),
            ('fleet_id.internal', '=', True),
        ])
        # Prevent from removing employee address when linked to a car
        if car_ids:
            raise ValidationError(_('Cannot remove address from employees with linked cars.'))


    def write(self, vals):
        res = super().write(vals)
        #Update car partner when it is changed on the employee
        if 'address_home_id' in vals:
            car_ids = self.env['fleet.vehicle'].sudo().search([
                ('driver_employee_id', 'in', self.ids),
                ('driver_id', 'in', self.mapped('address_home_id').ids),
                ('fleet_id.internal', '=', True),
            ])
            if car_ids:
                car_ids.write({'driver_id': vals['address_home_id']})
        if 'mobility_card' in vals:
            #NOTE: keeping it as a search on driver_id but we might be able to use driver_employee_id in the future
            vehicles = self.env['fleet.vehicle'].search([('driver_id', 'in', (self.user_id.partner_id | self.sudo().address_home_id).ids)])
            vehicles._compute_mobility_card()
        return res

class EmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    mobility_card = fields.Char(readonly=True)
