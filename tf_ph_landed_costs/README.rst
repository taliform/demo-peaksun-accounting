.. |vspace| raw:: latex

   \vspace{4 mm}

.. |pagebreak| raw:: latex

   \newpage

Prerequisities
##############

Introduction
************

In this section contains the steps to be performed before the configuration and processing transaction for *Landed Cost*.

Installation
************

1. On the *Inventory > Configuration > Settings* menu, check if *Landed Cost* setting is already ticked. If not, kindly ticked to install the base landed cost module.

   .. image:: images/install0.png
      :align: center
      :width: 100 %

   |vspace|

2. On the *Apps > Apps* menu, search for *Philippines - Landed Cost* module and click **Install** button.

   .. image:: images/install1.png
      :align: center
      :width: 100 %

   |vspace|

Configuration
#############

Introduction
************

In main menu, the image below shows the application needed for processing configurations:

.. image:: images/inventory_menu.png
   :align: center
   :width: 100 %

|vspace|

Product Categories
******************

1. Go to *Configuration > Products > Product Categories* menu.

   .. image:: images/conf_menu.png
      :align: center
      :width: 50 %

   |vspace|

2. Select the corresponding *Product Category* record.

   .. image:: images/product_category1.png
      :align: center
      :width: 100 %

   |vspace|

3. Check if the *Costing Method* is **First In First Out**.

   .. image:: images/product_category2.png
      :align: center
      :width: 100 %

   |vspace|

   |pagebreak|

Product Template
****************

1. Go to *Master Data > Products > Products* menu.

   .. image:: images/master_menu.png
      :align: center
      :width: 50 %

   |vspace|

2. Select the corresponding *Product Template* record.

   .. image:: images/product_template1.png
      :align: center
      :width: 100 %

   |vspace|

3. Check if the *Product Category* is the same product category configured.

   .. image:: images/product_template2.png
      :align: center
      :width: 100 %

   |vspace|

   |pagebreak|

4. Check if the *Imported Items* is already checked under Inventory > Operations.

   .. image:: images/product_template3.png
      :align: center
      :width: 100 %

   |vspace|

   .. note::
      This part can be skip, if the Warehouse record was setup with 2-step receiving process.

   |pagebreak|

Landed Cost Types
*****************

1. In Main menu, click *Inventory* icon.

   .. image:: images/inventory_menu.png
      :align: center
      :width: 100 %

   |vspace|

2. Go to *Configuration > Products > Landed Cost Types* menu.

   .. image:: images/conf_menu.png
      :align: center
      :width: 50 %

   |vspace|

3. Select the corresponding *Landed Cost type* record.

   .. image:: images/cost_type1.png
      :align: center
      :width: 100 %

   |vspace|

4. Click **[Edit]** button.

   .. image:: images/cost_type2.png
      :align: center
      :width: 100 %

   |vspace|

   |pagebreak|

5. Click *Accounting* tab to view the following fields:

   .. image:: images/cost_type3.png
      :align: center
      :width: 100 %

   |vspace|

   * *Taxable* - Check if cost type is subject for tax.

   * *Dutiable* - Check if cost type is an expense needed to importation of items.

   |vspace|

6. Click **[Save]** button.

   .. image:: images/cost_type4.png
      :align: center
      :width: 100 %

   |vspace|


Transaction
###########

Introduction
************

In this section contains the steps to be performed when processing *Landed Cost* record and application to the product cost.

Process Flow
************

.. image:: images/landed_cost_flow.png
   :align: center
   :width: 90 %

|vspace|

|pagebreak|

Procedure
*********

Ordering Items
==============

1. Purchase all the items needed.

   .. image:: images/purchase_order.png
      :align: center
      :width: 100 %

   |vspace|

   .. note::
      Purchase Order records are processed and received by default Odoo process flow.

   |pagebreak|

Receiving Items
===============

1. In Main menu, click *Inventory* icon.

   .. image:: images/inventory_menu.png
      :align: center
      :width: 100 %

   |vspace|

2. Navigate to *Inventory* menu.

   .. image:: images/menu_1.png
      :align: center
      :width: 50 %

   |vspace|

3. Navigate to *To Process* incoming receipts.

   .. image:: images/incoming1.png
      :align: center
      :width: 100 %

   |vspace|

4. Select the corresponding incoming shipment.

   .. image:: images/incoming2.png
      :align: center
      :width: 100 %

   |vspace|

   |pagebreak|

