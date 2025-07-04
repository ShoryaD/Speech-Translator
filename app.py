from flask import Flask, render_template, request, url_for, send_from_directory
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import os
import subprocess
import shutil
import azure.cognitiveservices.speech as speechsdk

# Load environment variables
load_dotenv()
cog_key = os.getenv("COG_SERVICE_KEY")
cog_region = os.getenv("COG_SERVICE_REGION")

# Flask setup
app = Flask(__name__)

STATIC_UPLOAD_FOLDER = "static/uploads"
CHUNK_FOLDER = os.path.join(STATIC_UPLOAD_FOLDER, "chunks")
DEFAULT_AUDIO = "station.wav"
ALLOWED_EXTENSIONS = {"wav"}

app.config["UPLOAD_FOLDER"] = STATIC_UPLOAD_FOLDER
app.config["CHUNK_FOLDER"] = CHUNK_FOLDER

# Target language options
LANGUAGES = {
    "fr": "French", "es": "Spanish", "hi": "Hindi", "de": "German", "it": "Italian",
    "ja": "Japanese", "ko": "Korean", "zh-Hans": "Chinese (Simplified)", "ru": "Russian", "ar": "Arabic"
}

# Check if file is a .wav file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Split large audio into chunks for processing
def split_audio(file_path, chunk_folder):
    os.makedirs(chunk_folder, exist_ok=True)
    chunk_pattern = os.path.join(chunk_folder, "chunk_%03d.wav")
    command = ["ffmpeg", "-i", file_path, "-f", "segment", "-segment_time", "60", "-c", "copy", chunk_pattern]
    subprocess.run(command, check=True)
    return sorted([os.path.join(chunk_folder, f) for f in os.listdir(chunk_folder) if f.endswith(".wav")])

# Translate each chunk using Azure Cognitive Services
def translate_audio_continuous(target_language, audio_file):
    config = speechsdk.translation.SpeechTranslationConfig(subscription=cog_key, region=cog_region)
    config.speech_recognition_language = "en-US"
    config.add_target_language(target_language)

    audio_input = speechsdk.audio.AudioConfig(filename=audio_file)
    recognizer = speechsdk.translation.TranslationRecognizer(translation_config=config, audio_config=audio_input)

    recognized_text = []
    translated_text = []
    done = False

    def result_callback(evt):
        if evt.result.reason == speechsdk.ResultReason.TranslatedSpeech:
            recognized_text.append(evt.result.text)
            translated_text.append(evt.result.translations.get(target_language, ""))
        elif evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            recognized_text.append(evt.result.text)
            translated_text.append("(No translation)")

    def stop_callback(evt):
        nonlocal done
        done = True

    recognizer.recognized.connect(result_callback)
    recognizer.session_stopped.connect(stop_callback)
    recognizer.canceled.connect(stop_callback)

    recognizer.start_continuous_recognition()
    while not done:
        pass
    recognizer.stop_continuous_recognition()

    return " ".join(recognized_text), " ".join(translated_text)

@app.route("/", methods=["GET", "POST"])
def index():
    result = {}

    if request.method == "POST":
        target_lang = request.form.get("language")
        uploaded_file = request.files.get("audio")
        audio_file_path = None
        result_audio_path = None
        used_fallback = False

        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

        if uploaded_file and uploaded_file.filename and allowed_file(uploaded_file.filename):
            filename = secure_filename(uploaded_file.filename)
            audio_file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            uploaded_file.save(audio_file_path)
            result_audio_path = url_for("uploaded_file", filename=filename)
        elif os.path.exists(DEFAULT_AUDIO):
            audio_file_path = DEFAULT_AUDIO
            result_audio_path = url_for("serve_station_audio")
            used_fallback = True
        else:
            result = {
                "language": LANGUAGES.get(target_lang, target_lang),
                "recognized": "(Error)",
                "translated": "No audio uploaded, and station.wav not found.",
                "audio_path": None
            }
            return render_template("index.html", languages=LANGUAGES, result=result)

        recognized_all, translated_all = "", ""
        try:
            chunks = split_audio(audio_file_path, CHUNK_FOLDER)
            for chunk in chunks:
                recognized, translated = translate_audio_continuous(target_lang, chunk)
                recognized_all += recognized + " "
                translated_all += translated + " "
        except Exception as e:
            recognized_all, translated_all = "(Error)", str(e)
        finally:
            try:
                if os.path.exists(CHUNK_FOLDER):
                    shutil.rmtree(CHUNK_FOLDER)
            except Exception as cleanup_error:
                print(f"Cleanup error: {cleanup_error}")

        result = {
            "language": LANGUAGES.get(target_lang, target_lang),
            "recognized": recognized_all.strip(),
            "translated": translated_all.strip(),
            "audio_path": result_audio_path
        }

    return render_template("index.html", languages=LANGUAGES, result=result)

# Serve uploaded file from static/uploads/
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# Serve station.wav from root (used as fallback)
@app.route("/station.wav")
def serve_station_audio():
    return send_from_directory(".", DEFAULT_AUDIO)

if __name__ == "__main__":
    os.makedirs(STATIC_UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)
