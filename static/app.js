// Global variables
let socket;
let mediaRecorder;  // For analysis only
let segmentRecorder = null;  // For actual recording of speech segments
let audioStream = null;  // Store the stream for reuse
let audioChunks = [];
let isRecording = false;
let isCallActive = false;
let sessionId = generateSessionId();
let callStartTime;
let durationInterval;
let silenceTimeout;
let audioContext;
let analyser;
let microphone;
let isAISpeaking = false;
let recordingStartTime = null;
let hasUserSpokenYet = false;  // Track if user has started speaking
let isFirstGreeting = false;  // Track if Sofia is giving initial greeting

// Segment recording state
let segmentActive = false;
let segmentStartMs = null;
let segmentChunks = []; // Collect chunks for current segment
let inFlightRequestId = null;
let currentRequestId = 0; // monotonically increasing request ids
let isProcessing = false; // STT/LLM/TTS in-flight on server

// UI Elements
const callButton = document.getElementById('callButton');
const phoneIcon = document.getElementById('phoneIcon');
const avatar = document.getElementById('avatar');
const micIcon = document.getElementById('micIcon');
const pulseWaves = document.getElementById('pulseWaves');
const waveform = document.getElementById('waveform');
const actionText = document.getElementById('actionText');
const statusText = document.getElementById('statusText');
const callDuration = document.getElementById('callDuration');
const assistantName = document.getElementById('assistantName');
const endCallButton = document.getElementById('endCallButton');
const conversationDisplay = document.getElementById('conversationDisplay');
const responseAudio = document.getElementById('responseAudio');
const interruptBadge = document.getElementById('interruptBadge');

// Generate unique session ID
function generateSessionId() {
    return 'session_' + Math.random().toString(36).substr(2, 9);
}

// Initialize Socket.IO connection
function initializeSocket() {
    socket = io();

    socket.on('connect', () => {
        console.log('Connected to server');
    });

    socket.on('connected', (data) => {
        console.log(data.status);
    });

    socket.on('ai_response', (data) => {
        const dataRequestId = typeof data.request_id === 'number' ? data.request_id : null;
        console.log('AI Response received:', data.text, 'request_id:', dataRequestId);
        if (data.audio) {
            console.log('Audio base64 length:', data.audio.length);
        }
        // Ignore stale responses
        if (dataRequestId !== null && dataRequestId < currentRequestId) {
            console.warn('Ignoring stale ai_response with request_id', dataRequestId, 'current is', currentRequestId);
            return;
        }
        // Clear in-flight state for matching request
        if (dataRequestId !== null && inFlightRequestId !== null && dataRequestId === inFlightRequestId) {
            inFlightRequestId = null;
            isProcessing = false;
        }
        playAIResponse(data.audio, data.text);
    });

    socket.on('user_text', (data) => {
        console.log('User said:', data.text);
        addToConversation('user', data.text);
    });

    socket.on('status', (data) => {
        console.log('Status:', data.message);
        showStatus(data.message);
    });

    socket.on('no_speech_detected', (data) => {
        console.log('No speech detected, continuing to listen');
        // Silently return to listening mode without showing error
        isProcessing = false;
        inFlightRequestId = null;
        if (isCallActive && !isAISpeaking) {
            startListening();
        }
    });

    socket.on('error', (data) => {
        console.error('Error:', data.message);
        showError(data.message);
    });

    socket.on('call_ended', (data) => {
        console.log('Call ended');
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server');
    });

    socket.on('start_listening', () => {
        console.log('Server requested to start listening immediately');
        if (isCallActive) {
            startListening();
        }
    });
}

