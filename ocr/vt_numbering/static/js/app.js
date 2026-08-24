/* VT Numbering & Pairing-specific: fillForm only (base.js handles common functions) */

function fillForm(ocrResult) {
    var data = parseOcrJson(ocrResult);
    if (!data) return;
    lastOcrData = data;

    var textFields = ['TEN_CN', 'MA_SO_CN', 'NGAY'];

    var cols = ['MA_HANG', 'SO_FILE', 'LOAI_VAI', 'SO_BAN', 'MAU',
                'TI_LE', 'SO_BO', 'SO_LOP', 'GHI_CHU'];
    for (var r = 1; r <= 20; r++) {
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
