# Amazon Smart Home Skill

## What it does

Controls Amazon Alexa smart plugs using the same local plugin architecture as other Jarvis skills.

Current scope:
- Turn a named smart plug on/off
- Turn all plugs in a matched Alexa room/group on/off (when room relationships are available)
- Turn all smart plugs on/off
- Return clear errors for missing setup, unknown targets, or ambiguous matches
- Provide setup guidance intent (`setup amazon plugs`)

## Required environment variables

- `AMAZON_ALEXA_COOKIE`: Authenticated Alexa web session cookie string
- `AMAZON_ALEXA_CSRF`: CSRF token from the same Alexa browser session

Optional:
- `AMAZON_ALEXA_BASE_URL`: Alexa web endpoint for your region
  - Default: `https://alexa.amazon.com`
  - UK example: `https://alexa.amazon.co.uk`

## Setup notes

1. Sign in to Alexa web for your account in a browser.
2. Capture cookie + csrf values from your authenticated session.
3. Export `AMAZON_ALEXA_COOKIE` and `AMAZON_ALEXA_CSRF`.
4. Optionally set `AMAZON_ALEXA_BASE_URL`.
5. Restart Core.

## Example commands

- `setup amazon plugs`
- `turn on office plug`
- `turn off desk outlet`
- `landing light on`
- `sidelight on`
- `turn off landing lights`
- `switch on coffee machine plug`
- `turn off all plugs`
- `power on all smart plugs`

## Safety behavior

- The skill does not toggle all plugs unless you explicitly ask for all plugs.
- If no target is provided, it asks for clarification.
