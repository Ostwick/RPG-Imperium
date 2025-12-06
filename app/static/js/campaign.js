// DICE SIMULATOR LOGIC

// 1. Database of Difficulty (Matches Python)
const DIFF_LEVELS = {
    1: 2, 2: 5, 3: 10, 4: 15, 5: 20
};

function updateSimulator() {
    // Get Inputs
    const actionSelect = document.getElementById('sim-action');
    const diffInput = document.getElementById('sim-difficulty');
    const attrInput = document.getElementById('sim-attribute-val');
    const resultSpan = document.getElementById('sim-result');

    if (!actionSelect || !diffInput || !attrInput || !resultSpan) return;

    const diffLevel = parseInt(diffInput.value);
    const charAttr = parseInt(attrInput.value) || 0;

    // Find selected option and its attributes
    let selectedOption = actionSelect.options[actionSelect.selectedIndex];
    // If you changed selection programmatically by setting a key elsewhere,
    // selectedOption may be null — try to find by value or data-attr-key
    if (!selectedOption) {
        selectedOption = actionSelect.querySelector('option[selected]') || actionSelect.querySelector('option');
    }

    // raw key and translated label
    const relatedAttrKey = selectedOption ? (selectedOption.getAttribute('data-attr-key') || selectedOption.value) : null;
    const relatedAttrLabel = selectedOption ? selectedOption.getAttribute('data-attr') : null;

    // Update visible translated attribute label
    const attrLabel = document.getElementById('sim-related-attr');
    if (attrLabel) {
        if (relatedAttrLabel) {
            attrLabel.innerText = relatedAttrLabel;
        } else if (relatedAttrKey) {
            // attempt to locate an option that carries the translated label
            const match = actionSelect.querySelector(`option[data-attr-key="${relatedAttrKey}"]`);
            if (match && match.getAttribute('data-attr')) {
                attrLabel.innerText = match.getAttribute('data-attr');
            } else {
                // fallback to raw key (last resort)
                attrLabel.innerText = relatedAttrKey;
            }
        } else {
            attrLabel.innerText = '';
        }
    }

    // rest of simulator logic (no change)...
    const baseDC = DIFF_LEVELS[diffLevel] || 10;
    const baseDCDisplay = document.getElementById('display-base-dc');
    if (baseDCDisplay) baseDCDisplay.innerText = baseDC;

    const reduction = Math.floor(charAttr / 2);
    const reductionDisplay = document.getElementById('display-reduction');
    if (reductionDisplay) reductionDisplay.innerText = reduction;

    let finalDC = baseDC - reduction;
    if (finalDC < 2) finalDC = 2;
    resultSpan.innerText = finalDC + "+";

    if (finalDC <= 5) resultSpan.style.color = "green";
    else if (finalDC <= 10) resultSpan.style.color = "#c5a004";
    else if (finalDC <= 15) resultSpan.style.color = "orange";
    else resultSpan.style.color = "red";
}

// --- INITIALIZE ON LOAD ---
document.addEventListener("DOMContentLoaded", function() {
    // Run simulator once to set initial values
    if (document.getElementById('sim-action')) {
        updateSimulator();
    }
});

// --- HELPER FUNCTIONS FOR MODALS ---
// (Keep these here so they are available globally)

function openTransfer(charId, charName, direction) {
    document.getElementById('transferModal').style.display = 'block';
    document.getElementById('transferCharId').value = charId;
    
    const title = document.getElementById('transferTitle');
    const desc = document.getElementById('transferDesc');
    const dirInput = document.getElementById('transferDirection');
    
    if (direction === 'in') {
        title.innerText = "Collect Taxes / Fees";
        desc.innerText = `Take gold FROM ${charName} to Party Treasury.`;
        dirInput.value = "1"; 
    } else {
        title.innerText = "Distribute Loot";
        desc.innerText = `Give gold TO ${charName} from Treasury.`;
        dirInput.value = "-1"; 
    }
}

function submitTransfer() {
    const form = document.querySelector('#transferModal form');
    const raw = document.getElementById('transferAmount').value;
    const dir = document.getElementById('transferDirection').value;
    
    // Create hidden input for final amount
    const finalAmount = parseInt(raw) * parseInt(dir);
    const hiddenAmt = document.createElement('input');
    hiddenAmt.type = 'hidden';
    hiddenAmt.name = 'amount';
    hiddenAmt.value = finalAmount;
    form.appendChild(hiddenAmt);
    
    document.getElementById('transferAmount').removeAttribute('name');
    form.submit();
}

function openPinModal(event) {
    const mapImg = document.getElementById('campaign-map');
    const modal = document.getElementById('pinModal');
    const inputX = document.getElementById('pinX');
    const inputY = document.getElementById('pinY');

    const rect = mapImg.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    const xPercent = (x / rect.width) * 100;
    const yPercent = (y / rect.height) * 100;

    inputX.value = xPercent.toFixed(2);
    inputY.value = yPercent.toFixed(2);
    
    modal.style.display = 'block';
    modal.querySelector('input[name="label"]').focus();
}

function openCampaignBio(name, bioText) {
    document.getElementById('campBioTitle').innerText = name;
    document.getElementById('campBioContent').innerText = bioText;
    document.getElementById('campBioModal').style.display = 'block';
}

function duplicateEnemySelect() {
    const container = document.getElementById('enemy-container');
    const select = container.querySelector('select').cloneNode(true);
    container.appendChild(select);
}