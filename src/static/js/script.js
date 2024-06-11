// variables
let MESSAGE_COST = 1;
let creditsDisplay = document.querySelector('.credits-display');

// prevent user from sending message if there are no credits
function sufficientCredits() {
    let currentCredits = parseInt(creditsDisplay.textContent, 10);
    return currentCredits >= MESSAGE_COST;
}

// send chat message only if the user has enough credits
function sendChatMessage() {
    if (!sufficientCredits()) {
        alert('You do not have enough credits to send a message. Please either upgrade your plan or wait for your credits to refresh. Beta users can also reach out to us at info@pocketai.com for more credits.');
        return;
    }
    sendMessage();
}

// format all timestamps
const timestamps = document.querySelectorAll('[data-timestamp]');
timestamps.forEach(element => {
    const rawTimestamp = element.getAttribute('data-timestamp');
    const formatted = formatTimestamp(rawTimestamp);
    element.textContent = formatted;
});

// Purpose: Format a timestamp to a human-readable format
function formatTimestamp(timestamp) {
    const utcDate = new Date(timestamp + 'Z');
    const now = new Date();

    // Formatting options
    const timeOptions = { hour: '2-digit', minute: '2-digit', hour12: true };
    const dateOptions = { month: 'long', day: 'numeric', ...timeOptions };

    // Compare dates without time
    const isToday = utcDate.toDateString() === now.toDateString();

    // Format based on whether it's today or another day
    const formatted = new Intl.DateTimeFormat('en-US', isToday ? timeOptions : dateOptions).format(utcDate);

    return formatted;
}