// Start call
async function startCall() {
    if (isCallActive) return;

    try {
        // CRITICAL: Unlock audio context IMMEDIATELY on user click (before any async operations)
        // This ensures browser allows audio playback later
        try {
            const unlockAudio = new Audio();
            unlockAudio.src = 'data:audio/mp3;base64,SUQzBAAAAAABEVRYWFgAAAAtAAADY29tbWVudABCaWdTb3VuZEJhbmsuY29tIC8gTGFTb25vdGhlcXVlLm9yZwBURU5DAAAAHQAAA1N3aXRjaCBQbHVzIMKpIE5DSCBTb2Z0d2FyZQBUSVQyAAAABgAAAzIyMzUAVFNTRQAAAA8AAANMYXZmNTcuODMuMTAwAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
            unlockAudio.play().then(() => {
                console.log('Audio unlocked successfully');
                unlockAudio.pause();
                unlockAudio.remove();
            }).catch(() => {
                console.log("Audio unlock attempt (may fail, but that's ok)");
            });
        } catch (e) {
            console.log('Audio unlock error (not critical):', e);
        }

        isCallActive = true;
        isFirstGreeting = true;  // Mark that we're expecting the first greeting
        document.body.classList.add('call-active');

        // Trigger a quick ripple on click visual
        callButton.classList.add('ripple');
        setTimeout(() => callButton.classList.remove('ripple'), 600);

        // Change UI to calling state
        callButton.classList.remove('ready');
        callButton.classList.add('active', 'calling');
        phoneIcon.classList.add('hidden');
        avatar.classList.remove('hidden');
        pulseWaves.classList.remove('hidden');
        actionText.classList.add('hidden');
        statusText.classList.remove('hidden');
        statusText.textContent = "Bog'lanmoqda...";
        endCallButton.classList.remove('hidden');
        callDuration.classList.remove('hidden');

        // Start call duration timer
        callStartTime = Date.now();
        updateCallDuration();
        durationInterval = setInterval(updateCallDuration, 1000);

        // Initialize socket
        initializeSocket();

        // Request microphone access with noise/echo reduction
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1
            }
        });
        setupAudioContext(stream);

        // Enable audio context (fixes Chrome auto-play policy)
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
            console.log('Audio context resumed');
        }

        // Wait for socket connection
        await new Promise(resolve => {
            if (socket.connected) {
                resolve();
            } else {
                socket.on('connect', resolve);
            }
        });

        // Notify server to start call
        console.log('Requesting start_call with session:', sessionId);
        socket.emit('start_call', { session_id: sessionId });

        // Update status to show Sofia is preparing to speak
        statusText.textContent = "Sofia gaplashishga tayyor...";
        statusText.classList.remove('hidden');
        statusText.style.display = 'block';

        // Start unified VAD/monitoring loop (always-on)
        startUnifiedVAD();

    } catch (error) {
        console.error('Error starting call:', error);
        showError('Mikrofonni ishga tushirib bo\'lmadi');
        endCall();
    }
}

// Setup audio context for recording
function setupAudioContext(stream) {
    audioStream = stream;  // Store stream for creating segment recorders

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    microphone = audioContext.createMediaStreamSource(stream);
    microphone.connect(analyser);
    analyser.fftSize = 256;

    isRecording = true;
    console.log('Audio analysis ready');
}

// Start recording a speech segment
function startSegmentRecording() {
    if (segmentRecorder) {
        console.warn('Segment recorder already active');
        return;
    }

    const options = {
        mimeType: 'audio/webm;codecs=opus',
        audioBitsPerSecond: 128000
    };

    segmentRecorder = new MediaRecorder(audioStream, options);
    segmentChunks = [];

    segmentRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
            segmentChunks.push(event.data);
        }
    };

    segmentRecorder.onstop = () => {
        console.log('Segment recording stopped, chunks:', segmentChunks.length);
        if (segmentChunks.length > 0) {
            const blob = new Blob(segmentChunks, { type: 'audio/webm;codecs=opus' });
            console.log('Segment blob size:', blob.size);
            handleSegmentComplete(blob);
        }
        segmentRecorder = null;
        segmentChunks = [];
    };

    segmentRecorder.start(100);  // Collect in 100ms chunks
    console.log('Segment recording started');
}

// Stop recording current segment
function stopSegmentRecording() {
    if (segmentRecorder && segmentRecorder.state === 'recording') {
        segmentRecorder.stop();
    }
}

