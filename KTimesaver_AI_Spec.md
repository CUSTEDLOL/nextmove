# K-Timesaver Matrix --- AI System Specification

## Objective

The AI layer converts unstructured commitments into a prioritized and
scheduled task system while minimizing user decision making.

------------------------------------------------------------------------

## AI Responsibilities

1.  Parse natural language task dumps
2.  Detect commitments from Gmail
3.  Infer deadlines and effort
4.  Score tasks using Matrix Engine
5.  Schedule tasks intelligently
6.  Adapt schedule using behavior learning
7.  Generate nudges and conversational prompts

------------------------------------------------------------------------

## Parsing Model

Input: Natural language text dump

Example: "I need to finish the ML assignment by Friday and review
lecture notes tonight."

Output JSON:

{ "tasks": \[ { "title": "Finish ML assignment", "deadline": "Friday",
"effort": "High" }, { "title": "Review lecture notes", "deadline":
"Tonight", "effort": "Medium" } \] }

------------------------------------------------------------------------

## Matrix Scoring

Each task receives scores 0--10 for:

Urgency\
Importance\
Effort\
Dependency

Priority Index:

P = 0.35U + 0.30I + 0.20E + 0.15D

Tasks sorted by P.

------------------------------------------------------------------------

## Scheduling Rules

1.  Respect existing calendar events
2.  Assign heavy tasks to peak energy windows
3.  Fill low-energy slots with light tasks
4.  Ensure dependencies resolved before scheduling

------------------------------------------------------------------------

## Learning Model

Inputs: - completion times - skipped tasks - productivity hours

Outputs: - user energy profile - optimal scheduling patterns

------------------------------------------------------------------------

## Nudge Generation

Types:

Morning Brief: - today's main task - schedule overview

Pre‑Task Prompt: - motivational context - quick start suggestion

Procrastination Interrupt: Conversational prompt asking: - what's
blocking you?

Response adapts depending on: - stress - confusion - fatigue

------------------------------------------------------------------------

## Weekly Intelligence

AI analyzes:

-   completion rate
-   productivity days
-   missed tasks

Outputs: - behavioral insight - adjusted scheduling model
