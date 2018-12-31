# -*- coding: utf-8 -*-
# Copyright 2015 AvanzOSC - Oihane Crucelaegi
# Copyright 2015 Tecnativa - Pedro M. Baeza
# Copyright 2018 Tecnativa - David Vidal
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import _, api, fields, models


class StockInventoryEmptyLines(models.Model):
    _name = 'stock.inventory.line.empty'

    product_code = fields.Char(
        string='Product Code',
        required=True,
    )
    product_qty = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
    )
    inventory_id = fields.Many2one(
        comodel_name='stock.inventory',
        string='Inventory',
        required=True,
        ondelete="cascade",
    )


class StockInventory(models.Model):
    _inherit = 'stock.inventory'

    @api.model
    def _get_available_filters(self):
        """This function will return the list of filters allowed according to
        the options checked in 'Settings/Warehouse'.

        :return: list of tuple
        """
        res_filters = super(StockInventory, self)._get_available_filters()
        res_filters.append(('categories', _('Selected Categories')))
        res_filters.append(('products', _('Selected Products')))
        for res_filter in res_filters:
            if res_filter[0] == 'lot':
                res_filters.append(('lots', _('Selected Lots')))
                break
        res_filters.append(('empty', _('Empty list')))
        return res_filters

    filter = fields.Selection(
        selection='_get_available_filters',
        string='Selection Filter',
        required=True,
    )
    categ_ids = fields.Many2many(
        comodel_name='product.category', relation='rel_inventories_categories',
        column1='inventory_id', column2='category_id', string='Categories')
    product_ids = fields.Many2many(
        comodel_name='product.product', relation='rel_inventories_products',
        column1='inventory_id', column2='product_id', string='Products')
    lot_ids = fields.Many2many(
        comodel_name='stock.production.lot', relation='rel_inventories_lots',
        column1='inventory_id', column2='lot_id', string='Lots')
    empty_line_ids = fields.One2many(
        comodel_name='stock.inventory.line.empty', inverse_name='inventory_id',
        string='Capture Lines')

    @api.model
    def _get_inventory_lines(self, inventory):
        vals = []
        product_obj = self.env['product.product']
        tmp_inventory = self.new(self._convert_to_write(inventory._cache))
        # inventory = self.new(self._convert_to_write(self._cache))
        if inventory.filter in ('categories', 'products'):
            if inventory.filter == 'categories':
                products = product_obj.search([
                    ('product_tmpl_id.categ_id', 'in', inventory.categ_ids.ids)
                ])
            else:  # filter = 'products'
                products = inventory.product_ids
            tmp_inventory.filter = 'product'
            for product in products:
                tmp_inventory.product_id = product
                vals += super(StockInventory,
                              self)._get_inventory_lines(tmp_inventory)
        elif inventory.filter == 'lots':
            tmp_inventory.filter = 'lot'
            for lot in inventory.lot_ids:
                tmp_inventory.lot_id = lot
                vals += super(StockInventory,
                              self)._get_inventory_lines(tmp_inventory)
        elif inventory.filter == 'empty':
            tmp_lines = {}
            for line in inventory.empty_line_ids:
                tmp_lines.setdefault(line.product_code, 0)
                tmp_lines[line.product_code] += line.product_qty
            inventory.empty_line_ids.unlink()
            tmp_inventory.filter = 'product'
            for product_code in tmp_lines.keys():
                product = product_obj.search([
                    '|',
                    ('default_code', '=', product_code),
                    ('barcode', '=', product_code),
                ], limit=1)
                if not product:
                    continue
                tmp_inventory.product_id = product
                values = super(StockInventory,
                               self)._get_inventory_lines(tmp_inventory)
                if values:
                    values[0]['product_qty'] = tmp_lines[product_code]
                else:
                    vals += [{
                        'product_id': product.id,
                        'product_qty': tmp_lines[product_code],
                        'location_id': inventory.location_id.id,
                    }]
                vals += values
        else:
            vals = super(StockInventory, self)._get_inventory_lines(inventory)
        for val in vals:
            val.update({'inventory_id': inventory.id})
        return vals