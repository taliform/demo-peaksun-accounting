/**
	/ss_ph_payment_withholding/static/src/js/account_reconciliation_widget_inherit.js
 */

odoo.define('ss_ph_payment_withholding_v12.withholding_tax_computation', function (require) {
	"use strict";  

	var core = require('web.core');
	var FieldMany2One = core.form_widget_registry.get('many2one');
	var _t = core._t;
	
	var accountReconciliation = require('account.reconciliation');
	var abstractReconciliation = accountReconciliation.abstractReconciliation;
	var abstractReconciliationLine = accountReconciliation.abstractReconciliationLine;
	var manualReconciliationLine = accountReconciliation.manualReconciliationLine;
	
	//ADD FIELDS
	abstractReconciliation.include({
		init: function(parent, context) {
	    	this._super(parent);
	    	var form_fields = this.create_form_fields;
	    	
	    	form_fields.withholding_tax_id = {
	                id: "withholding_tax_id",
	                index: 25, // position in the form
	                corresponding_property: "withholding_tax_id", // a account.move.line field name
	                label: _t("Withholding Tax"),
	                required: false,
	                constructor: FieldMany2One,
	                field_properties: {
	                    relation: "account.tax",
	                    string: _t("Withholding Tax"),
	                    type: "many2one",
	                    domain: [['amount', '<', 0.0]],
	                },
	            };
	    	
	    	this.create_form_fields = form_fields;
	    } 
	});
	
	
	abstractReconciliationLine.include({
		prepareCreatedMoveLinesForPersisting: function(lines) {
			var dicts = this._super(lines);

			for (var x=0; x<lines.length; x++){
				for (var i=0; i<dicts.length; i++){
					if (lines[x].label === dicts[i].name){
						dicts[i]['withholding_tax_id'] = lines[x].withholding_tax_id;
						console.log(dicts[i]['withholding_tax_id']);
					};
				};
			};
			return dicts;
		}
	});
	
	//INHERIT ONCHANGE FUNCTION
	abstractReconciliationLine.include({
		formCreateInputChanged: function(elt, val) {
			self = this;
			var mv_lines_selected = self.get("mv_lines_selected")

			if (elt === self.withholding_tax_id_field && val.newValue !== false){
				var withholding_tax_id = self.withholding_tax_id_field.get("value");		
				var mv_lines_selected = self.get("mv_lines_selected");
				var withholding_account_id = self.withholding_tax_id
				var line_created_being_edited = self.get("line_created_being_edited");
				var mv_lines_amount = 0
				self.amount_field.set("value", 0); //Reset Amount Value to Zero
				
				_.each(mv_lines_selected, function(o) { //Loop through chosen selected lines
					if (o.tax_line_id.length == 0) {
						mv_lines_amount += o.base_amount;
						//mv_lines_amount += (o.account_type === 'receivable') ? o.debit : o.credit;
					};

		        });
				
				
				self.model_tax
				.call("json_friendly_compute_all", [[withholding_tax_id], mv_lines_amount, self.get("currency_id")])
				.then(function(data){ //compute taxes
					$.each(data.taxes,function(index,tax){
						var amount_value = self.amount_field.get("value")  + Math.abs(tax.amount)
						self.amount_field.set("value", amount_value); // set account 
						self.account_id_field.set("value", tax.account_id) //Set amount field
                        line_created_being_edited[0].amount = amount_value;
						self.label_field.set("value",'Withholding Tax - ' + tax.name);
                        
					});
				});
								
			}
			return this._super(elt,val);
		}
	});
});

