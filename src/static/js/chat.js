// variables
let MESSAGE_COST = 1;
let creditsDisplay = document.querySelector('.credits-display');
let chatArea = document.querySelector('.message-area');

// Dropdown for ai models
const aiSelector = document.getElementById('ai-selector');
const aiOptions = document.getElementById('ai-options');
const nameElement = aiSelector.querySelector('h2');
const modelElement = aiSelector.querySelector('p');
const imageElement = aiSelector.querySelector('img');
const arrowIcon = aiSelector.querySelector('svg');

aiSelector.addEventListener('click', function () {
    aiOptions.classList.toggle('hidden');
    arrowIcon.classList.toggle('rotate-180');
});

aiOptions.addEventListener('click', function (e) {
    const option = e.target.closest('.ai-option');
    if (option) {
        const aiId = option.getAttribute('data-id');
        nameElement.textContent = option.getAttribute('data-name');
        modelElement.textContent = option.getAttribute('data-model-name');
        imageElement.src = option.getAttribute('data-image-url');
        aiOptions.classList.add('hidden');
        arrowIcon.classList.remove('rotate-180');

        // Redirect to change AI and reload the chat page
        window.location.href = `/change-ai/${aiId}`;
    }
});

// Close dropdown when clicking outside
document.addEventListener('click', function (e) {
    if (!aiSelector.contains(e.target) && !aiOptions.contains(e.target)) {
        aiOptions.classList.add('hidden');
        arrowIcon.classList.remove('rotate-180');
    }
});


// CHAT UI FEATURES

// handle message regeneration
function regenerateMessage(messageContainer) {
    let selectedAIModel = document.querySelector('[data-selected-model]');
    let modelId = selectedAIModel.getAttribute('data-selected-model');
    const aiMessageContainer = messageContainer.closest('.bot-message');
    const aiMessageId = aiMessageContainer.dataset.messageId;

    // Find the previous user message
    let previousUserMessage = aiMessageContainer.previousElementSibling;
    while (previousUserMessage && !previousUserMessage.classList.contains('user-message')) {
        previousUserMessage = previousUserMessage.previousElementSibling;
    }

    if (!previousUserMessage) {
        displayErrorMessage('Cannot regenerate the first message in the conversation.');
        return;
    }

    const userMessageContent = previousUserMessage.querySelector('.message-bubble').textContent.trim();

    // Remove the current AI message
    aiMessageContainer.remove();

    // Show loading indicator
    const loadingHtml = `
        <div class="message-container bot-message">
            <div class="message-wrapper flex items-end gap-2 justify-start">
                <div class="avatar relative p-[2px] rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5]">
                    <img src="${AI_PROFILE_IMAGE}" width="40" height="40" alt="Avatar" class="rounded-full" style="aspect-ratio: 40 / 40; object-fit: cover;" />
                    <div class="status-indicator absolute -bottom-0.5 -right-0.5 rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5] p-[2px]">
                        <div class="rounded-full bg-white p-[2px]"></div>
                    </div>
                </div>
                <div class="ai-message-placeholder chat-message-ai backdrop-blur-sm rounded-t-2xl rounded-br-2xl p-3 max-w-[70%]">
                    <div class="loading-dots"><div></div><div></div><div></div></div>
                </div>
            </div>
            <div class="timestamp text-xs text-gray-500 mt-1">Now</div>
        </div>`;
    chatArea.insertAdjacentHTML('beforeend', loadingHtml);

    console.log('we are here');
    console.log(aiMessageId);

    // Call backend to regenerate message
    fetch('/regenerate_message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ai_message_id: aiMessageId, user_message: userMessageContent, modelId: modelId })
        }).then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw err; });
                }
                return response.json();
            })
            .then(data => {
                // insert response into placeholder chat message
                updateChatArea(data.response, data.ai_message_id);
                // deduct credits from client-side
                const newCredits = getCurrentCredits() - MESSAGE_COST;
                updateCreditDisplay(newCredits);
            })
            .catch(error => {
                console.error('Error:', error);
                let errorMessage;
                switch (error.code) {
                    case 'INSUFFICIENT_CREDITS':
                        errorMessage = "You don't have enough credits. Please add more to continue.";
                        break;
                    case 'MODEL_NOT_FOUND':
                        errorMessage = "The selected AI model doesn't exist. Please choose another.";
                        break;
                    case 'ACCESS_DENIED':
                        errorMessage = "You don't have access to this AI model. Please select another.";
                        break;
                    case 'BAD_REQUEST':
                        errorMessage = "There was an issue with your request. Please try again.";
                        break;
                    default:
                        errorMessage = "An unexpected error occurred. Please try again later.";
                }
                displayErrorMessage(errorMessage);
            });
}

