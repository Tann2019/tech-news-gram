import os
import requests

def post_video_to_tiktok(
    access_token,
    video_path,
    title="this is a #sample #video",
    privacy_level="SELF_ONLY",
    disable_duet=False,
    disable_comment=False,
    disable_stitch=False
):
    
    print(f"Posting video to TikTok: {video_path}")
    file_size = os.path.getsize(video_path)

    # 1. Initialize post
    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    init_payload = {
        "post_info": {
            "title": title,
            "privacy_level": privacy_level,
            "disable_duet": disable_duet,
            "disable_comment": disable_comment,
            "disable_stitch": disable_stitch
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,     # single-chunk example
            "total_chunk_count": 1
        }
    }

    init_resp = requests.post(init_url, headers=headers, json=init_payload)
    if init_resp.status_code != 200:
        print(f"Init failed: {init_resp.text}")
        return f"Init failed: {init_resp.text}"

    init_data = init_resp.json().get("data", {})
    publish_id = init_data.get("publish_id")
    upload_url = init_data.get("upload_url")

    print(f"publish_id: {publish_id}")
    print(f"upload_url: {upload_url}")

    if not upload_url:
        return f"Publish init error: {init_resp.text}"

    # 2. Upload the file in one chunk
    with open(video_path, "rb") as f:
        chunk_data = f.read()
    upload_headers = {
        "Content-Type": "video/mp4",
        "Content-Length": str(file_size),
        "Content-Range": f"bytes 0-{file_size-1}/{file_size}"
    }
    print(f"Uploading {file_size} bytes to TikTok...")
    upload_resp = requests.put(upload_url, headers=upload_headers, data=chunk_data)
    if upload_resp.status_code not in [200, 201, 204]:
        return f"Upload failed: {upload_resp.text}"
    print("Upload successful, now publishing...")

    print("Upload successful, now publishing...")

    # 3. Publish the video
    publish_url = "https://open.tiktokapis.com/v2/post/publish/"
    publish_payload = {
        "publish_id": publish_id
    }
    publish_resp = requests.post(publish_url, headers=headers, json=publish_payload)
    if publish_resp.status_code != 200:
        return f"Publish failed: {publish_resp.text}"
    
    #4. Check post status
    status_resp = check_post_status(access_token, publish_id)
    if status_resp.get("status") != "SUCCESS":
        return f"Post status check failed: {status_resp.text}"
    

    #5. Return success message
    return f"Successfully uploaded to publish_id: {publish_id}"

def check_post_status(access_token, publish_id):
    status_url = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8"
    }
    resp = requests.post(status_url, headers=headers, json={"publish_id": publish_id})
    return resp.json()