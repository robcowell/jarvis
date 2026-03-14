# Philips Hue Lights Skill

## What it does

Controls Philips Hue power state via a local Hue Bridge using the plugin system.

Current scope:
- Turn lights on/off
- Set brightness levels (1-100%)
- Set named colors
- Target a named light, room, or zone
- Pairing guidance intent (`pair hue bridge`)

## Required environment variables

- `HUE_BRIDGE_IP`: Hue Bridge IP or hostname on your LAN
- `HUE_APP_KEY`: Hue application key for local API access

## First-time pairing

1. Press the physical button on your Hue Bridge.
2. Run:

```bash
python -m core.tools.hue_pair --bridge-ip <bridge-ip>
```

3. Copy the printed app key into `HUE_APP_KEY`.
4. Set `HUE_BRIDGE_IP`.
5. Restart Core.

## Example commands

- `pair hue bridge`
- `turn on kitchen light`
- `turn office lamp off`
- `set office lights to 35 percent`
- `dim office lights to 20`
- `set office lights to blue`
- `turn on all lights`

## Safety behavior

- The skill does not toggle all lights unless you explicitly ask for all lights.
- If no target is provided, it asks for clarification.