// initialize hover panels for existing bot messages
function initializeExistingMessages() {
    const existingBotMessages = document.querySelectorAll('.bot-message > .message-wrapper');
    existingBotMessages.forEach(messageContainer => {
        if (!messageContainer.querySelector('.hover-panel')) {
            createHoverPanel(messageContainer);
        }
    });
}

function createHoverPanel(messageContainer) {
    if (messageContainer.querySelector('.hover-panel')) {
        return; // Panel already exists, no need to create a new one
    }

    let hoverPanel = `<div class="hover-panel hide">
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
                    </div>`;

    messageContainer.insertAdjacentHTML('beforeend', hoverPanel);

    const panel = messageContainer.querySelector('.hover-panel');
    const retryBtn = panel.querySelector('.retry-btn');
    const copyBtn = panel.querySelector('.copy-btn');

    retryBtn.addEventListener('click', () => regenerateMessage(messageContainer));
    // copyBtn.addEventListener('click', () => copyMessageContent(messageContainer));

    messageContainer.addEventListener('mouseenter', () => {
        panel.classList.remove('hide');
        panel.classList.add('show');
        panel.style.display = 'flex';
    });

    messageContainer.addEventListener('mouseleave', () => {
        panel.classList.remove('show');
        panel.classList.add('hide');

        setTimeout(() => {
            if (panel.classList.contains('hide')) {
                panel.style.display = 'none';
            }
        }, 300);
    });
}

function copyMessageContent(messageContainer) {
    const messageContent = messageContainer.querySelector('.message-content').textContent;
    navigator.clipboard.writeText(messageContent).then(() => {
        console.log('Message content copied to clipboard');
    }).catch(err => {
        console.error('Failed to copy message content: ', err);
    });
}

// SENDING MESSAGES

// Purpose: prevent user from sending message if there are no credits
function sufficientCredits() {
    let currentCredits = parseInt(creditsDisplay.textContent, 10);
    return currentCredits >= MESSAGE_COST;
}

// Purpose: send chat message only if the user has enough credits
function sendChatMessage() {
    if (!sufficientCredits()) {
        displayErrorMessage('You do not have enough credits to send a message. Please either upgrade your plan or wait for your credits to refresh. Beta users can also reach out to us at info@pocketai.com for more credits.');
        return;
    }
    sendMessage();
}

