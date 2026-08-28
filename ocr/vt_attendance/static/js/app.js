/* VT Attendance: fillForm only — 손글씨 기입 그리드(A_1~F_6)만 인식 대상 */

function fillForm(ocrResult) {
    var data = parseOcrJson(ocrResult);
    if (!data) return;
    lastOcrData = data;

    for (var r = 1; r <= 6; r++) {
        for (var c = 0; c < 6; c++) {
            var id = 'ABCDEF'[c] + '_' + r;
            var el = document.getElementById(id);
            if (el && data[id] !== undefined) el.value = data[id];
        }
    }
}
