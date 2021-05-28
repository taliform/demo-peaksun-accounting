odoo.define('tf_ph_bank_recon.recon_renderer_inherit', function (require) {
    "use strict";

    const Widget = require('web.Widget');
    const FieldManagerMixin = require('web.FieldManagerMixin');
    const relational_fields = require('web.relational_fields');
    const basic_fields = require('web.basic_fields');
    const core = require('web.core');
    const time = require('web.time');
    const session = require('web.session');
    const qweb = core.qweb;
    const _t = core._t;
    const ReconRenderer = require('account.ReconciliationRenderer');

    ReconRenderer.LineRenderer.include({
        _renderCreate: async function (state) {
            var self = this;
            async function getCfSectionIds() {
                let cfSectionIds = await self._rpc({
                        model: 'account.reconciliation.widget',
                        method: 'get_cf_section_ids',
                        args: ['account'],
                        context: self.context,
                    })
                    .then( res => {
                        return res;
                    });
                return cfSectionIds;
            }
            let cfSectionIds = await getCfSectionIds();
            return this.model.makeRecord('account.bank.statement.line',
            [{
                relation: 'account.account',
                type: 'many2one',
                name: 'account_id',
                domain: [['company_id', '=', state.st_line.company_id], ['deprecated', '=', false]],
            }, {
                relation: 'account.journal',
                type: 'many2one',
                name: 'journal_id',
                domain: [['company_id', '=', state.st_line.company_id]],
            }, {
                relation: 'account.tax',
                type: 'many2many',
                name: 'tax_ids',
                domain: [['company_id', '=', state.st_line.company_id]],
            }, {
                relation: 'account.analytic.account',
                type: 'many2one',
                name: 'analytic_account_id',
            }, {
                relation: 'account.analytic.tag',
                type: 'many2many',
                name: 'analytic_tag_ids',
            }, {
                relation: 'account.financial.html.report.line',
                type: 'many2one',
                name: 'cf_html_type_id',
                domain: [['cf_type', '=', true]],
            }, {
                relation: 'account.financial.html.report.line',
                type: 'many2one',
                name: 'cf_html_section_id_59',
                domain: [['parent_id', '=', cfSectionIds.cf_operating]],
            },{
                relation: 'account.financial.html.report.line',
                type: 'many2one',
                name: 'cf_html_section_id_64',
                domain: [['parent_id', '=', cfSectionIds.cf_investing]],
            }, {
                relation: 'account.financial.html.report.line',
                type: 'many2one',
                name: 'cf_html_section_id_67',
                domain: [['parent_id', '=', cfSectionIds.cf_financing]],
            }, {
                type: 'boolean',
                name: 'force_tax_included',
            }, {
                type: 'char',
                name: 'label',
            }, {
                type: 'float',
                name: 'amount',
            }, {
                type: 'char', //TODO is it a bug or a feature when type date exists ?
                name: 'date',
            }, {
                type: 'boolean',
                name: 'to_check',
            }], {
                account_id: {
                    string: _t("Account"),
                },
                label: { string: _t("Label") },
                amount: { string: _t("Account") },
            }).then(function (recordID) {
                self.handleCreateRecord = recordID;
                var record = self.model.get(self.handleCreateRecord);
                self.fields.account_id = new relational_fields.FieldMany2One(self,
                    'account_id', record, { mode: 'edit', attrs: { can_create: false } });

                self.fields.journal_id = new relational_fields.FieldMany2One(self,
                    'journal_id', record, { mode: 'edit' });

                self.fields.tax_ids = new relational_fields.FieldMany2ManyTags(self,
                    'tax_ids', record, { mode: 'edit', additionalContext: { append_type_to_tax_name: true } });

                self.fields.analytic_account_id = new relational_fields.FieldMany2One(self,
                    'analytic_account_id', record, { mode: 'edit' });

                self.fields.cf_html_type_id = new relational_fields.FieldMany2One(self,
                    'cf_html_type_id', record, { mode: 'edit'});

                self.fields.cf_html_section_id_59 = new relational_fields.FieldMany2One(self,
                    'cf_html_section_id_59', record, { mode: 'edit' });

                self.fields.cf_html_section_id_64 = new relational_fields.FieldMany2One(self,
                    'cf_html_section_id_64', record, { mode: 'edit' });

                self.fields.cf_html_section_id_67 = new relational_fields.FieldMany2One(self,
                    'cf_html_section_id_67', record, { mode: 'edit' });

                self.fields.analytic_tag_ids = new relational_fields.FieldMany2ManyTags(self,
                    'analytic_tag_ids', record, { mode: 'edit' });

                self.fields.force_tax_included = new basic_fields.FieldBoolean(self,
                    'force_tax_included', record, { mode: 'edit' });

                self.fields.label = new basic_fields.FieldChar(self,
                    'label', record, { mode: 'edit' });

                self.fields.amount = new basic_fields.FieldFloat(self,
                    'amount', record, { mode: 'edit' });

                self.fields.date = new basic_fields.FieldDate(self,
                    'date', record, { mode: 'edit' });

                self.fields.to_check = new basic_fields.FieldBoolean(self,
                    'to_check', record, { mode: 'edit' });

                var $create = $(qweb.render("reconciliation.line.create", { 'state': state, 'group_tags': self.group_tags, 'group_acc': self.group_acc }));
                self.fields.account_id.appendTo($create.find('.create_account_id .o_td_field'))
                    .then(addRequiredStyle.bind(self, self.fields.account_id));
                self.fields.journal_id.appendTo($create.find('.create_journal_id .o_td_field'));
                self.fields.tax_ids.appendTo($create.find('.create_tax_id .o_td_field'));
                self.fields.analytic_account_id.appendTo($create.find('.create_analytic_account_id .o_td_field'));
                self.fields.analytic_tag_ids.appendTo($create.find('.create_analytic_tag_ids .o_td_field'));
                self.fields.cf_html_type_id.appendTo($create.find('.create_cf_html_type_id .o_td_field'));
                self.fields.cf_html_section_id_59.appendTo($create.find('.create_cf_html_section_id_59 .o_td_field'));
                self.fields.cf_html_section_id_64.appendTo($create.find('.create_cf_html_section_id_64 .o_td_field'));
                self.fields.cf_html_section_id_67.appendTo($create.find('.create_cf_html_section_id_67 .o_td_field'));
                self.fields.force_tax_included.appendTo($create.find('.create_force_tax_included .o_td_field'));
                self.fields.label.appendTo($create.find('.create_label .o_td_field'))
                    .then(addRequiredStyle.bind(self, self.fields.label));
                self.fields.amount.appendTo($create.find('.create_amount .o_td_field'))
                    .then(addRequiredStyle.bind(self, self.fields.amount));
                self.fields.date.appendTo($create.find('.create_date .o_td_field'));
                self.fields.to_check.appendTo($create.find('.create_to_check .o_td_field'));
                self.$('.create').append($create);

                function addRequiredStyle(widget) {
                    widget.$el.addClass('o_required_modifier');
                }
            });
        },
    });
    console.log('recon renderer:', ReconRenderer);
});