// Purpose: Sends message to backend via fetch, waits, and displays bot response
function sendMessage() {
    let messageInput = document.querySelector('.message-input');
    let message = messageInput.value.trim();
    let chatArea = document.querySelector('.chat-container > .message-area');
    let selectedAIModel = document.querySelector('[data-selected-model]');
    let modelId = selectedAIModel.getAttribute('data-selected-model');

    // For empty messages
    if (!message) {
        return;
    }

    // client side validation for credits
    if (!sufficientCredits()) {
        displayErrorMessage('You do not have enough credits to send a message. Please either upgrade your plan or wait for your credits to refresh. Beta users can also reach out to us at info@pocketai.com for more credits.');
        return;
    }

    // Display user message
    let userMessageHtml = `
        <div class="message-container user-message">
            <div class="message-wrapper flex items-end gap-2 justify-end">
                <div class="message-bubble chat-message-user backdrop-blur-sm rounded-t-2xl rounded-bl-2xl p-3 max-w-[70%]" style="background-color:#7367F0;">
                    <p class="invert-text markdown-content">${convertMarkdownText(message)}</p>
                </div>
                <div class="avatar relative relative p-[2px] rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5]">
                    <img src="${USER_PROFILE_IMAGE}" width="40" height="40" alt="Avatar" class="rounded-full" style="aspect-ratio: 40 / 40; object-fit: cover;" />
                    <div class="status-indicator absolute -bottom-0.5 -right-0.5 rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5] p-[2px]">
                        <div class="rounded-full bg-white p-[2px]"></div>
                    </div>
                </div>
            </div>
            <div class="timestamp text-xs text-gray-500 mt-1 flex justify-end">
                ${getCurrentFormattedTime()}
            </div>
        </div>`;
    chatArea.insertAdjacentHTML('beforeend', userMessageHtml);

    // Display placeholder AI's response and play loading animation
    let botMessageHtml = `
        <div class="message-container bot-message">
            <div class="message-wrapper flex items-end gap-2 justify-start">
                <div class="avatar relative p-[2px] rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5]">
                    <img src="${AI_PROFILE_IMAGE}" width="40" height="40" alt="Avatar" class="rounded-full" style="aspect-ratio: 40 / 40; object-fit: cover;" />
                    <div class="status-indicator absolute -bottom-0.5 -right-0.5 rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5] p-[2px]">
                        <div class="rounded-full bg-white p-[2px]"></div>
                    </div>
                </div>
                <div class="ai-message-placeholder chat-message-ai backdrop-blur-sm rounded-t-2xl rounded-br-2xl p-3 max-w-[70%]">
                    <div class="loading-dots"><div></div><div></div><div></div></div>
                </div>
            </div>
            <div class="timestamp text-xs text-gray-500 mt-1">Now</div>
        </div>`;
    chatArea.insertAdjacentHTML('beforeend', botMessageHtml);

    // Scroll to the latest message
    chatArea.scrollTop = chatArea.scrollHeight;

    // Clear the message input
    messageInput.value = '';
    // Reset the height of the textarea
    autoGrow(messageInput);

    console.log('model ID', modelId);

    // Check if the message is not empty
    if (message) {
        fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ "message": message, "modelId": modelId })
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw err; });
                }
                return response.json();
            })
            .then(data => {
                // insert response into placeholder chat message
                updateChatArea(data.response, data.ai_message_id);
                // deduct credits from client-side
                const newCredits = getCurrentCredits() - MESSAGE_COST;
                updateCreditDisplay(newCredits);
            })
            .catch(error => {
                console.error('Error:', error);
                let errorMessage;
                switch (error.code) {
                    case 'INSUFFICIENT_CREDITS':
                        errorMessage = "You don't have enough credits. Please add more to continue.";
                        break;
                    case 'MODEL_NOT_FOUND':
                        errorMessage = "The selected AI model doesn't exist. Please choose another.";
                        break;
                    case 'ACCESS_DENIED':
                        errorMessage = "You don't have access to this AI model. Please select another.";
                        break;
                    case 'BAD_REQUEST':
                        errorMessage = "There was an issue with your request. Please try again.";
                        break;
                    default:
                        errorMessage = "An unexpected error occurred. Please try again later.";
                }
                displayErrorMessage(errorMessage);
            });
    }
}


// Fills in the placeholder bot msg with generated ai response
function updateChatArea(response, messageId) {
    let latestBotMessage = chatArea.querySelector('.bot-message:last-child');
    if (latestBotMessage) {
        let aiResponsePlaceholder = latestBotMessage.querySelector('.ai-message-placeholder');
        let timestamp = latestBotMessage.querySelector('.timestamp');
        if (aiResponsePlaceholder && timestamp) {
            aiResponsePlaceholder.innerHTML = `<p class="invert-text markdown-content">${convertMarkdownText(response)}</p>`;
            timestamp.innerHTML = getCurrentFormattedTime();

            console.log(latestBotMessage);
            console.log(messageId);

            // Add message ID to the container
            latestBotMessage.dataset.messageId = messageId;

            // Add the hover panel to the message container
            createHoverPanel(latestBotMessage);
        }
    }
    chatArea.scrollTop = chatArea.scrollHeight;
}


// UTILITY FUNCTIONS

