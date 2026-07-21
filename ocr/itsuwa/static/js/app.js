var params = new URLSearchParams(window.location.search);
var key = params.get('key');

var seq = null;
var formid = null;
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

    // OCR 결과 키가 대문자일 수 있으므로 소문자로 변환하여 매칭
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
    return data;
}

function clearForm() {
    document.querySelectorAll('.form-input').forEach(function(input) { input.value = ''; });
    lastOcrData = null;
}
