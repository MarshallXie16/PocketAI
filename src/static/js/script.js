document.addEventListener('DOMContentLoaded', (event) => {
    // Find all elements with a data-timestamp attribute
    const timestamps = document.querySelectorAll('[data-timestamp]');

    timestamps.forEach(element => {
        const rawTimestamp = element.getAttribute('data-timestamp');
        const formatted = formatTimestamp(rawTimestamp);
        element.textContent = formatted;
    });
});


function autoGrow(element) {
    element.style.height = '1.5em';  // Reset height to shrink back if text is removed
    element.style.height = (element.scrollHeight) + "px";  // Set height to fit all content

    // Adjust the bottom panel's height
    var bottomPanel = document.querySelector('.bottom-panel');
    if (bottomPanel) {
        bottomPanel.style.height = 'auto';  // Allow bottom panel to grow
    }

    // Set maximum height and enable scroll
    if (parseInt(element.style.height, 10) >= 200) {
        element.style.height = "200px";
        element.style.overflowY = "scroll";
    }
}


function formatTimestamp(timestamp) {
    const utcDate = new Date(timestamp + 'Z'); // Add 'Z' to indicate UTC
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

function sendMessage() {
    var messageInput = document.querySelector('.message-input');
    var message = messageInput.value.trim();
    var chatArea = document.querySelector('.chat-container > .message-area');

    console.log(message);

    // Display user message
    var userMessageHtml = `<div class="message-container user-message flex flex-col">
                <div class="message-wrapper flex flex-row items-center justify-end">
                    <div class="text-sm bg-blue-100 text-blue-800 rounded-full rounded-br-none px-4 py-2">
                        ${message}
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

    // Display placeholder AI's response and play loading animation
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

    // Clear the message input
    messageInput.value = '';
    // Reset the height of the textarea
    autoGrow(messageInput);

    // Check if the message is not empty
    // remove ability to send empty message (!!!)
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
            console.log(`latest bot message: ${latestBotMessage}`);
            if (latestBotMessage) {
                var aiResponsePlaceholder = latestBotMessage.querySelector('.ai-message-placeholder');
                var timestamp = latestBotMessage.querySelector('.timestamp');
                if (aiResponsePlaceholder && timestamp) {
                    aiResponsePlaceholder.innerHTML = data.response;
                    timestamp.innerHTML = getCurrentFormattedTime();
                }
            }

            // Scroll to the latest message
            chatArea.scrollTop = chatArea.scrollHeight;

        });
    }
}

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

let mediaRecorder;
let audioChunks = [];
let isRecording = false;

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

// Attach event listener to the microphone button
document.querySelector('.mic-button').addEventListener('click', recordVoice);

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