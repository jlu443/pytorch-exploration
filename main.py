from flask import Flask, request, jsonify
import yt_dlp
import re
import requests

app = Flask(__name__)

def download_video(url, resolution, subtitles=False):
    try:
        subtitles = bool(subtitles)
        ydl_opts = {
            'format': f'best[height<={resolution}]',
            'outtmpl': '%(title)s.%(ext)s',
        }

        if subtitles:
            ydl_opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,  # Fetch auto-generated subs too
                'subtitleslangs': ['en'],
                'subtitleformat': 'srt',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

            if not info_dict:  
                return False, "Failed to retrieve video information."

            subtitle_content = None

            # 1️⃣ Check for manually uploaded subtitles
            requested_subs = info_dict.get("requested_subtitles", {})
            subtitle_info = requested_subs.get("en")

            # 2️⃣ If no manual subtitles, check for automatic captions
            if not subtitle_info:
                    auto_subs = info_dict.get("automatic_captions", {})

                    # Find any English variant in automatic captions (e.g., en, en-US, en-auto)
                    english_variants = [lang for lang in auto_subs.keys() if lang.startswith("en")]

                    if english_variants:
                        subtitle_url = auto_subs[english_variants[0]][0].get("url")  # Extract first available English auto-caption URL
                    if subtitle_url:
                        response = requests.get(subtitle_url)
                        if response.status_code == 200:
                            subtitle_content = response.text  # Download the auto-generated captions
                        else:
                            subtitle_content = "Failed to download auto-generated subtitles."
                    else:
                        subtitle_content = "No English auto-captions available."


            # 3️⃣ Read from manually downloaded subtitle file if available
            if subtitle_info and isinstance(subtitle_info, dict) and "filepath" in subtitle_info:
                try:
                    with open(subtitle_info["filepath"], "r", encoding="utf-8") as file:
                        subtitle_content = file.read()
                except FileNotFoundError:
                    subtitle_content = "Subtitles not found, but video downloaded."

            return True, subtitle_content

    except Exception as e:
        return False, str(e)



def get_video_info(url):
    try:
        ydl_opts = {
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            available_subtitles = info_dict.get("subtitles", {})

            video_info = {
                "title": info_dict.get("title"),
                "author": info_dict.get("uploader"),
                "length": info_dict.get("duration"),
                "views": info_dict.get("view_count"),
                "description": info_dict.get("description"),
                "publish_date": info_dict.get("upload_date"),
                "available_subtitles": list(available_subtitles.keys()) if available_subtitles else "No subtitles available"
            }
            return video_info, None
    except Exception as e:
        return None, str(e)

def is_valid_youtube_url(url):
    pattern = r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.*$"
    return re.match(pattern, url) is not None

@app.route('/download/<resolution>', methods=['POST'])
def download_by_resolution(resolution):
    data = request.get_json()
    url = data.get('url')
    subtitles = data.get('subtitles', False)

    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400

    success, subtitle_content = download_video(url, resolution, subtitles)

    if success:
        response = {"message": f"Video with resolution {resolution} downloaded successfully."}

        # Handle subtitles explicitly
        if subtitles:
            if subtitle_content is None:
                response["subtitles"] = "Subtitles not found."
            else:
                response["subtitles"] = subtitle_content
        
        return jsonify(response), 200
    else:
        return jsonify({"error": subtitle_content}), 500


@app.route('/video_info', methods=['POST'])
def video_info():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({"error": "Missing 'url' parameter in the request body."}), 400

    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL."}), 400

    video_info, error_message = get_video_info(url)

    if video_info:
        return jsonify(video_info), 200
    else:
        return jsonify({"error": error_message}), 500

if __name__ == '__main__':
    app.run(debug=True)