// Handle completed segment
function handleSegmentComplete(blob) {
    if (!blob || blob.size < 5000) {
        console.log('Segment blob too small, skipping. Size:', (blob ? blob.size : 0));
        // Silently return to listening
        if (isCallActive && !isAISpeaking) {
            startListening();
        }
        return;
    }

    // Validate WebM format (check for EBML header)
    const reader = new FileReader();
    reader.onload = (e) => {
        const arr = new Uint8Array(e.target.result);
        // Check for EBML header signature (0x1A 0x45 0xDF 0xA3)
        if (arr.length < 4 || arr[0] !== 0x1A || arr[1] !== 0x45 || arr[2] !== 0xDF || arr[3] !== 0xA3) {
            console.warn('Invalid WebM format detected, skipping segment');
            // Silently return to listening
            if (isCallActive && !isAISpeaking) {
                startListening();
            }
            return;
        }

        // Valid WebM file, proceed with sending
        console.log('Valid WebM segment, size:', blob.size);

        // UI: show processing
        statusText.textContent = "Analiz qilinmoqda...";
        statusText.classList.remove('hidden');
        callButton.classList.add('calling');
        callButton.classList.remove('user-speaking');

        // Issue new request id
        inFlightRequestId = ++currentRequestId;
        isProcessing = true;
        console.log('Sending segment, request_id', inFlightRequestId, 'bytes', blob.size);
        sendAudioToServer(blob, inFlightRequestId);
    };
    reader.readAsArrayBuffer(blob.slice(0, 4));
}

// Play AI response
function playAIResponse(audioBase64, text) {
    console.log('playAIResponse called with text:', text);

    // If no audio (TTS failed), just show text and start listening
    if (!audioBase64) {
        console.warn('No audio data provided - TTS may have failed');

        // Still show the text prominently
        addToConversation('ai', text);

        // Update UI to show AI responded (but no audio)
        callButton.classList.remove('calling', 'user-speaking');
        callButton.classList.add('ai-speaking');
        avatar.classList.add('pulsing');
        statusText.textContent = text;
        statusText.classList.remove('hidden');
        assistantName.classList.remove('hidden');

        // After showing the text briefly, switch to listening
        setTimeout(() => {
            avatar.classList.remove('pulsing');
            assistantName.classList.add('hidden');

            // If this was the first greeting without audio, enable barge-in now
            if (isFirstGreeting) {
                console.log('First greeting completed (no audio) - barge-in now enabled');
                isFirstGreeting = false;
            }

            if (isCallActive) {
                startListening();
            }
        }, 3000); // Slightly longer to give user time to read

        return;
    }

    isAISpeaking = true;

    // Update UI to AI speaking state
    callButton.classList.remove('calling', 'user-speaking');
    callButton.classList.add('ai-speaking');
    avatar.classList.add('pulsing');
    micIcon.classList.add('hidden');
    // Keep waveform available (always listening), but you may keep it subtle via CSS
    // waveform.classList.add('hidden');
    pulseWaves.classList.remove('inward');
    statusText.classList.add('hidden');
    assistantName.classList.remove('hidden');

    // Add to conversation
    addToConversation('ai', text);

    // Convert base64 to audio and play
    const audioData = 'data:audio/mp3;base64,' + audioBase64;
    console.log('Setting audio source, base64 length:', audioBase64.length);

    // Set volume to maximum
    responseAudio.volume = 1.0;
    responseAudio.src = audioData;

    responseAudio.onloadeddata = () => {
        console.log('Audio loaded, attempting to play...');
        console.log('Audio duration:', responseAudio.duration);
    };

    responseAudio.onerror = (e) => {
        console.error('Audio error:', e);
        console.error('Audio error details:', responseAudio.error);
    };

    responseAudio.onended = () => {
        console.log('Audio playback ended');
        isAISpeaking = false;
        avatar.classList.remove('pulsing');

        // After first greeting completes, enable barge-in for future responses
        if (isFirstGreeting) {
            console.log('First greeting completed - barge-in now enabled');
            isFirstGreeting = false;
        }

        // Immediately switch to listening mode for real-time feel
        if (isCallActive) {
            startListening();  // No delay
        }
    };

    // Play with promise handling (with autoplay workaround)
    responseAudio.muted = false;  // Ensure not muted
    const playPromise = responseAudio.play();

    if (playPromise !== undefined) {
        playPromise.then(() => {
            console.log('Audio playback started successfully');
        }).catch(err => {
            console.error('Error playing audio:', err);
            console.error('Error name:', err.name);
            console.error('Error message:', err.message);
            isAISpeaking = false;

            // If this was the first greeting and playback failed, enable barge-in
            if (isFirstGreeting) {
                console.log('First greeting playback failed - barge-in now enabled');
                isFirstGreeting = false;
            }

            // If initial greeting fails, still switch to listening
            if (text.includes('Assalomu alaykum')) {
                setTimeout(() => startListening(), 1000);
            } else {
                startListening();
            }
        });
    }
}

