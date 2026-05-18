# Security Guide for OpenEmotion

This document covers security best practices for managing tokens and sensitive data in OpenEmotion.

## Token Management

### Token Storage Locations

OpenEmotion tokens are loaded with the following priority order:

1. **Environment variable**: `EMOTIOND_TOKEN` (highest priority)
2. **User config directory**: `~/.config/openemotion/emotiond_token`
3. **User home directory**: `~/.openemotion/emotiond_token`
4. **Auto-generation**: If no token exists, one is generated and saved to `~/.config/openemotion/emotiond_token`

### Recommended Token Setup

#### Option 1: Environment Variable (Recommended for production)

```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc, etc.)
export EMOTIOND_TOKEN="your-secure-random-token-here"
```

Generate a secure token:
```bash
openssl rand -hex 32
```

#### Option 2: User Config File (Recommended for development)

```bash
# Create the config directory
mkdir -p ~/.config/openemotion

# Generate and save a token
openssl rand -hex 32 > ~/.config/openemotion/emotiond_token

# Set secure permissions (readable only by owner)
chmod 600 ~/.config/openemotion/emotiond_token
```

#### Option 3: Auto-generation (Simplest)

Just start emotiond - it will automatically generate a token on first run:
```bash
python -m emotiond.main
# Token will be created at ~/.config/openemotion/emotiond_token
```

Check the logs to see where the token was saved:
```bash
tail -f /tmp/emotiond.log | grep -i token
```

## Token Rotation

To rotate a token (change to a new one):

### Using Environment Variable

1. Generate a new token:
   ```bash
   NEW_TOKEN=$(openssl rand -hex 32)
   echo "New token: $NEW_TOKEN"
   ```

2. Update the environment variable:
   ```bash
   export EMOTIOND_TOKEN="$NEW_TOKEN"
   ```

3. Restart emotiond to use the new token.

### Using Token File

1. Generate a new token:
   ```bash
   openssl rand -hex 32 > ~/.config/openemotion/emotiond_token
   chmod 600 ~/.config/openemotion/emotiond_token
   ```

2. Restart emotiond to use the new token.

### For OpenClaw Integration

After rotating the token, update the OpenClaw configuration:

```bash
# Edit OpenClaw config
vim ~/.openclaw/openclaw.json

# Update EMOTIOND_OPENCLAW_TOKEN with the new token
# Then restart the gateway
openclaw gateway restart
```

## Cleaning Git History (If Token Was Committed)

If a token was accidentally committed to git, you need to remove it from history:

### Step 1: Remove from current tracking

```bash
cd /path/to/OpenEmotion
git rm --cached .emotiond_token
git commit -m "Remove token from tracking"
```

### Step 2: Remove from git history (use with caution!)

**Warning**: This rewrites git history. Coordinate with all collaborators before running.

```bash
# Using git filter-branch (legacy method)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .emotiond_token' \
  --prune-empty --tag-name-filter cat -- --all

# OR using BFG Repo-Cleaner (faster, recommended)
# Install BFG first: https://rtyley.github.io/bfg-repo-cleaner/
bfg --delete-files .emotiond_token
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

### Step 3: Force push (if already pushed to remote)

```bash
git push origin --force --all
git push origin --force --tags
```

### Step 4: Rotate the compromised token

The token that was committed should be considered compromised. Generate a new one immediately using the rotation steps above.

## Security Best Practices

### Token Storage

1. **Never commit tokens to git** - Add token files to `.gitignore`
2. **Use environment variables in production** - Harder to accidentally leak
3. **Set file permissions to 600** - Only the owner should be able to read
4. **Don't share tokens in chat/email** - Use secure channels for sharing

### Token Usage

1. **Use different tokens for different purposes**:
   - `EMOTIOND_SYSTEM_TOKEN` - For system-level operations
   - `EMOTIOND_OPENCLAW_TOKEN` - For OpenClaw integration
   - `EMOTIOND_TOKEN` - General-purpose token

2. **Rotate tokens periodically** - Especially after any suspected exposure

3. **Monitor token usage** - Check logs for unauthorized access attempts

### Network Security

1. **Bind to localhost by default** - emotiond defaults to `127.0.0.1:18080`
2. **Use HTTPS in production** - Place behind a reverse proxy with TLS
3. **Implement firewall rules** - Restrict access to the emotiond port

## Verifying Token Configuration

Check if tokens are loaded correctly:

```python
# Python REPL
from emotiond.security import init_tokens, get_token_file_location

# Initialize tokens and check status
tokens = init_tokens()
print(f"System token: {'loaded' if tokens['system'] else 'not set'}")
print(f"OpenClaw token: {'loaded' if tokens['openclaw'] else 'not set'}")
print(f"General token: {'loaded' if tokens['general'] else 'not set'}")
print(f"Token file location: {get_token_file_location()}")
```

Or check via API:

```bash
# Health check (doesn't reveal tokens)
curl http://localhost:18080/health

# If the daemon starts successfully, tokens were loaded
```

## Incident Response

If you suspect a token has been compromised:

1. **Immediately rotate** the affected token
2. **Check access logs** for unauthorized activity
3. **Review git history** for accidental commits
4. **Update all clients** with the new token
5. **Document the incident** for future reference
