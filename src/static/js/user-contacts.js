// Contacts CRUD — same-origin fetch to /add-contact, /edit-contact/<id> (PUT),
// /delete-contact/<id> (DELETE). No CSRF tokens wired yet.

const contactsList = document.getElementById('contacts-list');
const addContactBtn = document.getElementById('add-contact-btn');
const contactModal = document.getElementById('contact-modal');
const contactForm = document.getElementById('contact-form');
const cancelContactBtn = document.getElementById('cancel-contact');
const deleteConfirmation = document.getElementById('delete-confirmation');
const cancelDeleteBtn = document.getElementById('cancel-delete');
const confirmDeleteBtn = document.getElementById('confirm-delete');
let currentContactId = null;

// --- Modal helpers ----------------------------------------------------------
function showModal(title) {
  document.getElementById('modal-title').textContent = title || 'Add contact';
  contactModal.classList.add('open');
}
function hideModal() {
  contactModal.classList.remove('open');
  contactForm.reset();
  currentContactId = null;
}
function hideDelete() {
  deleteConfirmation.classList.remove('open');
  currentContactId = null;
}

// --- Add --------------------------------------------------------------------
addContactBtn.addEventListener('click', function () {
  currentContactId = null;
  contactForm.reset();
  document.getElementById('contact-id').value = '';
  showModal('Add contact');
});
cancelContactBtn.addEventListener('click', hideModal);

// --- Submit (create or edit) ------------------------------------------------
contactForm.addEventListener('submit', function (e) {
  e.preventDefault();
  const formData = new FormData(contactForm);
  const url = currentContactId ? `/edit-contact/${currentContactId}` : '/add-contact';
  const method = currentContactId ? 'PUT' : 'POST';

  fetch(url, { method: method, body: formData })
    .then((r) => r.json())
    .then((data) => {
      if (!data.success) { showAlert(data.error || 'An error occurred', 'error'); return; }
      if (currentContactId) {
        const existing = contactsList.querySelector(`tr[data-contact-id="${currentContactId}"]`);
        if (existing) existing.replaceWith(createContactRow(data.contact));
        showAlert('Contact updated', 'success');
      } else {
        removeEmpty();
        contactsList.appendChild(createContactRow(data.contact));
        showAlert('Contact added', 'success');
      }
      hideModal();
    })
    .catch((err) => { console.error(err); showAlert('An error occurred', 'error'); });
});

// --- Edit / delete (delegated) ---------------------------------------------
contactsList.addEventListener('click', function (e) {
  const target = e.target;
  const row = target.closest('tr');
  if (!row) return;

  if (target.classList.contains('edit-contact')) {
    currentContactId = row.getAttribute('data-contact-id');
    document.getElementById('contact-id').value = currentContactId;
    document.getElementById('name').value = row.getAttribute('data-name') || '';
    document.getElementById('email').value = row.getAttribute('data-email') || '';
    document.getElementById('relationship').value = row.getAttribute('data-relationship') || '';
    document.getElementById('phone').value = row.getAttribute('data-phone') || '';
    document.getElementById('notes').value = row.getAttribute('data-notes') || '';
    showModal('Edit contact');
  } else if (target.classList.contains('delete-contact')) {
    currentContactId = row.getAttribute('data-contact-id');
    deleteConfirmation.classList.add('open');
  }
});

// --- Delete confirm ---------------------------------------------------------
confirmDeleteBtn.addEventListener('click', function () {
  if (!currentContactId) return;
  fetch(`/delete-contact/${currentContactId}`, { method: 'DELETE' })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        const row = contactsList.querySelector(`tr[data-contact-id="${currentContactId}"]`);
        if (row) row.remove();
        showAlert('Contact deleted', 'success');
      } else {
        showAlert(data.error || 'An error occurred', 'error');
      }
      hideDelete();
    })
    .catch((err) => { console.error(err); showAlert('An error occurred', 'error'); hideDelete(); });
});
cancelDeleteBtn.addEventListener('click', hideDelete);

// Close modals on backdrop click
window.addEventListener('click', function (e) {
  if (e.target === contactModal) hideModal();
  if (e.target === deleteConfirmation) hideDelete();
});

// --- Helpers ----------------------------------------------------------------
function removeEmpty() {
  const empty = document.getElementById('contacts-empty');
  if (empty) empty.remove();
}

function esc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function createContactRow(contact) {
  const tr = document.createElement('tr');
  tr.setAttribute('data-contact-id', contact.id);
  tr.setAttribute('data-name', contact.name || '');
  tr.setAttribute('data-email', contact.email || '');
  tr.setAttribute('data-relationship', contact.relationship || '');
  tr.setAttribute('data-phone', contact.phone || '');
  tr.setAttribute('data-notes', contact.notes || '');
  tr.innerHTML = `
    <td class="c-name">${esc(contact.name)}</td>
    <td class="c-email">${esc(contact.email)}</td>
    <td class="c-relationship">${esc(contact.relationship) || '—'}</td>
    <td class="c-phone">${esc(contact.phone) || '—'}</td>
    <td class="ops">
      <button type="button" class="op-btn edit-contact" data-contact-id="${contact.id}">Edit</button>
      <button type="button" class="op-btn delete-contact" data-contact-id="${contact.id}">Delete</button>
    </td>`;
  return tr;
}

// --- Alerts (self-contained toast) -----------------------------------------
function showAlert(message, type) {
  const el = document.createElement('div');
  el.textContent = message;
  el.style.cssText =
    'position:fixed;top:16px;right:16px;z-index:100;padding:12px 16px;border-radius:10px;' +
    'font-size:13.5px;font-weight:600;border:1px solid var(--line);background:var(--surface);' +
    'box-shadow:0 6px 20px -8px rgba(50,40,20,0.35);' +
    (type === 'error' ? 'color:var(--clay);border-left:3px solid var(--clay);'
                      : 'color:var(--ink-soft);border-left:3px solid var(--clay);');
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}
