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

# Read OpenAI API key from key.txt
with open(os.path.join(os.path.dirname(__file__), 'key.txt'), 'r') as f:
    OPENAI_API_KEY = f.read().strip()

app = Flask(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_system_prompt(analysis_type):
    prompts = {
        "hazards": """You are a professional emergency risk assessment assistant. Analyze the image and identify:
1. Immediate hazards and dangers
2. Environmental risks
3. Structural threats
Be concise and actionable for first responders.""",
        "survivors": """You are a professional emergency response analyst. Analyze the image and provide a simple count.
Start your response with: "There are X victims/survivors present in the image." where X is the number (0, 1, 2, etc.).
Then briefly mention any signs of occupancy or life if visible.
Keep the response concise and focused on victim count.""",
        "precautions": """You are a professional emergency safety expert. Based on the image, provide:
1. Required personal protective equipment (PPE)
2. Safety precautions and protocols
3. Recommended operational procedures
Keep recommendations specific and actionable."""
    }
    return prompts.get(analysis_type, prompts["hazards"])


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image_file = request.files["image"]
    analysis_type = request.form.get("analysis_type", "hazards")

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
                    "content": get_system_prompt(analysis_type)
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this image for emergency response purposes."
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
    # Extract request data while in request context
    frame_data = request.files.get("frame")
    analysis_type = request.form.get("analysis_type", "hazards")

    if not frame_data:
        return jsonify({"error": "No frame data"}), 400

    # Convert frame to base64 while in request context
    frame_bytes = frame_data.read()
    base64_frame = base64.b64encode(frame_bytes).decode("utf-8")

    def generate():
        try:
            # Send to OpenAI Vision API with streaming
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": get_system_prompt(analysis_type)
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analyze this video frame for emergency response purposes."
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

            # Stream the response back, preserving newlines for markdown
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    # Escape any special characters and preserve structure
                    yield f"data: {content}\n\n"

        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True)
