/* ThermoFisher-specific (base.js handles common functions) */

// Override loadImage for page navigation
function loadImage(page) {
    var img = document.getElementById('docImage');
    img.src = '/api/image?seq=' + seq + '&idx=' + page;
    document.getElementById('pageInfo').textContent = page + ' / ' + totalPages;
    document.getElementById('prevBtn').disabled = (currentPage === 0);
    document.getElementById('nextBtn').disabled = (currentPage >= totalPages - 1);
}

function changePage(delta) {
    currentPage = Math.max(0, Math.min(totalPages - 1, currentPage + delta));
    loadImage(currentPage + 1);
}

function fillForm(ocrResult) {
    var data = parseOcrJson(ocrResult);
    if (!data) return;
    lastOcrData = data;

    for (var fieldId in data) {
        var el = document.getElementById(fieldId);
        if (el) {
            if (el.type === 'checkbox') {
                el.checked = (data[fieldId] !== '' && data[fieldId] !== null);
            } else {
                el.value = data[fieldId];
            }
        }
    }
}
