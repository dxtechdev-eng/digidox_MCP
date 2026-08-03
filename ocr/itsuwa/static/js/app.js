/* Itsuwa-specific: fillForm only (base.js handles common functions) */

function fillForm(ocrResult) {
    var data = parseOcrJson(ocrResult);
    if (!data) return;
    lastOcrData = data;

    // lowercase normalization (OCR may return uppercase keys)
    var normalized = {};
    Object.keys(data).forEach(function(k) {
        normalized[k.toLowerCase()] = data[k];
    });

    var fields = [
        'time', 'packcondition', 'inspector',
        'foreignsub', 'poll', 'defect',
        'ijp', 'verifier', 'card'
    ];

    for (var row = 1; row <= 8; row++) {
        fields.forEach(function(field) {
            var id = field + '_' + row;
            var el = document.getElementById(id);
            if (el && normalized[id] !== undefined) {
                el.value = normalized[id];
            }
        });
    }
}
