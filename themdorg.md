# Poster Automation Telegram Bot

## Overview
The Poster Automation Telegram Bot streamlines the creation of official college posters (such as congratulations or event posters). Instead of manually designing, users can simply send an image and caption to a Telegram bot, and the system automatically generates a polished poster using predefined templates.

---

## Workflow

### 1. Telegram Bot Setup
- Created via **BotFather** in Telegram.
- Users send an **image + caption** to this bot.

### 2. n8n Workflow
- **n8n** acts as the automation engine.
- It listens for **Telegram triggers** (image + caption).
- Once triggered, it forwards the data (image + caption) to the backend using a **GET/POST request**.
- Installed using **Node.js** (lighter and more stable than Docker for this use case).
- **Ngrok** is used to convert local `http://` into secure `https://`, required by Telegram's webhook API.

### 3. Backend (FastAPI in Python)
- Receives the image and caption.
- **Image Processing**:
  - Places the uploaded image into the template’s **image holder**.
  - Resizes or scales down automatically if larger than the template space (optimization).
- **Template Selection**:
  - Caption format: `1-message`, `2-message`, etc.
  - The number (`1`, `2`, etc.) determines **which poster template** to use.
- **Text Embedding**:
  - Extracted text from the caption is embedded into the chosen template in the correct style and position.

### 4. Final Output
- A completed **poster image** is generated automatically.
- The poster can then be:
  - Sent back to the Telegram bot (user receives it directly).
  - Stored in a local folder or cloud drive.

## Summary
The system automates poster creation by:
1. Accepting image + caption via Telegram.
2. Routing them through **n8n automation**.
3. Processing them in a **FastAPI backend**.
4. Producing a ready-to-use poster with image + text embedded into predefined templates.
