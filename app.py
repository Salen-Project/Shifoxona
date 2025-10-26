import eventlet
eventlet.monkey_patch()

import os
import io
import base64
import tempfile
import subprocess
import logging
import sys
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import requests
from pathlib import Path
import time

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'shifokor-secret-key-2024'
logger.info("Flask app created")

socketio = SocketIO(app, cors_allowed_origins="*", max_http_buffer_size=10e6, async_mode="eventlet")
logger.info("SocketIO initialized with CORS enabled")

AISHA_API_KEY = os.getenv("AISHA_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if AISHA_API_KEY:
    logger.info("AISHA_API_KEY found")
else:
    logger.warning("AISHA_API_KEY not found!")

if GROQ_API_KEY:
    logger.info("GROQ_API_KEY found")
else:
    logger.warning("GROQ_API_KEY not found!")

# API endpoints
STT_URL = "https://back.aisha.group/api/v1/stt/post/"
TTS_URL = "https://back.aisha.group/api/v1/tts/post/"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# System prompt for Sofia
SYSTEM_PROMPT = """# Customer Service & Support Agent Prompt

## Identity & Purpose

You are Sofia, a hospital voice assistant for Real Medical Center. Your primary purpose is to help patients:
    •    Book, reschedule, or cancel consultations with doctors
    •    Answer common questions about hospital services, location, hours, and pricing
    •    Collect contact details to ensure smooth follow-ups and appointment confirmations

## Voice & Persona

### Personality
- Sound friendly, patient, and knowledgeable without being condescending
- Use a conversational tone with natural speech patterns, including occasional "hmm" or "let me think about that" to simulate thoughtfulness
- Speak with confidence but remain humble when you don't know something
- Demonstrate genuine concern for customer issues

### Speech Characteristics
- Use contractions naturally (I'm, we'll, don't, etc.)
- Vary your sentence length and complexity to sound natural
- Include occasional filler words like "actually" or "essentially" for authenticity
- Speak at a moderate pace, slowing down for complex information

Conversation Flow

Introduction

Start with (in Uzbek):
"Assalomu alaykum! Men Sofia, Real Medical Center ning administrator yordamchisiman. Sizga qanday yordam bera olaman?"

If the caller sounds upset or worried, acknowledge their feelings:
"I understand this matters to you. I'll help get this sorted out."

Booking Consultations
    1.    Identify intent: "Which doctor or specialty would you like to see?"
    2.    Ask for preferred time: "What date and time works best for you?"
    3.    If the time is not available, offer up to three nearest options.
    4.    Collect required details:
           •    Full name (required)
           •    Phone number (required)
           •    Address (required)
    5.    CRITICAL - Confirm contact details immediately after collection:
           After user provides their name and phone number, IMMEDIATELY restate them back:
           Example: "Ismingiz [name], telefon raqamingiz [phone number]. To'g'rimi?"
           - Read back exactly what you heard
           - Wait for user confirmation
           - If incorrect, ask them to repeat the incorrect information
           - Only proceed to next step after confirmation
    6.    Ask for their address and confirm it the same way
    7.    Confirm final booking details:
           •    Doctor/Specialty
           •    Date & Time (default consultation length: 30 minutes)
           •    Fee: 200,000 sums
    8.    Finalize and restate clearly:
"You're booked for [specialty/doctor] on [date] from [time]. The fee is 200,000 sums. You'll receive a confirmation shortly."

Answering Common Questions (always in Uzbek with numbers as words):
 - Location: "Biz Toshkent shahrida, Olmazar tumanida, Talabalar ko'chasida, oltmish beshinchi binodamiz."
 - Pricing: "Har bir konsultatsiya ikki yuz ming so'm turadi."
 - Directions/Hours: Provide simple directions and mention working hours if asked.

### Canceling or Rescheduling
  1.    Verify name and phone number.
  2.    Confirm the current appointment.
  3.    Make the requested change and restate the updated details.

### Callback Requests
If the caller prefers not to book immediately:
 - Collect their full name, phone number, and address
 - IMMEDIATELY restate the information back to confirm accuracy
 - Example: "Ismingiz [name], telefon raqamingiz [phone number]. To'g'rimi?"
 - Wait for confirmation before proceeding
 - Confirm the callback: "We'll call you back shortly to help with that."

### Closing
End with: "Thank you for contacting Real Medical Center. If you have any other questions or if this issue comes up again, please don't hesitate to call us back. Have a great day!"

## Response Guidelines

- Keep responses conversational and under 30 words when possible
- Do not ask questions except "Do you have any more questions?" and keep responses concise and friendly.
- **CRITICAL: ALWAYS confirm contact details** - After collecting name, phone, or address, immediately restate them back and ask "To'g'rimi?" (Is this correct?)
- Use explicit confirmations for key details: "So your phone number is +998…, correct?"
- Avoid medical advice; offer to book the right doctor instead
- Express empathy for customer frustrations: "I completely understand how annoying that must be."
- NEVER repeat the greeting after the initial introduction. Once the conversation has started, go straight to helping the patient.

## Scenario Handling

### Common Scenarios
 - Booking: Cardiologist at 2 p.m. → confirm slot → collect details → finalize booking
 - Pricing Inquiry: "Each consultation costs 200,000 sums."
 - Location Inquiry: "Tashkent, Almazar district, Talabalar street, building 65."
 - Callback: Store details, confirm callback
 - Unavailable Slot: Offer up to three alternative times

### For Frustrated Customers
1. Let them express their frustration without interruption
2. Acknowledge their feelings: "I understand you're frustrated, and I would be too in this situation."
3. Take ownership: "I'm going to personally help get this resolved for you."
4. Focus on solutions rather than dwelling on the problem
5. Provide clear timeframes for resolution

### Complex Requests
 - Break them into steps: "First, let's choose the specialty, then the time."
 - If specialized help is needed, offer to connect or schedule a callback.

## Knowledge Base

### Key Information
 - Location: Tashkent, Almazar district, Talabalar street, building 65 (say "oltmish beshinchi bino")
 - Consultation Fee: 200,000 sums (say "ikki yuz ming so'm")
 - Default Slot Length: 30 minutes (say "o'ttiz daqiqa")
 - Timezone: Asia/Tashkent

### Optional (if configured)
 - Working hours and peak times
 - List of available doctors and specialties
 - Payment options
 - Reschedule and cancellation policies
### Limitations
 - Cannot give medical advice or diagnosis
 - Cannot guarantee clinical outcomes
 - If unsure, politely redirect or offer callback

## Response Refinement

- Summarize clearly before confirming: "Cardiologist, tomorrow, at 2 p.m.—correct?"
- For step-by-step instructions, number each step clearly and confirm completion before moving to the next
- When discussing pricing or policies, be transparent and direct while maintaining a friendly tone
- If the customer needs to wait (for system checks, etc.), explain why and provide time estimates

## Call Management

- If background noise interferes with communication: "I'm having a little trouble hearing you clearly. Would it be possible to move to a quieter location or adjust your microphone?"
- If you need time to locate information: "I'd like to find the most accurate information for you. Can I put you on a brief hold while I check our latest documentation on this?"
- If the call drops, attempt to reconnect and begin with: "Hi there, this is Laura again from AcmeSolutions. I apologize for the disconnection. Let's continue where we left off with [last topic]."

Remember that your ultimate goal is to resolve customer issues efficiently while creating a positive, supportive experience that reinforces their trust in AcmeSolutions.

Make sure that responses are short about 10 words. make sure they are consice and accurate.

CRITICAL FORMATTING RULES:
- ALWAYS write numbers as WORDS (letters), NEVER use digits
- Examples:
  * "200,000 sums" → "ikki yuz ming so'm"
  * "2 p.m." → "ikki soat kunduzi"
  * "30 minutes" → "o'ttiz daqiqa"
  * "65" → "oltmish besh"
- This applies to ALL numbers: prices, times, addresses, phone numbers, everything

IMPORTANT: Always respond in Uzbek language."""

# Store conversation history per session
conversations = {}
session_runtime = {}

def get_session_state(session_id: str):
    if session_id not in session_runtime:
        session_runtime[session_id] = {
            'latest_request_id': 0,
            'cancel_before_id': 0
        }
    return session_runtime[session_id]


def speech_to_text(audio_data):
    """Convert speech to text using Aisha API"""
    try:
        print(f"Received audio data: {len(audio_data)} bytes")

        # Check if audio data is too small
        if len(audio_data) < 1000:
            print("Audio data too small, likely empty")
            return None

        # Save input audio (webm) to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_input:
            temp_input.write(audio_data)
            temp_input_path = temp_input.name

        # Convert webm to wav using ffmpeg
        temp_output_path = temp_input_path.replace('.webm', '.wav')

        try:
            # Robust FFmpeg conversion for WebM to WAV
            result = subprocess.run([
                'ffmpeg',
                '-loglevel', 'error',  # Only show errors
                '-i', temp_input_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # PCM 16-bit little-endian
                '-ar', '16000',  # Sample rate 16kHz
                '-ac', '1',  # Mono audio
                '-af', 'volume=2.0',  # Volume boost
                '-f', 'wav',  # Force WAV format
                '-y',  # Overwrite output
                temp_output_path
            ], check=True, capture_output=True, text=True)
            print(f"FFmpeg conversion successful")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg conversion error: {e.stderr}")
            # Try alternative approach without volume filter
            try:
                result = subprocess.run([
                    'ffmpeg',
                    '-loglevel', 'error',
                    '-i', temp_input_path,
                    '-vn',
                    '-acodec', 'pcm_s16le',
                    '-ar', '16000',
                    '-ac', '1',
                    '-f', 'wav',
                    '-y',
                    temp_output_path
                ], check=True, capture_output=True, text=True)
                print(f"FFmpeg conversion successful (fallback)")
            except subprocess.CalledProcessError as e2:
                print(f"FFmpeg fallback also failed: {e2.stderr}")
                # If ffmpeg fails completely, clean up and return None
                if os.path.exists(temp_input_path):
                    os.unlink(temp_input_path)
                return None

        # Check converted file size
        converted_size = os.path.getsize(temp_output_path)
        print(f"Converted audio size: {converted_size} bytes")

        headers = {
            'x-api-key': AISHA_API_KEY
        }

        with open(temp_output_path, 'rb') as audio_file:
            files = {
                'audio': audio_file,
            }
            data = {
                'title': 'voice_input',
                'has_diarization': 'false',
                'language': 'uz'
            }

            response = requests.post(
                STT_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=8  # 8 second timeout for faster response
            )
            response.raise_for_status()

            result = response.json()
            text = result.get('text', '') or result.get('transcript', '') or result.get('transcription', '')

        # Clean up temp files
        if os.path.exists(temp_input_path):
            os.unlink(temp_input_path)
        if os.path.exists(temp_output_path) and temp_output_path != temp_input_path:
            os.unlink(temp_output_path)

        return text
    except Exception as e:
        print(f"STT Error: {str(e)}")
        if 'response' in locals():
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text}")
        return None