// Start listening to user
function startListening() {
    if (!isCallActive || isAISpeaking) return;

    console.log('Starting listening mode...');

    // Reset the flag when starting a new listening session after Sofia speaks
    hasUserSpokenYet = false;

    // Update UI to user speaking state
    callButton.classList.remove('ai-speaking', 'calling');
    callButton.classList.add('user-speaking');
    pulseWaves.classList.add('inward');
    micIcon.classList.remove('hidden');
    waveform.classList.remove('hidden');
    waveform.classList.add('active');
    assistantName.classList.add('hidden');

    // Show listening status prominently
    statusText.textContent = "Tinglanmoqda...";
    statusText.classList.remove('hidden');
    statusText.style.display = 'block'; // Force display

    // Visualization and monitoring are always running once call starts
    startAudioVisualization();
}


// Visualize audio levels in real-time
let visualizationAnimationId = null;
let reactiveAnimationId = null;
let smoothedVoiceLevel = 0; // 0..1

function startAudioVisualization() {
    if (!analyser || !waveform) return;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const waveBars = waveform.querySelectorAll('.wave-bar');

    function updateVisualization() {
        if (!isRecording) {
            // Stop visualization
            if (visualizationAnimationId) {
                cancelAnimationFrame(visualizationAnimationId);
                visualizationAnimationId = null;
            }
            if (reactiveAnimationId) {
                cancelAnimationFrame(reactiveAnimationId);
                reactiveAnimationId = null;
            }
            // Reset bars to minimum height
            waveBars.forEach(bar => {
                bar.style.height = '5px';
            });
            // Reset reactive vars
            document.documentElement.style.setProperty('--voice-level', '0');
            document.documentElement.style.setProperty('--ring-speed', '5s');
            document.documentElement.style.setProperty('--gradient-shift-speed', '8s');
            return;
        }

        analyser.getByteFrequencyData(dataArray);

        // Get different frequency ranges for each bar
        const barRanges = [
            { start: 0, end: 20 },    // Low frequencies
            { start: 20, end: 60 },   // Low-mid
            { start: 60, end: 120 },  // Mid
            { start: 120, end: 200 }, // High-mid
            { start: 200, end: 255 }  // High frequencies
        ];

        waveBars.forEach((bar, index) => {
            if (barRanges[index]) {
                const range = barRanges[index];
                let sum = 0;
                let count = 0;

                // Calculate average for this frequency range
                for (let i = range.start; i < Math.min(range.end, bufferLength); i++) {
                    sum += dataArray[i];
                    count++;
                }

                const average = count > 0 ? sum / count : 0;
                // Scale to height (5px min, 50px max)
                const height = Math.max(5, Math.min(50, (average / 255) * 50 + 5));
                bar.style.height = `${height}px`;
            }
        });

        // Compute overall level for reactive UI (EMA smoothing)
        let total = 0;
        for (let i = 0; i < bufferLength; i++) total += dataArray[i];
        const avg = total / bufferLength; // 0..255
        const level = Math.min(1, Math.max(0, avg / 140)); // normalize roughly
        // Exponential moving average to stabilize visuals
        smoothedVoiceLevel = smoothedVoiceLevel * 0.85 + level * 0.15;

        // Map level to ring speed (faster with louder voice) and gradient speed
        const ringSeconds = (5 - 3.2 * smoothedVoiceLevel).toFixed(2); // 5s .. ~1.8s
        const gradientSeconds = (8 - 4 * smoothedVoiceLevel).toFixed(2); // 8s .. 4s
        document.documentElement.style.setProperty('--voice-level', String(smoothedVoiceLevel.toFixed(3)));
        document.documentElement.style.setProperty('--ring-speed', `${ringSeconds}s`);
        document.documentElement.style.setProperty('--gradient-shift-speed', `${gradientSeconds}s`);

        // Continue animation
        visualizationAnimationId = requestAnimationFrame(updateVisualization);
    }

    // Start the visualization loop
    updateVisualization();
}

function stopAudioVisualization() {
    if (visualizationAnimationId) {
        cancelAnimationFrame(visualizationAnimationId);
        visualizationAnimationId = null;
    }
    if (reactiveAnimationId) {
        cancelAnimationFrame(reactiveAnimationId);
        reactiveAnimationId = null;
    }
    // Reset bars
    const waveBars = waveform.querySelectorAll('.wave-bar');
    waveBars.forEach(bar => {
        bar.style.height = '5px';
    });
    document.documentElement.style.setProperty('--voice-level', '0');
    document.documentElement.style.setProperty('--ring-speed', '5s');
    document.documentElement.style.setProperty('--gradient-shift-speed', '8s');
}

