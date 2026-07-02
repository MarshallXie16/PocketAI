// get DOM elements
const dropdownButtons = document.querySelectorAll('[data-dropdown-button]');
const dropdownPanels = document.querySelectorAll('[data-dropdown-panel]');
const createAIForm = document.getElementById('ai-settings-form');
const profileImageInput = document.getElementById('profile-image-input');
const profileImagePreview = document.getElementById('profile-image-preview');

// show dropdown panel on button click
dropdownButtons.forEach(button => {
    button.addEventListener('click', () => {
        const panel = document.querySelector(`[data-dropdown-panel="${button.getAttribute('data-dropdown-button')}"]`);
        panel.classList.toggle('hidden');
    });
});

// select dropdown option
dropdownPanels.forEach(panel => {
    const options = panel.querySelectorAll('[data-dropdown-option]');
    options.forEach(option => {
        option.addEventListener('click', (e) => {
            e.preventDefault();
            const button = document.querySelector(`[data-dropdown-button="${panel.getAttribute('data-dropdown-panel')}"]`);
            button.textContent = option.textContent;
            document.querySelector(`[name="${panel.getAttribute('data-dropdown-panel')}"]`).value = option.textContent;
            panel.classList.add('hidden');
        });
    });
});

// close dropdown panel on outside click
document.addEventListener('click', (e) => {
    if (!e.target.closest('[data-dropdown-button]') && !e.target.closest('[data-dropdown-panel]')) {
        dropdownPanels.forEach(panel => panel.classList.add('hidden'));
    }
});

// sets profile picture and displays preview picture
profileImageInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            profileImagePreview.src = e.target.result;
        };
        reader.readAsDataURL(file);
    }
});

// Voice Settings Dropdown
const voiceSettingsHeader = document.getElementById('voice-settings-header');
const voiceSettingsContent = document.getElementById('voice-settings-content');
const dropdownArrow = voiceSettingsHeader.querySelector('#voice-settings-header-wrapper > svg');

// replace the voice settings click handler
voiceSettingsHeader.addEventListener('click', () => {
    // Toggle the content visibility
    voiceSettingsContent.classList.toggle('active');

    // Rotate the arrow
    dropdownArrow.classList.toggle('rotate-180');

    // If we're showing the content, we need to explicitly set max-height
    if (voiceSettingsContent.classList.contains('active')) {
        // Use scrollHeight to get the actual height needed
        voiceSettingsContent.style.maxHeight = "1000px";
    } else {
        voiceSettingsContent.style.maxHeight = "0px";
    }
});