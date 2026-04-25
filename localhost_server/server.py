
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/get_video_url')
def get_video_url():
    # Replace this with the actual logic to fetch the video URL
    return jsonify({'url': 'http://localhost:8000/video.mp4'})

if __name__ == '__main__':
    app.run(port=8000)
