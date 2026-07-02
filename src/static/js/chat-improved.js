// Config
const CONFIG = {
    MESSAGE_COST: 1,
    MAX_TEXTAREA_HEIGHT: 200,
    ELEMENTS: {
        creditsDisplay: '.credits-display',
        chatArea: '.message-area',
        messageInput: '.message-input',
        aiSelector: '#ai-selector',
        aiOptions: '#ai-options',
        errorAlert: '#error-alert',
        errorMessage: '#error-message',
        bottomPanel: '.bottom-panel'
    }
};

// DOM Element Cache
const Elements = {
    init() {
        // Cache all DOM elements
        Object.entries(CONFIG.ELEMENTS).forEach(([key, selector]) => {
            this[key] = document.querySelector(selector);
        });
    }
};

// Credit Management
const CreditManager = {
    getCurrentCredits() {
        return parseInt(document.querySelector('.credits-text').textContent, 10);
    },

    updateCredits(newCredits) {
        document.querySelector('.credits-text').textContent = newCredits;
    },

    hasEnoughCredits() {
        return this.getCurrentCredits() >= CONFIG.MESSAGE_COST;
    },

    deductMessageCost() {
        const newCredits = this.getCurrentCredits() - CONFIG.MESSAGE_COST;
        this.updateCredits(newCredits);
    }
};

// UI Management
const UIManager = {
    displayError(message, duration = 5000) {
        const { errorAlert, errorMessage } = Elements;
        
        errorMessage.textContent = message;
        errorAlert.classList.remove('hidden');
        errorAlert.classList.add('show');

        setTimeout(() => {
            errorAlert.classList.remove('show');
            setTimeout(() => {
                errorAlert.classList.add('hidden');
            }, 500);
        }, duration);
    },

    autoGrow(element) {
        element.style.height = '1.5em';
        element.style.height = `${element.scrollHeight}px`;

        if (Elements.bottomPanel) {
            Elements.bottomPanel.style.height = 'auto';
        }

        if (parseInt(element.style.height, 10) >= CONFIG.MAX_TEXTAREA_HEIGHT) {
            element.style.height = `${CONFIG.MAX_TEXTAREA_HEIGHT}px`;
            element.style.overflowY = "scroll";
        }
    },

    scrollToBottom() {
        Elements.chatArea.scrollTop = Elements.chatArea.scrollHeight;
    }
};

// Message Display
const MessageDisplay = {
    templates: {
        userMessage(message, timestamp) {
            return `
                <div class="message-container user-message">
                    <div class="message-wrapper flex items-end gap-2 justify-end">
                        <div class="message-bubble chat-message-user backdrop-blur-sm rounded-t-2xl rounded-bl-2xl p-3 max-w-[70%]" style="background-color:#7367F0;">
                            <p class="invert-text markdown-content">${MarkdownHandler.convert(message)}</p>
                        </div>
                        <div class="avatar relative p-[2px] rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5]">
                            <img src="${USER_PROFILE_IMAGE}" width="40" height="40" alt="Avatar" class="rounded-full" style="aspect-ratio: 40 / 40; object-fit: cover;" />
                            <div class="status-indicator absolute -bottom-0.5 -right-0.5 rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5] p-[2px]">
                                <div class="rounded-full bg-white p-[2px]"></div>
                            </div>
                        </div>
                    </div>
                    <div class="timestamp text-xs text-gray-500 mt-1 flex justify-end">
                        ${timestamp}
                    </div>
                </div>`;
        },

        botMessage(message, timestamp, isLoading = false) {
            const messageContent = isLoading 
                ? '<div class="loading-dots"><div></div><div></div><div></div></div>'
                : `<p class="invert-text markdown-content">${MarkdownHandler.convert(message)}</p>`;

            return `
                <div class="message-container bot-message">
                    <div class="message-wrapper flex items-end gap-2 justify-start">
                        <div class="avatar relative p-[2px] rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5]">
                            <img src="${AI_PROFILE_IMAGE}" width="40" height="40" alt="Avatar" class="rounded-full" style="aspect-ratio: 40 / 40; object-fit: cover;" />
                            <div class="status-indicator absolute -bottom-0.5 -right-0.5 rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5] p-[2px]">
                                <div class="rounded-full bg-white p-[2px]"></div>
                            </div>
                        </div>
                        <div class="${isLoading ? 'ai-message-placeholder' : 'message-bubble'} chat-message-ai backdrop-blur-sm rounded-t-2xl rounded-br-2xl p-3 max-w-[70%]">
                            ${messageContent}
                        </div>
                    </div>
                    <div class="timestamp text-xs text-gray-500 mt-1">${timestamp}</div>
                </div>`;
        }
    },

    addMessage(html) {
        Elements.chatArea.insertAdjacentHTML('beforeend', html);
        UIManager.scrollToBottom();
    },

    updateLatestBotMessage(response, messageId) {
        const latestBot = Elements.chatArea.querySelector('.bot-message:last-child');
        if (latestBot) {
            const placeholder = latestBot.querySelector('.ai-message-placeholder');
            if (placeholder) {
                placeholder.innerHTML = `<p class="invert-text markdown-content">${MarkdownHandler.convert(response)}</p>`;
                latestBot.dataset.messageId = messageId;
                HoverPanel.create(latestBot);
            }
        }
    }
};

