var params = new URLSearchParams(window.location.search);
var key = params.get('key');

var seq = null;
var formid = null;
var totalPages = 1;
var currentPage = 0;
var lastOcrData = null;

if (key) {
    try {
        var decoded = atob(decodeURIComponent(key));
        var p = new URLSearchParams(decoded);
        seq = p.get('seq');
        formid = p.get('formid');
    } catch (e) {
        console.error('key decode failed:', e);
    }
}

window.addEventListener('DOMContentLoaded', function() {
    if (seq) {
        document.getElementById('docInfo').textContent = 'seq: ' + seq + ' | formid: ' + formid;
        loadImage(1);
        runOcr(false);
    } else {
        document.getElementById('docInfo').textContent = 'key parameter missing';
    }
});

function loadImage(page) {
    var img = document.getElementById('docImage');
    img.src = '/api/image?seq=' + seq + '&idx=' + page;
}

async function runOcr(force) {
    if (!seq) return;
    var overlay = document.getElementById('loadingOverlay');
    overlay.classList.add('active');

    try {
        var url = '/api/ocr?seq=' + seq + '&formid=' + formid;
        if (force) url += '&force=true';
        var res = await fetch(url);
        var data = await res.json();

        if (data.resultCode === '200') {
            totalPages = data.pages || 1;
            fillForm(data.ocrResult);
        } else {
            alert('OCR error: ' + data.resultMsg);
        }
    } catch (e) {
        console.error('Error:', e);
        alert('Request failed: ' + e.message);
    } finally {
        overlay.classList.remove('active');
    }
}

function fillForm(ocrResult) {
    if (!ocrResult) return;

    var data = null;
    try {
        var text = typeof ocrResult === 'string' ? ocrResult : JSON.stringify(ocrResult);
        var match = text.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (match) text = match[1].trim();
        data = JSON.parse(text);
        lastOcrData = data;
        console.log('OCR parsed:', data);
    } catch (e) {
        console.error('OCR JSON parse failed:', e);
        return;
    }

    // 텍스트 필드
    var textFields = [
        'YEAR', 'MONTH', 'DAY',
        'HURIGANA_1', 'NAME_1', 'POSTCODE_1', 'ADDRESS_1', 'TEL_1',
        'HURIGANA_2', 'NAME_2', 'POSTCODE_2', 'ADDRESS_2', 'TEL_2',
        'TODOKE_MONTH', 'TODOKE_DAY', 'HASSOU_MONTH', 'HASSOU_DAY',
        'COURSE_1', 'C_1', 'S_1', 'UNIT_1', 'AMOUNT_1', 'HAGAKI_1',
        'COURSE_2', 'C_2', 'S_2', 'UNIT_2', 'AMOUNT_2', 'HAGAKI_2',
        'COURSE_3', 'C_3', 'S_3', 'UNIT_3', 'AMOUNT_3', 'HAGAKI_3',
        'COURSE_4', 'C_4', 'S_4', 'UNIT_4', 'AMOUNT_4', 'HAGAKI_4',
        'COURSE_5', 'C_5', 'S_5', 'UNIT_5', 'AMOUNT_5', 'HAGAKI_5',
        'C_TOTAL', 'S_TOTAL', 'AMOUNT_6',
        'C_TOTAL_D', 'S_TOTAL_D', 'AMOUNT_7',
        'SYSTEM_1', 'AMOUNT_8',
        'SYSTEM_2', 'AMOUNT_9',
        'SYSTEM_3', 'AMOUNT_10',
        'SYSTEM_4', 'UNIT_6', 'AMOUNT_11',
        'EMPTY', 'UNIT_7', 'AMOUNT_12',
        'CATALOG', 'AMOUNT_13',
        'AMOUNT_14', 'AMOUNT_15', 'AMOUNT_16',
        'NOTES_1',
        'SONOTA',
        'USE_MONTH', 'USE_DAY',
        'SIYOU_1', 'SIYOU_4',
        'CARD_1', 'CARD_2',
        'NAME_3', 'POSTCODE_3', 'ADDRESS_3', 'TEL_3', 'CC_1',
        'NAME_4', 'POSTCODE_4', 'ADDRESS_4', 'TEL_4', 'CC_2',
    ];

    textFields.forEach(function(id) {
        var el = document.getElementById(id);
        if (el && data[id] !== undefined) {
            el.value = data[id];
        }
    });

    // NOTES_2 (textarea)
    var notes2 = document.getElementById('NOTES_2');
    if (notes2 && data['NOTES_2'] !== undefined) {
        notes2.value = data['NOTES_2'];
    }

    // 체크박스
    var checkFields = [
        'REPORT_OK', 'REPORT_NO',
        'HANA', 'KET', 'SYUSSAN', 'KAIKI',
        'KOHAKU', 'MUJI', 'KUROSIRO',
        'REN_OK', 'REN_NO',
        'NOSI_UCHI', 'NOSI_SOTO',
        'SIYOU_2', 'SIYOU_2_2',
        'SIYOU_3', 'SIYOU_3_2',
    ];

    checkFields.forEach(function(id) {
        var el = document.getElementById(id);
        if (el && data[id] !== undefined) {
            el.checked = (data[id] === '✓' || data[id] === true || data[id] === '1');
        }
    });
}

function rerunOcr() {
    runOcr(true);
}

async function saveResult() {
    var ocrData = collectFormData();
    if (!seq || Object.keys(ocrData).length === 0) {
        alert('No data to save.');
        return;
    }

    try {
        var res = await fetch('/api/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ seq: seq, formid: formid, ocrData: ocrData })
        });
        var data = await res.json();
        if (data.resultCode === '200') {
            alert('Saved successfully.');
        } else {
            alert('Save failed: ' + data.resultMsg);
        }
    } catch (e) {
        alert('Save failed: ' + e.message);
    }
}

function collectFormData() {
    var data = {};
    document.querySelectorAll('.form-input').forEach(function(input) {
        if (input.id) data[input.id] = input.value;
    });
    document.querySelectorAll('input[type="hidden"]').forEach(function(input) {
        if (input.id) data[input.id] = input.value;
    });
    document.querySelectorAll('input[type="checkbox"]').forEach(function(cb) {
        if (cb.id) data[cb.id] = cb.checked ? '✓' : '';
    });
    var notes2 = document.getElementById('NOTES_2');
    if (notes2) data['NOTES_2'] = notes2.value;
    return data;
}

function clearForm() {
    document.querySelectorAll('.form-input').forEach(function(input) { input.value = ''; });
    document.querySelectorAll('input[type="checkbox"]').forEach(function(cb) { cb.checked = false; });
    var notes2 = document.getElementById('NOTES_2');
    if (notes2) notes2.value = '';
    lastOcrData = null;
}
