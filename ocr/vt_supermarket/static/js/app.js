/* VT Supermarket-specific: fillForm only (base.js handles common functions) */

function fillForm(ocrResult) {
    var data = parseOcrJson(ocrResult);
    if (!data) return;
    lastOcrData = data;

    var textFields = ['MA_SO_THE', 'HO_TEN', 'NGAY'];

    var cols = ['MA_HANG', 'LOAI_VAI', 'SO_FILE', 'MAU',
                'SO_TT_BO', 'SO_LOP_BO', 'SO_SIZE_XE'];
    for (var r = 1; r <= 40; r++) {
        var n = r < 10 ? '0' + r : '' + r;
        cols.forEach(function(col) {
            textFields.push(col + '.' + n);
        });
    }

    textFields.forEach(function(id) {
        var el = document.getElementById(id);
        if (el && data[id] !== undefined) el.value = data[id];
    });
}
