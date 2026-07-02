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

    let userMessageContent;

    try {
        userMessageContent = previousUserMessage.querySelector('.message-bubble').textContent.trim();
    } catch (error) {
        userMessageContent = 'None';
    }

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
            console.log(data.deleted_ids); // debug
            // remove all subsequent messages
            for (let id of data.deleted_ids) {
                console.log(id); // debug
                removeMessage(id);
            }
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

// Add these functions at the appropriate place in chat.js

// Function to handle message editing
function editMessage(messageId, newContent) {
    fetch('/edit_message', {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message_id: messageId,
            new_content: newContent
        })
    })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw err; });
            }
            return response.json();
        })
        .then(data => {
            // Update the message content in the UI
            const messageContainer = document.querySelector(`[data-message-id="${messageId}"]`);
            const messageContent = messageContainer.querySelector('.message-bubble p');
            messageContent.innerHTML = convertMarkdownText(newContent);
        })
        .catch(error => {
            console.error('Error:', error);
            displayErrorMessage('Failed to edit message. Please try again.');
        });
}

// Modify the createHoverPanel function to handle both user and bot messages
function createHoverPanel(messageContainer) {
    let messageWrapper = messageContainer.querySelector('.message-wrapper');

    // Don't create hover panel if it already exists
    if (messageWrapper.querySelector('.hover-panel')) {
        return;
    }

    const isUserMessage = messageContainer.classList.contains('user-message');
    console.log('Is user message:', isUserMessage);

    let hoverPanelHtml;
    let position;
    if (isUserMessage) {
        hoverPanelHtml = `
            <div class="hover-panel hide">
                <button class="hover-panel-btn edit-btn">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
                    </svg>
                    Edit
                </button>
                <button class="hover-panel-btn copy-btn">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
                        <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
                    </svg>
                    Copy
                </button>
            </div>`;
        position = 'afterBegin';
    } else {
        hoverPanelHtml = `<div class="hover-panel hide">
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
        position = 'beforeEnd';
    }

    messageWrapper.insertAdjacentHTML(position, hoverPanelHtml);

    const panel = messageWrapper.querySelector('.hover-panel');
    const copyBtn = panel.querySelector('.copy-btn');

    if (isUserMessage) {
        const editBtn = panel.querySelector('.edit-btn');
        editBtn.addEventListener('click', () => {
            const messageContent = messageWrapper.querySelector('.message-bubble p').textContent;
            const messageId = messageContainer.dataset.messageId;

            // Create edit form
            const editForm = document.createElement('div');
            // Update this part of the createHoverPanel function where we create the edit form
            editForm.className = 'edit-form w-[70%] space-y-2 flex-col mb-2';
            editForm.innerHTML = `
            <textarea 
                class="w-full p-3 bg-transparent border-2 border-[#7367F0] rounded-lg focus:ring-2 focus:ring-[#9E95F5] focus:border-[#7367F0] resize-none outline-none transition-all duration-300"
                style="min-height: 6rem;">${messageContent}</textarea>
            <div class="flex gap-2 justify-end">
                <button class="panel-btn-save confirm-edit-btn flex items-center gap-2 px-3 py-1.5 bg-[#7367F0] hover:bg-[#5f53eb] backdrop-blur-sm rounded-md text-sm font-medium text-white transition-colors">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" style="fill: none; stroke: white;" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M20 6L9 17L4 12"></path>
                    </svg>
                    Save
                </button>
                <button class="panel-btn-cancel text-gray-600 border border-gray-600">
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" style="fill: none; stroke: gray;" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                    Cancel
                </button>
            </div>`;

            // Replace message content with edit form
            const messageBubble = messageWrapper.querySelector('.message-bubble');
            messageBubble.style.display = 'none';
            messageBubble.insertAdjacentElement('afterend', editForm);

            // Focus textarea
            const textarea = editForm.querySelector('textarea');
            textarea.focus();

            // Handle cancel
            editForm.querySelector('.panel-btn-cancel').addEventListener('click', () => {
                editForm.remove();
                messageBubble.style.display = 'block';
            });

            // Handle confirm
            editForm.querySelector('.panel-btn-save').addEventListener('click', () => {
                const newContent = textarea.value.trim();
                if (newContent) {
                    editMessage(messageId, newContent);
                    editForm.remove();
                    messageBubble.style.display = 'block';
                }
            });
        });
    } else {
        const retryBtn = panel.querySelector('.retry-btn');
        retryBtn.addEventListener('click', () => regenerateMessage(messageWrapper));
    }

    copyBtn.addEventListener('click', () => copyMessageContent(messageContainer));


    // Modify the hover event listeners to check for active edit form
    messageWrapper.addEventListener('mouseenter', () => {
        // Only show hover panel if there's no active edit form
        if (!messageWrapper.querySelector('.edit-form')) {
            panel.classList.remove('hide');
            panel.classList.add('show');
            panel.style.display = 'flex';
        }
    });

    messageWrapper.addEventListener('mouseleave', () => {
        panel.classList.remove('show');
        panel.classList.add('hide');
        setTimeout(() => {
            if (panel.classList.contains('hide')) {
                panel.style.display = 'none';
            }
        }, 300);
    });
}


// initialize hover panels for existing bot messages
function initializeExistingMessages() {
    const existingMessages = document.querySelectorAll('.message-container');
    console.log(existingMessages);
    existingMessages.forEach(messageContainer => {
        if (!messageContainer.querySelector('.hover-panel')) {
            createHoverPanel(messageContainer);
        }
    });
}

// function createHoverPanel(messageContainer) {
//     let messageWrapper = messageContainer.querySelector('.message-wrapper');
//     console.log(messageWrapper); // debug

//     if (messageWrapper.querySelector('.hover-panel')) {
//         return; // Panel already exists, no need to create a new one
//     }

//     let hoverPanel = `<div class="hover-panel hide">
//                         <button class="hover-panel-btn retry-btn">
//                             <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
//                                 <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.3"/>
//                             </svg>
//                             Retry
//                         </button>
//                         <button class="hover-panel-btn copy-btn">
//                             <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
//                                 <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
//                                 <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
//                             </svg>
//                             Copy
//                         </button>
//                     </div>`;

//     messageWrapper.insertAdjacentHTML('beforeend', hoverPanel);

//     const panel = messageContainer.querySelector('.hover-panel');
//     const retryBtn = panel.querySelector('.retry-btn');
//     const copyBtn = panel.querySelector('.copy-btn');

//     retryBtn.addEventListener('click', () => regenerateMessage(messageWrapper));
//     // copyBtn.addEventListener('click', () => copyMessageContent(messageContainer));

//     messageWrapper.addEventListener('mouseenter', () => {
//         panel.classList.remove('hide');
//         panel.classList.add('show');
//         panel.style.display = 'flex';
//     });

//     messageWrapper.addEventListener('mouseleave', () => {
//         panel.classList.remove('show');
//         panel.classList.add('hide');

//         setTimeout(() => {
//             if (panel.classList.contains('hide')) {
//                 panel.style.display = 'none';
//             }
//         }, 300);
//     });
// }


// Copy message content to clipboard
function copyMessageContent(messageContainer) {
    const messageContent = messageContainer.querySelector('.message-bubble p').textContent;

    // Use the newer clipboard API if available
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(messageContent)
            .then(() => {
                // Show success feedback
                const copyBtn = messageContainer.querySelector('.copy-btn');
                const originalText = copyBtn.innerHTML;

                // Change button text/icon to show success
                copyBtn.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    Copied!
                `;

                // Reset button after 2 seconds
                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                }, 2000);
            })
            .catch((err) => {
                console.error('Failed to copy text: ', err);
                displayErrorMessage('Failed to copy text to clipboard');
            });
    } else {
        // Fallback for older browsers
        try {
            // Create temporary textarea
            const textArea = document.createElement('textarea');
            textArea.value = messageContent;
            textArea.style.position = 'fixed';  // Avoid scrolling to bottom
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);

            // Select and copy
            textArea.select();
            document.execCommand('copy');

            // Cleanup
            document.body.removeChild(textArea);

            // Show success feedback
            const copyBtn = messageContainer.querySelector('.copy-btn');
            const originalText = copyBtn.innerHTML;

            copyBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                Copied!
            `;

            setTimeout(() => {
                copyBtn.innerHTML = originalText;
            }, 2000);
        } catch (err) {
            console.error('Failed to copy text: ', err);
            displayErrorMessage('Failed to copy text to clipboard');
        }
    }
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
                updateChatArea(
                    data.response, 
                    data.user_message_id, 
                    data.ai_message_id,
                    data.voice_url
                );

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
function updateChatArea(response, userMessageId, botMessageId, voiceUrl) {
    let latestBotMessage = chatArea.querySelector('.bot-message:last-child');
    let allUserMessages = chatArea.querySelectorAll('.user-message');
    let latestUserMessage = allUserMessages[allUserMessages.length - 1];

    console.log(latestUserMessage);

    if (latestBotMessage && latestUserMessage) {
        let aiResponsePlaceholder = latestBotMessage.querySelector('.ai-message-placeholder');
        let timestamp = latestBotMessage.querySelector('.timestamp');
        if (aiResponsePlaceholder && timestamp) {

            // message content with optional audio player
            let messageContent = `
                <div class="message-content">
                    <p class="invert-text markdown-content">${convertMarkdownText(response)}</p>
                    ${voiceUrl ? `
                        <div class="audio-player mt-2 flex items-center gap-2">
                            <audio src="${voiceUrl}" class="hidden" autoplay></audio>
                            <button class="play-pause-btn p-1 rounded-full hover:bg-gray-700/20">
                                <svg class="pause-icon w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="6" y="4" width="4" height="16"/>
                                    <rect x="14" y="4" width="4" height="16"/>
                                </svg>
                                <svg class="play-icon hidden w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polygon points="5 3 19 12 5 21"/>
                                </svg>
                            </button>
                            <div class="progress-container flex-1 h-1 bg-gray-700/20 rounded-full">
                                <div class="progress h-full bg-[#7367F0] rounded-full" style="width: 0%"></div>
                            </div>
                            <span class="time text-xs text-gray-500">0:00</span>
                        </div>
                    ` : ''}
                </div>`;

            aiResponsePlaceholder.innerHTML = messageContent;
            timestamp.innerHTML = getCurrentFormattedTime();

            console.log(latestBotMessage);
            console.log(botMessageId);

            // Add message ID to the container
            latestUserMessage.dataset.messageId = userMessageId;
            latestBotMessage.dataset.messageId = botMessageId;

            // Initialize tool copy buttons
            initializeToolCopyButtons();

            // Initialize audio player if voice URL exists
            if (voiceUrl) {
                initializeAudioPlayer(latestBotMessage.querySelector('.audio-player'));
            }

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

function convertMarkdownText(markdown) {
    if (!markdown.trim()) {
      return '';
    }
  
    const renderer = new marked.Renderer();
  
    renderer.code = (code, lang) => {

        const pattern = /<ToolType>\[([^\]]+)]<\/ToolType>/;
        const match = code.text.match(pattern);
        console.log(match); // debug
        const defaultTitle = 'Tool Call';
  
        return `
            <div class="mt-4 rounded-lg overflow-hidden border border-[#7367F0]/20">
            <div class="bg-[#7367F0]/10 px-4 py-2 flex justify-between items-center">
                <div class="flex items-center gap-2">
                <span class="h-2 w-2 rounded-full bg-[#7367F0]"></span>
                <span class="text-sm font-medium text-[#7367F0]">${match || defaultTitle}</span>
                </div>
                <button class="p-1 hover:bg-[#7367F0]/20 rounded transition-colors tool-copy-button">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"
                    viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                    class="text-[#7367F0]">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
                </button>
            </div>
            <div class="bg-[#7367F0]/5 p-4">
                <pre class="text-sm whitespace-pre-wrap font-mono invert-text">${code.text.trim()}</pre>
            </div>
            </div>
        `;
    };
  
    let html;
    try {
      html = marked.parse(markdown, { renderer });
      // Additional post-processing if desired
      html = html.replace(/(?:^|\s)\*([^\*\n]+)\*(?=$|\s)/g, (match, p1) => ` <em>${p1}</em>`);
    } catch (error) {
      console.error('Error parsing markdown:', error);
      // Fallback to raw markdown if something fails
      html = markdown;
    }
  
    return html;
  }
  

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


// Purpose: finds and removes a message given a messageID
function removeMessage(messageId) {
    // find the message container using the msg id
    const messageContainer = document.querySelector(`[data-message-id="${messageId}"]`);

    console.log(messageContainer); // debug

    if (messageContainer) {
        // remove hover panels
        const hoverPanel = messageContainer.querySelector('.hover-panel');
        if (hoverPanel) {
            hoverPanel.remove();
        }

        // then remove entire message container
        messageContainer.remove();
    }
}


// initializes audio player
function initializeAudioPlayer(playerElement) {
    const audio = playerElement.querySelector('audio');
    const playPauseBtn = playerElement.querySelector('.play-pause-btn');
    const playIcon = playPauseBtn.querySelector('.play-icon');
    const pauseIcon = playPauseBtn.querySelector('.pause-icon');
    const progress = playerElement.querySelector('.progress');
    const timeDisplay = playerElement.querySelector('.time');

    // update the play/pause button
    function updatePlayButton(playing) {
        if (playing) {
            playIcon.classList.add('hidden');
            pauseIcon.classList.remove('hidden');
        } else {
            playIcon.classList.remove('hidden');
            pauseIcon.classList.add('hidden');
        }
    }

    // formats time in MM:SS
    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        seconds = Math.floor(seconds % 60);
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }

    // handles play/pause buttons
    playPauseBtn.addEventListener('click', () => {
        if (audio.paused) {
            audio.play();
        } else {
            audio.pause();
        }
    });

    // audio event listeners
    audio.addEventListener('play', () => updatePlayButton(true));
    audio.addEventListener('pause', () => updatePlayButton(false));
    audio.addEventListener('ended', () => updatePlayButton(false));

    audio.addEventListener('timeupdate', () => {
        const percent = (audio.currentTime / audio.duration) * 100;
        progress.style.width = `${percent}%`;
        timeDisplay.textContent = formatTime(audio.currentTime);
    });
}

// Add click handler for copy buttons after updating chat area
function initializeToolCopyButtons() {
    document.querySelectorAll('.tool-copy-button').forEach(button => {
        button.addEventListener('click', function() {
            const toolOutput = this.closest('.rounded-lg').querySelector('pre').textContent;
            navigator.clipboard.writeText(toolOutput).then(() => {
                // Show feedback
                const originalHTML = this.innerHTML;
                this.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-[#7367F0]">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                `;
                setTimeout(() => {
                    this.innerHTML = originalHTML;
                }, 2000);
            });
        });
    });
}

// Initialize markdown conversion and UI elements
function initializeChat() {
    // Convert all markdown content
    const markdownElements = document.querySelectorAll('.markdown-content');
    markdownElements.forEach((element, index) => {
        const markdown = element.textContent || element.innerText;
        console.log(`Processing message ${index}:`, {
            original: markdown,
            isToolOutput: markdown.includes('<pre><code>Tool:')
        });
        const html = convertMarkdownText(markdown);
        console.log(`Converted message ${index}:`, html);
        element.innerHTML = html;
    });

    // Initialize UI elements
    initializeToolCopyButtons();
    initializeExistingMessages();
}

initializeChat();