// Password validation function
function validatePassword() {
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    // password requirements
    const passwordValid = password.length >= 8;
    const passwordsMatch = password === confirmPassword;

    updateRequirement('password-requirement', 'password-check', passwordValid);
    updateRequirement('confirm-requirement', 'confirm-check', passwordsMatch);

    return passwordValid && passwordsMatch;
}

// Update requirement status
function updateRequirement(requirementId, checkId, isValid) {
    const requirement = document.getElementById(requirementId);
    const check = document.getElementById(checkId);
    
    requirement.classList.toggle('text-green-500', isValid);
    requirement.classList.toggle('text-red-500', !isValid);
    
    const svgContent = isValid
        ? '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check-circle-fill" viewBox="0 0 16 16"><path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0m-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/></svg>'
        : '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-x-circle-fill" viewBox="0 0 16 16"><path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0M5.354 4.646a.5.5 0 1 0-.708.708L7.293 8l-2.647 2.646a.5.5 0 0 0 .708.708L8 8.707l2.646 2.647a.5.5 0 0 0 .708-.708L8.707 8l2.647-2.646a.5.5 0 0 0-.708-.708L8 7.293z"/></svg>';
    
    check.innerHTML = svgContent;
}

// Toggle password visibility
function togglePasswordVisibility(inputId, toggleId) {
    const input = document.getElementById(inputId);
    const toggle = document.getElementById(toggleId);
    
    if (input.type === 'password') {
        input.type = 'text';
        toggle.textContent = 'Hide';
    } else {
        input.type = 'password';
        toggle.textContent = 'Show';
    }
}

// Event listeners
document.getElementById('password').addEventListener('input', validatePassword);
document.getElementById('confirm-password').addEventListener('input', validatePassword);
document.getElementById('toggle-password').addEventListener('click', () => togglePasswordVisibility('password', 'toggle-password'));
document.getElementById('toggle-confirm-password').addEventListener('click', () => togglePasswordVisibility('confirm-password', 'toggle-confirm-password'));

// Prevent form submission if validation fails
document.querySelector('form').addEventListener('submit', function(event) {
    if (!validatePassword()) {
        event.preventDefault();
        alert('Please ensure all password requirements are met.');
    }
});

// Initial validation
validatePassword();