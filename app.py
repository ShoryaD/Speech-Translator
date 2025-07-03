from flask import Flask, render_template, request
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import os
import subprocess
import shutil
import azure.cognitiveservices.speech as speechsdk

# Load credentials from .env
load_dotenv()
cog_key = os.getenv("COG_SERVICE_KEY")
cog_region = os.getenv("COG_SERVICE_REGION")

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
CHUNK_FOLDER = os.path.join(UPLOAD_FOLDER, "chunks")
DEFAULT_AUDIO = "station.wav"
ALLOWED_EXTENSIONS = {"wav"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["CHUNK_FOLDER"] = CHUNK_FOLDER

LANGUAGES = {
    "fr": "French",
    "es": "Spanish",
    "hi": "Hindi",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh-Hans": "Chinese (Simplified)",
    "ru": "Russian",
    "ar": "Arabic"
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def split_audio(file_path, chunk_folder):
    os.makedirs(chunk_folder, exist_ok=True)
    chunk_pattern = os.path.join(chunk_folder, "chunk_%03d.wav")
    command = [
        "ffmpeg",
        "-i", file_path,
        "-f", "segment",
        "-segment_time", "60",
        "-c", "copy",
        chunk_pattern
    ]
    subprocess.run(command, check=True)
    return sorted([os.path.join(chunk_folder, f) for f in os.listdir(chunk_folder) if f.endswith(".wav")])

def translate_audio_continuous(target_language, audio_file):
    config = speechsdk.translation.SpeechTranslationConfig(
        subscription=cog_key,
        region=cog_region
    )
    config.speech_recognition_language = "en-US"
    config.add_target_language(target_language)

    audio_input = speechsdk.audio.AudioConfig(filename=audio_file)
    recognizer = speechsdk.translation.TranslationRecognizer(
        translation_config=config,
        audio_config=audio_input
    )

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
        used_fallback = False

        # ✅ Validate file input and fallback
        if uploaded_file and uploaded_file.filename and allowed_file(uploaded_file.filename):
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filename = secure_filename(uploaded_file.filename)
            audio_file_path = os.path.join(UPLOAD_FOLDER, filename)
            uploaded_file.save(audio_file_path)
        elif os.path.exists(DEFAULT_AUDIO):
            audio_file_path = DEFAULT_AUDIO
            used_fallback = True
        else:
            result = {
                "language": LANGUAGES.get(target_lang, target_lang),
                "recognized": "(Error)",
                "translated": "No audio uploaded, and default.wav not found."
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
                if not used_fallback and audio_file_path and os.path.exists(audio_file_path):
                    os.remove(audio_file_path)
                if os.path.exists(CHUNK_FOLDER):
                    shutil.rmtree(CHUNK_FOLDER)
            except Exception as cleanup_error:
                print(f"Cleanup error: {cleanup_error}")

        result = {
            "language": LANGUAGES.get(target_lang, target_lang),
            "recognized": recognized_all.strip(),
            "translated": translated_all.strip()
        }

    return render_template("index.html", languages=LANGUAGES, result=result)

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(CHUNK_FOLDER, exist_ok=True)
    app.run(debug=True)
