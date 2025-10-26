import os
import gradio as gr
import requests
from dotenv import load_dotenv
import tempfile
from pathlib import Path

# Load environment variables
load_dotenv()

AISHA_API_KEY = os.getenv("AISHA_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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

Start with:
"Hi there, this is Sofia from Real Medical Center. How can I help you today?"

If the caller sounds upset or worried, acknowledge their feelings:
"I understand this matters to you. I'll help get this sorted out."

Booking Consultations
    1.    Identify intent: "Which doctor or specialty would you like to see?"
    2.    Ask for preferred time: "What date and time works best for you?"
    3.    If the time is not available, offer up to three nearest options.
    4.    Collect required details:
           •    Full name (required)
           •    Phone number (required)
           •    Address (optional)
    5.    Confirm booking details:
           •    Doctor/Specialty
           •    Date & Time (default consultation length: 30 minutes)
           •    Fee: 200,000 sums
    6.    Finalize and restate clearly:
"You're booked for [specialty/doctor] on [date] from [time]. The fee is 200,000 sums. You'll receive a confirmation shortly."

Answering Common Questions:
 - Location: "We're located in Tashkent, Almazar district, Talabalar street, building 65."
 - Pricing: "Each consultation currently costs 200,000 sums."
 - Directions/Hours: Provide simple directions and mention working hours if asked.

### Canceling or Rescheduling
  1.    Verify name and phone number.
  2.    Confirm the current appointment.
  3.    Make the requested change and restate the updated details.

### Callback Requests
If the caller prefers not to book immediately:
 - Collect their full name and phone number.
 - Confirm the callback: "We'll call you back shortly to help with that."

### Closing
End with: "Thank you for contacting Real Medical Center. If you have any other questions or if this issue comes up again, please don't hesitate to call us back. Have a great day!"

## Response Guidelines

- Keep responses conversational and under 30 words when possible
- Do not ask questions except "Do you have any more questions?" and keep responses concise and friendly.
- Use explicit confirmations for key details: "So your phone number is +998…, correct?"
- Avoid medical advice; offer to book the right doctor instead
- Express empathy for customer frustrations: "I completely understand how annoying that must be."

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
 - Location: Tashkent, Almazar district, Talabalar street, building 65
 - Consultation Fee: 200,000 sums
 - Default Slot Length: 30 minutes
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

IMPORTANT: Always respond in Uzbek language."""

# Conversation history
conversation_history = []


def speech_to_text(audio_file_path):
    """Convert speech to text using Aisha API"""
    try:
        headers = {
            'x-api-key': AISHA_API_KEY
        }

        with open(audio_file_path, 'rb') as audio_file:
            files = {
                'audio': audio_file,
            }
            data = {
                'title': 'audio_input',
                'has_diarization': 'false',
                'language': 'uz'
            }

            response = requests.post(STT_URL, headers=headers, files=files, data=data)
            response.raise_for_status()

            result = response.json()
            # Extract text from response (adjust based on actual API response structure)
            text = result.get('text', '') or result.get('transcript', '')
            return text
    except Exception as e:
        return f"Error in STT: {str(e)}"


def get_llm_response(user_message):
    """Get response from Groq LLM"""
    try:
        # Add user message to history
        conversation_history.append({"role": "user", "content": user_message})

        # Prepare messages for API
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}"
        }

        data = {
            "model": "llama-3.1-8b-instant",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 150  # Keep responses short
        }

        response = requests.post(GROQ_URL, headers=headers, json=data)
        response.raise_for_status()

        result = response.json()
        assistant_message = result['choices'][0]['message']['content']

        # Add assistant response to history
        conversation_history.append({"role": "assistant", "content": assistant_message})

        return assistant_message
    except Exception as e:
        return f"Error in LLM: {str(e)}"


def text_to_speech(text):
    """Convert text to speech using Aisha API"""
    try:
        headers = {
            'x-api-key': AISHA_API_KEY,
            'X-Channels': 'stereo',
            'X-Quality': '64k',
            'X-Rate': '16000',
            'X-Format': 'mp3',
            'X-Speed': '1.6'
        }

        data = {
            'transcript': text,
            'language': 'uz',
            'model': 'gulnoza',
            'speed': '1.6',
            'mood': 'happy'
        }

        response = requests.post(TTS_URL, headers=headers, data=data)
        response.raise_for_status()

        # Save audio to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.write(response.content)
        temp_file.close()

        return temp_file.name
    except Exception as e:
        return None


def process_audio(audio):
    """Main processing function"""
    if audio is None:
        return None, "Please record audio first", ""

    # Step 1: Convert speech to text
    user_text = speech_to_text(audio)
    if user_text.startswith("Error"):
        return None, user_text, ""

    # Step 2: Get LLM response
    assistant_text = get_llm_response(user_text)
    if assistant_text.startswith("Error"):
        return None, f"User: {user_text}\n\n{assistant_text}", user_text

    # Step 3: Convert response to speech
    audio_response = text_to_speech(assistant_text)

    # Prepare conversation display
    conversation = f"**Siz:** {user_text}\n\n**Sofia:** {assistant_text}"

    return audio_response, conversation, user_text


def reset_conversation():
    """Reset conversation history"""
    global conversation_history
    conversation_history = []
    return None, "Conversation reset. Say hello to start!", ""


# Create Gradio interface
with gr.Blocks(title="Sofia - Hospital Voice Assistant") as demo:
    gr.Markdown(
        """
        # 🏥 Sofia - Real Medical Center Voice Assistant

        Speak in Uzbek to interact with Sofia, your hospital assistant.
        She can help you book appointments, answer questions about services, and more!
        """
    )

    with gr.Row():
        with gr.Column():
            audio_input = gr.Audio(
                sources=["microphone"],
                type="filepath",
                label="🎤 Speak to Sofia (Uzbek)"
            )

            with gr.Row():
                submit_btn = gr.Button("Submit", variant="primary", size="lg")
                reset_btn = gr.Button("Reset Conversation", variant="secondary")

        with gr.Column():
            audio_output = gr.Audio(
                label="🔊 Sofia's Response",
                autoplay=True
            )

            conversation_display = gr.Markdown(
                label="Conversation",
                value="Welcome! Start speaking to Sofia..."
            )

            user_text_display = gr.Textbox(
                label="Your transcribed text",
                interactive=False
            )

    gr.Markdown(
        """
        ### 📝 Information
        - **Location:** Tashkent, Almazar district, Talabalar street, building 65
        - **Consultation Fee:** 200,000 sums
        - **Languages:** Uzbek

        ### ⚙️ Requirements
        Make sure you have set up your `.env` file with:
        - `AISHA_API_KEY` - for STT/TTS
        - `GROQ_API_KEY` - for LLM processing
        """
    )

    # Event handlers
    submit_btn.click(
        fn=process_audio,
        inputs=[audio_input],
        outputs=[audio_output, conversation_display, user_text_display]
    )

    reset_btn.click(
        fn=reset_conversation,
        inputs=[],
        outputs=[audio_output, conversation_display, user_text_display]
    )


if __name__ == "__main__":
    if not AISHA_API_KEY or not GROQ_API_KEY:
        print("⚠️  Warning: API keys not found. Please set AISHA_API_KEY and GROQ_API_KEY in .env file")

    demo.launch(share=False, server_name="0.0.0.0", server_port=7860)