function displayErrorMessage(message) {
    const errorAlert = document.getElementById('error-alert');
    const errorMessage = document.getElementById('error-message');

    errorMessage.textContent = message;
    errorAlert.classList.remove('hidden');
    errorAlert.classList.add('show');

    // Hide the alert after 5 seconds
    setTimeout(() => {
        errorAlert.classList.remove('show');
        setTimeout(() => {
            errorAlert.classList.add('hidden');
        }, 500);
    }, 5000);
}


// CHAT UI FUNCTIONALITY
let messageArea = document.querySelector('.message-area');
let isFetching = false;

messageArea.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
        if (e.ctrlKey) {
            // Ctrl+Enter: Insert a new line
            const start = this.selectionStart;
            const end = this.selectionEnd;
            const value = this.value;
            this.value = value.slice(0, start) + '\n' + value.slice(end);
            this.selectionStart = this.selectionEnd = start + 1;
            e.preventDefault();
        } else {
            // Enter without Ctrl: Send the message
            e.preventDefault();
            sendChatMessage();
        }
    }
});



// Purpose: Automatically adjust the height of the textarea to fit the content
function autoGrow(element) {
    // reset the height to default
    element.style.height = '1.5em';
    element.style.height = (element.scrollHeight) + "px";

    // Adjust the bottom panel's height
    let bottomPanel = document.querySelector('.bottom-panel');
    if (bottomPanel) {
        bottomPanel.style.height = 'auto';
    }

    // Set maximum height and enable scroll
    if (parseInt(element.style.height, 10) >= 200) {
        element.style.height = "200px";
        element.style.overflowY = "scroll";
    }
}

// Event listener for up scroll to display more messages
messageArea.addEventListener('scroll', function () {
    if (messageArea.scrollTop === 0 && !isFetching) {
        isFetching = true;
        console.log('Fetching more messages...');
        fetchMoreMessages();
    }
});
// Purpose: Fetch more messages from the server and display them in the chat area
function fetchMoreMessages() {
    let currentMessageCount = chatArea.querySelectorAll('.message-container').length;
    let oldScrollHeight = chatArea.scrollHeight;

    fetch('/load-more-messages', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ current_message_count: currentMessageCount })
    })
        .then(response => {
            console.log('Response received:', response);
            return response.json();
        })
        .then(data => {
            console.log('Fetched more messages:', data);
            if (data.length > 0) {
                let firstMessageContainer = chatArea.querySelector('.message-container:first-child');

                data.forEach(msg => {
                    let messageHtml = '';
                    let formattedMessage = convertMarkdownText(msg.message);
                    let formattedTimestamp = formatTimestamp(msg.timestamp);

                    if (msg.sender === 'assistant') {
                        messageHtml = `
                        <div class="message-container bot-message">
                            <div class="message-wrapper flex items-end gap-2 justify-start">
                                <div class="avatar relative p-[2px] rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5]">
                                    <img src="${AI_PROFILE_IMAGE}" width="40" height="40" alt="Avatar" class="rounded-full" style="aspect-ratio: 40 / 40; object-fit: cover;" />
                                    <div class="status-indicator absolute -bottom-0.5 -right-0.5 rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5] p-[2px]">
                                        <div class="rounded-full bg-white p-[2px]"></div>
                                    </div>
                                </div>
                                <div class="message-bubble chat-message-ai backdrop-blur-sm rounded-t-2xl rounded-br-2xl p-3 max-w-[70%]">
                                    <p class="invert-text markdown-content">${formattedMessage}</p>
                                </div>
                            </div>
                            <div class="timestamp text-xs text-gray-500 mt-1" data-timestamp="${msg.timestamp}">
                            ${formattedTimestamp}
                            </div>
                        </div>`;
                    } else {
                        messageHtml = `
                        <div class="message-container user-message">
                            <div class="message-wrapper flex items-end gap-2 justify-end">
                                <div class="message-bubble chat-message-user backdrop-blur-sm rounded-t-2xl rounded-bl-2xl p-3 max-w-[70%]">
                                    <p class="invert-text markdown-content">${formattedMessage}</p>
                                </div>
                                <div class="avatar relative p-[2px] rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5]">
                                    <img src="${USER_PROFILE_IMAGE}" width="40" height="40" alt="Avatar" class="rounded-full" style="aspect-ratio: 40 / 40; object-fit: cover;" />
                                    <div class="status-indicator absolute -bottom-0.5 -right-0.5 rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5] p-[2px]">
                                        <div class="rounded-full bg-white p-[2px]"></div>
                                    </div>
                                </div>
                            </div>
                            <div class="timestamp text-xs text-gray-500 mt-1 flex justify-end" data-timestamp="${msg.timestamp}">
                            ${formattedTimestamp}
                            </div>
                        </div>`;
                    }

                    let messageNode = document.createElement('div');
                    messageNode.innerHTML = messageHtml;
                    while (messageNode.firstChild) {
                        chatArea.insertBefore(messageNode.firstChild, firstMessageContainer);
                    }
                });

                // Calculate the new scroll position to maintain the view
                let newScrollHeight = chatArea.scrollHeight;
                chatArea.scrollTop = newScrollHeight - oldScrollHeight;
            }

            isFetching = false;
        })
        .catch(error => {
            console.error('Error fetching more messages:', error);
            isFetching = false;
        });
}




