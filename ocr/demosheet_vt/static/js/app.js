/* DemoSheet VT-specific: fillForm only (base.js handles common functions) */

function fillForm(ocrResult) {
    var data = parseOcrJson(ocrResult);
    if (!data) return;
    lastOcrData = data;

    // text fields
    var textFields = [
        'WORK_DATE', 'WOKR_ENDDATE',
        'WORKERNO', 'WORKERNAME',
    ];

    for (var i = 1; i <= 6; i++) {
        var n = i < 10 ? '0' + i : '' + i;
        textFields.push('LEVEL_VALUE.' + n);
        textFields.push('GAUGE_VALUE.' + n);
        textFields.push('GAUGE_CVALUE.' + n);
    }

    textFields.forEach(function(id) {
        var el = document.getElementById(id);
        if (el && data[id] !== undefined) el.value = data[id];
    });

    var memo = document.getElementById('MEMO');
    if (memo && data['MEMO'] !== undefined) memo.value = data['MEMO'];

    // ST_EQNO (text)
    for (var i = 1; i <= 5; i++) {
        var n = i < 10 ? '0' + i : '' + i;
        var el = document.getElementById('ST_EQNO.' + n);
        if (el && data['ST_EQNO.' + n] !== undefined) el.value = data['ST_EQNO.' + n];
    }

    // checkboxes
    var checkFields = [
        'WORK_CHECK_A', 'WORK_CHECK_B', 'WORK_CHECK_C',
    ];
    for (var i = 1; i <= 20; i++) {
        var n = i < 10 ? '0' + i : '' + i;
        checkFields.push(i === 7 ? 'ST_GOOD.7' : 'ST_GOOD.' + n);
        checkFields.push('ST_BAD.' + n);
    }
    for (var i = 1; i <= 5; i++) {
        var n = i < 10 ? '0' + i : '' + i;
        checkFields.push('ST_CONDITION_A.' + n, 'ST_CONDITION_B.' + n, 'ST_CONDITION_C.' + n);
    }

    checkFields.forEach(function(id) {
        var el = document.getElementById(id);
        if (el && data[id] !== undefined) {
            el.checked = (data[id] === '✓' || data[id] === true || data[id] === '1' || data[id] === '○');
        }
    });
}
