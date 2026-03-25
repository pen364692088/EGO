# User Affect Classifier

Classifies user message text into affect dimensions for tone modulation.

## Schema

See `schemas/user_affect.schema.json`

```json
{
  "valence": -1.0 ~ 1.0,   // Negative to positive sentiment
  "arousal": 0.0 ~ 1.0,    // Calm to excited energy level
  "confidence": 0.0 ~ 1.0, // Classification certainty
  "evidence": ["short evidence 1", "short evidence 2"]
}
```

## Usage

```python
from integrations.openclaw.classifiers.user_affect import classify_user_affect, get_affect_for_emotiond

# Basic usage
affect = classify_user_affect("I love this! It's amazing!")
print(affect.to_dict())
# {"valence": 0.67, "arousal": 0.6, "confidence": 0.6, "evidence": [...]}

# For emotiond API integration
affect_dict = get_affect_for_emotiond(user_message_text)
```

## Key Principles

1. **Low confidence (<0.55)**: Output neutral/uncertain style
2. **Never triggers high-impact events**: Affect is for tone only, not decision changes
3. **Isolated from betrayal/rejection**: No subtype or high-impact flags

## Detection Features

- **Emoji detection**: Positive (😊😄👍) and negative (😡😠👎) emojis
- **Sarcasm indicators**: Quoted text, /s markers, "sure... but" patterns
- **Busy/cold responses**: Short one-word answers, "gtg", "ttyl", dots only
- **Arousal indicators**: Exclamation marks, all caps, repeated punctuation

## Integration with emotiond-bridge

The classifier can be called from the hook to provide affect data for tone modulation:

```javascript
// In handler.js
const { PythonShell } = require('python-shell');

async function getUserAffect(text) {
  // Call Python classifier
  // Return affect for emotiond context
}
```

## Tests

Run: `pytest tests/test_user_affect.py -v`

41 tests covering:
- Schema compliance and range validation
- Emoji usage patterns
- Sarcasm/irony detection
- Busy/cold responses
- Positive/negative sentiment
- Low confidence edge cases
- Isolation from high-impact events
