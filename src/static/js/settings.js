// Settings page — chips, pause auto-submit, and the memory trust surface.
// All calls are same-origin; no CSRF tokens are wired yet.

document.addEventListener('DOMContentLoaded', function () {
  // --- Choice chips (daily check-in + frequency) -> hidden inputs -----------
  document.querySelectorAll('[data-chip-group]').forEach(function (group) {
    var name = group.getAttribute('data-chip-group');
    var hidden = document.getElementById(name);
    group.querySelectorAll('.chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        group.querySelectorAll('.chip').forEach(function (c) { c.classList.remove('is-selected'); });
        chip.classList.add('is-selected');
        if (hidden) hidden.value = chip.getAttribute('data-value');
      });
    });
  });

  // --- Quiet-hours bar: draw the dark segment(s) from the actual inputs ----
  var quietStart = document.getElementById('quiet_start');
  var quietEnd = document.getElementById('quiet_end');
  var quietBar = document.getElementById('quiet-bar');
  function drawQuietBar() {
    if (!quietBar) return;
    quietBar.innerHTML = '';
    function pct(value) {
      var m = /^(\d{1,2}):(\d{2})$/.exec(value || '');
      if (!m) return null;
      return ((+m[1] * 60 + +m[2]) / 1440) * 100;
    }
    var start = pct(quietStart && quietStart.value);
    var end = pct(quietEnd && quietEnd.value);
    if (start == null || end == null || start === end) return;
    function seg(left, width, radius) {
      var s = document.createElement('span');
      s.className = 'seg';
      s.style.left = left + '%';
      s.style.width = width + '%';
      if (radius) s.style.borderRadius = radius;
      quietBar.appendChild(s);
    }
    if (start < end) {
      seg(start, end - start, '8px');
    } else {
      // overnight window: start→midnight + midnight→end
      seg(start, 100 - start, '0 8px 8px 0');
      seg(0, end, '8px 0 0 8px');
    }
  }
  if (quietBar) {
    drawQuietBar();
    [quietStart, quietEnd].forEach(function (el) {
      if (el) el.addEventListener('input', drawQuietBar);
    });
  }

  // --- Pause everything: auto-submit the proactive form on toggle ----------
  var pause = document.getElementById('paused-toggle');
  var proactiveForm = document.getElementById('proactive-form');
  if (pause && proactiveForm) {
    pause.addEventListener('change', function () { proactiveForm.submit(); });
  }

  // --- Memory surface ------------------------------------------------------
  var card = document.getElementById('memory-card');
  var list = document.getElementById('mem-list');
  var countEl = document.getElementById('mem-count');
  if (!card || !list) return;

  function updateCount() {
    var n = list.querySelectorAll('.memory-row').length;
    if (countEl) countEl.textContent = n;
  }

  function clearEmpty() {
    var empty = document.getElementById('mem-empty');
    if (empty) empty.remove();
  }

  function makeRow(type, id, content) {
    var row = document.createElement('div');
    row.className = 'memory-row';
    row.setAttribute('data-type', type);
    row.setAttribute('data-id', id);
    var span = document.createElement('span');
    span.className = 'content';
    span.textContent = content;
    row.appendChild(span);
    if (type === 'fact') {
      var edit = document.createElement('button');
      edit.type = 'button';
      edit.className = 'op edit';
      edit.textContent = 'edit';
      row.appendChild(edit);
    }
    var forget = document.createElement('button');
    forget.type = 'button';
    forget.className = 'op forget';
    forget.textContent = 'forget';
    row.appendChild(forget);
    return row;
  }

  // Delegated clicks: forget + edit
  list.addEventListener('click', function (e) {
    var target = e.target;
    var row = target.closest('.memory-row');
    if (!row) return;
    var type = row.getAttribute('data-type');
    var id = row.getAttribute('data-id');

    // Forget
    if (target.classList.contains('forget')) {
      var url = type === 'fact' ? '/settings/fact/' + id : '/settings/memory/' + id;
      fetch(url, { method: 'DELETE' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.success) { row.remove(); updateCount(); }
        })
        .catch(function (err) { console.error(err); });
      return;
    }

    // Edit (facts only)
    if (target.classList.contains('edit') && type === 'fact') {
      startEdit(row, id);
    }
  });

  function startEdit(row, id) {
    var span = row.querySelector('.content');
    var current = span.textContent;
    var wrap = document.createElement('span');
    wrap.className = 'content';
    var input = document.createElement('input');
    input.type = 'text';
    input.value = current;
    input.maxLength = 300;
    wrap.appendChild(input);

    var save = document.createElement('button');
    save.type = 'button';
    save.className = 'op edit';
    save.textContent = 'save';
    var cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'op forget';
    cancel.textContent = 'cancel';

    row.innerHTML = '';
    row.appendChild(wrap);
    row.appendChild(save);
    row.appendChild(cancel);
    input.focus();

    function restore(content) {
      var fresh = makeRow('fact', id, content);
      row.replaceWith(fresh);
    }

    cancel.addEventListener('click', function () { restore(current); });
    save.addEventListener('click', function () {
      var value = input.value.trim();
      if (!value) { restore(current); return; }
      var body = new FormData();
      body.append('content', value);
      fetch('/settings/fact/' + id, { method: 'PUT', body: body })
        .then(function (r) { return r.json(); })
        .then(function (data) { restore(data.success ? data.content : current); })
        .catch(function (err) { console.error(err); restore(current); });
    });
  }

  // Add something
  var addInput = document.getElementById('mem-add-input');
  var addBtn = document.getElementById('mem-add-btn');
  function submitAdd() {
    var value = addInput.value.trim();
    if (!value) return;
    var body = new FormData();
    body.append('content', value);
    fetch(card.getAttribute('data-add-url'), { method: 'POST', body: body })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          clearEmpty();
          list.insertBefore(makeRow('fact', data.id, data.content), list.firstChild);
          addInput.value = '';
          updateCount();
        }
      })
      .catch(function (err) { console.error(err); });
  }
  if (addBtn) addBtn.addEventListener('click', submitAdd);
  if (addInput) addInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); submitAdd(); }
  });

  // Forget everything
  var forgetAll = document.getElementById('forget-all');
  if (forgetAll) {
    forgetAll.addEventListener('click', function () {
      if (!confirm('Forget everything? This is instant and permanent.')) return;
      fetch(card.getAttribute('data-forget-all-url'), { method: 'POST' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.success) {
            list.querySelectorAll('.memory-row').forEach(function (row) { row.remove(); });
            updateCount();
          }
        })
        .catch(function (err) { console.error(err); });
    });
  }
});
