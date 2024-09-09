const contactsList = document.getElementById('contacts-list');
const addContactBtn = document.getElementById('add-contact-btn');
const contactModal = document.getElementById('contact-modal');
const contactForm = document.getElementById('contact-form');
const cancelContactBtn = document.getElementById('cancel-contact');
const deleteConfirmation = document.getElementById('delete-confirmation');
const cancelDeleteBtn = document.getElementById('cancel-delete');
const confirmDeleteBtn = document.getElementById('confirm-delete');
let currentContactId = null;



// ADD CONTACTS

// Add contact -> show modal
addContactBtn.addEventListener('click', () => {
    showModal('Add Contact');
});

// Show modal
function showModal(title = 'Add Contact') {
    document.getElementById('modal-title').textContent = title;
    contactModal.classList.remove('hidden');
    contactModal.classList.add('flex');
}

// Cancel contact -> hide modal
cancelContactBtn.addEventListener('click', hideModal);

// Hide modal
function hideModal() {
    contactModal.classList.add('hidden');
    contactModal.classList.remove('flex');
    contactForm.reset();
}


// submit contacts modal form
contactForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const formData = new FormData(contactForm);

    // if modal appears with selected contact, then it's an edit
    const url = currentContactId ? `/edit-contact/${currentContactId}` : '/add-contact';
    const method = currentContactId ? 'PUT' : 'POST';

    // For PUT requests, we need to explicitly set the method as PUT
    const fetchOptions = {
        method: method,
        body: formData,
    };

    // if (method === 'PUT') {
    //     fetchOptions.headers = {
    //         'X-HTTP-Method-Override': 'PUT'
    //     };
    // }

    fetch(url, fetchOptions)
        .then(response => response.json())
        .then(data => {
            // if request is succesful
            if (data.success) {
                hideModal();
                console.log(currentContactId);
                if (currentContactId) {
                    console.log('Edit:', data.contact);
                    // An edit; update the contact in the contact list
                    const existingRow = contactsList.querySelector(`[data-contact-id="${currentContactId}"]`).closest('tr');
                    console.log('existingRow:', existingRow);
                    existingRow.replaceWith(createContactRow(data.contact));
                    showAlert('Contact updated successfully', 'success');
                    // unselect the current contact
                    currentContactId = null;
                } else {
                    // Add new contact to the list
                    contactsList.appendChild(createContactRow(data.contact));
                    showAlert('Contact added successfully', 'success');
                }
            } else {
                showAlert(data.error || 'An error occurred', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('An error occurred', 'error');
        });
});



// EDIT CONTACTS

// Edit and delete contact for each contact
contactsList.addEventListener('click', (e) => {
    // click on edit contact
    if (e.target.classList.contains('edit-contact')) {
        // fetch the current row
        const contactRow = e.target.closest('tr');
        const contactId = e.target.getAttribute('data-contact-id');
        currentContactId = contactId;

        console.log('Edit:', contactId);

        // Populate the form with data from the selected row
        const [name, email, relationship, phone] = contactRow.querySelectorAll('td');
        document.getElementById('name').value = name.textContent.trim();
        document.getElementById('email').value = email.textContent.trim();
        document.getElementById('relationship').value = relationship.textContent.trim() !== 'N/A' ? relationship.textContent.trim() : '';
        document.getElementById('phone').value = phone.textContent.trim() !== 'N/A' ? phone.textContent.trim() : '';

        // Note: We don't have the 'notes' field in the table, so it will be left blank when editing
        document.getElementById('notes').value = '';

        showModal('Edit Contact');
    // click on delete contact
    } else if (e.target.classList.contains('delete-contact')) {
        // set the modal to be deleted
        currentContactId = e.target.getAttribute('data-contact-id');
        // show delete-confirmation modal
        deleteConfirmation.classList.remove('hidden');
        deleteConfirmation.classList.add('flex');
    }
});

// DELETE CONTACTS


// Confirm delete
confirmDeleteBtn.addEventListener('click', () => {
    if (currentContactId) {
        fetch(`/delete-contact/${currentContactId}`, { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    deleteConfirmation.classList.add('hidden');
                    deleteConfirmation.classList.remove('flex');
                    const contactRow = contactsList.querySelector(`[data-contact-id="${currentContactId}"]`).closest('tr');
                    contactRow.remove();
                    currentContactId = null;
                    showAlert('Contact deleted successfully', 'success');
                } else {
                    showAlert(data.error || 'An error occurred while deleting the contact', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('An error occurred while deleting the contact', 'error');
            });
    }
});

// Cancel delete
cancelDeleteBtn.addEventListener('click', () => {
    deleteConfirmation.classList.add('hidden');
    deleteConfirmation.classList.remove('flex');
    currentContactId = null;
});


// HELPER FUNCTIONS

// Create contact row
function createContactRow(contact) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td class="px-6 py-4 whitespace-nowrap">${contact.name}</td>
        <td class="px-6 py-4 whitespace-nowrap">${contact.email}</td>
        <td class="px-6 py-4 whitespace-nowrap">${contact.relationship || 'N/A'}</td>
        <td class="px-6 py-4 whitespace-nowrap">${contact.phone || 'N/A'}</td>
        <td class="text-right px-6 whitespace-nowrap">
            <button class="edit-contact py-2 px-3 font-medium text-primary-600 hover:text-primary-500 duration-150 hover:bg-gray-50 rounded-lg" data-contact-id="${contact.id}">
                Edit
            </button>
            <button class="delete-contact py-2 leading-none px-3 font-medium text-red-600 hover:text-red-500 duration-150 hover:bg-gray-50 rounded-lg" data-contact-id="${contact.id}">
                Delete
            </button>
        </td>
    `;
    return tr;
}

// Close modals when clicking outside
window.addEventListener('click', (e) => {
    if (e.target === contactModal) {
        hideModal();
    }
    if (e.target === deleteConfirmation) {
        deleteConfirmation.classList.add('hidden');
        deleteConfirmation.classList.remove('flex');
        currentContactId = null;
    }
});

// ALERTS
function showAlert(message, type = 'success') {
    const alertContainer = document.createElement('div');
    alertContainer.className = 'fixed top-4 right-4 z-50';
    alertContainer.innerHTML = `
    <div class="flex rounded-md ${type === 'success' ? 'bg-green-50 text-green-500' : 'bg-primary-50 text-primary-500'} p-4 text-sm">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="mr-3 h-5 w-5 flex-shrink-0">
            <path fill-rule="evenodd" d="${type === 'success' ? 'M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z' : 'M19 10.5a8.5 8.5 0 11-17 0 8.5 8.5 0 0117 0zM8.25 9.75A.75.75 0 019 9h.253a1.75 1.75 0 011.709 2.13l-.46 2.066a.25.25 0 00.245.304H11a.75.75 0 010 1.5h-.253a1.75 1.75 0 01-1.709-2.13l.46-2.066a.25.25 0 00-.245-.304H9a.75.75 0 01-.75-.75zM10 7a1 1 0 100-2 1 1 0 000 2z'}" clip-rule="evenodd" />
        </svg>
        <div>
            <h4 class="font-bold">${type === 'success' ? 'Success' : 'Info'}</h4>
            <div class="mt-1">${message}</div>
        </div>
        <button class="ml-auto close-alert">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-5 w-5">
                <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
        </button>
    </div>
`;

    document.body.appendChild(alertContainer);

    const closeButton = alertContainer.querySelector('.close-alert');
    closeButton.addEventListener('click', () => {
        alertContainer.remove();
    });

    setTimeout(() => {
        alertContainer.remove();
    }, 5000);
}

