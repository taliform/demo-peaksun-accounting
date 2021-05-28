odoo.define('tf_ph_bank_recon.recon_model_inherit', function(require){
    "use strict";

    const BasicModel = require('web.BasicModel');
    const field_utils = require('web.field_utils');
    const utils = require('web.utils');
    const session = require('web.session');
    const WarningDialog = require('web.CrashManager').WarningDialog;
    const core = require('web.core');
    const _t = core._t;
    const relational_fields = require('web.relational_fields');
    const ReconModel = require('account.ReconciliationModel');

    ReconModel.StatementModel.include({
        init: function (parent, options) {
            this._super.apply(this, arguments);
            this.reconcileModels = [];
            this.lines = {};
            this.valuenow = 0;
            this.valuemax = 0;
            this.alreadyDisplayed = [];
            this.domain = [];
            this.defaultDisplayQty = options && options.defaultDisplayQty || 10;
            this.limitMoveLines = options && options.limitMoveLines || 15;
            this.getStatementLines();
            this.display_context = 'init';
        },
        quickCreateFields: ['account_id', 'amount', 'analytic_account_id', 'label', 'tax_ids', 'force_tax_included',
        'analytic_tag_ids', 'to_check', 'cf_html_type_id', 'cf_html_section_id_59', 'cf_html_section_id_64', 'cf_html_section_id_67'],
        // getStatementLines: function () {
        //     var self = this;
        //     var linesToDisplay = _.pick(this.lines, function (value, key, object) {
        //         if (value.reconciliation_proposition.length ) {
        //             self.validate(value.handle);
        //         }
        //         if (value.visible === true && self.alreadyDisplayed.indexOf(key) === -1) {
        //             self.alreadyDisplayed.push(key);
        //             return object;
        //         }
        //     });
        //     return linesToDisplay;
        // },
        validate: function (handle) {
            var self = this;
            this.display_context = 'validate';
            var handles = [];
            if (handle) {
                handles = [handle];
            } else {
                _.each(this.lines, function (line, handle) {
                    if (!line.reconciled && line.balance && !line.balance.amount && line.reconciliation_proposition.length) {
                        handles.push(handle);
                    }
                });
            }
            var ids = [];
            var values = [];
            var handlesPromises = [];
            _.each(handles, function (handle) {
                var line = self.getLine(handle);
                var props = _.filter(line.reconciliation_proposition, function (prop) { return !prop.invalid; });
                var computeLinePromise;
                if (props.length === 0) {
                    // Usability: if user has not chosen any lines and click validate, it has the same behavior
                    // as creating a write-off of the same amount.
                    props.push(self._formatQuickCreate(line, {
                        account_id: [line.st_line.open_balance_account_id, self.accounts[line.st_line.open_balance_account_id]],
                    }));
                    // update balance of line otherwise it won't be to zero and another line will be added
                    line.reconciliation_proposition.push(props[0]);
                    computeLinePromise = self._computeLine(line);
                }
                ids.push(line.id);
                handlesPromises.push(Promise.resolve(computeLinePromise).then(function () {
                    var values_dict = {
                        "partner_id": line.st_line.partner_id,
                        "counterpart_aml_dicts": _.map(_.filter(props, function (prop) {
                            return !isNaN(prop.id) && !prop.already_paid;
                        }), self._formatToProcessReconciliation.bind(self, line)),
                        "payment_aml_ids": _.pluck(_.filter(props, function (prop) {
                            return !isNaN(prop.id) && prop.already_paid;
                        }), 'id'),
                        "new_aml_dicts": _.map(_.filter(props, function (prop) {
                            return isNaN(prop.id) && prop.display;
                        }), self._formatToProcessReconciliation.bind(self, line)),
                        "to_check": line.to_check,
                    };

                    // If the lines are not fully balanced, create an unreconciled amount.
                    // line.st_line.currency_id is never false here because its equivalent to
                    // statement_line.currency_id or statement_line.journal_id.currency_id or statement_line.journal_id.company_id.currency_id (Python-side).
                    // see: get_statement_line_for_reconciliation_widget method in account/models/account_bank_statement.py for more details
                    var currency = session.get_currency(line.st_line.currency_id);
                    var balance = line.balance.amount;
                    if (!utils.float_is_zero(balance, currency.digits[1])) {
                        var unreconciled_amount_dict = {
                            'account_id': line.st_line.open_balance_account_id,
                            'credit': balance > 0 ? balance : 0,
                            'debit': balance < 0 ? -balance : 0,
                            'name': line.st_line.name + ' : ' + _t("Open balance"),
                        };
                        values_dict['new_aml_dicts'].push(unreconciled_amount_dict);
                    }
                    values.push(values_dict);
                    line.reconciled = true;
                }));

                _.each(self.lines, function (other_line) {
                    if (other_line != line) {
                        var filtered_prop = other_line.reconciliation_proposition.filter(p => !line.reconciliation_proposition.map(l => l.id).includes(p.id));
                        if (filtered_prop.length != other_line.reconciliation_proposition.length) {
                            other_line.need_update = true;
                            other_line.reconciliation_proposition = filtered_prop;
                        }
                        self._computeLine(line);
                    }
                })
            });
            return Promise.all(handlesPromises).then(function () {
                return self._rpc({
                    model: 'account.reconciliation.widget',
                    method: 'process_bank_statement_line',
                    args: [ids, values],
                    context: self.context,
                })
                    .then(self._validatePostProcess.bind(self))
                    .then(function () {
                        self.valuenow += handles.length;
                        return { handles: handles };
                    });
            });
        },
        _formatQuickCreate: function (line, values) {
            values = values || {};
            var today = new moment().utc().format();
            var account = this._formatNameGet(values.account_id);
            var formatOptions = {
                currency_id: line.st_line.currency_id,
            };
            var amount;
            switch (values.amount_type) {
                case 'percentage':
                    amount = line.balance.amount * values.amount / 100;
                    break;
                case 'regex':
                    var matching = line.st_line.name.match(new RegExp(values.amount_from_label_regex))
                    amount = 0;
                    if (matching && matching.length == 2) {
                        matching = matching[1].replace(new RegExp('\\D' + values.decimal_separator, 'g'), '');
                        matching = matching.replace(values.decimal_separator, '.');
                        amount = parseFloat(matching) || 0;
                        amount = line.balance.amount > 0 ? amount : -amount;
                    }
                    break;
                case 'fixed':
                    amount = values.amount;
                    break;
                default:
                    amount = values.amount !== undefined ? values.amount : line.balance.amount;
            }


            var prop = {
                'id': _.uniqueId('createLine'),
                'label': values.label || line.st_line.name,
                'account_id': account,
                'account_code': account ? this.accounts[account.id] : '',
                'analytic_account_id': this._formatNameGet(values.analytic_account_id),
                'analytic_tag_ids': this._formatMany2ManyTags(values.analytic_tag_ids || []),
                'cf_html_type_id': this._formatNameGet(values.cf_html_type_id),
                'cf_html_section_id_59': this._formatNameGet(values.cf_html_section_id_59),
                 'cf_html_section_id_64': this._formatNameGet(values.cf_html_section_id_64),
                'cf_html_section_id_67': this._formatNameGet(values.cf_html_section_id_67),
                'journal_id': this._formatNameGet(values.journal_id),
                'tax_ids': this._formatMany2ManyTagsTax(values.tax_ids || []),
                'tag_ids': values.tag_ids,
                'tax_repartition_line_id': values.tax_repartition_line_id,
                'debit': 0,
                'credit': 0,
                'date': values.date ? values.date : field_utils.parse.date(today, {}, { isUTC: true }),
                'force_tax_included': values.force_tax_included || false,
                'base_amount': amount,
                'percent': values.amount_type === "percentage" ? values.amount : null,
                'link': values.link,
                'display': true,
                'invalid': true,
                'to_check': !!values.to_check,
                '__tax_to_recompute': true,
                '__focus': '__focus' in values ? values.__focus : true,
            };
            if (prop.base_amount) {
                // Call to format and parse needed to round the value to the currency precision
                var sign = prop.base_amount < 0 ? -1 : 1;
                var amount = field_utils.format.monetary(Math.abs(prop.base_amount), {}, formatOptions);
                prop.base_amount = sign * field_utils.parse.monetary(amount, {}, formatOptions);
            }

            prop.amount = prop.base_amount;
            return prop;
        },
        _formatToProcessReconciliation: function (line, prop) {
            var amount = -prop.amount;
            if (prop.partial_amount) {
                amount = -prop.partial_amount;
            }
            let cf_section_id = 'cf_html_section_id_59' in prop ? prop.cf_html_section_id_59.id
                               :'cf_html_section_id_64' in prop ? prop.cf_html_section_id_64.id
                               :'cf_html_section_id_67' in prop ? prop.cf_html_section_id_67.id
                               : false;
            var result = {
                name: prop.label,
                debit: amount > 0 ? amount : 0,
                credit: amount < 0 ? -amount : 0,
                tax_exigible: prop.tax_exigible,
                analytic_tag_ids: [[6, null, _.pluck(prop.analytic_tag_ids, 'id')]],
                cf_html_type_id: 'cf_html_type_id' in prop ? prop.cf_html_type_id.id : false,
                cf_html_section_id: cf_section_id
            };
            if (!isNaN(prop.id)) {
                result.counterpart_aml_id = prop.id;
            } else {
                result.account_id = prop.account_id.id;
                if (prop.journal_id) {
                    result.journal_id = prop.journal_id.id;
                }
            }
            if (!isNaN(prop.id)) result.counterpart_aml_id = prop.id;
            if (prop.analytic_account_id) result.analytic_account_id = prop.analytic_account_id.id;
            if (prop.tax_ids && prop.tax_ids.length) result.tax_ids = [[6, null, _.pluck(prop.tax_ids, 'id')]];

            if (prop.tag_ids && prop.tag_ids.length) result.tag_ids = [[6, null, prop.tag_ids]];
            if (prop.tax_repartition_line_id) result.tax_repartition_line_id = prop.tax_repartition_line_id;
            if (prop.reconcileModelId) result.reconcile_model_id = prop.reconcileModelId
            return result;
        },
        updateProposition: function (handle, values) {
            var self = this;
            var line = this.getLine(handle);
            var prop = _.last(_.filter(line.reconciliation_proposition, '__focus'));
            if ('to_check' in values && values.to_check === false) {
                // check if we have another line with to_check and if yes don't change value of this proposition
                prop.to_check = line.reconciliation_proposition.some(function(rec_prop, index) {
                    return rec_prop.id !== prop.id && rec_prop.to_check;
                });
            }
            if (!prop) {
                prop = this._formatQuickCreate(line);
                line.reconciliation_proposition.push(prop);
            }
            _.each(values, function (value, fieldName) {
                if (fieldName === 'analytic_tag_ids') {
                    switch (value.operation) {
                        case "ADD_M2M":
                            // handle analytic_tag selection via drop down (single dict) and
                            // full widget (array of dict)
                            var vids = _.isArray(value.ids) ? value.ids : [value.ids];
                            _.each(vids, function (val) {
                                if (!_.findWhere(prop.analytic_tag_ids, {id: val.id})) {
                                    prop.analytic_tag_ids.push(val);
                                }
                            });
                            break;
                        case "FORGET":
                            var id = self.localData[value.ids[0]].ref;
                            prop.analytic_tag_ids = _.filter(prop.analytic_tag_ids, function (val) {
                                return val.id !== id;
                            });
                            break;
                    }
                }
                else if (fieldName === 'tax_ids') {
                    switch(value.operation) {
                        case "ADD_M2M":
                            prop.__tax_to_recompute = true;
                            var vids = _.isArray(value.ids) ? value.ids : [value.ids];
                            _.each(vids, function(val){
                                if (!_.findWhere(prop.tax_ids, {id: val.id})) {
                                    value.ids.price_include = self.taxes[val.id] ? self.taxes[val.id].price_include : false;
                                    prop.tax_ids.push(val);
                                }
                            });
                            break;
                        case "FORGET":
                            prop.__tax_to_recompute = true;
                            var id = self.localData[value.ids[0]].ref;
                            prop.tax_ids = _.filter(prop.tax_ids, function (val) {
                                return val.id !== id;
                            });
                            break;
                    }
                }
                else {
                    prop[fieldName] = values[fieldName];
                }
            });
            if ('cf_html_type_id' in values) {
                let cfSectionElements = {
                    59: document.getElementById('cf_section_59'),
                    64: document.getElementById('cf_section_64'),
                    67: document.getElementById('cf_section_67')
                }
                const cfTypeId = values.cf_html_type_id.id
                if (cfTypeId) {
                     let sectionElement = cfSectionElements[cfTypeId]
                    if ( sectionElement.classList.contains('d-none') ){
                        sectionElement.classList.remove('d-none');
                    }
                    for (let x in cfSectionElements) {
                        if (x != cfTypeId && !cfSectionElements[x].classList.contains('d-none')) {
                            cfSectionElements[x].classList.add('d-none');
                        }
                    }
                }
            }

            if ('account_id' in values) {
                prop.account_code = prop.account_id ? this.accounts[prop.account_id.id] : '';
            }
            if ('amount' in values) {
                prop.base_amount = values.amount;
                if (prop.reconcileModelId) {
                    this._computeReconcileModels(handle, prop.reconcileModelId);
                }
            }
            if ('force_tax_included' in values || 'amount' in values || 'account_id' in values) {
                prop.__tax_to_recompute = true;
            }
            line.createForm = _.pick(prop, this.quickCreateFields);
            // If you check/uncheck the force_tax_included box, reset the createForm amount.
            if(prop.base_amount)
                line.createForm.amount = prop.base_amount;
            if (prop.tax_ids.length !== 1 ) {
                // When we have 0 or more than 1 taxes, reset the base_amount and force_tax_included, otherwise weird behavior can happen
                prop.amount = prop.base_amount;
                line.createForm.force_tax_included = false;
            }
            return this._computeLine(line);
        },
    });

    console.log('recon model:', ReconModel);

});