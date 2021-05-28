odoo.define('tf_ph_bank_recon.recon_action_inherit', function(require){
    "use strict";

    var AbstractAction = require('web.AbstractAction');
    var ReconciliationModel = require('account.ReconciliationModel');
    var ReconciliationRenderer = require('account.ReconciliationRenderer');
    var core = require('web.core');
    var QWeb = core.qweb;

    var ReconAction = require('account.ReconciliationClientAction');
    ReconAction.StatementAction.include({
         _renderLines: function () {
            var self = this;
            var linesToDisplay = this.model.getStatementLines();
            var linePromises = [];
            _.each(linesToDisplay, function (line, handle) {
                var widget = new self.config.LineRenderer(self, self.model, line);
                widget.handle = handle;
                self.widgets.push(widget);
                linePromises.push(widget.appendTo(self.$('.o_reconciliation_lines')));
            });
            if (this.model.hasMoreLines() === false) {
                this.renderer.hideLoadMoreButton(true);
            }
            else {
                this.renderer.hideLoadMoreButton(false);
            }
            return Promise.all(linePromises);
        },
    });

    console.log('recon action:', ReconAction);
});