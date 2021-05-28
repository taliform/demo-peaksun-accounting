/**
	/ss_ph_payment_withholding/static/src/js/account_reconciliation_widget_inherit.js
 */

odoo.define('ss_ph_payment_withholding.withholding_tax_computation', function (require) {
	"use strict";  

	var Widget = require('web.Widget');
	var FieldManagerMixin = require('web.FieldManagerMixin');
	var relational_fields = require('web.relational_fields');
	var basic_fields = require('web.basic_fields');
	var core = require('web.core');
	var time = require('web.time');
	var session = require('web.session');
	var qweb = core.qweb;
	var _t = core._t;
	var accountReconciliationRenderer = require('account.ReconciliationRenderer');
	var accountLineRenderer = accountReconciliationRenderer.LineRenderer

	//ADD FIELDS
	accountLineRenderer.include({	
		_renderCreate: function (state) {
			var self = this;
			this.model.makeRecord('account.bank.statement.line', [{
			    relation: 'account.tax',
			    type: 'many2one',
			    name: 'withholding_tax_id',

			}]).then(function (recordID) {
				self.handleCreateRecord = recordID;
				var record = self.model.get(self.handleCreateRecord);

				self.fields.withholding_tax_id = new relational_fields.FieldMany2One(self,
					'withholding_tax_id', record, {mode: 'edit'});
				 
				 var $create = $(qweb.render("reconciliation.line.create", {'state': state}));
				 self.fields.withholding_tax_id.appendTo($create.find('.create_withholding_tax_id .o_td_field'));
                                 self.$('.create').append($create);

				    function addRequiredStyle(widget) {
					widget.$el.addClass('o_required_modifier');


	    	
			    }
			});
		    },
	    } 
	});
	

