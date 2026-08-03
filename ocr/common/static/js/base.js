/* === Common Base JS === */

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

function parseOcrJson(ocrResult) {
    if (!ocrResult) return null;
    var text = typeof ocrResult === 'string' ? ocrResult : JSON.stringify(ocrResult);
    var match = text.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (match) text = match[1].trim();
    return JSON.parse(text);
}

function rerunOcr() {
    runOcr(true);
}

function collectFormData() {
    var data = {};
    document.querySelectorAll('.form-input').forEach(function(input) {
        if (input.id) data[input.id] = input.value;
    });
    document.querySelectorAll('input[type="checkbox"]').forEach(function(cb) {
        if (cb.id) data[cb.id] = cb.checked ? '✓' : '';
    });
    var memo = document.getElementById('MEMO');
    if (memo) data['MEMO'] = memo.value;
    return data;
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

function clearForm() {
    document.querySelectorAll('.form-input').forEach(function(input) { input.value = ''; });
    document.querySelectorAll('input[type="checkbox"]').forEach(function(cb) { cb.checked = false; });
    var memo = document.getElementById('MEMO');
    if (memo) memo.value = '';
    lastOcrData = null;
}
