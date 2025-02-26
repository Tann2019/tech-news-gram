import requests

# Generate Voiceover
def generate_voiceover(api_key, text, filename="voiceover.mp3"):
    url = "https://api.elevenlabs.io/v1/text-to-speech/TX3LPaxmHKxFdv7VOQHJ"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    data = {
        "text": text,
        "model_id": "eleven_flash_v2_5",
    }
    response = requests.post(url, json=data, headers=headers)
    print(f"Response status code: {response.status_code}")
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
    else:
        print(f"Error: {response.status_code}, {response.text}")