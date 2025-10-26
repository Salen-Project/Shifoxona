# Sofia - Hospital Voice Assistant

A voice-enabled hospital assistant that converses in Uzbek language using Speech-to-Text (STT), Large Language Model (LLM), and Text-to-Speech (TTS) technologies.

## Features

- **Voice Input**: Record audio in Uzbek language
- **Speech-to-Text**: Converts Uzbek speech to text using Aisha API
- **AI Processing**: Uses Llama 3.3 70B Versatile on Groq infrastructure for better Uzbek understanding
- **Text-to-Speech**: Converts responses back to Uzbek speech using Aisha TTS API
- **Ultra-Minimalist UI**: Phone call-style interface with single-button interaction
- **Real-time Communication**: WebSocket-based instant voice conversation
- **Automatic Turn-Taking**: Voice activity detection for natural conversation flow
- **Hospital Assistant**: Sofia helps with appointment bookings, inquiries, and more

## Prerequisites

- Python 3.8 or higher
- FFmpeg (for audio format conversion)
- Microphone for audio input
- Active internet connection

## Installation

1. **Install FFmpeg** (required for audio conversion):

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

2. Clone or navigate to the project directory:
```bash
cd /path/to/Shifokor
```

3. Install required Python dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file from the example:
```bash
cp .env.example .env
```

5. Edit the `.env` file and add your API keys:
```
AISHA_API_KEY=your_actual_aisha_api_key
GROQ_API_KEY=your_actual_groq_api_key
```

## API Keys Setup

### Aisha API Key
- Used for STT (Speech-to-Text) and TTS (Text-to-Speech)
- Get your API key from Aisha platform

### Groq API Key
- Used for LLM processing with Llama 3.3 70B Versatile
- Get your API key from [Groq Console](https://console.groq.com/)

## Usage

1. Run the application:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:8080
```

3. **Press the blue call button** to start the conversation

4. **Speak naturally** in Uzbek when it's your turn (indicated by teal/inward pulses)

5. **Listen to Sofia's response** (indicated by blue/outward pulses)

6. **Press the red button** to end the call

### Phone Call Interface

The interface mimics a real phone call for intuitive interaction:

- **Ready State**: Large blue circular button in the center - press to start
- **Calling State**: Button expands with pulse animation while connecting
- **AI Speaking**: Blue outward pulses indicate Sofia is speaking
- **Your Turn**: Teal inward pulses indicate it's your turn to speak
- **Automatic Turn-Taking**: The system automatically detects when you finish speaking (2 seconds of silence)
- **End Call**: Small red button at the bottom to hang up

## How It Works

1. **Call Initiation**: Press the blue button to start - WebSocket connection established
2. **Initial Greeting**: Sofia greets you automatically in Uzbek
3. **Continuous Conversation Loop**:
   - **AI Speaks**: Sofia's response plays with blue outward pulse animation
   - **Auto-Switch to Listening**: When Sofia finishes, the UI automatically switches to teal inward pulses
   - **You Speak**: The system records your voice in real-time (up to 25 seconds)
   - **Smart Silence Detection**:
     - 2 seconds wait when you first start (gives you time to think)
     - 0.7 seconds wait after you've started speaking (fast response)
     - Requires 200ms of consecutive silence to avoid cutting off mid-sentence
   - **Processing**: Audio → STT (Aisha) → LLM (Groq Llama 3.3 70B) → TTS (Aisha, 1.3x speed) → Audio
   - **AI Responds**: The cycle continues seamlessly
4. **Natural Flow**: No button presses needed during conversation - just speak naturally
5. **End Call**: Press the red button when done

## Sofia's Capabilities

Sofia can help with:
- **Booking appointments** with doctors
- **Rescheduling or canceling** consultations
- **Answering questions** about hospital services
- **Providing information** about location, hours, and pricing
- **Collecting contact details** (name, phone, address) with confirmation for accuracy

### Hospital Information

- **Location**: Tashkent, Almazar district, Talabalar street, building 65
- **Consultation Fee**: 200,000 sums
- **Default Appointment Duration**: 30 minutes
- **Timezone**: Asia/Tashkent

## Conversation Management

- **Start Fresh**: End the current call and start a new one to reset conversation history
- **Context Awareness**: The app maintains conversation context throughout the call session
- **Short Responses**: Sofia keeps responses concise (around 10 words for natural phone conversation)
- **Call Duration**: Timer displayed in top-right corner shows how long you've been on the call

## Troubleshooting

### No API Keys Warning
If you see a warning about missing API keys, make sure:
1. Your `.env` file exists in the project directory
2. The API keys are correctly set without extra spaces
3. The variable names match exactly: `AISHA_API_KEY` and `GROQ_API_KEY`

### Audio Not Recording
- Check microphone permissions in your browser
- Ensure your microphone is properly connected
- Try a different browser if issues persist

### API Errors
- Verify your API keys are valid and active
- Check your internet connection
- Ensure you have sufficient API credits/quota

## Technical Stack

- **Backend Framework**: Flask with Flask-SocketIO
- **Real-time Communication**: WebSocket (Socket.IO)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Audio Processing**: Web Audio API, MediaRecorder API
- **STT Service**: Aisha STT API
- **TTS Service**: Aisha TTS API (Gulnoza voice model, 1.3x speed)
- **LLM**: Llama 3.3 70B Versatile (via Groq - better Uzbek understanding)
- **Language**: Python 3.8+

## File Structure

```
Shifokor/
├── app.py                    # Flask backend with WebSocket handling
├── templates/
│   └── index.html           # Main HTML template with phone call UI
├── static/
│   ├── style.css            # Ultra-minimalist UI styles and animations
│   └── app.js               # Frontend JavaScript for voice interaction
├── requirements.txt         # Python dependencies
├── .env.example            # Example environment variables
├── .env                    # Your API keys (create this)
└── README.md               # This file
```

## Development

### Customizing Sofia's Behavior

To modify Sofia's behavior, edit the `SYSTEM_PROMPT` variable in `app.py`. The prompt contains detailed instructions for:
- Personality and tone
- Conversation flow
- Response guidelines
- Scenario handling

### Customizing the UI

- **Visual Design**: Edit `static/style.css` to change colors, animations, and layout
- **Interaction Logic**: Edit `static/app.js` to modify voice detection, turn-taking, or UI state transitions
- **HTML Structure**: Edit `templates/index.html` to add or remove UI elements

## Security Notes

- Never commit your `.env` file with actual API keys
- Keep your API keys confidential
- The `.env.example` file is safe to share

## License

This project is for educational and development purposes.

## Support

For issues or questions:
1. Check the Troubleshooting section
2. Verify API key configuration
3. Review Aisha API and Groq API documentation
