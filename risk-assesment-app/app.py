import os
import base64
import threading
import time
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image
import io

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=
                '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')

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image_file = request.files["image"]
    question = request.form.get("question")

    if image_file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(image_file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    # Convert image to base64
    img_bytes = image_file.read()
    base64_image = base64.b64encode(img_bytes).decode("utf-8")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Vision capable
            messages=[
                {
                    "role": "system",
                    "content": """You are a professional emergency risk assessment assistant
                    helping first responders. Provide:
                    1. Immediate hazards
                    2. Environmental risks
                    3. Structural threats
                    4. Recommended precautions
                    Keep responses structured and concise."""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": question
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=800
        )

        return jsonify({
            "analysis": response.choices[0].message.content
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analyze_stream", methods=["POST"])
def analyze_stream():
    def generate():
        try:
            # Get frame data from request
            frame_data = request.files.get("frame")
            question = request.form.get("question", "Analyze this frame for risks and hazards")

            if not frame_data:
                yield "data: {\"error\": \"No frame data\"}\n\n"
                return

            # Convert frame to base64
            frame_bytes = frame_data.read()
            base64_frame = base64.b64encode(frame_bytes).decode("utf-8")

            # Send to OpenAI Vision API with streaming
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a professional emergency risk assessment assistant
                        analyzing video streams. Provide quick, actionable observations about:
                        1. Immediate hazards
                        2. Environmental risks
                        3. Recommended precautions
                        Keep responses brief for real-time streaming."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": question
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_frame}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=400,
                stream=True
            )

            # Stream the response back
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield f"data: {chunk.choices[0].delta.content}\n\n"

        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True)
