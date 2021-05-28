.. |vspace| raw:: latex

   \vspace{5mm}
   
.. |pagebreak| raw:: latex

    \newpage

.. description

Overview
^^^^^^^^

.. contents

This module improves the default Bank Statement of Odoo with the following features:

- Summary Report 
- Adding of Outstanding and In-Transit Payments.
- Tagging of Outstanding Payments as Released or Unreleased. 
- Creation of Adjustments for Bank and Book Errors. 

Procedure
^^^^^^^^^

Users
~~~~~
-   Accounting & Finance

Prerequisites
~~~~~~~~~~~~~

**Bank Jounal**

Configure your bank journal to be viewable in the accounting dashboard by opening/creating a bank journal record in *Accounting/Configuration/Accounting/Journals* 
and check the **Show journal on dashboard** option under the **Advanced Setting** tab. This will open the journal to additional features such as bank statements.

.. image:: tf_ph_bank_recon/static/images/bs_journal.png
   :align: center
   :width: 800 px
   :scale: 100 %


Creation of Bank Statement
~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Create a new bank statement by going to *Accounting/Dashboard*.
2. On the preffered bank journal, click **[New Statement]**

.. image:: tf_ph_bank_recon/static/images/bs_new_statement.png
   :align: center
   :width: 800 px
   :scale: 100 %
   
;Or open an existing statement in 'New' state, by clicking on **[More]** and then *View/Bank Statements*.

.. image:: tf_ph_bank_recon/static/images/view_bs.png
   :align: center
   :width: 800 px
   :scale: 100 %
   
3. On bank statement record, click **[Load Payments]** to load the bank statement record with un-reconciled payments that are less than or equal to the bank statement date.

.. image:: tf_ph_bank_recon/static/images/load_payments.png
   :align: center
   :width: 800 px
   :scale: 100 %
  
4. Click the **[Lock]** button, to prevent the Book's Unadjusted Balance amount from changing.

.. image:: tf_ph_bank_recon/static/images/load_payments.png
   :align: center
   :width: 800 px
   :scale: 100 %
  
4. Set payments in In-Transit and Outstanding tabs as 'Bounced' or 'Cancelled'.

.. image:: tf_ph_bank_recon/static/images/bs_bounce_cancel.png
   :align: center
   :width: 800 px
   :scale: 100 %
 
5. Set outstanding paymanent as 'Released' or 'Unreleased' by clicking on the release/unrelease switch.

.. image:: tf_ph_bank_recon/static/images/bs_release.png
   :align: center
   :width: 800 px
   :scale: 100 %
   
6. Create book and bank adjustments in the adjustments tab by clicking on *'Add an item'* on the list while on edit mode. 

.. image:: tf_ph_bank_recon/static/images/bs_adjustments.png
   :align: center
   :width: 800 px
   :scale: 100 %
   
7. Create a journal entry for unreleased checks by clicking on the **[Create Journal Entry]** button under **Outstanding tab**.

.. image:: tf_ph_bank_recon/static/images/bs_create_je.png
   :align: center
   :width: 800 px
   :scale: 100 %


 