// Unified VAD: segmentation + barge-in + continuous listening
function startUnifiedVAD() {
    if (!analyser) return;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    let silenceStartTime = null;
    let consecutiveSilentChecks = 0;
    let consecutiveLoudChecks = 0;

    // Tunables - adjusted for better UX and reduced sensitivity
    const SILENCE_THRESHOLD = 35; // average gate (increased from 25 to reduce noise pickup)
    const PEAK_THRESHOLD = 130;   // peak gate (increased from 100 to reduce noise pickup)
    const CHECK_INTERVAL = 50;    // 50ms cadence
    const MIN_SEGMENT_MS = 800;   // don't send tiny segments
    const MAX_SEGMENT_MS = 20000; // safety cutoff (20s)
    const SILENCE_CUT_MS = 700;   // 0.7s trailing silence to finalize (as requested)
    const BARGE_IN_MS = 800;      // sustained loud speech to barge-in (faster)

    function finalizeAndSendSegment(endReason = 'silence') {
        const now = Date.now();
        if (!segmentActive || segmentStartMs === null) return;
        const segDur = now - segmentStartMs;

        if (segDur < MIN_SEGMENT_MS) {
            console.log('Segment too short to send, duration:', segDur);
            segmentActive = false;
            segmentStartMs = null;
            stopSegmentRecording();
            return;
        }

        console.log(`Finalizing segment (${endReason}), duration: ${segDur}ms`);
        segmentActive = false;
        segmentStartMs = null;

        // Stop the segment recorder - it will trigger handleSegmentComplete
        stopSegmentRecording();
    }

    function checkLoop() {
        if (!isCallActive || !isRecording) return;

        analyser.getByteFrequencyData(dataArray);

        // Average and peak
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
        const average = sum / bufferLength;
        const maxAmplitude = Math.max(...dataArray);

        const isLoud = (average > SILENCE_THRESHOLD && maxAmplitude > PEAK_THRESHOLD);

        if (isLoud) {
            consecutiveLoudChecks++;
            consecutiveSilentChecks = 0;
            silenceStartTime = null;

            if (!segmentActive && !isFirstGreeting) {
                // Start a new segment if none active AND not during first greeting
                segmentStartMs = Date.now();
                segmentActive = true;
                startSegmentRecording();
                console.log('Speech segment started');
            } else if (isFirstGreeting) {
                // During first greeting, ignore user's speech attempts
                console.log('Speech detected during first greeting - ignoring');
            }

            // Barge-in: if AI speaking or processing, and loud sustained >= 0.8s
            // BUT: Never allow barge-in during the first greeting
            if ((isAISpeaking || isProcessing) && (consecutiveLoudChecks * CHECK_INTERVAL >= BARGE_IN_MS) && !isFirstGreeting) {
                console.log('Barge-in detected');

                // Cancel TTS playback immediately
                try { responseAudio.pause(); } catch (e) {}
                isAISpeaking = false;
                avatar.classList.remove('pulsing');
                callButton.classList.add('user-speaking');
                callButton.classList.remove('ai-speaking');
                micIcon.classList.remove('hidden');
                waveform.classList.remove('hidden');
                waveform.classList.add('active');
                assistantName.classList.add('hidden');

                // Notify server to cancel work-in-progress
                const cancelId = inFlightRequestId != null ? inFlightRequestId : currentRequestId;
                if (socket && cancelId != null) {
                    socket.emit('interrupt', { session_id: sessionId, request_id: cancelId });
                }
                isProcessing = false;
                inFlightRequestId = null;

                // Subtle UI indicator: flash halo and show badge briefly
                try {
                    callButton.classList.add('interrupt-flash');
                    interruptBadge.classList.add('show');
                    setTimeout(() => {
                        callButton.classList.remove('interrupt-flash');
                        interruptBadge.classList.remove('show');
                    }, 900);
                } catch (e) {}

                // Reset barge-in counter
                consecutiveLoudChecks = 0;
            }
        } else {
            consecutiveSilentChecks++;
            if (consecutiveSilentChecks >= 4) { // require ~200ms stability before counting silence
                if (silenceStartTime == null) silenceStartTime = Date.now();
                const silenceDuration = Date.now() - silenceStartTime;

                if (segmentActive) {
                    const segDur = Date.now() - segmentStartMs;
                    // Finalize if enough trailing silence and minimum duration reached
                    if (silenceDuration >= SILENCE_CUT_MS && segDur >= MIN_SEGMENT_MS) {
                        finalizeAndSendSegment('silence');
                        // Prepare for potential next segment; keep listening
                        consecutiveSilentChecks = 0;
                        silenceStartTime = null;
                    } else if (segDur >= MAX_SEGMENT_MS) {
                        finalizeAndSendSegment('max_duration');
                        consecutiveSilentChecks = 0;
                        silenceStartTime = null;
                    }
                }
            }
            consecutiveLoudChecks = 0;
        }

        setTimeout(checkLoop, CHECK_INTERVAL);
    }

    console.log('Starting unified VAD...');
    checkLoop();
}