// FORMATTING

// Initially converts all messages to markdown format
function convertAndDisplayAllMarkdown() {
    const markdownElements = document.querySelectorAll('.markdown-content');
    markdownElements.forEach(element => {
        convertAndDisplaySingleMarkdown(element);
    });
}

// Converts a message element to markdown format
function convertAndDisplaySingleMarkdown(element) {
    const markdown = element.textContent || element.innerText;
    const html = convertMarkdownText(markdown);

    // Replace the element's content with the parsed HTML
    element.innerHTML = html;
}

// Converts text to markdown format 
function convertMarkdownText(markdown) {
    let html;

    if (!markdown.trim()) {
        return '';
    }

    try {
        // Convert markdown to HTML
        html = marked.parse(markdown);

        // Convert *text* to <em>text</em>
        html = html.replace(/(?:^|\s)\*([^\*\n]+)\*(?=$|\s)/g, (match, p1) => ` <em>${p1}</em>`);
    } catch (error) {
        console.error('Error parsing markdown:', error);
        // If there's an error, fall back to displaying the original markdown text
        html = markdown;
    }

    return html;
}

// convert all initial messages to markdown format
convertAndDisplayAllMarkdown();


// TIMESTAMPS

// Format current time (based on user's timezone)
function getCurrentFormattedTime() {
    let now = new Date();
    let hours = now.getHours();
    let minutes = now.getMinutes();
    let ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    minutes = minutes < 10 ? '0' + minutes : minutes;
    let strTime = hours + ':' + minutes + ' ' + ampm;
    return strTime;
}

// Purpose: Format timestamp for OLD message to a human-readable format
// Note: these are for messages retrieved from the database
function formatTimestamp(timestamp) {
    const utcDate = new Date(timestamp + 'Z');
    const now = new Date();

    // Compare dates without time
    const isToday = utcDate.toDateString() === now.toDateString();

    // Formatting options
    const timeOptions = { hour: '2-digit', minute: '2-digit', hour12: true };
    const dateOptions = { month: 'long', day: 'numeric', ...timeOptions };

    // Format based on whether it's today or another day
    const formatted = new Intl.DateTimeFormat('en-US', isToday ? timeOptions : dateOptions).format(utcDate);

    return formatted;
}

// Format timestamps of old messages
const timestamps = document.querySelectorAll('[data-timestamp]');
timestamps.forEach(element => {
    const rawTimestamp = element.getAttribute('data-timestamp');
    const formatted = formatTimestamp(rawTimestamp);
    element.textContent = formatted;
});



// HELPER FUNCTIONS

// Purpose: get the current credit amount from the display
function getCurrentCredits() {
    const creditsText = document.querySelector('.credits-text').textContent;
    return parseInt(creditsText, 10);
}

// Purpose: update the credit display
function updateCreditDisplay(newCredits) {
    document.querySelector('.credits-text').textContent = newCredits;
}

// Purpose: prevent user from sending message if there are no credits
function sufficientCredits() {
    let currentCredits = getCurrentCredits();
    return currentCredits >= MESSAGE_COST;
}


initializeExistingMessages();