/* ==========================================================================
   PocketAI — chat surface
   Vanilla JS for the message-first chat UI. Preserves the server fetch
   contracts exactly:
     POST /send_message        {message, modelId}        -> {response, voice_url, timestamp, ai_message_id}
     POST /regenerate_message  {ai_message_id, user_message, modelId} -> {response, timestamp, ai_message_id, deleted_ids}
     PUT  /edit_message        {message_id, new_content}
     POST /load-more-messages  {current_message_count}
     POST /transcribe          multipart 'audio' (clip.webm) -> {text}
   ========================================================================== */
(function () {
  'use strict';

  const app = document.querySelector('.chat-app');
  if (!app) return;

  const MODEL_ID = app.dataset.selectedModel;
  const SETTINGS_URL = app.dataset.settingsUrl || '#';

  const messageArea = document.getElementById('message-area');
  const input = document.getElementById('composer-input');
  const sendBtn = document.getElementById('send-btn');
  const micBtn = document.getElementById('mic-btn');
  const micTimer = document.getElementById('mic-timer');
  const voiceHint = document.getElementById('voice-hint');
  const notice = document.getElementById('composer-notice');

  const ERROR_TEXT = {
    INSUFFICIENT_CREDITS: "You're out of credits. Add more to keep chatting.",
    MODEL_NOT_FOUND: "That companion no longer exists.",
    ACCESS_DENIED: "You don't have access to this companion.",
    BAD_REQUEST: "Something was off with that request. Try again.",
    DEFAULT: "Something went wrong. Please try again.",
  };

  // ---- utilities ---------------------------------------------------------

  function showNotice(text) {
    if (!notice) return;
    notice.textContent = text;
    notice.hidden = false;
    clearTimeout(showNotice._t);
    showNotice._t = setTimeout(() => { notice.hidden = true; }, 6000);
  }

  function esc(str) {
    const d = document.createElement('div');
    d.textContent = str == null ? '' : String(str);
    return d.innerHTML;
  }

  function scrollToBottom() {
    messageArea.scrollTop = messageArea.scrollHeight;
  }

  function autoGrow(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }

  // ---- timestamp formatting ----------------------------------------------

  function parseUTC(ts) {
    // DB timestamps are naive UTC ("YYYY-MM-DD HH:MM:SS").
    return new Date(ts.replace(' ', 'T') + 'Z');
  }

  function formatTime(date) {
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  }

  function formatDateLabel(date) {
    const now = new Date();
    const startOf = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const diffDays = Math.round((startOf(now) - startOf(date)) / 86400000);
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric' });
  }

  function relabelDividers() {
    messageArea.querySelectorAll('.date-divider[data-date]').forEach((el) => {
      const d = parseUTC(el.dataset.date);
      if (!isNaN(d)) el.textContent = formatDateLabel(d);
    });
  }

  function relabelReachedOut() {
    messageArea.querySelectorAll('.reached-out-time[data-timestamp]').forEach((el) => {
      if (el.dataset.done) return;
      const d = parseUTC(el.dataset.timestamp);
      if (!isNaN(d)) { el.textContent = '— ' + formatTime(d); el.dataset.done = '1'; }
    });
  }

  // ---- rendering ---------------------------------------------------------

  function userBubbleHTML(text, id) {
    return (
      '<div class="msg msg-user"' + (id != null ? ' data-message-id="' + id + '"' : '') + '>' +
        '<div class="bubble-user">' + esc(text) + '</div>' +
        '<div class="msg-actions">' +
          '<button type="button" class="msg-action" data-action="edit">Edit</button>' +
          '<button type="button" class="msg-action" data-action="copy">Copy</button>' +
        '</div>' +
      '</div>'
    );
  }

  function typingHTML() {
    return (
      '<div class="msg msg-assistant" data-typing="1">' +
        '<div class="bubble-companion typing"><span></span><span></span><span></span></div>' +
      '</div>'
    );
  }

  function voiceBubbleHTML(url) {
    const bars = [8, 16, 22, 12, 19, 9, 15, 24, 11, 18, 7, 14]
      .map((h) => '<span style="height:' + h + 'px"></span>').join('');
    return (
      '<div class="voice-bubble" data-voice-url="' + esc(url) + '">' +
        '<button type="button" class="voice-play" aria-label="Play voice message">' +
          '<svg width="12" height="14" viewBox="0 0 12 14"><path d="M0 0 L12 7 L0 14 Z"/></svg>' +
        '</button>' +
        '<span class="waveform" aria-hidden="true">' + bars + '</span>' +
        '<span class="voice-time">0:00</span>' +
        '<audio src="' + esc(url) + '" preload="metadata"></audio>' +
      '</div>'
    );
  }

  function assistantMessage(text, id, voiceUrl) {
    const div = document.createElement('div');
    div.innerHTML =
      '<div class="msg msg-assistant" data-message-id="' + id + '">' +
        '<div class="bubble-companion">' + esc(text) + '</div>' +
        (voiceUrl ? voiceBubbleHTML(voiceUrl) : '') +
        '<div class="msg-actions">' +
          '<button type="button" class="msg-action" data-action="regenerate">Regenerate</button>' +
          '<button type="button" class="msg-action" data-action="copy">Copy</button>' +
        '</div>' +
      '</div>';
    return div.firstChild;
  }

  // ---- voice playback (real <audio>) -------------------------------------

  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function mmss(secs) {
    if (!isFinite(secs)) return '0:00';
    return Math.floor(secs / 60) + ':' + pad(Math.floor(secs % 60));
  }

  function initVoiceBubble(bubble) {
    if (!bubble || bubble.dataset.init) return;
    bubble.dataset.init = '1';
    const audio = bubble.querySelector('audio');
    const btn = bubble.querySelector('.voice-play');
    const time = bubble.querySelector('.voice-time');
    if (!audio || !btn) return;

    const setIcon = (playing) => {
      btn.innerHTML = playing
        ? '<svg width="12" height="14" viewBox="0 0 14 14"><rect x="1" y="1" width="4" height="12"/><rect x="9" y="1" width="4" height="12"/></svg>'
        : '<svg width="12" height="14" viewBox="0 0 12 14"><path d="M0 0 L12 7 L0 14 Z"/></svg>';
    };

    audio.addEventListener('loadedmetadata', () => { if (time) time.textContent = mmss(audio.duration); });
    btn.addEventListener('click', () => { audio.paused ? audio.play() : audio.pause(); });
    audio.addEventListener('play', () => { bubble.classList.add('is-playing'); setIcon(true); });
    audio.addEventListener('pause', () => { bubble.classList.remove('is-playing'); setIcon(false); });
    audio.addEventListener('ended', () => {
      bubble.classList.remove('is-playing'); setIcon(false);
      if (time) time.textContent = mmss(audio.duration);
    });
    audio.addEventListener('timeupdate', () => {
      if (time) time.textContent = mmss(audio.currentTime);
    });
  }

  function initAllVoiceBubbles() {
    messageArea.querySelectorAll('.voice-bubble').forEach(initVoiceBubble);
  }

  // ---- send flow ---------------------------------------------------------

  let sending = false;

  function sendMessage(text) {
    const message = (text != null ? text : input.value).trim();
    if (!message || sending) return;
    sending = true;

    messageArea.insertAdjacentHTML('beforeend', userBubbleHTML(message));
    messageArea.insertAdjacentHTML('beforeend', typingHTML());
    if (text == null) { input.value = ''; autoGrow(input); }
    hideVoiceHint();
    scrollToBottom();

    const typingEl = messageArea.querySelector('[data-typing="1"]');

    fetch('/send_message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message, modelId: MODEL_ID }),
    })
      .then((res) => res.ok ? res.json() : res.json().then((e) => Promise.reject(e)))
      .then((data) => {
        const node = assistantMessage(data.response, data.ai_message_id, data.voice_url);
        if (typingEl) typingEl.replaceWith(node); else messageArea.appendChild(node);
        const vb = node.querySelector('.voice-bubble');
        if (vb) { initVoiceBubble(vb); const a = vb.querySelector('audio'); if (a) a.play().catch(() => {}); }
        scrollToBottom();
      })
      .catch((err) => {
        if (typingEl) typingEl.remove();
        showNotice(ERROR_TEXT[err && err.code] || ERROR_TEXT.DEFAULT);
      })
      .finally(() => { sending = false; });
  }

  // ---- regenerate --------------------------------------------------------

  function regenerate(msgEl) {
    if (sending) return;
    const aiMessageId = msgEl.dataset.messageId;

    // preceding user message text (walk backwards over dividers/other nodes)
    let prev = msgEl.previousElementSibling;
    while (prev && !prev.classList.contains('msg-user')) prev = prev.previousElementSibling;
    const userMessage = prev ? (prev.querySelector('.bubble-user')?.textContent.trim() || 'None') : 'None';

    sending = true;
    const typing = document.createElement('div');
    typing.innerHTML = typingHTML();
    const typingNode = typing.firstChild;
    msgEl.replaceWith(typingNode);

    fetch('/regenerate_message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ai_message_id: aiMessageId, user_message: userMessage, modelId: MODEL_ID }),
    })
      .then((res) => res.ok ? res.json() : res.json().then((e) => Promise.reject(e)))
      .then((data) => {
        (data.deleted_ids || []).forEach((id) => {
          const el = messageArea.querySelector('[data-message-id="' + id + '"]');
          if (el) el.remove();
        });
        const node = assistantMessage(data.response, data.ai_message_id);
        typingNode.replaceWith(node);
        scrollToBottom();
      })
      .catch((err) => {
        typingNode.remove();
        showNotice(ERROR_TEXT[err && err.code] || ERROR_TEXT.DEFAULT);
      })
      .finally(() => { sending = false; });
  }

  // ---- inline edit -------------------------------------------------------

  function startEdit(msgEl) {
    if (msgEl.querySelector('.msg-edit')) return;
    const bubble = msgEl.querySelector('.bubble-user');
    const actions = msgEl.querySelector('.msg-actions');
    const messageId = msgEl.dataset.messageId;
    const original = bubble.textContent;

    const form = document.createElement('div');
    form.className = 'msg-edit';
    form.innerHTML =
      '<textarea>' + esc(original) + '</textarea>' +
      '<div class="msg-edit-actions">' +
        '<button type="button" class="btn btn-primary-ink" data-edit="save">Save</button>' +
        '<button type="button" class="btn btn-quiet" data-edit="cancel">Cancel</button>' +
      '</div>';

    bubble.style.display = 'none';
    if (actions) actions.style.display = 'none';
    msgEl.appendChild(form);
    const ta = form.querySelector('textarea');
    ta.focus();
    ta.setSelectionRange(ta.value.length, ta.value.length);

    const close = () => {
      form.remove();
      bubble.style.display = '';
      if (actions) actions.style.display = '';
    };

    form.querySelector('[data-edit="cancel"]').addEventListener('click', close);
    form.querySelector('[data-edit="save"]').addEventListener('click', () => {
      const value = ta.value.trim();
      if (!value || value === original) { close(); return; }
      fetch('/edit_message', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId, new_content: value }),
      })
        .then((res) => res.ok ? res.json() : res.json().then((e) => Promise.reject(e)))
        .then(() => { bubble.textContent = value; close(); })
        .catch((err) => { showNotice(ERROR_TEXT[err && err.code] || ERROR_TEXT.DEFAULT); close(); });
    });
  }

  // ---- copy --------------------------------------------------------------

  function copyMessage(msgEl) {
    const text = (msgEl.querySelector('.bubble-companion, .bubble-user') || {}).textContent || '';
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).catch(() => showNotice('Could not copy.'));
    } else {
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch (e) { showNotice('Could not copy.'); }
      document.body.removeChild(ta);
    }
  }

  // ---- draft card (preserves the server confirm gate) --------------------

  function wireDraftCard() {
    const card = document.querySelector('#pending-draft [data-draft-card]');
    if (!card) return;
    const wrapper = document.getElementById('pending-draft');
    card.querySelectorAll('[data-draft-action]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.draftAction;
        if (action === 'send') {
          if (wrapper) wrapper.remove();
          sendMessage('Yes — send it.');
        } else if (action === 'dismiss') {
          if (wrapper) wrapper.remove();
          sendMessage("Not now — don't send it.");
        } else if (action === 'edit') {
          input.value = 'Change the draft: ';
          autoGrow(input);
          input.focus();
          input.setSelectionRange(input.value.length, input.value.length);
        }
      });
    });
  }

  // ---- load more (infinite scroll up) ------------------------------------

  let fetchingMore = false;
  let noMore = false;

  function loadMore() {
    if (fetchingMore || noMore) return;
    fetchingMore = true;
    const count = messageArea.querySelectorAll('.msg[data-message-id]').length;
    const prevHeight = messageArea.scrollHeight;
    const firstMsg = messageArea.querySelector('.msg, .date-divider');

    fetch('/load-more-messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_message_count: count }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (!data.length) { noMore = true; return; }
        const frag = document.createDocumentFragment();
        data.forEach((msg) => {
          const wrap = document.createElement('div');
          if (msg.sender === 'assistant') {
            wrap.innerHTML =
              '<div class="msg msg-assistant">' +
                '<div class="bubble-companion">' + esc(msg.message) + '</div>' +
                '<div class="msg-actions">' +
                  '<button type="button" class="msg-action" data-action="regenerate">Regenerate</button>' +
                  '<button type="button" class="msg-action" data-action="copy">Copy</button>' +
                '</div>' +
              '</div>';
          } else {
            wrap.innerHTML = userBubbleHTML(msg.message);
          }
          frag.appendChild(wrap.firstChild);
        });
        messageArea.insertBefore(frag, firstMsg);
        messageArea.scrollTop = messageArea.scrollHeight - prevHeight;
      })
      .catch(() => {})
      .finally(() => { fetchingMore = false; });
  }

  // ---- mic / transcription -----------------------------------------------

  const micSupported = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);

  function showVoiceHint() { if (voiceHint) voiceHint.hidden = false; }
  function hideVoiceHint() { if (voiceHint) voiceHint.hidden = true; }

  function setupMic() {
    if (!micSupported) { if (micBtn) micBtn.hidden = true; return; }

    let recorder = null;
    let chunks = [];
    let stream = null;
    let timerInt = null;
    let seconds = 0;

    const startTimer = () => {
      seconds = 0;
      if (micTimer) { micTimer.hidden = false; micTimer.textContent = '0:00'; }
      timerInt = setInterval(() => { seconds += 1; if (micTimer) micTimer.textContent = mmss(seconds); }, 1000);
    };
    const stopTimer = () => {
      clearInterval(timerInt);
      if (micTimer) micTimer.hidden = true;
    };
    const cleanup = () => {
      micBtn.classList.remove('is-recording');
      stopTimer();
      if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
      recorder = null;
    };

    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (e) {
        showNotice('Microphone access was blocked. Enable it to record.');
        return;
      }
      chunks = [];
      try {
        recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      } catch (e) {
        recorder = new MediaRecorder(stream);
      }
      recorder.addEventListener('dataavailable', (e) => { if (e.data.size) chunks.push(e.data); });
      recorder.addEventListener('stop', onStop);
      recorder.start();
      micBtn.classList.add('is-recording');
      micBtn.setAttribute('aria-label', 'Stop recording');
      startTimer();
    }

    function onStop() {
      const blob = new Blob(chunks, { type: 'audio/webm' });
      cleanup();
      micBtn.setAttribute('aria-label', 'Record voice message');
      if (!blob.size) return;
      transcribe(blob);
    }

    function transcribe(blob) {
      const fd = new FormData();
      fd.append('audio', blob, 'clip.webm');
      showNotice('Transcribing…');
      fetch('/transcribe', { method: 'POST', body: fd })
        .then((res) => res.ok ? res.json() : Promise.reject(res))
        .then((data) => {
          if (notice) notice.hidden = true;
          input.value = (input.value ? input.value + ' ' : '') + (data.text || '');
          autoGrow(input);
          input.focus();
          showVoiceHint();
        })
        .catch(() => showNotice('Could not transcribe that clip. Try again.'));
    }

    micBtn.addEventListener('click', () => {
      if (recorder && recorder.state === 'recording') recorder.stop();
      else start();
    });
  }

  // ---- event wiring ------------------------------------------------------

  sendBtn.addEventListener('click', () => sendMessage());

  input.addEventListener('input', () => { autoGrow(input); hideVoiceHint(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  messageArea.addEventListener('click', (e) => {
    const btn = e.target.closest('.msg-action');
    if (!btn) return;
    const msgEl = btn.closest('.msg');
    const action = btn.dataset.action;
    if (action === 'regenerate') regenerate(msgEl);
    else if (action === 'edit') startEdit(msgEl);
    else if (action === 'copy') copyMessage(msgEl);
  });

  messageArea.addEventListener('scroll', () => {
    if (messageArea.scrollTop <= 4) loadMore();
  });

  // AI switcher dropdown
  const switcher = document.getElementById('ai-switcher');
  const switchMenu = document.getElementById('ai-switch-menu');
  if (switcher && switchMenu) {
    switcher.addEventListener('click', () => {
      const open = switchMenu.hidden;
      switchMenu.hidden = !open;
      switcher.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    document.addEventListener('click', (e) => {
      if (!switcher.contains(e.target) && !switchMenu.contains(e.target)) {
        switchMenu.hidden = true;
        switcher.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // ---- init --------------------------------------------------------------

  relabelDividers();
  relabelReachedOut();
  initAllVoiceBubbles();
  wireDraftCard();
  setupMic();
  autoGrow(input);
  scrollToBottom();
})();
