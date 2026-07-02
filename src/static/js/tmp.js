// Modify updateChatArea function
function updateChatArea(response, userMessageId, botMessageId, voiceUrl) {
    let latestBotMessage = chatArea.querySelector('.bot-message:last-child');
    let allUserMessages = chatArea.querySelectorAll('.user-message');
    let latestUserMessage = allUserMessages[allUserMessages.length - 1];

    if (latestBotMessage && latestUserMessage) {
        let aiResponsePlaceholder = latestBotMessage.querySelector('.ai-message-placeholder');
        let timestamp = latestBotMessage.querySelector('.timestamp');
        
        if (aiResponsePlaceholder && timestamp) {
            // Create message content with optional audio player
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

            // Add message IDs to containers
            latestUserMessage.dataset.messageId = userMessageId;
            latestBotMessage.dataset.messageId = botMessageId;

            // Initialize audio player if voice URL exists
            if (voiceUrl) {
                initializeAudioPlayer(latestBotMessage.querySelector('.audio-player'));
            }

            // Add hover panel
            createHoverPanel(latestBotMessage);
        }
    }
    chatArea.scrollTop = chatArea.scrollHeight;
}

// Add audio player initialization function
function initializeAudioPlayer(playerElement) {
    const audio = playerElement.querySelector('audio');
    const playPauseBtn = playerElement.querySelector('.play-pause-btn');
    const playIcon = playPauseBtn.querySelector('.play-icon');
    const pauseIcon = playPauseBtn.querySelector('.pause-icon');
    const progress = playerElement.querySelector('.progress');
    const timeDisplay = playerElement.querySelector('.time');

    // Update play/pause button
    function updatePlayButton(playing) {
        if (playing) {
            playIcon.classList.add('hidden');
            pauseIcon.classList.remove('hidden');
        } else {
            playIcon.classList.remove('hidden');
            pauseIcon.classList.add('hidden');
        }
    }

    // Format time in MM:SS
    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        seconds = Math.floor(seconds % 60);
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }

    // Play/Pause button click handler
    playPauseBtn.addEventListener('click', () => {
        if (audio.paused) {
            audio.play();
        } else {
            audio.pause();
        }
    });

    // Audio event listeners
    audio.addEventListener('play', () => updatePlayButton(true));
    audio.addEventListener('pause', () => updatePlayButton(false));
    audio.addEventListener('ended', () => updatePlayButton(false));

    audio.addEventListener('timeupdate', () => {
        const percent = (audio.currentTime / audio.duration) * 100;
        progress.style.width = `${percent}%`;
        timeDisplay.textContent = formatTime(audio.currentTime);
    });
}

// Modify sendMessage function to handle voice response
function sendMessage() {
    // ... existing code ...

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
            // Update chat area with text and voice
            updateChatArea(
                data.response,
                data.user_message_id,
                data.ai_message_id,
                data.voice_url
            );
            
            // Update credits
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