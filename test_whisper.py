import whisper
import os
import ssl
import urllib.request

# Disable SSL verification (for self-signed certificates)
ssl._create_default_https_context = ssl._create_unverified_context

# Add FFmpeg to PATH
os.environ["PATH"] += os.pathsep + r"D:\Altria_Ops\ffmpeg\ffmpeg-master-latest-win64-gpl-shared\bin"

print("=" * 60)
print("WHISPER TRANSCRIPTION TEST")
print("=" * 60)

print("\n📥 Loading Whisper model...")
model = whisper.load_model("base")  # "tiny" is faster for testing

# Download the recording
url = "http://216.219.88.67/RECORDINGS/MP3/20260323-175448_3016550881-all.mp3"
filename = "test_recording.mp3"

print(f"\n📥 Downloading recording from: {url}")
try:
    urllib.request.urlretrieve(url, filename)
    print(f"   ✅ Downloaded to {filename}")
except Exception as e:
    print(f"   ❌ Download failed: {e}")
    print("\nTrying alternative method...")
    # Alternative: use requests library
    try:
        import requests
        response = requests.get(url, verify=False)
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"   ✅ Downloaded to {filename} using requests")
    except Exception as e2:
        print(f"   ❌ Alternative also failed: {e2}")
        exit(1)

# Transcribe
print(f"\n🎤 Transcribing (may take 1-2 minutes)...")
result = model.transcribe(filename)

print("\n" + "=" * 60)
print("📝 TRANSCRIPT:")
print("=" * 60)
print(result["text"])
print("=" * 60)

# Clean up
os.remove(filename)
print(f"\n✅ Done! Deleted temp file: {filename}")