// Send audio to server
function sendAudioToServer(audioBlob, requestId) {
    const reader = new FileReader();
    reader.readAsDataURL(audioBlob);
    reader.onloadend = () => {
        const base64Audio = reader.result.split(',')[1];
        const payload = {
            session_id: sessionId,
            audio: base64Audio,
            request_id: typeof requestId === 'number' ? requestId : undefined
        };
        socket.emit('process_audio', payload);
    };
}

// End call
function endCall() {
    isCallActive = false;
    isRecording = false;
    isAISpeaking = false;
    isProcessing = false;
    isFirstGreeting = false;  // Reset first greeting flag

    // Stop segment recording
    if (segmentRecorder && segmentRecorder.state === 'recording') {
        segmentRecorder.stop();
        segmentRecorder = null;
    }

    // Stop audio stream
    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
    }

    // Stop audio playback
    responseAudio.pause();
    responseAudio.src = '';

    // Clear timers
    if (durationInterval) {
        clearInterval(durationInterval);
    }
    if (silenceTimeout) {
        clearTimeout(silenceTimeout);
    }

    // Close audio context
    if (audioContext) {
        audioContext.close();
    }

    // Notify server
    if (socket) {
        socket.emit('end_call', { session_id: sessionId });
        socket.disconnect();
    }

    // Reset UI to ready state
    document.body.classList.remove('call-active');
    callButton.classList.remove('active', 'calling', 'ai-speaking', 'user-speaking', 'error');
    callButton.classList.add('ready');
    phoneIcon.classList.remove('hidden');
    avatar.classList.add('hidden');
    avatar.classList.remove('pulsing');
    micIcon.classList.add('hidden');
    pulseWaves.classList.add('hidden');
    pulseWaves.classList.remove('inward');
    waveform.classList.add('hidden');
    waveform.classList.remove('active');
    actionText.classList.remove('hidden');
    statusText.classList.add('hidden');
    callDuration.classList.add('hidden');
    assistantName.classList.add('hidden');
    endCallButton.classList.add('hidden');
    conversationDisplay.classList.add('hidden');
    conversationDisplay.innerHTML = '';

    // Generate new session ID for next call
    sessionId = generateSessionId();
}

// Update call duration display
function updateCallDuration() {
    const elapsed = Math.floor((Date.now() - callStartTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    callDuration.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

// Show status message
function showStatus(message) {
    statusText.textContent = message;
    statusText.classList.remove('hidden');
}

// Show error
function showError(message) {
    callButton.classList.add('error');
    statusText.textContent = message;
    statusText.classList.remove('hidden');

    setTimeout(() => {
        callButton.classList.remove('error');
        if (isCallActive && !isAISpeaking && !isRecording) {
            startListening();
        }
    }, 2000);
}

// Add to conversation display
function addToConversation(sender, text) {
    const messageDiv = document.createElement('p');
    messageDiv.className = sender === 'user' ? 'user-message' : 'ai-message';
    messageDiv.textContent = `${sender === 'user' ? 'Siz' : 'Sofia'}: ${text}`;
    conversationDisplay.appendChild(messageDiv);

    // Auto-scroll to bottom
    conversationDisplay.scrollTop = conversationDisplay.scrollHeight;

    // Show conversation display (optional - for debugging)
    // conversationDisplay.classList.remove('hidden');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Sofia Voice Assistant initialized');
});
