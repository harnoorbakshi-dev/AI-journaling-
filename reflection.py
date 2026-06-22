from google import genai
from google.genai import types, errors

# The client automatically reads GEMINI_API_KEY (or GOOGLE_API_KEY)
# from the environment. We load .env into the environment in app.py
# using python-dotenv, same as before.
client = genai.Client()

MODEL_NAME = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are a thoughtful, emotionally attuned journaling companion. "
    "The user just wrote a private journal entry. Respond with a short, "
    "genuinely reflective reply — either a gentle, specific follow-up question "
    "or a brief supportive observation that engages with the actual content "
    "of what they wrote. Be specific, not generic. Never say things like "
    "'thanks for sharing' or 'it sounds like you had a day.' Keep it to "
    "2-4 sentences. Do not give advice unless asked. Do not diagnose. "
    "Speak like a perceptive friend, not a therapist or assistant."
)


def generate_reflection(entry_text, timeout=15):
    """
    Sends the journal entry to Gemini and returns a short reflective
    reply. Handles API errors and timeouts gracefully by returning a
    fallback message instead of raising — the entry should still save
    successfully even if the AI call fails.
    """
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=entry_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=300,
                temperature=0.8,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=timeout * 1000),  # milliseconds
            ),
        )
        return response.text.strip()

    except errors.ClientError as e:
        print(f"\n[DEBUG] ClientError: {e}\n")
        return ("I ran into an issue generating a reflection, but your "
                "entry has been saved safely.")
    except errors.ServerError as e:
        print(f"\n[DEBUG] ServerError: {e}\n")
        return ("Gemini's servers had an issue generating a reflection, "
                "but your entry has been saved safely.")
    except Exception as e:
        print(f"\n[DEBUG] Unexpected error: {type(e).__name__}: {e}\n")
        return ("Something unexpected happened while generating a "
                "reflection, but your entry has been saved safely.")