5. Click **[Validate]** button to receive the items.

   .. image:: images/incoming3.png
      :align: center
      :width: 100 %

   |vspace|

   .. note::
      The items are received in Input location for Landed Cost Processing.

6. The incoming shipment are moved to *Done* state.

   .. image:: images/incoming4.png
      :align: center
      :width: 100 %

   |vspace|

   |pagebreak|

Landed Cost Processing
======================

1. In Main menu, click *Inventory* icon.

   .. image:: images/inventory_menu.png
      :align: center
      :width: 100 %

   |vspace|

2. Go to *Operations > Landed Cost* menu.

   .. image:: images/menu_1.png
      :align: center
      :width: 50 %

   |vspace|

3. In list view, click **[Create]** button to load the *Landed Cost* form.

   .. image:: images/menu_2.png
      :align: center
      :width: 100 %

   |vspace|

4. In form view, input the following fields:

   .. image:: images/form_1.png
      :align: center
      :width: 100 %

   |vspace|

   * *Date* - Date of processing the costing.
   * *Vendor* - Name of Vendor whom bought the items
   * *Account Journal* - Journal used for accounting entries
   * *Reference* - Any source document reference 

   |vspace|

5. Click *Add a line* link to add warehouse transactions.

   .. image:: images/form_2.png
      :align: center
      :width: 100 %

   |vspace|


6. Check the corresponding stock transfer records.

   .. image:: images/transfer_1.png
      :align: center
      :width: 75 %

   |vspace|

7. In the *Importation Details* section, input the following fields:

   .. image:: images/form_2_1.png
      :align: center
      :width: 100 %

   |vspace|

   * *Country of Origin*
   * *Broker*
   * *Expected Arrival Date*
   * *Importation Date* 
   * *Assessment/Release Date*
   * *Date of VAT Payment*
   * *Invoice Reference*
   * *Import Entry Declaration Number*
   * *Official Receipt*

   |pagebreak|

8. In the Amount section, input the following fields:

   .. image:: images/form_3.png
      :align: center
      :width: 100 %

   |vspace|

   * *Transaction Value (in Foreign Currency)*
   * *Exempted Tax Amount*

   Other fields included are:

   * *Bill of Landing*
   * *HS Code*
   * *Gross Weight*
   * *Net Weight*

   |vspace|
 

9. In *Cost Lines* section, the user should select the corresponding *Landed Cost Types* record.

   .. image:: images/form_4.png
      :align: center
      :width: 100 %

   |vspace|

   |pagebreak|

10. Click **[Save]** button.

   .. image:: images/form_5.png
      :align: center
      :width: 100 %

   |vspace|

11. After inputting all the information, click **[Compute]** button.

   .. image:: images/form_6.png
      :align: center
      :width: 100 %

   |vspace|

   |pagebreak|

12. After the computation, navigate to *Valuation Adjustments* section to view the computation of product cost including the former, allocated, and landed cost.

   .. image:: images/form_7.png
      :align: center
      :width: 100 %

   |vspace|

   * *Product* - Name of the product to be applied
   * *Name* - Name of the additional cost
   * *Quantity* - Total Quantity of the items per product
   * *Purchase Unit of Measure* - UoM used in Purchase Orders
   * *Former Cost* - Total Purchase Cost based on Purchase Orders
   * *Former Cost per Unit* - Total Purchase Cost / Item Quantity
   * *Allocated Cost* - Total Additional Cost based on Cost Lines
   * *Allocated Cost per Unit* - Total Additional Cost / Item Quantity
   * *Landed Cost* - Total Landed Cost from Purchase Cost and Additional Cost
   * *Landed Cost per Unit* - Total Landed Cost / Item Quantity

   |vspace|

13. To view the detailed computation of cost, click **[Detailed Adjustment]** smart button on the upper right side of the form.

   .. image:: images/detailed.png
      :align: center
      :width: 100 %

   |vspace|

14. After checking the cost computation, click **[Confirm]** button to move the record to *Confirm* state.

   .. image:: images/form_5.png
      :align: center
      :width: 100 %

   |vspace|

15. Landed Cost record will moved to *Confirmed* state.

   .. image:: images/form_8.png
      :align: center
      :width: 100 %

   |vspace|

16. After the landed cost is already checked and validated,click **[Validate]** button to apply the cost in the product.

   .. image:: images/form_9.png
      :align: center
      :width: 100 %

   |vspace|

17. *Internal Transfer* all purchased items from input/imported location to stock location.   