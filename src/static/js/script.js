// Profile Dropdown
const profileButton = document.querySelector('.profile-button');
const profileDropdown = document.querySelector('.profile-dropdown');

profileDropdown.addEventListener('mouseleave', () => {
    profileDropdown.classList.remove('show');
    profileDropdown.classList.add('hide');

    setTimeout(() => {
        if (profileDropdown.classList.contains('hide')) {
            profileDropdown.style.display = 'none';
        }
    }, 500);
});

profileButton.addEventListener('mouseenter', () => {
    profileDropdown.style.display = 'block';
    profileDropdown.classList.remove('hide');
    profileDropdown.classList.add('show');
});