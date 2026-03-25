# Emotion Core Skill

Use the emotiond daemon to maintain emotional state and generate response plans for OpenClaw.

## Usage

This skill calls the local emotiond daemon to:
- Track emotional state over time
- Maintain relationship bonds and grudges
- Generate response plans based on current emotional context

## Requirements

- emotiond daemon running on 127.0.0.1:18080
- OpenEmotion project installed

## Behavior

- On user input: POST /event with type=user_message
- Generate response plan: POST /plan
- On assistant reply: POST /event with type=assistant_reply

If emotiond is unreachable, the skill will fail gracefully with a clear error message.