// Message Handler
const MessageHandler = {
    async sendMessage() {
        const message = Elements.messageInput.value.trim();
        if (!message || !CreditManager.hasEnoughCredits()) return;

        const modelId = document.querySelector('[data-selected-model]')?.getAttribute('data-selected-model');
        
        // Display messages and clear input
        MessageDisplay.addMessage(
            MessageDisplay.templates.userMessage(message, TimeFormatter.getCurrentTime())
        );
        MessageDisplay.addMessage(
            MessageDisplay.templates.botMessage('', TimeFormatter.getCurrentTime(), true)
        );
        Elements.messageInput.value = '';
        UIManager.autoGrow(Elements.messageInput);

        try {
            const response = await this.sendToServer(message, modelId);
            MessageDisplay.updateLatestBotMessage(response.response, response.ai_message_id);
            CreditManager.deductMessageCost();
        } catch (error) {
            this.handleError(error);
        }
    },

    async sendToServer(message, modelId) {
        const response = await fetch('/send_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, modelId })
        });

        if (!response.ok) {
            throw await response.json();
        }
        return response.json();
    },

    handleError(error) {
        const errorMessages = {
            INSUFFICIENT_CREDITS: "You don't have enough credits. Please add more to continue.",
            MODEL_NOT_FOUND: "The selected AI model doesn't exist. Please choose another.",
            ACCESS_DENIED: "You don't have access to this AI model. Please select another.",
            BAD_REQUEST: "There was an issue with your request. Please try again.",
            DEFAULT: "An unexpected error occurred. Please try again later."
        };

        UIManager.displayError(errorMessages[error.code] || errorMessages.DEFAULT);
    }
};

// Markdown Handler
const MarkdownHandler = {
    convert(text) {
        if (!text.trim()) return '';
        
        try {
            let html = marked.parse(text);
            return html.replace(/(?:^|\s)\*([^\*\n]+)\*(?=$|\s)/g, ' <em>$1</em>');
        } catch (error) {
            console.error('Markdown parsing error:', error);
            return text;
        }
    },

    convertAll() {
        document.querySelectorAll('.markdown-content').forEach(element => {
            const markdown = element.textContent || element.innerText;
            element.innerHTML = this.convert(markdown);
        });
    }
};

// Time Formatter
const TimeFormatter = {
    getCurrentTime() {
        const now = new Date();
        const hours = now.getHours() % 12 || 12;
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const ampm = now.getHours() >= 12 ? 'PM' : 'AM';
        return `${hours}:${minutes} ${ampm}`;
    },

    formatTimestamp(timestamp) {
        const utcDate = new Date(timestamp + 'Z');
        const now = new Date();
        const isToday = utcDate.toDateString() === now.toDateString();
        
        const options = {
            ...(isToday ? {} : { month: 'long', day: 'numeric' }),
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        };

        return new Intl.DateTimeFormat('en-US', options).format(utcDate);
    }
};

// Hover Panel
const HoverPanel = {
    template: `
        <div class="hover-panel hide">
            <button class="hover-panel-btn retry-btn">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"/>
                </svg>
                Retry
            </button>
            <button class="hover-panel-btn copy-btn">
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
                    <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
                </svg>
                Copy
            </button>
        </div>`,

    create(messageContainer) {
        const wrapper = messageContainer.querySelector('.message-wrapper');
        if (wrapper.querySelector('.hover-panel')) return;

        wrapper.insertAdjacentHTML('beforeend', this.template);
        this.attachHandlers(wrapper);
    },

    attachHandlers(wrapper) {
        const panel = wrapper.querySelector('.hover-panel');
        
        wrapper.addEventListener('mouseenter', () => {
            panel.classList.remove('hide');
            panel.classList.add('show');
            panel.style.display = 'flex';
        });

        wrapper.addEventListener('mouseleave', () => {
            panel.classList.remove('show');
            panel.classList.add('hide');
            setTimeout(() => {
                if (panel.classList.contains('hide')) {
                    panel.style.display = 'none';
                }
            }, 300);
        });

        // Attach retry and copy handlers
        panel.querySelector('.retry-btn').addEventListener('click', () => this.handleRetry(wrapper));
        panel.querySelector('.copy-btn').addEventListener('click', () => this.handleCopy(wrapper));
    },

    handleRetry(wrapper) {
        // Your existing regenerateMessage logic
    },

    handleCopy(wrapper) {
        const content = wrapper.querySelector('.message-content')?.textContent;
        if (content) {
            navigator.clipboard.writeText(content)
                .then(() => console.log('Copied to clipboard'))
                .catch(err => console.error('Copy failed:', err));
        }
    }
};

// Initialize everything
function initialize() {
    Elements.init();
    
    // Initialize message input handler
    Elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            if (e.ctrlKey) {
                // Insert newline
                const start = e.target.selectionStart;
                const end = e.target.selectionEnd;
                const value = e.target.value;
                e.target.value = value.slice(0, start) + '\n' + value.slice(end);
                e.target.selectionStart = e.target.selectionEnd = start + 1;
            } else {
                // Send message
                e.preventDefault();
                MessageHandler.sendMessage();
            }
        }
    });

    // Initialize hover panels
    document.querySelectorAll('.bot-message').forEach(msg => HoverPanel.create(msg));
    
    // Initialize markdown
    MarkdownHandler.convertAll();
    
    // Initialize infinite scroll
    // Your existing infinite scroll logic here
}

// Start the application
initialize();