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
    "of what they wrote. Be specific, not generic, BUT ONLY about details the "
    "user actually wrote — never invent people, events, or specifics they did "
    "not mention. If the entry is very short, vague, or low on detail (such as "
    "a greeting like 'hi' or a single word), do not fabricate a scenario — "
    "instead, warmly invite them to share more about what's on their mind. "
    "Never say things like 'thanks for sharing' or 'it sounds like you had a "
    "day.' Keep it to 2-4 sentences. Do not give advice unless asked. Do not "
    "diagnose. Speak like a perceptive friend, not a therapist or assistant."
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
    
def generate_chat_reply(entry_text, conversation_history, timeout=15):
    """
    Continues an ongoing reflective conversation. `conversation_history`
    is a list of dicts like [{"role": "user"/"ai", "content": "..."}],
    representing everything said so far in this entry's chat (not
    including the entry itself or the initial reflection). Returns the
    AI's next reply, with the same graceful fallback behavior as
    generate_reflection.
    """
    # Build the conversation so Gemini sees the original entry first,
    # then every message that's happened since, in order.
    contents = []
    for msg in conversation_history:
        role = "model" if msg["role"] == "ai" else "user"
        contents.append(
            types.Content(role=role, parts=[types.Part(text=msg["content"])])
        )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=(
                    SYSTEM_PROMPT +
                    f"\n\nFor context, here is the journal entry that started "
                    f"this conversation: \"{entry_text}\""
                ),
                max_output_tokens=300,
                temperature=0.8,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=timeout * 1000),
            ),
        )
        return response.text.strip()

    except errors.ClientError:
        return ("I ran into an issue replying just now, but the conversation "
                "has been saved safely.")
    except errors.ServerError:
        return ("Gemini's servers had an issue replying, but the conversation "
                "has been saved safely.")
    except Exception:
        return ("Something unexpected happened, but the conversation has "
                "been saved safely.")


def generate_summary(entry_text, conversation_history, timeout=15):
    """
    Generates a short summary of the entire conversation (the original
    entry plus everything discussed afterward), to be saved once the
    user ends the chat. Always returns *something* usable, even on
    failure, so ending a conversation never leaves an entry without
    some kind of summary.
    """
    transcript_lines = [f"Journal entry: {entry_text}"]
    for msg in conversation_history:
        speaker = "Companion" if msg["role"] == "ai" else "User"
        transcript_lines.append(f"{speaker}: {msg['content']}")
    transcript = "\n".join(transcript_lines)

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=transcript,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Summarize this journaling conversation in 1-2 short, "
                    "warm sentences. Focus on what the person actually "
                    "shared and how the conversation evolved, not generic "
                    "phrasing. Write it as a brief note for the person to "
                    "read later, not as advice."
                ),
                max_output_tokens=150,
                temperature=0.7,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=timeout * 1000),
            ),
        )
        return response.text.strip()

    except Exception:
        return "Summary unavailable, but the full conversation is saved below."
    