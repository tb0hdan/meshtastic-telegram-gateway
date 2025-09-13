# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Meshtastic Telegram Gateway - a bot that bridges communication between Meshtastic mesh networks and Telegram chat rooms. It supports bidirectional message forwarding, node management, and provides a web interface for visualizing mesh network topology.

## Common Development Commands

### Linting and Type Checking
```bash
make lint        # Run pylint on mesh.py and mtg/ directory
make mypy        # Run mypy type checker on mesh.py
make check       # Run both lint and mypy
```

### Testing
```bash
make test        # Run pytest with coverage for mtg module
pytest           # Run all tests
pytest -v        # Run tests with verbose output
pytest --cov mtg # Run tests with coverage report
```

### Running the Application
```bash
./mesh.py run                  # Run the bot normally
./start.sh                     # Run in screen sessions with monitoring
make run                       # Run in a loop with automatic restart
./mesh.py post2mesh -m "msg"   # Send message to mesh network
./mesh.py command -c reboot    # Send command to Meshtastic device
```

### Device Management
```bash
make reboot      # Reboot connected Meshtastic device
```

## Architecture Overview

### Core Components

1. **Main Entry Point** (`mesh.py`): Orchestrates all components, handles argument parsing, and manages the application lifecycle.

2. **Bot Layer** (`mtg/bot/`):
   - `meshtastic.py`: Handles Meshtastic-specific commands and message processing
   - `telegram.py`: Manages Telegram bot interactions and command handling
   - `openai.py`: Optional OpenAI integration for AI-powered responses

3. **Connection Layer** (`mtg/connection/`):
   - `meshtastic.py`: Direct connection to Meshtastic hardware via serial/TCP
   - `telegram.py`: Telegram API connection management
   - `mqtt.py`: MQTT support for bridging multiple mesh networks
   - `aprs.py`: APRS-IS integration for amateur radio operators
   - `rich.py`: Enhanced Meshtastic connection with additional features

4. **Database** (`mtg/database/`): SQLite database for storing node information, messages, and location data using Pony ORM.

5. **Web Interface** (`mtg/webapp/`): Flask-based web server providing a map visualization of mesh nodes with clustering support.

6. **Filters** (`mtg/filter/`): Message filtering logic for both Telegram and Meshtastic sides, including call sign validation.

7. **External Plugins** (`external/plugins/`): Support for custom plugins that can extend functionality with access to all bot connections.

### Message Flow

1. **Meshtastic → Telegram**: Hardware device → RichConnection → MeshtasticBot → Filter → TelegramConnection → Telegram chat
2. **Telegram → Meshtastic**: Telegram chat → TelegramBot → Filter → RichConnection → Hardware device
3. **MQTT Bridge**: Allows multiple gateway instances to share messages across different geographic locations
4. **APRS Integration**: Bidirectional text messaging with APRS nodes for licensed amateur radio operators

### Configuration

The bot uses `mesh.ini` configuration file (created from `mesh.ini.example`) with sections for:
- Telegram bot token and room configuration
- Meshtastic device connection settings
- MQTT broker configuration (optional)
- APRS-IS settings (optional)
- Web interface configuration
- Database settings

### Key Dependencies

- `meshtastic`: Core library for Meshtastic device communication
- `python-telegram-bot`: Telegram bot API wrapper
- `flask`: Web interface framework
- `pony`: ORM for database operations
- `reverse-geocoder`: Location name resolution
- `paho-mqtt`: MQTT client for network bridging
- `aprslib`: APRS-IS protocol support

## Development Notes

- The project supports Python 3.9+
- Uses screen sessions for production deployment with automatic restart on failure
- FIFO pipes are used for inter-process communication (`/tmp/mesh_fifo`, `/tmp/mesh_cmd_fifo`)
- Supports both serial and TCP connections to Meshtastic devices
- Web interface provides real-time map with node clustering and tail duration control
- Extensive logging with optional Sentry.io APM integration for monitoring