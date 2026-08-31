/* VT Supermarket: fillForm only — DigiDox 등록 필드ID(예: CARD_NUM, PRODUCT_CODE1, SIZE7)와 input id가 1:1 */

function fillForm(ocrResult) {
    var data = parseOcrJson(ocrResult);
    if (!data) return;
    lastOcrData = data;
    Object.keys(data).forEach(function(id) {
        var el = document.getElementById(id);
        if (el && el.classList.contains('form-input')) el.value = data[id] == null ? '' : data[id];
    });
}
