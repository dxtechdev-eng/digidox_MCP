/* VT Attendance-specific: fillForm only (base.js handles common functions) */

function fillForm(ocrResult) {
    var data = parseOcrJson(ocrResult);
    if (!data) return;
    lastOcrData = data;

    var textFields = ['LINE_NAME', 'HANGER_INFO'];

    for (var c = 1; c <= 6; c++) {
        textFields.push('DATE.' + (c < 10 ? '0' + c : '' + c));
    }

    for (var r = 1; r <= 40; r++) {
        var n = r < 10 ? '0' + r : '' + r;
        textFields.push('MA_SO.' + n, 'HO_TEN.' + n, 'GHI_CHU.' + n);
        for (var c = 1; c <= 6; c++) {
            textFields.push('D' + c + '.' + n);
        }
    }

    textFields.forEach(function(id) {
        var el = document.getElementById(id);
        if (el && data[id] !== undefined) el.value = data[id];
    });
}
