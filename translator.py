# from dotenv import load_dotenv
# from datetime import datetime
# import os

# # Import namespaces


# def main():
#     try:
#         global speech_config
#         global translation_config

#         # Get Configuration Settings
#         load_dotenv()
#         cog_key = os.getenv('COG_SERVICE_KEY')
#         cog_region = os.getenv('COG_SERVICE_REGION')

#         # Configure translation


#         # Configure speech


#         # Get user input
#         targetLanguage = ''
#         while targetLanguage != 'quit':
#             targetLanguage = input('\nEnter a target language\n fr = French\n es = Spanish\n hi = Hindi\n Enter anything else to stop\n').lower()
#             if targetLanguage in translation_config.target_languages:
#                 Translate(targetLanguage)
#             else:
#                 targetLanguage = 'quit'
                

#     except Exception as ex:
#         print(ex)

# def Translate(targetLanguage):
#     translation = ''

#     # Translate speech


#     # Synthesize translation



# if __name__ == "__main__":
#     main()

from dotenv import load_dotenv
import os
import azure.cognitiveservices.speech as speechsdk

# Load environment variables
load_dotenv()
cog_key = os.getenv('COG_SERVICE_KEY')
cog_region = os.getenv('COG_SERVICE_REGION')

def main():
    try:
        # Create translation config
        translation_config = speechsdk.translation.SpeechTranslationConfig(
            subscription=cog_key, region=cog_region
        )

        # Set source language (input audio is in English)
        translation_config.speech_recognition_language = "en-US"

        # Add supported target languages
        translation_config.add_target_language("fr")  # French
        translation_config.add_target_language("es")  # Spanish
        translation_config.add_target_language("hi")  # Hindi

        # Get user input
        targetLanguage = ''
        while targetLanguage != 'quit':
            targetLanguage = input(
                '\nEnter a target language\n fr = French\n es = Spanish\n hi = Hindi\n Enter anything else to stop\n').lower()
            if targetLanguage in translation_config.target_languages:
                translate_audio(translation_config, targetLanguage)
            else:
                print("Exiting...")
                targetLanguage = 'quit'

    except Exception as ex:
        print("Error:", ex)

def translate_audio(config, target_language):
    try:
        # Create audio config (pointing to station.wav)
        audio_input = speechsdk.audio.AudioConfig(filename="station.wav")

        # Create translation recognizer
        recognizer = speechsdk.translation.TranslationRecognizer(
            translation_config=config,
            audio_config=audio_input
        )

        print(f"Translating into {target_language}...")
        result = recognizer.recognize_once_async().get()

        # Process the result
        if result.reason == speechsdk.ResultReason.TranslatedSpeech:
            print("Recognized: {}".format(result.text))
            print("Translated: {}".format(result.translations[target_language]))
        elif result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print("Recognized (but no translation): {}".format(result.text))
        elif result.reason == speechsdk.ResultReason.NoMatch:
            print("No speech could be recognized.")
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details
            print("Canceled: {}".format(cancellation.reason))
            if cancellation.reason == speechsdk.CancellationReason.Error:
                print("Error details: {}".format(cancellation.error_details))

    except Exception as e:
        print("Translation error:", e)

if __name__ == "__main__":
    main()
