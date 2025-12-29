import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request
import pickle

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def get_youtube_service():
    creds = None
    # Token caching
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                r"C:\Users\Ravikumar Rangu\Desktop\Major Project\Project\AiGuardian\client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=8080)

        # Save the credentials for next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)


if __name__ == "__main__":
    youtube = get_youtube_service()
    print("✅ YouTube API service created successfully")
