// DICE SIMULATOR LOGIC

// 1. Database of Difficulty (Matches Python)
const DIFF_LEVELS = {
    1: 2, 2: 5, 3: 10, 4: 15, 5: 20
};

function updateSimulator() {
    // Get Inputs
    const actionSelect = document.getElementById('sim-action');
    const diffLevel = parseInt(document.getElementById('sim-difficulty').value);
    const charAttr = parseInt(document.getElementById('sim-attribute-val').value) || 0;
    
    // 1. Auto-select Attribute name based on Action
    const selectedOption = actionSelect.options[actionSelect.selectedIndex];
    const relatedAttr = selectedOption.getAttribute('data-attr');
    document.getElementById('sim-related-attr').innerText = relatedAttr || "Attribute";

    // 2. Calculate Base Difficulty
    const baseDC = DIFF_LEVELS[diffLevel] || 10;
    document.getElementById('display-base-dc').innerText = baseDC;

    // 3. Calculate Bonus (Attr / 2)
    // Note: In typical d20, it's floor((Attr - 10) / 2), but your rule is specific: Attr / 2.
    // Assuming integer division (floor).
    const reduction = Math.floor(charAttr / 2);
    document.getElementById('display-reduction').innerText = reduction;

    // 4. Calculate Final Target
    let finalDC = baseDC - reduction;
    
    // Rule: Min 2
    if (finalDC < 2) finalDC = 2;

    const resultSpan = document.getElementById('sim-result');
    resultSpan.innerText = finalDC + "+";

    // Visual Feedback
    if (finalDC <= 5) resultSpan.style.color = "green";
    else if (finalDC <= 10) resultSpan.style.color = "#c5a004"; // gold
    else if (finalDC <= 15) resultSpan.style.color = "orange";
    else resultSpan.style.color = "red";
}