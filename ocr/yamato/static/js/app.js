/* Yamato-specific: fillForm only (base.js handles common functions) */

function fillForm(ocrResult) {
    var data = parseOcrJson(ocrResult);
    if (!data) return;
    lastOcrData = data;

    // text fields
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
        'NOTES_1', 'NOTES_2',
        'SONOTA',
        'USE_MONTH', 'USE_DAY',
        'SIYOU_1', 'SIYOU_4',
        'CARD_1', 'CARD_2',
        'NAME_3', 'POSTCODE_3', 'ADDRESS_3', 'TEL_3', 'CC_1',
        'NAME_4', 'POSTCODE_4', 'ADDRESS_4', 'TEL_4', 'CC_2',
    ];

    textFields.forEach(function(id) {
        var el = document.getElementById(id);
        if (el && data[id] !== undefined) el.value = data[id];
    });

    // checkboxes
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
