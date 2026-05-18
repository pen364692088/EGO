#!/bin/bash
# Optional install script for OpenClaw skill

SKILL_DIR="$HOME/.openclaw/skills/emotion_core"
SOURCE_DIR="$(dirname "$0")"

if [ ! -d "$SKILL_DIR" ]; then
    echo "Creating skill directory: $SKILL_DIR"
    mkdir -p "$SKILL_DIR"
fi

echo "Installing emotion core skill..."
cp "$SOURCE_DIR/SKILL.md" "$SKILL_DIR/"
cp "$SOURCE_DIR/skill.py" "$SKILL_DIR/"

chmod +x "$SKILL_DIR/skill.py"

echo "Skill installed to $SKILL_DIR"
echo "Make sure emotiond is running on 127.0.0.1:18080"