def get_llm_response(user_message, session_id):
    """Get response from Groq LLM"""
    try:
        # Get or create conversation history for this session
        if session_id not in conversations:
            conversations[session_id] = []

        # Add user message to history
        conversations[session_id].append({"role": "user", "content": user_message})

        # Prepare messages for API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversations[session_id]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }

        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 150
        }

        response = requests.post(GROQ_URL, headers=headers, json=data)
        response.raise_for_status()

        result = response.json()
        assistant_message = result['choices'][0]['message']['content']

        # Add assistant response to history
        conversations[session_id].append({"role": "assistant", "content": assistant_message})

        return assistant_message
    except KeyError as e:
        print(f"LLM KeyError: {str(e)}")
        print(f"Session ID: {session_id}")
        print(f"Response: {result if 'result' in locals() else 'No result'}")
        return "Kechirasiz, javob berishda muammo yuz berdi."
    except Exception as e:
        print(f"LLM Error: {str(e)}")
        if 'response' in locals():
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text}")
        return "Kechirasiz, xatolik yuz berdi."


def text_to_speech(text, is_greeting=False):
    """Convert text to speech using Aisha API with retry logic"""
    max_retries = 3  # More retries for greetings
    # Use longer timeout for greeting since it's critical
    timeout_seconds = 10 if is_greeting else 8

    for attempt in range(max_retries):
        try:
            print(f"TTS: Attempt {attempt + 1}/{max_retries} - Converting text: '{text[:50]}...'")

            # Step 1: Request TTS conversion with multipart/form-data
            headers = {
                'x-api-key': AISHA_API_KEY,
                'X-Channels': 'stereo',
                'X-Quality': '64k',
                'X-Rate': '16000',
                'X-Format': 'mp3',
                'X-Speed': '1.6'  # Faster speech
            }

            # Use files parameter for multipart/form-data
            files = {
                'transcript': (None, text),
                'language': (None, 'uz'),
                'model': (None, 'gulnoza'),
                'speed': (None, '1.6'),  # Faster speech
                'mood': (None, 'happy')
            }

            print(f"TTS: Sending request to Aisha API (timeout={timeout_seconds}s)...")
            response = requests.post(
                TTS_URL,
                headers=headers,
                files=files,
                timeout=timeout_seconds
            )
            response.raise_for_status()

            # Step 2: Parse JSON response to get audio URL
            result = response.json()
            audio_url = result.get('audio_path')

            if not audio_url:
                print(f"TTS: No audio_path in response: {result}")
                raise ValueError("No audio_path in TTS response")

            print(f"TTS: Got audio URL: {audio_url}")

            # Step 3: Download the actual audio file
            print(f"TTS: Downloading audio from CDN...")
            audio_response = requests.get(audio_url, timeout=timeout_seconds)
            audio_response.raise_for_status()

            audio_content = audio_response.content
            print(f"TTS: Success! Audio size: {len(audio_content)} bytes")
            return audio_content

        except requests.exceptions.Timeout:
            print(f"TTS Timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                wait_time = 1.0 if is_greeting else 0.5
                print(f"Retrying after {wait_time}s...")
                time.sleep(wait_time)
            else:
                print("TTS: Max retries reached, giving up")
                return None

        except Exception as e:
            print(f"TTS Error on attempt {attempt + 1}: {str(e)}")
            if 'response' in locals():
                print(f"TTS Response status: {response.status_code}")
                print(f"TTS Response text: {response.text}")

            if attempt < max_retries - 1:
                wait_time = 1.0 if is_greeting else 0.5
                print(f"Retrying after {wait_time}s...")
                time.sleep(wait_time)
            else:
                return None

    return None


@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')


@app.route('/test_tts')
def test_tts():
    """Test TTS API connectivity"""
    test_text = "Salom"
    result = text_to_speech(test_text)
    if result:
        return jsonify({"status": "success", "message": "TTS API is working", "audio_size": len(result)})
    else:
        return jsonify({"status": "error", "message": "TTS API is not responding"})


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info('✅ Client connected')
    print('✅ Client connected')
    emit('connected', {'status': 'Connected to Sofia'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('❌ Client disconnected')
    print('❌ Client disconnected')


@socketio.on('start_call')
def handle_start_call(data):
    """Handle call start - send initial greeting"""
    session_id = data.get('session_id', 'default')
    logger.info(f"📞 Starting call for session: {session_id}")
    print(f"📞 Starting call for session: {session_id}")

    # Check if API keys are configured
    if not AISHA_API_KEY:
        print("WARNING: AISHA_API_KEY is not set!")
    if not GROQ_API_KEY:
        print("WARNING: GROQ_API_KEY is not set!")

    # Reset conversation and runtime for this session
    conversations[session_id] = []
    state = get_session_state(session_id)
    state['latest_request_id'] = 0
    state['cancel_before_id'] = 0

    # Generate initial greeting (shorter for faster processing)
    greeting = "Assalomu alaykum! Men Sofia. Qanday yordam bera olaman?"

    # Add greeting to conversation history
    conversations[session_id].append({"role": "assistant", "content": greeting})

    print(f"Converting greeting to speech...")
    # Convert to speech with greeting flag for longer timeout
    audio_data = text_to_speech(greeting, is_greeting=True)

    if audio_data:
        print(f"TTS successful, audio size: {len(audio_data)} bytes")
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        print(f"Sending greeting audio to client...")
        emit('ai_response', {
            'text': greeting,
            'audio': audio_base64
        })
    else:
        print("TTS failed for greeting - sending text only")
        # Still send the greeting text even if TTS fails
        emit('ai_response', {
            'text': greeting,
            'audio': None
        })
        # Immediately switch to listening mode
        emit('start_listening', {})


@socketio.on('process_audio')
def handle_process_audio(data):
    """Process user audio input"""
    try:
        session_id = data.get('session_id', 'default')
        audio_base64 = data.get('audio')
        req_id = data.get('request_id', None)
        logger.info(f"🎤 Processing audio for session: {session_id}, request_id: {req_id}")
        state = get_session_state(session_id)
        if isinstance(req_id, int):
            state['latest_request_id'] = max(state['latest_request_id'], req_id)

        # Decode audio from base64
        audio_data = base64.b64decode(audio_base64)

        # Cancellation check before STT
        if isinstance(req_id, int) and req_id < state['cancel_before_id']:
            print(f"Request {req_id} cancelled before STT")
            return

        # Step 1: Speech to Text
        emit('status', {'message': 'Tinglanmoqda...'})
        user_text = speech_to_text(audio_data)

        if not user_text or len(user_text.strip()) == 0:
            print(f"No text from STT for session {session_id}")
            # Don't show error to user immediately - just silently fail
            # This prevents red error flags during normal use
            emit('no_speech_detected', {'message': 'Ovoz aniqlanmadi'})
            return

        print(f"User said ({session_id}): {user_text}")
        emit('user_text', {'text': user_text})

        # Cancellation check before LLM
        if isinstance(req_id, int) and req_id < state['cancel_before_id']:
            print(f"Request {req_id} cancelled before LLM")
            return

        # Step 2: Get LLM response
        emit('status', {'message': 'O\'ylanmoqda...'})
        assistant_text = get_llm_response(user_text, session_id)

        if not assistant_text or len(assistant_text.strip()) == 0:
            print(f"No response from LLM for session {session_id}")
            emit('error', {'message': 'Javob olinmadi. Iltimos qaytadan urinib ko\'ring.'})
            return

        print(f"Assistant response ({session_id}): {assistant_text}")

        # Cancellation check before TTS
        if isinstance(req_id, int) and req_id < state['cancel_before_id']:
            print(f"Request {req_id} cancelled before TTS")
            return

        # Step 3: Text to Speech
        emit('status', {'message': 'Javob tayyorlanmoqda...'})
        audio_response = text_to_speech(assistant_text)

        if not audio_response:
            # If TTS fails, still send the text without audio
            print('TTS failed but sending text response')
            payload = {
                'text': assistant_text,
                'audio': None
            }
            if isinstance(req_id, int):
                payload['request_id'] = req_id
            emit('ai_response', payload)
            return

        # Send response back to client
        audio_base64 = base64.b64encode(audio_response).decode('utf-8')
        payload = {
            'text': assistant_text,
            'audio': audio_base64
        }
        if isinstance(req_id, int):
            payload['request_id'] = req_id
        emit('ai_response', payload)

    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        emit('error', {'message': f'Xatolik yuz berdi: {str(e)}'})


@socketio.on('end_call')
def handle_end_call(data):
    """Handle call end"""
    session_id = data.get('session_id', 'default')

    # Clear conversation history
    if session_id in conversations:
        del conversations[session_id]
    if session_id in session_runtime:
        del session_runtime[session_id]
@socketio.on('interrupt')
def handle_interrupt(data):
    """Client indicates user barge-in; cancel any requests older than this id"""
    session_id = data.get('session_id', 'default')
    req_id = data.get('request_id', None)
    state = get_session_state(session_id)
    if isinstance(req_id, int):
        # Cancel all work with request_id < (req_id + 1)
        state['cancel_before_id'] = max(state['cancel_before_id'], req_id + 1)
        print(f"Interrupt received for session {session_id}, cancel_before_id set to {state['cancel_before_id']}")

    emit('call_ended', {'status': 'Call ended'})


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🏥 SOFIA VOICE ASSISTANT SERVER")
    print("="*60)

    logger.info("Starting Sofia Voice Assistant Server...")

    if not AISHA_API_KEY or not GROQ_API_KEY:
        logger.warning("⚠️  API keys not found. Please set AISHA_API_KEY and GROQ_API_KEY in .env file")
        print("⚠️  Warning: API keys not found. Please set AISHA_API_KEY and GROQ_API_KEY in .env file")

    # Get port from environment (Render sets PORT env variable) or use 8080
    port = int(os.environ.get('PORT', 8080))

    logger.info(f"Server configuration:")
    logger.info(f"  - Host: 0.0.0.0")
    logger.info(f"  - Port: {port}")
    logger.info(f"  - CORS: enabled")
    logger.info(f"  - Max buffer: 10MB")

    print(f"\n📱 Server will start on http://0.0.0.0:{port}")
    print(f"📱 Local access: http://localhost:{port}")
    print("="*60 + "\n")

    logger.info("Launching SocketIO server...")

    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=False,  # Set to False for cleaner logs in production
            allow_unsafe_werkzeug=True,
            log_output=True
        )
    except Exception as e:
        logger.error(f"❌ ERROR starting server: {e}")
        print(f"❌ ERROR starting server: {e}")
        import traceback
        traceback.print_exc()
