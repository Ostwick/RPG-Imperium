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

    // Safety check: if core inputs are missing, stop to prevent crash
    if (!actionSelect || !diffInput || !attrInput || !resultSpan) {
        return;
    }

    const diffLevel = parseInt(diffInput.value);
    const charAttr = parseInt(attrInput.value) || 0;
    
    // 1. Auto-select Attribute name based on Action
    const selectedOption = actionSelect.options[actionSelect.selectedIndex];
    const relatedAttr = selectedOption.getAttribute('data-attr');
    
    const attrLabel = document.getElementById('sim-related-attr');
    if (attrLabel) {
        // Only overwrite the label if the option provides a translated attribute string.
        // The small element's initial content is rendered server-side and already localized.
        if (relatedAttr) attrLabel.innerText = relatedAttr;
    }

    // 2. Calculate Base Difficulty
    const baseDC = DIFF_LEVELS[diffLevel] || 10;
    
    // Update Base DC text (only if the element exists in HTML)
    const baseDCDisplay = document.getElementById('display-base-dc');
    if (baseDCDisplay) {
        baseDCDisplay.innerText = baseDC;
    }

    // 3. Calculate Bonus (Attr / 2)
    const reduction = Math.floor(charAttr / 2);
    
    // Update Reduction text (only if the element exists in HTML)
    const reductionDisplay = document.getElementById('display-reduction');
    if (reductionDisplay) {
        reductionDisplay.innerText = reduction;
    }

    // 4. Calculate Final Target
    let finalDC = baseDC - reduction;
    
    // Rule: Min 2 (Natural 1 always fails)
    if (finalDC < 2) finalDC = 2;

    resultSpan.innerText = finalDC + "+";

    // Visual Feedback
    if (finalDC <= 5) resultSpan.style.color = "green";
    else if (finalDC <= 10) resultSpan.style.color = "#c5a004"; // gold
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