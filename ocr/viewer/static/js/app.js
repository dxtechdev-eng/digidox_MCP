var params = new URLSearchParams(window.location.search);
var key = params.get('key');

var seq = null;
var formid = null;
var formWidth = 700;
var formHeight = 990;
var fieldPositions = {};
var userEdits = {};      // 서버 보관된 사용자 수정본 (OCR이 덮지 못함)
var dirtyFields = {};    // 이번 세션에서 손댄 필드

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

// URL 파라미터 직접 지원
if (!seq) seq = params.get('seq');
if (!formid) formid = params.get('formid');

window.addEventListener('DOMContentLoaded', function() {
    if (seq) {
        document.getElementById('docInfo').textContent = 'seq: ' + seq + (formid ? ' | formid: ' + formid : '');
        loadImage(1);
        if (formid) {
            loadFields().then(function() { runOcr(false); });
        } else {
            runOcr(false);
        }
    } else {
        document.getElementById('docInfo').textContent = 'seq parameter missing';
    }
});

function loadImage(page) {
    var img = document.getElementById('docImage');
    img.src = '/api/image?seq=' + seq + '&idx=' + page;
    img.onload = function() {
        renderOverlays();
    };
}

async function loadFields() {
    try {
        var res = await fetch('/api/fields?formid=' + formid + '&page=1');
        var data = await res.json();
        if (data.resultCode === '200') {
            fieldPositions = data.fields || {};
            formWidth = data.formWidth || 700;
            formHeight = data.formHeight || 990;
        }
    } catch (e) {
        console.error('Fields load failed:', e);
    }
}

async function runOcr(force) {
    if (!seq) return;
    var overlay = document.getElementById('loadingOverlay');
    overlay.classList.add('active');

    try {
        var url = '/api/ocr?seq=' + seq;
        if (formid) url += '&formid=' + formid;
        if (force) url += '&force=true';
        var res = await fetch(url);
        var data = await res.json();

        if (data.resultCode === '200') {
            userEdits = data.edits || {};
            applyOcrResult(data.ocrResult);
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

function applyOcrResult(ocrResult) {
    if (!ocrResult) return;

    var data = null;
    try {
        var text = typeof ocrResult === 'string' ? ocrResult : JSON.stringify(ocrResult);
        var match = text.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (match) text = match[1].trim();
        data = JSON.parse(text);
        console.log('OCR parsed:', data);
    } catch (e) {
        console.error('OCR JSON parse failed:', e);
        return;
    }

    // OCR 결과를 fieldPositions에 병합
    window._ocrData = data;
    renderOverlays();
}

function renderOverlays() {
    var layer = document.getElementById('overlayLayer');
    var img = document.getElementById('docImage');
    layer.innerHTML = '';

    if (!img.naturalWidth || !window._ocrData) return;

    var imgW = img.clientWidth;
    var imgH = img.clientHeight;
    var scaleX = imgW / formWidth;
    var scaleY = imgH / formHeight;

    var data = window._ocrData;

    for (var fid in fieldPositions) {
        var info = fieldPositions[fid];
        if (!info.top && info.top !== 0) continue;
        if (!info.left && info.left !== 0) continue;

        var value = data[fid] !== undefined ? data[fid] : '';
        var edited = false;
        if (dirtyFields[fid] !== undefined) { value = dirtyFields[fid]; edited = true; }
        else if (userEdits[fid] !== undefined) { value = userEdits[fid]; edited = true; }

        var div = document.createElement('div');
        div.className = 'ocr-overlay';
        div.style.top = (info.top * scaleY) + 'px';
        div.style.left = (info.left * scaleX) + 'px';
        div.style.width = ((info.width || 50) * scaleX) + 'px';
        div.style.height = ((info.height || 20) * scaleY) + 'px';

        var input = document.createElement('input');
        input.type = 'text';
        input.value = value;
        input.id = 'field_' + fid;
        input.title = fid + (edited ? ' (수정됨 — OCR이 덮어쓰지 않음)' : '');
        if (edited) input.classList.add('user-edited');
        input.addEventListener('change', (function(f) {
            return function(ev) {
                dirtyFields[f] = ev.target.value;
                ev.target.classList.add('user-edited');
            };
        })(fid));
        div.appendChild(input);

        layer.appendChild(div);
    }
}

function rerunOcr() {
    runOcr(true);
}

async function saveResult() {
    var ocrData = {};
    document.querySelectorAll('#overlayLayer input').forEach(function(input) {
        if (input.id && input.id.indexOf('field_') === 0) {
            ocrData[input.id.substring(6)] = input.value;
        }
    });
    if (!seq || Object.keys(ocrData).length === 0) { alert('저장할 내용이 없습니다.'); return; }
    try {
        var res = await fetch('/api/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ seq: seq, formid: formid, ocrData: ocrData, editedFields: dirtyFields })
        });
        var data = await res.json();
        if (data.resultCode === '200') {
            Object.assign(userEdits, dirtyFields);
            dirtyFields = {};
            alert('저장되었습니다. (보호 필드 ' + (data.protectedFields || 0) + '개)');
        } else {
            alert('저장 실패: ' + data.resultMsg);
        }
    } catch (e) { alert('저장 실패: ' + e.message); }
}

function clearOverlays() {
    var layer = document.getElementById('overlayLayer');
    layer.innerHTML = '';
    window._ocrData = null;
}

// 창 리사이즈 시 오버레이 재배치
window.addEventListener('resize', function() {
    renderOverlays();
});
