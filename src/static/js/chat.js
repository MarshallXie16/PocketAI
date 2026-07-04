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
  const AI_NAME = app.dataset.aiName || '';

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

  // Voice bubble built with DOM APIs — the URL goes through setAttribute /
  // .src, never string-interpolated into an HTML attribute context.
  function voiceBubbleEl(url) {
    const bubble = document.createElement('div');
    bubble.className = 'voice-bubble';
    bubble.setAttribute('data-voice-url', url);

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'voice-play';
    btn.setAttribute('aria-label', 'Play voice message');
    btn.innerHTML = '<svg width="12" height="14" viewBox="0 0 12 14"><path d="M0 0 L12 7 L0 14 Z"/></svg>';
    bubble.appendChild(btn);

    const wave = document.createElement('span');
    wave.className = 'waveform';
    wave.setAttribute('aria-hidden', 'true');
    [8, 16, 22, 12, 19, 9, 15, 24, 11, 18, 7, 14].forEach((h) => {
      const s = document.createElement('span');
      s.style.height = h + 'px';
      wave.appendChild(s);
    });
    bubble.appendChild(wave);

    const time = document.createElement('span');
    time.className = 'voice-time';
    time.textContent = '0:00';
    bubble.appendChild(time);

    const audio = document.createElement('audio');
    audio.src = url;
    audio.preload = 'metadata';
    bubble.appendChild(audio);

    return bubble;
  }

  // Assistant message built entirely with DOM APIs. opts: {initiated, timestamp}.
  // Mirrors the initial server render (reached-out header + initiated-row when
  // the message was companion-initiated).
  function assistantMessage(text, id, voiceUrl, opts) {
    opts = opts || {};
    const node = document.createElement('div');
    node.className = 'msg msg-assistant';
    if (id != null) node.setAttribute('data-message-id', id);
    if (opts.timestamp) node.setAttribute('data-timestamp', opts.timestamp);

    if (opts.initiated) {
      const reached = document.createElement('div');
      reached.className = 'reached-out';
      const dot = document.createElement('span');
      dot.className = 'dot';
      reached.appendChild(dot);
      const label = document.createElement('span');
      label.textContent = AI_NAME + ' reached out';
      reached.appendChild(label);
      const meta = document.createElement('span');
      meta.className = 'reached-out-meta reached-out-time';
      if (opts.timestamp) meta.setAttribute('data-timestamp', opts.timestamp);
      reached.appendChild(meta);
      node.appendChild(reached);
    }

    const bubble = document.createElement('div');
    bubble.className = 'bubble-companion';
    bubble.textContent = text == null ? '' : String(text);
    node.appendChild(bubble);

    if (voiceUrl) node.appendChild(voiceBubbleEl(voiceUrl));

    if (opts.initiated) {
      const row = document.createElement('div');
      row.className = 'initiated-row';
      const link = document.createElement('a');
      link.className = 'quiet-link';
      link.href = SETTINGS_URL;
      link.innerHTML = 'less often &middot; pause';
      row.appendChild(link);
      node.appendChild(row);
    }

    const actions = document.createElement('div');
    actions.className = 'msg-actions';
    actions.innerHTML =
      '<button type="button" class="msg-action" data-action="regenerate">Regenerate</button>' +
      '<button type="button" class="msg-action" data-action="copy">Copy</button>';
    node.appendChild(actions);

    return node;
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

    const userWrap = document.createElement('div');
    userWrap.innerHTML = userBubbleHTML(message);
    const userNode = userWrap.firstChild;
    messageArea.appendChild(userNode);
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
        // stamp the optimistic user bubble with its real id so edit/count work
        if (userNode && data.user_message_id != null) {
          userNode.setAttribute('data-message-id', data.user_message_id);
        }
        const node = assistantMessage(data.response, data.ai_message_id, data.voice_url);
        if (typingEl) typingEl.replaceWith(node); else messageArea.appendChild(node);
        const vb = node.querySelector('.voice-bubble');
        if (vb) { initVoiceBubble(vb); const a = vb.querySelector('audio'); if (a) a.play().catch(() => {}); }
        // reconcile the pending-draft card with the server's authoritative state
        if (data.pending_action) renderDraftCard(data.pending_action);
        else removeDraftCard();
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
  // The card reflects the server's pending_action. Buttons send plain chat
  // messages so the server-side confirm gate stays intact; 'dismiss' also
  // clears the server-side draft first so a stale action can't later fire.

  function removeDraftCard() {
    const w = document.getElementById('pending-draft');
    if (w) w.remove();
  }

  // Map a pending_action {tool, args, message_id} to the {to, subject, body}
  // the draft_card macro renders — mirrors the Jinja mapping in chat.html.
  function draftFromAction(pa) {
    const a = (pa && pa.args) || {};
    if (pa && pa.tool === 'email_send') {
      return { to: a.recipient_email || a.recipient_name || '', subject: a.subject || '', body: a.body || '' };
    }
    const range = (a.start || '') + (a.end ? ' — ' + a.end : '');
    return { to: a.title || '', subject: range, body: a.description || 'New calendar event' };
  }

  function renderDraftCard(pa) {
    removeDraftCard();
    const draft = draftFromAction(pa);

    const wrapper = document.createElement('div');
    wrapper.className = 'msg msg-assistant';
    wrapper.id = 'pending-draft';

    const card = document.createElement('div');
    card.className = 'draft-card';
    card.setAttribute('data-draft-card', '');

    const head = document.createElement('div');
    head.className = 'draft-card-head';
    const toMeta = document.createElement('div');
    toMeta.className = 'draft-card-meta';
    toMeta.appendChild(document.createTextNode('To: '));
    const toStrong = document.createElement('strong');
    toStrong.textContent = draft.to;
    toMeta.appendChild(toStrong);
    head.appendChild(toMeta);
    if (draft.subject) {
      const subMeta = document.createElement('div');
      subMeta.className = 'draft-card-meta';
      subMeta.appendChild(document.createTextNode('Subject: '));
      const subStrong = document.createElement('strong');
      subStrong.textContent = draft.subject;
      subMeta.appendChild(subStrong);
      head.appendChild(subMeta);
    }
    card.appendChild(head);

    const body = document.createElement('p');
    body.className = 'draft-card-body';
    body.textContent = draft.body;
    card.appendChild(body);

    const actions = document.createElement('div');
    actions.className = 'draft-card-actions';
    actions.innerHTML =
      '<button type="button" class="btn btn-primary-ink" data-draft-action="send">Send it</button>' +
      '<button type="button" class="btn btn-tertiary" data-draft-action="edit">Edit first</button>' +
      '<button type="button" class="btn btn-quiet" data-draft-action="dismiss">Not now</button>';
    card.appendChild(actions);
    wrapper.appendChild(card);

    const caption = document.createElement('div');
    caption.className = 'draft-caption';
    caption.textContent = 'Nothing sends without your okay.';
    wrapper.appendChild(caption);

    messageArea.appendChild(wrapper);
    wireDraftActions(card);
    scrollToBottom();
  }

  function wireDraftActions(card) {
    card.querySelectorAll('[data-draft-action]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.draftAction;
        if (action === 'send') {
          // card is cleared by the next response's pending_action (null)
          sendMessage('Yes — send it.');
        } else if (action === 'dismiss') {
          fetch('/dismiss-draft', { method: 'POST' })
            .then((res) => res.ok ? res.json() : Promise.reject(res))
            .then(() => { removeDraftCard(); sendMessage("Not now — don't send it."); })
            .catch(() => showNotice(ERROR_TEXT.DEFAULT));
        } else if (action === 'edit') {
          input.value = 'Change the draft: ';
          autoGrow(input);
          input.focus();
          input.setSelectionRange(input.value.length, input.value.length);
        }
      });
    });
  }

  // Wire the server-rendered card present on initial page load, if any.
  function wireInitialDraftCard() {
    const card = document.querySelector('#pending-draft [data-draft-card]');
    if (card) wireDraftActions(card);
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
          if (msg.sender === 'assistant') {
            frag.appendChild(assistantMessage(msg.message, msg.id, msg.voice_url, {
              initiated: msg.initiated, timestamp: msg.timestamp,
            }));
          } else {
            const wrap = document.createElement('div');
            wrap.innerHTML = userBubbleHTML(msg.message, msg.id);
            frag.appendChild(wrap.firstChild);
          }
        });
        messageArea.insertBefore(frag, firstMsg);
        // hydrate the newly prepended rows the same way the initial render does
        relabelReachedOut();
        initAllVoiceBubbles();
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
    let starting = false;  // getUserMedia is pending — guards against double-start

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
      // bail if a recorder is already live or one is being spun up
      if (recorder || starting) return;
      starting = true;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (e) {
        starting = false;
        showNotice('Microphone access was blocked. Enable it to record.');
        return;
      }
      chunks = [];
      // permission is granted and the stream is live; from here any failure
      // must release the tracks so the mic indicator doesn't stay on
      try {
        try {
          recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        } catch (e) {
          recorder = new MediaRecorder(stream);
        }
        recorder.addEventListener('dataavailable', (e) => { if (e.data.size) chunks.push(e.data); });
        recorder.addEventListener('stop', onStop);
        recorder.start();
      } catch (e) {
        cleanup();
        starting = false;
        showNotice('Could not start recording. Try again.');
        return;
      }
      micBtn.classList.add('is-recording');
      micBtn.setAttribute('aria-label', 'Stop recording');
      startTimer();
      starting = false;
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
  wireInitialDraftCard();
  setupMic();
  autoGrow(input);
  scrollToBottom();
})();
