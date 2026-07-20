# SmartChat — Graduation Project 🎓

An **AI-powered smart chat application** developed as a graduation project. It combines a **large language model** with custom **sentiment analysis** and **writing-style adaptation** models to produce responses that match the tone and mood of the conversation.

## ✨ Features

- 💬 Conversational chat powered by an **LLM** (OpenAI API)
- 😊 **Sentiment analysis** — classical ML and a **BERT**-based model
- ✍️ **Style adapter** — adjusts the assistant's writing style to the user
- 🔐 User accounts with **bcrypt** password hashing
- 🗄️ Persistence with **MySQL**
- 🐳 Dockerized with **docker-compose**

## 🛠️ Tech Stack

- **Python** · **Flask** (REST backend) · Gunicorn
- **OpenAI API**
- scikit-learn / **BERT** for sentiment & style models
- MySQL
- Docker · docker-compose

## 📂 Project Structure

| Path | Description |
| :--- | :--- |
| `backend/` | Flask API (`app.py`) and services |
| `ai_module/` | AI / model integration layer |
| `*.ipynb` | Model training notebooks (sentiment, BERT, style) |
| `*.pkl` | Trained model artifacts |
| `docs/`, `raporlar/` | Project documentation & reports |

## 🚀 Getting Started

```bash
pip install -r requirements.txt

# Configure your OpenAI API key and MySQL connection, then:
python backend/app.py
```

Or run the full stack with Docker:

```bash
docker-compose up --build
```

## 📄 License

Open source, developed for academic purposes.
