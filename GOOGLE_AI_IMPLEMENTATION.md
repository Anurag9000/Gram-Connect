# Google AI Tooling & Gemini Implementation Documentation

Gram Connect leverages advanced Google AI tools to provide a seamless, multimodal experience for rural community coordination. This document outlines the specific models and their roles within the platform.

## 1. Core Multimodal Engine: Gemini 2.5 Flash
The platform primarily uses **Gemini 2.5 Flash** (via the Google GenAI SDK) as its high-performance, multimodal backbone. It is used in four critical areas:

### A. Multimodal Problem Intake
When a villager reports a problem, Gemini processes the input:
- **Audio Transcription**: Transcribes voice notes in local languages (Hindi, Gujarati, Tamil, etc.) with high fidelity, preserving the original script.
- **Visual Analysis**: Analyzes photos to automatically detect categories (e.g., "broken handpump", "road damage") and generate visual tags for indexing.
- **Intelligent Triage**: Infers the severity (LOW, NORMAL, HIGH) by reasoning over the combination of text, audio transcripts, and visual tags.

### B. The Nexus Matching Engine
The matching engine uses Gemini to perform "Semantic Skill Alignment":
- **Requirement Extraction**: Parses complex problem descriptions into a list of required technical and soft skills.
- **Volunteer Profiling**: Analyzes volunteer biographies to identify latent expertise not explicitly listed in their profiles.
- **Explainable Team Generation**: Provides a natural language explanation (the "Why this team?" section) for each generated assignment, describing the logic behind the match.

### C. Before & After Proof Verification
Gemini acts as an automated auditor for task resolution:
- **Change Detection**: Compares "Before" and "After" photos to verify that the visible issue (e.g., a pile of waste) has actually been resolved.
- **Fraud Prevention**: Detects if a volunteer has uploaded unrelated images or mismatched content (e.g., uploading a photo of a school for a water pump task).

### D. Intelligent Internationalization (i18n)
The platform uses the **Google Cloud Translation API** (via `deep_translator`) to localize over 8,000 dynamic strings into 12 Indian languages:
- **Dynamic Content**: Localizes village names, problem descriptions, and volunteer names on the fly.
- **Technical UI**: Ensures complex technical explanations of the Nexus score and AI models are accessible in the local language.

---

## 2. Model Configuration & Fallbacks
The backend is designed for high availability and offline-first development:

| Function | Primary Model | Fallback System (Local) |
| :--- | :--- | :--- |
| **Audio** | `gemini-2.5-flash` | OpenAI Whisper (Tiny) |
| **Image** | `gemini-2.5-flash` | OpenAI CLIP (ViT-B/32) |
| **Text** | `gemini-2.5-flash` | Keyword Heuristics |
| **Translation** | Google Translate API | English Source |

## 3. Environment Setup
The models are configured via the following environment variables in the `.env` file:
- `GOOGLE_API_KEY`: Required for all Gemini operations.
- `GEMINI_MODEL`: Defaults to `gemini-2.5-flash`.
- `GEMINI_VISION_MODEL`: Used for image analysis.
- `GEMINI_AUDIO_MODEL`: Used for transcription.
- `GEMINI_PROOF_MODEL`: Used for Before/After verification.

## 4. Key Implementation Files
- `backend/multimodal_service.py`: Central hub for all Gemini interactions.
- `backend/nexus.py`: Implementation of the skill matching logic.
- `extract_seeds.py` & `fast_translate_all.py`: Scripts for large-scale localized data generation.
