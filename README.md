# Osiris

A local AI home assistant running entirely on a home network — no cloud, no internet required.

## Hardware

- **Primary:** Mac Studio M3, 96GB unified memory
- **Inference:** Ollama running llama3.1:70b locally

## What it does

- Answers questions via a local chat interface
- Accessible from any device on the home WiFi network
- All data stays local — nothing sent to external servers

## How to run

1. Make sure Ollama is running:
```
   ollama serve
```

2. Start the Osiris server:
```
   gunicorn app:app
```

3. Open a browser on any device on your network and go to:
```
   http://<mac-studio-ip>:8000
```

## Project structure
```
osiris/
├── app.py          # Main Flask application
├── add_user.py     # User management script
├── docs/
│   └── adr/        # Architecture Decision Records
└── README.md
```

## Architecture decisions

All major technical decisions are documented as Architecture Decision Records (ADRs) in `docs/adr/`.
