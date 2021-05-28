let companyDetails = [];
odoo.define('tf_ph_bir.print_csv_button', function (require) {
    "use strict";

    const rpc = require('web.rpc');
    console.log('print_csv javascript running...');
    rpc.query({
            model: 'account.alphalist.map',
            method: 'get_company_data'
        }).then((res) => {
            console.log(res);
            companyDetails.push(res);
            companyDetails = JSON.parse(companyDetails);
        });

});
function print_csv() {
    const dataHeaders = document.querySelectorAll('.o_account_reports_level2');
    console.log(dataHeaders);

    const tableData = [
        ["name1", "city1", "some other info"],
        ["name2", "city2", "more info"]
    ];
    const fileType = "data:text/csv;charset=utf-8";
    let csvContent = tableData.map(e => e.join(",")).join("\n");
    let currentDateTime = new moment().utc().format('MM/YYYY');
    let companyDetailsLatestData = companyDetails.length - 1;
    const companyTin = companyDetails.company_tin.substring(0, 9);
    const companyBranch = companyDetails.company_tin.substring(9, 12);
    let alphalist_type = companyDetails.alphalist_type == "QAP" ? "1601EQ" : "2307E";
    let filename = `${companyTin}${companyBranch}${currentDateTime.replace("/", "")}${alphalist_type}.dat.csv`;
    const blob = new Blob([csvContent], {
        type: fileType
    });

    saveAs(blob, filename);
}