// Purpose: Sends message to backend via fetch, waits, and displays bot response
function sendMessage() {
    creditsDisplay.textContent -= MESSAGE_COST;
    
    var messageInput = document.querySelector('.message-input');
    var message = messageInput.value.trim();
    var chatArea = document.querySelector('.chat-container > .message-area');

    if (!message) {
        return;
    }

    // Display user message
    var userMessageHtml = `
        <div class="message-container user-message">
            <div class="message-wrapper flex items-end gap-2 justify-end">
                <div class="message-bubble backdrop-blur-sm rounded-t-2xl rounded-bl-2xl p-3 max-w-[70%]" style="background-color:#7367F0;">
                    <p class="text-white">${message}</p>
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
    chatArea.innerHTML += userMessageHtml;

    // Display placeholder AI's response and play loading animation
    var botMessageHtml = `
        <div class="message-container bot-message">
            <div class="message-wrapper flex items-end gap-2 justify-start">
                <div class="avatar relative p-[2px] rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5]">
                    <img src="${AI_PROFILE_IMAGE}" width="40" height="40" alt="Avatar" class="rounded-full" style="aspect-ratio: 40 / 40; object-fit: cover;" />
                    <div class="status-indicator absolute -bottom-0.5 -right-0.5 rounded-full bg-gradient-to-br from-[#7367F0] to-[#9E95F5] p-[2px]">
                        <div class="rounded-full bg-white p-[2px]"></div>
                    </div>
                </div>
                <div class="ai-message-placeholder backdrop-blur-sm rounded-t-2xl rounded-br-2xl p-3 max-w-[70%]" style="background-color: #525252;">
                    <div class="loading-dots"><div></div><div></div><div></div></div>
                </div>
            </div>
            <div class="timestamp text-xs text-gray-500 mt-1">Now</div>
        </div>`;
    chatArea.innerHTML += botMessageHtml;

    // Scroll to the latest message
    chatArea.scrollTop = chatArea.scrollHeight;

    // Clear the message input
    messageInput.value = '';
    // Reset the height of the textarea
    autoGrow(messageInput);

    // Check if the message is not empty
    if (message) {
        fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ "message": message })
        })
            .then(response => response.json())
            .then(data => {
                var latestBotMessage = chatArea.querySelector('.bot-message:last-child');
                if (latestBotMessage) {
                    // fill the placeholder with the AI's response
                    var aiResponsePlaceholder = latestBotMessage.querySelector('.ai-message-placeholder');
                    var timestamp = latestBotMessage.querySelector('.timestamp');
                    if (aiResponsePlaceholder && timestamp) {
                        aiResponsePlaceholder.innerHTML = `<p class="text-white">${convertMarkdownToHtml(data.response)}</p>`;
                        timestamp.innerHTML = getCurrentFormattedTime();
                    }
                }

                // Scroll to the latest message
                chatArea.scrollTop = chatArea.scrollHeight;
            });
    }
}

// Formats the time
// WORK IN PROGRESS
function getCurrentFormattedTime() {
    var now = new Date();
    var hours = now.getHours();
    var minutes = now.getMinutes();
    var ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    minutes = minutes < 10 ? '0' + minutes : minutes;
    var strTime = hours + ':' + minutes + ' ' + ampm;
    return strTime;
}

// Purpose: Automatically adjust the height of the textarea to fit the content
function autoGrow(element) {
    // reset the height to default
    element.style.height = '1.5em';
    element.style.height = (element.scrollHeight) + "px";

    // Adjust the bottom panel's height
    var bottomPanel = document.querySelector('.bottom-panel');
    if (bottomPanel) {
        bottomPanel.style.height = 'auto';
    }

    // Set maximum height and enable scroll
    if (parseInt(element.style.height, 10) >= 200) {
        element.style.height = "200px";
        element.style.overflowY = "scroll";
    }
}


// Fetching more messages when scrolling up
var messageArea = document.querySelector('.message-area');
var isFetching = false;

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
    var chatArea = document.querySelector('.message-area');
    var currentMessageCount = chatArea.querySelectorAll('.message-container').length;
    var oldScrollHeight = chatArea.scrollHeight;

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
            var firstMessageContainer = chatArea.querySelector('.message-container:first-child');

            data.forEach(msg => {
                var messageHtml = '';
                var formattedMessage = convertMarkdownToHtml(msg.message);
                var formattedTimestamp = new Date(msg.timestamp).toLocaleString('en-US', {
                    month: 'short', 
                    day: 'numeric', 
                    hour: 'numeric', 
                    minute: 'numeric', 
                    hour12: true 
                });

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
                                <div class="message-bubble backdrop-blur-sm rounded-t-2xl rounded-br-2xl p-3 max-w-[70%]" style="background-color: #525252;">
                                    <p class="text-white">${formattedMessage}</p>
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
                                <div class="message-bubble backdrop-blur-sm rounded-t-2xl rounded-bl-2xl p-3 max-w-[70%]" style="background-color:#7367F0;">
                                    <p class="text-white">${formattedMessage}</p>
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

                var messageNode = document.createElement('div');
                messageNode.innerHTML = messageHtml;
                while (messageNode.firstChild) {
                    chatArea.insertBefore(messageNode.firstChild, firstMessageContainer);
                }
            });

            // Calculate the new scroll position to maintain the view
            var newScrollHeight = chatArea.scrollHeight;
            chatArea.scrollTop = newScrollHeight - oldScrollHeight;
        }
        
        isFetching = false;
    })
    .catch(error => {
        console.error('Error fetching more messages:', error);
        isFetching = false;
    });
}

// Purpose: Convert markdown text to HTML for better message formatting
// Note: The model generates markdown text, which is translated to HTML for display
// WORK IN PROGRESS
function convertMarkdownToHtml(text) {
    // Convert **bold** to <strong>bold</strong>
    let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Convert _italic_ to <em>italic</em>
    formattedText = formattedText.replace(/_(.*?)_/g, '<em>$1</em>');

    // Convert unordered lists (lines starting with - )
    formattedText = formattedText.replace(/(?:^|\n)-\s+(.*?)(?=\n|$)/g, '<li>$1</li>');
    formattedText = formattedText.replace(/(<li>.*<\/li>)+/g, '<ul>$&</ul>');

    // Convert ordered lists (lines starting with a number followed by a period)
    formattedText = formattedText.replace(/(?:^|\n)\d+\.\s+(.*?)(?=\n|$)/g, '<li>$1</li>');
    formattedText = formattedText.replace(/(<li>.*<\/li>)+/g, '<ol>$&</ol>');

    // Convert newlines to <br>, but not inside list items
    formattedText = formattedText.replace(/(?<!<\/li>)\n/g, '<br>');

    return formattedText;
}

// Purpose: Convert markdown text to HTML for all messages
const messages = document.querySelectorAll('.message-bubble p');
messages.forEach(message => {
    message.innerHTML = convertMarkdownToHtml(message.innerText);
});



// audio functionality (WIP)

// Attach event listener to the microphone button
document.querySelector('.mic-button').addEventListener('click', recordVoice);

let mediaRecorder;
let audioChunks = [];
let isRecording = false;

// Purpose: Records audio from the user's microphone and sends it to the server (same as sendMessage)
function recordVoice() {
    if (!isRecording) {
        // Start recording
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.start();

                mediaRecorder.addEventListener("dataavailable", event => {
                    audioChunks.push(event.data);
                });

                document.querySelector('.mic-button').style.color = 'red';

                mediaRecorder.addEventListener("stop", () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });

                    // Send the blob to the server
                    let formData = new FormData();
                    formData.append('audio', audioBlob);

                    fetch('/upload_audio', {
                        method: 'POST',
                        body: formData
                    })
                        .then(response => response.json())
                        .then(data => {
                            // Display the user's message and AI's response
                            displayMessages(data.user_message, data.ai_response);
                            console.log('Success:', data);
                        })
                        .catch((error) => {
                            console.error('Error:', error);
                        });

                    audioChunks = [];

                    document.querySelector('.mic-button').style.color = 'grey';
                });

                isRecording = true;
            })
            .catch(error => {
                console.error("Error accessing media devices.", error);
            });
    } else {
        // Stop recording
        mediaRecorder.stop();
        audioChunks = [];
        isRecording = false;
    }
}

// display messages after recording audio
function displayMessages(user_message, ai_response) {
    var chatArea = document.querySelector('.message-area');
    var messageInput = document.querySelector('.message-input');

    // Display user message
    var userMessageHtml = `<div class="message-container user-message flex flex-col">
                <div class="message-wrapper flex flex-row items-center justify-end">
                    <div class="text-sm bg-blue-100 text-blue-800 rounded-full rounded-br-none px-4 py-2">
                        ${user_message}
                    </div>
                    <div class="chat-profile-container">
                        <img src=${USER_PROFILE_IMAGE}
                             class="rounded-full">
                    </div>
                </div>
                <div class="timestamp-wrapper flex justify-end">
                    <div class="timestamp text-xs text-gray-500 mt-1 l">
                        ${getCurrentFormattedTime()}
                    </div>
                </div>
            </div>`;
    chatArea.innerHTML += userMessageHtml;

    // Display placeholder AI's response and play loading animation (???; gives the illusion of waiting)
    var botMessageHtml = `<div class="message-container bot-message flex flex-col">
                              <div class="message-wrapper flex flex-row items-center items-end">
                                  <div class="chat-profile-container">
                                      <img src=${AI_PROFILE_IMAGE} class="rounded-full">
                                  </div>
                                  <div class="ai-message-placeholder text-sm bg-blue-100 text-blue-800 rounded-full rounded-bl-none px-4 py-2">
                                    <div class="loading-dots"><div></div><div></div><div></div></div>
                                  </div>
                              </div>
                              <div class="timestamp text-xs text-gray-500 mt-1 l">Now</div>
                          </div>`;
    chatArea.innerHTML += botMessageHtml;

    // Scroll to the latest message
    chatArea.scrollTop = chatArea.scrollHeight;
    messageInput.value = '';
    autoGrow(messageInput);

    // Display AI's response
    var latestBotMessage = chatArea.querySelector('.bot-message:last-child');
    if (latestBotMessage) {
        var aiResponsePlaceholder = latestBotMessage.querySelector('.ai-message-placeholder');
        var timestamp = latestBotMessage.querySelector('.timestamp');
        if (aiResponsePlaceholder && timestamp) {
            aiResponsePlaceholder.innerHTML = ai_response;
            timestamp.innerHTML = getCurrentFormattedTime();
        }
    }

}