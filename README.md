# AiGuardian

![Architecture](/MP%20AD.png)

AI Guardian is a Django-based moderation assistant for content creators. It fetches YouTube comments, classifies them for toxicity using a Hugging Face transformer, and provides a dashboard for review and moderation.

**Quick Links**

- **Project:** AI Guardian
- **Architecture image:** [MP AD.png](MP%20AD.png)

## Features

- Fetch comments from YouTube videos (management commands)
- Classify comments with a transformer-based toxicity model
- Dashboard with per-video statistics and moderation actions
- Safe deletion flow — deletion via YouTube Data API preserved

## Architecture

The `MP AD.png` file (architecture diagram) illustrates how the web UI, Django backend, YouTube API, and the Hugging Face model interact. Place the `MP AD.png` file at the repository root so it renders in this README.

## Installation (Local)

1. Create a Python virtual environment and activate it:

```powershell
python -m venv venv
& .\venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```


3. Run migrations and start the development server:

```powershell
python manage.py migrate
python manage.py runserver
```

## Usage

- Fetch comments for a channel or video (management commands):

```powershell
python manage.py fetch_comments --video VIDEO_ID
python manage.py fetch_all_comments
python manage.py reclassify_video --video VIDEO_ID
```

- Open the dashboard in your browser (default `http://127.0.0.1:8000/`) to view videos and comment statistics.

## Model and Inference Notes

- Uses the Hugging Face `textdetox/bert-multilingual-toxicity-classifier` (PyTorch).
- The project intentionally does not commit the model weights or `venv` to the repository. Use `requirements.txt` to reproduce environment.

## Contributing

1. Fork the repo
2. Create a feature branch
3. Submit a PR describing your changes

## License

This project is released under the MIT License. See the `LICENSE` file for details.
