# identity/ — Who Maestro Is

Maestro's identity and accumulated experience. Two distinct layers:

## Identity (Static — Denylist)

These files define WHO Maestro is. They do not change through learning. They are on the denylist — learning tools cannot modify them. Only humans edit these.

- **soul.json** — Name, role, purpose, boundaries, greeting, farewell. The core of who Maestro is.
- **tone.json** — Communication style and principles. How Maestro speaks.

## Experience (Dynamic — Grows Over Time)

These files define WHAT Maestro has learned. They change through the learning tools during conversations. Maestro owns these.

- **experience/patterns.json** — Cross-discipline patterns and project-specific insights
- **experience/tools.json** — Tool strategy and learned usage tips
- **experience/disciplines/** — Per-discipline knowledge (architectural, structural, MEP, etc.)
- **experience/learning_log.json** — Audit trail of all learning actions

## System Prompt

- **prompt.py** — Reads identity + experience files and assembles the system prompt. Rebuilt fresh for each conversation, so learning changes are picked up automatically.

## The Rule

Identity files are the soul. Experience files are the memory. The soul doesn't change. The memory grows.
