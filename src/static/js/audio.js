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