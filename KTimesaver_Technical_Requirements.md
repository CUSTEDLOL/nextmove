# K-Timesaver Matrix --- Technical Requirements

## System Architecture

User → App / Telegram → API → AI Processing → Matrix Engine → Scheduling
Engine → Database → Notification Service

------------------------------------------------------------------------

## Core Components

### Input Capture Layer

Handles: - app task input - Telegram bot messages - Gmail scanning -
Calendar ingestion

Technologies: - Telegram Bot API - Google APIs - OAuth

------------------------------------------------------------------------

### AI Parsing Engine

Extracts from natural language:

-   task
-   deadline
-   effort level
-   dependencies
-   context

Example output JSON:

{ "task": "Finish ML assignment", "deadline": "Friday", "effort":
"High", "context": "Study" }

------------------------------------------------------------------------

### Matrix Scoring Engine

Priority Index formula example:

Priority =\
0.35 \* Urgency\
+ 0.30 \* Importance\
+ 0.20 \* Effort\
+ 0.15 \* Dependency

Triggered when: - task added - deadline changed - task completed

------------------------------------------------------------------------

### Scheduling Engine

Steps: 1. Read calendar 2. Detect free slots 3. Rank tasks 4. Match
energy vs effort 5. Assign time blocks

------------------------------------------------------------------------

### Behavior Learning Engine

Tracks: - task duration - completion time - productivity peaks

Updates: - energy model - scheduling preferences

------------------------------------------------------------------------

### Notification Engine

Types: - morning brief - midday check - pre‑task reminder - evening
wrap‑up - weekly summary

Delivered via: - Telegram - push notifications

------------------------------------------------------------------------

## Database Schema

### Users

id\
email\
timezone\
preferences

### Tasks

id\
user_id\
title\
deadline\
effort\
importance\
dependency\
priority_index\
status

### Schedule

task_id\
start_time\
end_time

### Productivity Logs

task_id\
completion_time\
duration

------------------------------------------------------------------------

## Recommended Tech Stack

Backend - Python - FastAPI - PostgreSQL - Redis

Frontend - React Native or Flutter

AI - Claude or GPT APIs

Integrations - Google Calendar API - Gmail API - Telegram Bot API

Infrastructure - Docker - AWS or GCP
