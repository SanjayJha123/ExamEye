# ExamEye — Detailed Vertical Slice Development Plan
## AI-Powered Exam Surveillance & Investigation Platform

---

# 1. Product Vision

## Product Name
# **ExamEye**

## Vision Statement
Build an AI-powered exam surveillance platform that transforms passive CCTV systems into intelligent investigation assistants using:
- Python
- Gemma 4
- vLLM
- OpenCV
- YOLOv8

The platform will:
- detect suspicious exam behavior
- generate AI summaries
- support natural language investigation
- provide real-time alerts
- scale for enterprise deployments

---

# 2. Why Vertical Slice Architecture?

Instead of building:
- backend separately
- AI separately
- frontend separately

We deliver:
> complete working user journeys incrementally.

Each phase contains:
- UI
- backend APIs
- AI logic
- database
- infrastructure
- testing
- deployment

This enables:
- faster demos
- continuous feedback
- hackathon-ready progress
- production-aligned architecture

---

# 3. Product Development Strategy

## Final User Journey

```text
Admin uploads CCTV footage
        ↓
AI processes video
        ↓
Suspicious events detected
        ↓
Gemma 4 generates investigation summary
        ↓
Admin queries incidents using natural language
        ↓
System retrieves evidence clips & reports
