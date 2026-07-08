# AMD Developer Hackathon: Participant Guide Summary

This document summarizes the requirements for the AMD Developer Hackathon, with a specific focus on how our current project (**AI-Rescue Connect**) fits into the competition.

## Overview of Tracks

The hackathon consists of three tracks:
1.  **Track 1: General-Purpose AI Agent** (Benchmarking 8 specific NLP tasks using Fireworks AI).
2.  **Track 2: Video Captioning Agent** (Generating stylized captions for video clips).
3.  **Track 3: Unicorn (Open Innovation)** (Building an original AI application that uses AMD compute resources).

## How AI-Rescue Connect Fits (Track 3: Unicorn)

**AI-Rescue Connect is a perfect fit for Track 3 (Unicorn).** 
Since our project is an original application (a volunteer emergency dispatch system) utilizing a local open-source LLM (Qwen) running on **AMD GPU compute instances**, it meets the exact criteria for the open innovation track.

### Track 3 Submission Requirements
For Track 3, you do **not** need to submit a Docker image conforming to strict input/output JSON formats like Tracks 1 and 2. 
You are also **not required to maintain a live API endpoint** for judges (as it is too expensive).
Instead, you ONLY need to prepare and submit the following by the deadline (**CET 6 pm July 12, 2026**):
*   **Required:** GitHub repository URL (which we are currently building).
*   **Required:** Demo video showing the system in action.
*   **Required:** Presentation deck (about 5 slides) explaining the architecture and value proposition.

*Note: AMD compute usage is a strict requirement and will be automatically pre-screened via your GitHub repo and Slide deck.*

### AMD Developer Cloud Jupyter Infrastructure (Act II)
Based on the latest FAQ, here are critical operational constraints for our backend infrastructure running on the AMD provided Jupyter Notebooks:
*   **Time Quotas:** We receive a fixed number of hours over a 24-hour period. We MUST stop/shutdown the instance when not actively developing to preserve our compute time.
*   **Persistent Storage:** We are allocated 25 GB of persistent storage located at `/workspace`. Any models or databases must be stored inside `/workspace` to survive pod restarts.
*   **GPU Memory:** The instance provides about 48 GB of GPU memory. This is plenty for the Qwen 7B model.
*   **vLLM Launching:** To launch the local Qwen model from the terminal within the Jupyter pod, use the official AMD provided command: 
    ```bash
    vllm serve Qwen/Qwen2-7B-Instruct --port 8000 --gpu-memory-utilization 0.3
    ```

---

## General Rules (If participating in Track 1 or 2)

If you plan to submit a Docker container for Track 1 or Track 2, you must adhere to these strict infrastructure rules:
*   **Image Architecture:** Must be `linux/amd64`. If building on Apple Silicon, you must use `--platform linux/amd64`.
*   **Startup Time:** Container must start and be ready within 60 seconds.
*   **Response Time:** Must process requests in under 30 seconds.
*   **Runtime Limit:** Maximum 10 minutes total runtime.
*   **Exit Code:** Must exit with code `0` on success.
*   **No Hardcoding:** Evaluation uses unseen hidden datasets.

### Track 1 Specifics (General Agent)
*   Must read from `/input/tasks.json` and write to `/output/results.json`.
*   Must route all API calls through `FIREWORKS_BASE_URL` using the injected `FIREWORKS_API_KEY`.
*   Only allowed to use models specified in `ALLOWED_MODELS`.
*   Scored on Accuracy first, then Token Efficiency (fewer tokens = higher rank).

### Track 2 Specifics (Video Captioning)
*   Must read `/input/tasks.json` containing `video_url` and required `styles` (formal, sarcastic, humorous_tech, humorous_non_tech).
*   Write captions to `/output/results.json`.
*   No API restrictions; you can bring your own API keys/frameworks.
*   Scored by an LLM-Judge on Caption Accuracy and Style Match.
