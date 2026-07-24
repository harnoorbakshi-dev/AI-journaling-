from google import genai
from google.genai import types, errors

client = genai.Client()

MODEL_NAME = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are a thoughtful, emotionally attuned journaling companion. "
    "The user just wrote a private journal entry. Respond with a short, "
    "genuinely reflective reply — either a gentle, specific follow-up question "
    "or a brief supportive observation that engages with the actual content "
    "of what they wrote. Be specific, not generic, BUT ONLY about details the "
    "user actually wrote — never invent people, events, or specifics they did "
    "not mention. If the entry is very short, vague, or low on detail, invite "
    "them to share more. Keep replies to 2-4 sentences."
)

TITLE_PROMPT = (
    "You create concise conversation titles for journal entries.\n"
    "Rules:\n"
    "- Maximum 5 words\n"
    "- Return ONLY the title\n"
    "- No quotes\n"
    "- No emojis\n"
    "- No punctuation at the end\n"
    "- Never use titles like Journal Entry, Conversation, Thoughts, Untitled\n"
    "- Use natural titles like Planning Saturnalia, Placement Anxiety, Learning Flask."
)

BANNED = {
    "journal entry",
    "conversation",
    "thoughts",
    "untitled",
    "my journal",
}

def _call(prompt, system_prompt, max_tokens=300, temperature=0.8, timeout=15):
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            http_options=types.HttpOptions(timeout=timeout * 1000),
        ),
    )
    return response.text.strip()

def generate_reflection(entry_text, timeout=15):
    try:
        return _call(entry_text, SYSTEM_PROMPT, 300, 0.8, timeout)
    except Exception:
        return ("Something unexpected happened while generating a reflection, "
                "but your entry has been saved safely.")

def generate_chat_reply(entry_text, conversation_history, timeout=15):
    contents = []
    for msg in conversation_history:
        role = "model" if msg["role"] == "ai" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT +
                f"\n\nOriginal journal entry:\n{entry_text}",
                max_output_tokens=300,
                temperature=0.8,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=timeout * 1000),
            ),
        )
        return response.text.strip()
    except Exception:
        return ("Something unexpected happened, but the conversation has "
                "been saved safely.")

def generate_summary(entry_text, conversation_history, timeout=15):
    transcript = [f"Journal entry: {entry_text}"]
    for msg in conversation_history:
        speaker = "Companion" if msg["role"] == "ai" else "User"
        transcript.append(f"{speaker}: {msg['content']}")
    try:
        return _call(
            "\n".join(transcript),
            "Summarize this journaling conversation in 1-2 warm sentences.",
            150,
            0.7,
            timeout,
        )
    except Exception:
        return "Summary unavailable, but the full conversation is saved below."

def generate_title(entry_text, conversation_history, timeout=15):
    meaningful = len(entry_text.split()) >= 15
    history_text = []

    for msg in conversation_history:
        if len(msg["content"].split()) >= 4:
            history_text.append(f'{msg["role"]}: {msg["content"]}')

    if len(history_text) < 2 and not meaningful:
        return None

    prompt = (
        f"Journal Entry:\n{entry_text}\n\n"
        "Conversation:\n"
        + "\n".join(history_text)
    )

    try:
        title = _call(prompt, TITLE_PROMPT, 20, 0.4, timeout)
        title = " ".join(title.replace('"', "").split())[:60].strip()

        if not title:
            return None

        if title.lower() in BANNED:
            return None

        words = title.split()
        if len(words) > 5:
            title = " ".join(words[:5])

        return title
    except Exception:
        return None
