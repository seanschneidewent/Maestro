# learning.py - Maestro's learning engine
# A separate AI that modifies Maestro's experience based on feedback.
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def learn(learning_mission: str, current_experience: dict) -> dict:
    """
    Takes a learning mission (what Maestro should learn) and the current
    experience config. Uses AI to figure out which parts of experience
    to update and how. Returns the updated experience.
    """

    # Build a text version of the current experience
    experience_text = ""
    for key, value in current_experience.items():
        experience_text += f'  "{key}": "{value}"\n'

    prompt = f"""You are a learning engine for an AI assistant called Maestro.

Maestro's current experience config:
{experience_text}

The superintendent gave this feedback or lesson:
"{learning_mission}"

Your job: Update the experience config so Maestro behaves better next time.

Rules:
- Only modify keys that are relevant to the feedback
- You can add NEW keys if the feedback introduces a new concept
- Keep values concise — these are instructions, not essays
- Return ONLY the updated Python dictionary, nothing else
- Use this exact format:

{{
    "soul": "...",
    "purpose": "...",
    "tools": "...",
    "tone": "...",
    "boundaries": "...",
    "greeting": "...",
    "farewell": "...",
}}

Include ALL keys (modified or not). Add new keys if needed.
"""

    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)

    # Parse the response back into a dictionary
    try:
        # Extract the dict from the response text
        response_text = response.text.strip()

        # Remove markdown code fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Drop first line (```python or ```) and last line (```)
            response_text = "\n".join(lines[1:-1])

        updated_experience = eval(response_text)
        return updated_experience
    except Exception as e:
        print(f"  [Learning Error] Couldn't parse update: {e}")
        print(f"  [Raw Response] {response.text}")
        return current_experience  # Return unchanged if parsing fails


def save_experience(experience: dict, filepath: str = "experience.py"):
    """Write the updated experience back to the file."""

    lines = ['# experience.py - Maestro\'s configurable identity']
    lines.append('# This file is managed by learning.py — Maestro updates it as he learns.')
    lines.append('# You can also edit it by hand anytime.')
    lines.append('')
    lines.append('experience = {')

    for key, value in experience.items():
        # Escape any quotes in the value
        escaped = value.replace('"', '\\"')
        lines.append(f'    "{key}": "{escaped}",')

    lines.append('}')
    lines.append('')

    with open(filepath, 'w') as f:
        f.write('\n'.join(lines))

    print(f"  [Learning] Experience updated and saved to {filepath}")
