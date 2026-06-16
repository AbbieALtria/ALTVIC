#!/usr/bin/env python3
"""
AI Assistant for Automated QC Scoring
Professional Interface - Real Agents, Pagination, Campaign/Agent/Date filters
Version: 5.0.0 - Fixed PyInstaller bundling for Whisper assets
Changes: - Added get_resource_path() for PyInstaller _MEIPASS support
         - Fixed mel_filters.npz not found error
         - Proper asset directory detection for frozen executables
         - Enhanced PDF report with full checkpoint details, transcript preview, and visual indicators
"""

import os
import sys
import ssl
import urllib.request
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# All timestamps use Eastern time — matches ViciDial call_date column
EST = ZoneInfo("America/New_York")
def now_est() -> datetime:
    return datetime.now(EST)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Suppress Whisper FP16 warning on CPU
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

import whisper
from core.database import db
from utils.colors import Colors, print_header, print_success, print_error, print_info, print_warning, print_color

# Try to import PDF libraries
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print_warning("PDF export requires reportlab. Install with: pip install reportlab")

# Disable SSL verification for self-signed certs
ssl._create_default_https_context = ssl._create_unverified_context

# Configuration
RECORDINGS_BASE_URL = "http://216.219.88.67/RECORDINGS/MP3/"
TEMP_DIR = Path(__file__).parent.parent / "temp"
EXPORTS_DIR = Path(__file__).parent.parent / "exports" / "qc_reports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)


def get_resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    When running as .exe, PyInstaller stores files in _MEIPASS temp folder.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Running as script - use current directory
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


def setup_ffmpeg():
    """
    Add FFmpeg to PATH. Handles three cases:
      1. Frozen .exe  -> ffmpeg bundled by PyInstaller into exe_dir/ffmpeg/
      2. Dev script   -> ffmpeg lives at src/ffmpeg/.../bin/ relative to this file
      3. System PATH  -> ffmpeg already installed globally (fallback)
    """
    if getattr(sys, 'frozen', False):
        # Running as .exe — PyInstaller places binaries next to the executable
        exe_dir = Path(sys.executable).parent
        bundled_path = exe_dir / "ffmpeg"
        if bundled_path.exists():
            os.environ["PATH"] = str(bundled_path) + os.pathsep + os.environ.get("PATH", "")
            return True
        # Also check _MEIPASS temp dir (one-file mode)
        meipass_ffmpeg = Path(getattr(sys, '_MEIPASS', '')) / "ffmpeg"
        if meipass_ffmpeg.exists():
            os.environ["PATH"] = str(meipass_ffmpeg) + os.pathsep + os.environ.get("PATH", "")
            return True
    else:
        # Dev / script mode
        possible_paths = [
            Path(__file__).parent / "ffmpeg" / "ffmpeg-master-latest-win64-gpl-shared" / "bin",
            Path(__file__).parent.parent / "ffmpeg" / "ffmpeg-master-latest-win64-gpl-shared" / "bin",
            r"C:\ffmpeg\bin",
            r"C:\Program Files\ffmpeg\bin",
        ]
        for path in possible_paths:
            if Path(path).exists():
                os.environ["PATH"] += os.pathsep + str(path)
                return True

    # Rely on system PATH as last resort
    return False


setup_ffmpeg()

# Whisper model — loaded once and reused
whisper_model = None


# =============================================================================
# Helper Functions
# =============================================================================

def get_whisper_model():
    """
    Load Whisper 'base' model with full PyInstaller support.
    - Handles both .exe and script modes
    - Properly locates bundled assets (mel_filters.npz) via _MEIPASS
    - Sets WHISPER_ASSETS_DIR environment variable for the library
    - Caches model to exe_dir/models/whisper/ or project_root/models/whisper/
    First run downloads ~142 MB; subsequent runs load from disk instantly.
    """
    global whisper_model

    if whisper_model is not None:
        return whisper_model

    print(f"{Colors.CYAN}i{Colors.RESET} Loading AI model (first time ~10-30s)... ", end="", flush=True)

    try:
        if getattr(sys, 'frozen', False):
            # Running as compiled .exe
            exe_dir = Path(sys.executable).parent
            model_dir = exe_dir / "models" / "whisper"
            
            # CRITICAL FIX: Tell Whisper where to find bundled asset files
            # The assets are located at whisper/assets relative to _MEIPASS
            if hasattr(sys, '_MEIPASS'):
                assets_dir = get_resource_path("whisper/assets")
                if os.path.exists(assets_dir):
                    os.environ["WHISPER_ASSETS_DIR"] = assets_dir
        else:
            # Running as script
            model_dir = Path(__file__).parent.parent / "models" / "whisper"

        # Create model directory if it doesn't exist
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # Load the model - Whisper will now find assets via the environment variable
        whisper_model = whisper.load_model("base", download_root=str(model_dir))

        print(f"{Colors.GREEN} Ready!{Colors.RESET}")
        return whisper_model

    except Exception as e:
        print(f"{Colors.RED} Failed: {e}{Colors.RESET}")
        print(f"{Colors.YELLOW}   Tip: Make sure whisper/assets is included in the build with --add-data{Colors.RESET}")
        raise


def get_rating_text(percentage):
    """Get professional rating text based on percentage"""
    if percentage >= 90:
        return "🌟 Excellent - Exceeds expectations"
    elif percentage >= 80:
        return "✅ Good - Meets expectations"
    elif percentage >= 70:
        return "📊 Satisfactory - Minor improvements needed"
    elif percentage >= 60:
        return "⚠️ Needs Work - Requires coaching"
    else:
        return "🔴 Poor - Immediate attention required"


def get_confidence_text(confidence):
    """Get confidence rating text"""
    if confidence >= 85:
        return "High Confidence"
    elif confidence >= 70:
        return "Medium Confidence"
    else:
        return "Low Confidence - Review Required"


def get_progress_bar(score, max_points, width=20):
    """Generate a visual progress bar for PDF"""
    if max_points <= 0:
        return "░░░░░░░░░░░░░░░░░░░░"
    percentage = score / max_points
    filled = int(width * percentage)
    empty = width - filled
    return "█" * filled + "░" * empty


# =============================================================================
# Data Retrieval Functions
# =============================================================================

def get_campaigns():
    """Get list of campaigns with recordings"""
    query = """
    SELECT DISTINCT campaign_id 
    FROM vicidial_closer_log 
    WHERE call_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    ORDER BY campaign_id
    """
    results = db.execute_query(query) or []
    return [r['campaign_id'] for r in results if r['campaign_id']]


def get_agents(campaign_id=None):
    """Get real agents for a campaign from agent_log"""
    if campaign_id:
        query = """
        SELECT DISTINCT a.user, u.full_name
        FROM vicidial_agent_log a
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE a.campaign_id = %s
          AND a.event_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
          AND a.user NOT IN ('6668', '6666', '6667', 'QA', 'MGR')
          AND a.user NOT LIKE '%%17177027118%%'
        ORDER BY a.user
        """
        results = db.execute_query(query, (campaign_id,)) or []
    else:
        query = """
        SELECT DISTINCT user, full_name
        FROM vicidial_users
        WHERE active = 'Y'
          AND user NOT IN ('6668', '6666', '6667', 'QA', 'MGR')
          AND user NOT LIKE '%%17177027118%%'
        ORDER BY user
        LIMIT 100
        """
        results = db.execute_query(query) or []
    
    agents = []
    for r in results:
        name = r.get('full_name', r['user'])
        if not name or name == r['user']:
            name = r['user']
        agents.append({
            'user': r['user'],
            'name': str(name) if name else str(r['user'])
        })
    return agents


def get_calls_for_evaluation(campaign_id=None, agent=None, days=7, page=1, page_size=50):
    """
    Get calls ready for evaluation with pagination - excludes already evaluated calls
    SIMPLIFIED: Gets calls first, then checks for recordings separately
    """
    
    offset = (page - 1) * page_size
    
    # First, get calls without recording check
    query = """
    SELECT 
        c.uniqueid,
        c.call_date,
        c.campaign_id,
        c.phone_number,
        c.length_in_sec,
        c.queue_seconds,
        a.user as agent_user,
        u.full_name as agent_name
    FROM vicidial_closer_log c
    LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
    LEFT JOIN vicidial_users u ON a.user = u.user
    WHERE c.call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
      AND c.length_in_sec >= 5
      AND c.uniqueid NOT IN (SELECT uniqueid FROM qc_results WHERE status = 'ACTIVE' OR status IS NULL)
    """
    
    params = [days]
    
    if campaign_id:
        query += " AND c.campaign_id = %s"
        params.append(campaign_id)
    
    if agent:
        query += " AND a.user = %s"
        params.append(agent)
    
    # Add pagination
    query += " ORDER BY c.call_date DESC LIMIT %s OFFSET %s"
    params.extend([page_size, offset])
    
    try:
        results = db.execute_query(query, params) or []
    except Exception as e:
        print_error(f"Main query error: {e}")
        return [], 0
    
    # Now check each call for a recording
    safe_results = []
    for r in results:
        phone = r.get('phone_number', '')
        call_date = r.get('call_date')
        
        if not phone or not call_date:
            continue
            
        # Try to find recording by phone number in filename and date
        try:
            recording_query = """
            SELECT filename, location 
            FROM recording_log 
            WHERE filename LIKE %s
              AND DATE(start_time) = %s
            LIMIT 1
            """
            
            # Create pattern with phone number
            pattern = f"%{phone}%"
            recording = db.execute_query(recording_query, (pattern, call_date.date()))
            
            if recording and recording[0].get('filename'):
                safe_call = {
                    'uniqueid': r.get('uniqueid', ''),
                    'call_date': r.get('call_date', now_est()),
                    'campaign_id': r.get('campaign_id', 'Unknown'),
                    'phone_number': r.get('phone_number', 'Unknown'),
                    'length_in_sec': r.get('length_in_sec', 0) or 0,
                    'queue_seconds': r.get('queue_seconds', 0) or 0,
                    'agent_user': r.get('agent_user', 'Unknown'),
                    'agent_name': r.get('agent_name') or r.get('agent_user') or 'Unknown',
                    'filename': recording[0].get('filename', ''),
                    'location': recording[0].get('location', '')
                }
                safe_results.append(safe_call)
        except Exception:
            # Silently skip recording check errors
            continue
    
    # Get total count
    total_calls = len(safe_results)
    
    return safe_results, total_calls


def get_checkpoints():
    """Get checkpoints for SOP_COMP scorecard"""
    query = """
    SELECT checkpoint_id, checkpoint_text, max_points, display_order
    FROM qc_checkpoints
    WHERE scorecard_id = 1 AND active = 'Y'
    ORDER BY display_order
    """
    results = db.execute_query(query) or []
    return results


# =============================================================================
# Audio Processing Functions
# =============================================================================

def download_recording(uniqueid, phone_number=None, call_date=None):
    """
    Download recording using phone number and date first, fallback to uniqueid
    """
    
    filename = None
    location = None
    
    # Method 1: Try to find by phone number and date (preferred method)
    if phone_number and call_date:
        query = """
        SELECT filename, location 
        FROM recording_log 
        WHERE filename LIKE %s
          AND DATE(start_time) = %s
        LIMIT 1
        """
        
        pattern = f"%{phone_number}%"
        result = db.execute_query(query, (pattern, call_date.date()))
        
        if result and result[0].get('filename'):
            filename = result[0]['filename']
            location = result[0].get('location', '')
    
    # Method 2: Fallback to original method using vicidial_id
    if not filename:
        query = "SELECT filename, location FROM recording_log WHERE vicidial_id = %s LIMIT 1"
        result = db.execute_query(query, (uniqueid,))
        
        if result and result[0].get('filename'):
            filename = result[0]['filename']
            location = result[0].get('location', '')
    
    if not filename:
        print_error(f"No recording found for this call")
        return None
    
    local_path = TEMP_DIR / filename
    
    if local_path.exists():
        print_info(f"Using cached recording")
        return local_path
    
    # Build URL
    if location and location.startswith('http'):
        url = location
    else:
        url = RECORDINGS_BASE_URL + filename
        if not url.endswith('.mp3'):
            url += '.mp3'
    
    # Use standard print for inline progress
    print(f"{Colors.CYAN}ℹ️{Colors.RESET} Downloading recording... ", end="", flush=True)
    try:
        urllib.request.urlretrieve(url, local_path)
        print(f"{Colors.GREEN}Done!{Colors.RESET}")
        return local_path
    except Exception as e:
        print(f"{Colors.RED} Failed: {e}{Colors.RESET}")
        return None


def transcribe_audio(audio_path):
    """Transcribe audio using Whisper. Normalises double/bad extensions before transcoding."""
    import shutil, tempfile as _tmp
    model = get_whisper_model()
    print(f"{Colors.CYAN}i{Colors.RESET} Transcribing audio... ", end="", flush=True)

    audio_path = Path(audio_path)

    # If the file has a non-standard extension (e.g. .mp3.mpeg, .mpeg, .wave)
    # rename a copy to .mp3 so FFmpeg decodes it correctly.
    normalized = audio_path
    stem = audio_path.name
    if stem.endswith('.mp3.mpeg') or stem.endswith('.mpeg') or not stem.endswith('.mp3'):
        normalized = audio_path.parent / (audio_path.stem.replace('.mp3', '') + '.mp3')
        if not normalized.exists():
            shutil.copy2(audio_path, normalized)

    try:
        result = model.transcribe(str(normalized))
        print(f"{Colors.GREEN}Done!{Colors.RESET}")
        return result["text"]
    except Exception as e:
        print(f"{Colors.RED} Failed: {e}{Colors.RESET}")
        return ""


# =============================================================================
# Analysis Functions
# =============================================================================

def calculate_confidence(scores, max_points):
    """Calculate AI confidence based on score distribution and completeness"""
    if not scores or not max_points:
        return 70.0
    
    score_values = list(scores.values())
    if not score_values:
        return 70.0
    
    avg = sum(score_values) / len(score_values)
    variance = sum((s - avg) ** 2 for s in score_values) / len(score_values)
    std_dev = variance ** 0.5
    
    std_score = min(30, std_dev * 3)
    zero_count = sum(1 for s in score_values if s == 0)
    zero_penalty = (zero_count / len(score_values)) * 20
    
    confidence = 70 + std_score - zero_penalty
    return min(100, max(50, confidence))


def detect_ghost_call(transcript, duration_sec=0):
    """
    Detect ghost calls (no live customer interaction) before scoring.
    Returns a dict:
        call_type : 'NORMAL' | 'GHOST' | 'SUSPICIOUS' | 'SHORT_REVIEW'
        reason    : human-readable explanation
        word_count: int
    """
    GHOST_DURATION_THRESHOLD = 60

    text = (transcript or "").strip()
    words = text.split()
    word_count = len(words)

    # Layer 1: Empty transcript
    if word_count == 0:
        return {"call_type": "GHOST",
                "reason": "Empty transcript — no audio content detected",
                "word_count": 0}

    # Layer 2: Very short transcript — split on duration
    if word_count <= 8:
        if duration_sec > 0 and duration_sec >= GHOST_DURATION_THRESHOLD:
            return {
                "call_type": "SUSPICIOUS",
                "reason": (f"Only {word_count} word(s) transcribed but call was "
                           f"{duration_sec//60}:{duration_sec%60:02d} long — "
                           f"possible call avoidance or silent agent. QA review required."),
                "word_count": word_count
            }
        return {"call_type": "GHOST",
                "reason": (f"Transcript too short ({word_count} words) — "
                           f"likely silence or IVR tone"),
                "word_count": word_count}

    text_lower = text.lower()

    # Layer 3: IVR / Automated voicemail patterns
    ivr_patterns = [
        "our customer support team is available",
        "our office is available",
        "our office hours are",
        "we are available",
        "available monday through",
        "available monday to",
        "available from monday",
        "your call is very important",
        "all of our representatives are",
        "please listen carefully as our menu",
        "press 1 for",
        "press 2 for",
        "to speak to a representative",
        "if you know your party's extension",
        "for quality assurance purposes",
        "this call may be recorded",
        "please continue to hold",
        "estimated wait time",
        "please leave a message",
        "leave a message after the tone",
        "mailbox is full",
        "the number you have reached",
        "this number is no longer in service",
    ]
    ivr_hits = [p for p in ivr_patterns if p in text_lower]
    if ivr_hits:
        if duration_sec > 0 and duration_sec >= GHOST_DURATION_THRESHOLD:
            return {
                "call_type": "SUSPICIOUS",
                "reason": (f"IVR message detected (matched: '{ivr_hits[0]}') but call was "
                           f"{duration_sec//60}:{duration_sec%60:02d} long — "
                           f"recording may be truncated. QA review required."),
                "word_count": word_count
            }
        return {
            "call_type": "GHOST",
            "reason": (f"IVR/automated message detected — no live agent present. "
                       f"Matched: '{ivr_hits[0]}'"),
            "word_count": word_count
        }

    # Layer 4: No live agent speech signals
    direct_address = ["you", "your", "sir", "ma'am", "maam", "mr.", "ms.", "mrs.",
                      "hello", "hi there", "good morning", "good afternoon", "good evening"]
    has_direct_address = any(p in text_lower for p in direct_address)

    interactive_phrases = [
        "how can i help", "how may i help", "how can i assist",
        "can i have your", "can i get your", "may i have your",
        "let me check", "let me look", "give me a moment",
        "i can help you", "i'll help you",
        "anything else", "is there anything",
        "have a great", "have a wonderful", "take care",
    ]
    has_interactive = any(p in text_lower for p in interactive_phrases)

    if not has_direct_address and not has_interactive:
        return {
            "call_type": "GHOST",
            "reason": (f"No live agent interaction detected — {word_count} words, likely IVR/noise"),
            "word_count": word_count
        }

    # Layer 5: Duration gates
    if duration_sec > 0 and duration_sec < 30:
        return {
            "call_type": "GHOST",
            "reason": f"Call duration only {duration_sec}s — too short for real interaction",
            "word_count": word_count
        }

    if duration_sec > 0 and duration_sec < GHOST_DURATION_THRESHOLD:
        return {
            "call_type": "SHORT_REVIEW",
            "reason": (f"Short call ({duration_sec//60}:{duration_sec%60:02d}) — "
                       f"score greeting/closing only, review manually"),
            "word_count": word_count
        }

    return {"call_type": "NORMAL", "reason": "Normal call", "word_count": word_count}


# Checkpoints that apply to ghost/short calls
GHOST_APPLICABLE_CHECKPOINTS = {1, 5}


def analyze_transcript(transcript):
    """Analyze transcript and suggest scores with confidence"""
    
    transcript_lower = transcript.lower()
    
    keywords = {
        1: {"positive": ["thank you for calling", "how can i help", "good morning", "good afternoon", "welcome"], "negative": [], "weight": 1.0},
        2: {"positive": ["thank you", "appreciate", "apologize", "certainly", "absolutely", "happy to help"], "negative": ["what?!", "can't", "won't", "no way"], "weight": 1.0},
        3: {"positive": ["can i have your", "verify", "confirm", "first and last name", "email address", "account"], "negative": [], "weight": 1.2},
        4: {"positive": ["let me check", "give me a sec", "processing", "resolve", "fix", "i can help"], "negative": ["please hold", "transferring", "hold on"], "weight": 1.0},
        5: {"positive": ["anything else", "have a great", "thank you for calling", "take care"], "negative": [], "weight": 1.0},
        6: {"positive": ["record", "note", "document", "update", "account"], "negative": [], "weight": 1.0},
        7: {"positive": ["escalated", "back office", "process", "approved", "standard procedure"], "negative": ["bypass", "exception"], "weight": 1.2},
        8: {"positive": ["thank you", "appreciate", "great", "awesome", "perfect", "excellent"], "negative": ["upset", "frustrated", "angry", "unhappy"], "weight": 1.0},
        9: {"positive": ["apologize", "resolve", "refund", "credit", "solution"], "negative": ["can't", "won't", "no refund", "not possible"], "weight": 1.5}
    }
    
    scores = {}
    for cp_id, kw in keywords.items():
        pos = sum(1 for k in kw.get("positive", []) if k in transcript_lower)
        neg = sum(1 for k in kw.get("negative", []) if k in transcript_lower)
        raw_score = min(10, max(0, 6 + pos - neg * 2))
        weighted_score = raw_score * kw.get("weight", 1.0)
        scores[cp_id] = min(10, weighted_score)
    
    confidence = calculate_confidence(scores, {1: 10, 2: 10, 3: 15, 4: 10, 5: 10, 6: 10, 7: 15, 8: 10, 9: 10})
    
    notes = []
    if "verify" in transcript_lower or "confirm" in transcript_lower:
        notes.append("✓ Verification completed")
    if "refund" in transcript_lower or "credit" in transcript_lower:
        notes.append("💰 Refund/credit processed")
    if "apologize" in transcript_lower:
        notes.append("🤝 Agent apologized")
    if "thank you" in transcript_lower:
        notes.append("👍 Customer gratitude")
    if not notes:
        notes.append("📝 Standard call")
    
    compliance_issues = []
    if "can't" in transcript_lower and "refund" in transcript_lower:
        compliance_issues.append("Initial denial")
    
    return {
        "scores": scores,
        "notes": " | ".join(notes),
        "compliance": "None" if not compliance_issues else ", ".join(compliance_issues),
        "confidence": confidence,
        "call_type": "NORMAL",
        "ghost_reason": ""
    }


# =============================================================================
# PDF Generation Functions - ENHANCED VERSION
# =============================================================================

def generate_pdf_report(selected_call, scores, checkpoints, total_score, total_max, percentage, analysis, result_id, na_checkpoints=None):
    """Generate COMPLETE professional PDF report matching terminal output"""
    
    if not PDF_AVAILABLE:
        print_warning("PDF generation requires reportlab. Install with: pip install reportlab")
        return None
    
    na_checkpoints = na_checkpoints or set()
    call_type = analysis.get('call_type', 'NORMAL')
    ghost_reason = analysis.get('ghost_reason', '')
    
    # Safe filename generation
    agent_name_raw = selected_call.get('agent_name') or selected_call.get('agent_user') or 'Unknown'
    agent_name = str(agent_name_raw).replace(' ', '_').replace('/', '_').replace('\\', '_')
    
    campaign_raw = selected_call.get('campaign_id') or 'Unknown'
    campaign = str(campaign_raw).replace(' ', '_').replace('/', '_').replace('\\', '_')
    
    call_date_obj = selected_call.get('call_date')
    if call_date_obj and hasattr(call_date_obj, 'strftime'):
        call_date_str = call_date_obj.strftime('%Y%m%d_%H%M%S')
    else:
        call_date_str = now_est().strftime('%Y%m%d_%H%M%S')
    
    phone_raw = selected_call.get('phone_number') or '0000'
    phone = str(phone_raw)[-4:] if len(str(phone_raw)) >= 4 else '0000'
    
    filename = f"QC_{campaign}_{agent_name}_{call_date_str}_{phone}.pdf"
    filepath = EXPORTS_DIR / filename
    
    try:
        doc = SimpleDocTemplate(str(filepath), pagesize=letter, 
                                rightMargin=50, leftMargin=50, 
                                topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                     fontSize=20, spaceAfter=20, alignment=TA_CENTER, 
                                     textColor=colors.HexColor('#2c3e50'))
        header_style = ParagraphStyle('Header', parent=styles['Heading2'], 
                                      fontSize=14, spaceAfter=12, spaceBefore=12,
                                      textColor=colors.HexColor('#3498db'))
        subheader_style = ParagraphStyle('SubHeader', parent=styles['Heading3'],
                                         fontSize=12, spaceAfter=8,
                                         textColor=colors.HexColor('#7f8c8d'))
        normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=10)
        monospace_style = ParagraphStyle('Monospace', parent=styles['Normal'], 
                                         fontName='Courier', fontSize=9, 
                                         leftIndent=10, rightIndent=10)
        
        # =====================================================================
        # HEADER / TITLE
        # =====================================================================
        story.append(Paragraph("ALTRIA OPERATIONS SYSTEM", title_style))
        story.append(Paragraph("Quality Control Evaluation Report", title_style))
        story.append(Spacer(1, 10))
        
        # =====================================================================
        # GHOST / SUSPICIOUS BANNER (if applicable)
        # =====================================================================
        if call_type in ("GHOST", "SUSPICIOUS", "SHORT_REVIEW"):
            if call_type == "GHOST":
                banner_text = "⚠️ GHOST CALL DETECTED — Partial Evaluation"
                banner_bg = colors.HexColor('#f8d7da')
                banner_color = colors.HexColor('#721c24')
            elif call_type == "SUSPICIOUS":
                banner_text = "⚠️ SUSPICIOUS CALL — QA Review Required"
                banner_bg = colors.HexColor('#fff3cd')
                banner_color = colors.HexColor('#856404')
            else:
                banner_text = "⚠️ SHORT CALL — Review Required"
                banner_bg = colors.HexColor('#fff3cd')
                banner_color = colors.HexColor('#856404')
            
            banner_style = ParagraphStyle('Banner', parent=styles['Normal'], 
                                          fontSize=11, alignment=TA_CENTER, 
                                          backColor=banner_bg, 
                                          textColor=banner_color,
                                          borderColor=banner_color, 
                                          borderWidth=1, borderPadding=8)
            story.append(Paragraph(banner_text, banner_style))
            if ghost_reason:
                reason_style = ParagraphStyle('Reason', parent=styles['Normal'], 
                                              fontSize=9, textColor=banner_color,
                                              leftIndent=10, spaceAfter=10)
                story.append(Paragraph(f"Detection: {ghost_reason}", reason_style))
            story.append(Spacer(1, 10))
        
        # =====================================================================
        # CALL INFORMATION TABLE
        # =====================================================================
        story.append(Paragraph("Call Information", header_style))
        
        # Format call date
        if call_date_obj and hasattr(call_date_obj, 'strftime'):
            call_date_display = call_date_obj.strftime('%Y-%m-%d %H:%M:%S')
        else:
            call_date_display = str(call_date_obj) if call_date_obj else 'Unknown'
        
        duration_sec = selected_call.get('length_in_sec', 0) or 0
        duration_display = f"{duration_sec // 60}:{duration_sec % 60:02d}"
        phone_display = str(selected_call.get('phone_number', 'Unknown'))
        
        call_info_data = [
            ["Campaign:", campaign_raw],
            ["Agent:", agent_name_raw],
            ["Phone Number:", phone_display],
            ["Call Date:", call_date_display],
            ["Duration:", duration_display],
            ["Call Type:", call_type],
            ["Evaluation ID:", str(result_id) if result_id else "Not saved"],
            ["AI Confidence:", f"{analysis.get('confidence', 0):.0f}% - {get_confidence_text(analysis.get('confidence', 70))}"],
            ["Evaluation Date:", now_est().strftime('%Y-%m-%d %H:%M:%S') + " EST"]
        ]
        
        call_info_table = Table(call_info_data, colWidths=[100, 400])
        call_info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(call_info_table)
        story.append(Spacer(1, 15))
        
        # =====================================================================
        # SCORE SUMMARY WITH RATING COLOR
        # =====================================================================
        story.append(Paragraph("Score Summary", header_style))
        
        # Color based on percentage
        if percentage >= 80:
            score_color = colors.HexColor('#27ae60')
            rating_bg = colors.HexColor('#d5f5e3')
        elif percentage >= 60:
            score_color = colors.HexColor('#f39c12')
            rating_bg = colors.HexColor('#fef9e7')
        else:
            score_color = colors.HexColor('#e74c3c')
            rating_bg = colors.HexColor('#fadbd8')
        
        score_summary_data = [
            ["Total Score:", f"{total_score} / {total_max}"],
            ["Percentage:", f"{percentage:.1f}%"],
            ["Rating:", get_rating_text(percentage)],
        ]
        
        score_table = Table(score_summary_data, colWidths=[100, 400])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('BACKGROUND', (1, 2), (1, 2), rating_bg),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TEXTCOLOR', (1, 1), (1, 1), score_color),
            ('FONTNAME', (1, 1), (1, 1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(score_table)
        story.append(Spacer(1, 20))
        
        # =====================================================================
        # CHECKPOINT DETAILS WITH VISUAL BARS (MATCHING TERMINAL OUTPUT)
        # =====================================================================
        story.append(Paragraph("SOP Checkpoint Analysis", header_style))
        
        # Prepare checkpoint table headers
        checkpoint_data = [["#", "Checkpoint", "Score", "Max", "%", "Progress", "Status"]]
        
        for cp in checkpoints:
            cp_id = cp['checkpoint_id']
            cp_text = cp['checkpoint_text']
            max_pts = cp['max_points']
            order = cp.get('display_order', cp_id)
            
            if cp_id in na_checkpoints:
                checkpoint_data.append([str(order), cp_text, "N/A", str(max_pts), "—", "—", "Not Applicable"])
            else:
                score_val = scores.get(cp_id, 0)
                pct = (score_val / max_pts * 100) if max_pts > 0 else 0
                progress_bar = get_progress_bar(score_val, max_pts, 15)
                
                if pct >= 80:
                    status = "✅ Excellent"
                elif pct >= 60:
                    status = "📊 Good"
                else:
                    status = "⚠️ Needs Improvement"
                
                checkpoint_data.append([str(order), cp_text, str(score_val), str(max_pts), f"{pct:.0f}%", progress_bar, status])
        
        checkpoint_table = Table(checkpoint_data, colWidths=[30, 220, 40, 40, 45, 80, 85])
        checkpoint_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        
        # Apply row colors based on performance
        for i, cp in enumerate(checkpoints, 1):
            cp_id = cp['checkpoint_id']
            max_pts = cp['max_points']
            
            if cp_id in na_checkpoints:
                checkpoint_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f2f3f4')),
                    ('TEXTCOLOR', (0, i), (-1, i), colors.HexColor('#aab2bd'))
                ]))
            else:
                score_val = scores.get(cp_id, 0)
                pct = (score_val / max_pts * 100) if max_pts > 0 else 0
                if pct >= 80:
                    checkpoint_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#d5f5e3'))
                    ]))
                elif pct >= 60:
                    checkpoint_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fef9e7'))
                    ]))
                else:
                    checkpoint_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fadbd8'))
                    ]))
        
        story.append(checkpoint_table)
        story.append(Spacer(1, 20))
        
        # =====================================================================
        # AI ANALYSIS NOTES
        # =====================================================================
        story.append(Paragraph("AI Analysis Notes", header_style))
        notes_text = analysis.get('notes', 'No AI notes available')
        notes_html = notes_text.replace(' | ', '<br/>• ')
        if not notes_html.startswith('•'):
            notes_html = f"• {notes_html}"
        notes_paragraph = Paragraph(f"<bullet>{notes_html}</bullet>", normal_style)
        story.append(notes_paragraph)
        story.append(Spacer(1, 10))
        
        # =====================================================================
        # COMPLIANCE ISSUES (if any)
        # =====================================================================
        compliance = analysis.get('compliance', 'None')
        if compliance != "None" and compliance != "":
            story.append(Paragraph("⚠️ Compliance Issues", subheader_style))
            compliance_style = ParagraphStyle('Compliance', parent=normal_style,
                                               textColor=colors.HexColor('#e74c3c'))
            story.append(Paragraph(f"• {compliance}", compliance_style))
            story.append(Spacer(1, 10))
        
        # =====================================================================
        # CALL TRANSCRIPT PREVIEW
        # =====================================================================
        story.append(Paragraph("Call Transcript Preview", header_style))
        
        # Get transcript preview
        transcript_text = analysis.get('transcript_preview', 'No transcript available')
        
        # Format transcript
        transcript_lines = []
        for i in range(0, min(len(transcript_text), 1200), 80):
            transcript_lines.append(transcript_text[i:i+80])
        transcript_display = '\n'.join(transcript_lines[:12])
        if len(transcript_lines) > 12:
            transcript_display += "\n... (truncated)"
        
        transcript_paragraph = Paragraph(transcript_display.replace('\n', '<br/>'), monospace_style)
        story.append(transcript_paragraph)
        story.append(Spacer(1, 15))
        
        # =====================================================================
        # WORD COUNT AND DURATION STATS
        # =====================================================================
        story.append(Paragraph("Call Quality Indicators", subheader_style))
        word_count = ghost_info.get('word_count', 0) if 'ghost_info' in dir() else len((analysis.get('transcript_preview', '')).split())
        
        stats_data = [
            ["Word Count:", str(word_count) if word_count else "N/A"],
            ["Words per Minute:", f"{word_count / (duration_sec / 60) if duration_sec > 0 and word_count else 0:.0f}" if word_count else "N/A"],
            ["Call Type Rationale:", ghost_reason[:200] + "..." if len(ghost_reason) > 200 else ghost_reason if ghost_reason else "Normal call"]
        ]
        stats_table = Table(stats_data, colWidths=[100, 400])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 15))
        
        # =====================================================================
        # FOOTER
        # =====================================================================
        story.append(Spacer(1, 30))
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], 
                                      fontSize=8, alignment=TA_CENTER, 
                                      textColor=colors.HexColor('#7f8c8d'))
        story.append(Paragraph(f"Generated by Altria Ops AI Assistant v5.0.0", footer_style))
        story.append(Paragraph(f"Report Date: {now_est().strftime('%Y-%m-%d %H:%M:%S')} EST", footer_style))
        story.append(Paragraph("This report is for internal quality assurance purposes only.", footer_style))
        
        # Build the PDF
        doc.build(story)
        return filepath
        
    except Exception as e:
        print_error(f"PDF generation error: {e}")
        import traceback
        traceback.print_exc()
        return None


# =============================================================================
# Database Save Functions
# =============================================================================

def save_evaluation(uniqueid, scores, ai_scores, notes, total_score, ai_total_score, analysis, user='6668'):
    """Save evaluation to database with full audit trail"""
    try:
        # Check if this call already has an evaluation
        existing = db.execute_query("""
            SELECT result_id, total_score, evaluation_date 
            FROM qc_results 
            WHERE uniqueid = %s AND (status = 'ACTIVE' OR status IS NULL)
        """, (uniqueid,))
        
        if existing:
            print_warning(f"\n⚠️ This call has already been evaluated!")
            print_info(f"   Previous evaluation ID: {existing[0]['result_id']}")
            print_info(f"   Previous score: {existing[0]['total_score']}%")
            print_info(f"   Previous date: {existing[0]['evaluation_date']}")
            
            confirm = input(f"\n{Colors.YELLOW}Do you want to overwrite the existing evaluation? (y/N): {Colors.RESET}").strip().lower()
            
            if confirm != 'y':
                print_info("Save cancelled - existing evaluation preserved")
                return False, "Cancelled - evaluation already exists"
            
            # Archive the old evaluation
            print_info("Archiving previous evaluation...")
            db.execute_query("""
                UPDATE qc_results 
                SET status = 'ARCHIVED', 
                    archived_date = NOW(),
                    archived_by = %s,
                    archived_reason = 'Overwritten by new evaluation'
                WHERE uniqueid = %s
            """, (user, uniqueid))
            
            # Delete old checkpoint scores
            db.execute_query("""
                DELETE FROM qc_results_detail 
                WHERE result_id = %s
            """, (existing[0]['result_id'],))
            
            print_success("Previous evaluation archived")
        
        # Insert evaluation header
        query = """
            INSERT INTO qc_results 
            (scorecard_id, uniqueid, evaluation_date, total_score, evaluator, 
             ai_total_score, ai_analysis, source, ai_confidence, reviewed_by, reviewed_at, comments, status)
            VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, NOW(), %s, 'ACTIVE')
        """
        
        params = (
            1, uniqueid, total_score, user, ai_total_score,
            analysis.get('notes', ''), 'HYBRID', analysis.get('confidence', 70),
            user, notes or analysis.get('notes', '')
        )
        
        db.execute_query(query, params)
        
        # Get the result_id
        result = db.execute_query("""
            SELECT result_id FROM qc_results 
            WHERE uniqueid = %s 
            ORDER BY evaluation_date DESC 
            LIMIT 1
        """, (uniqueid,))
        
        if not result:
            print_error("Could not retrieve result_id")
            return False, "Could not retrieve result_id"
        
        result_id = result[0]['result_id']
        
        # Insert checkpoint scores
        for checkpoint_id, score_given in scores.items():
            db.execute_query("""
                INSERT INTO qc_results_detail (result_id, checkpoint_id, score_given)
                VALUES (%s, %s, %s)
            """, (result_id, checkpoint_id, score_given))
        
        # Save notes to separate table (optional)
        try:
            db.execute_query("""
                INSERT INTO altria_qc_notes (result_id, notes, ai_analysis)
                VALUES (%s, %s, %s)
            """, (result_id, notes or analysis.get('notes', ''), analysis.get('notes', '')))
        except Exception:
            pass
        
        return True, result_id
        
    except Exception as e:
        print_error(f"Save error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


# =============================================================================
# Interactive Selection Functions
# =============================================================================

def select_campaign():
    """Interactive campaign selection"""
    campaigns = get_campaigns()
    
    if not campaigns:
        print_error("No campaigns found")
        return None
    
    print("\n📋 SELECT CAMPAIGN:")
    print("-" * 50)
    col_width = 20
    cols = 4
    for i, camp in enumerate(campaigns, 1):
        print(f"{i:3}. {camp:<{col_width-4}}", end="")
        if i % cols == 0:
            print()
    if len(campaigns) % cols != 0:
        print()
    print(f"  {len(campaigns) + 1}. All Campaigns")
    print("  0. Cancel")
    
    choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
    
    if choice == '0':
        return None
    elif choice.isdigit() and 1 <= int(choice) <= len(campaigns):
        return campaigns[int(choice) - 1]
    elif choice.isdigit() and int(choice) == len(campaigns) + 1:
        return None
    else:
        print_error("Invalid choice")
        return None


def select_agent(campaign_id=None):
    """Interactive agent selection (optional)"""
    agents = get_agents(campaign_id)
    
    if not agents:
        return None
    
    print("\n👤 SELECT AGENT (optional - press Enter to skip):")
    print("-" * 50)
    col_width = 25
    cols = 3
    for i, agent in enumerate(agents[:30], 1):
        print(f"{i:3}. {agent['user']:<15} ({agent['name'][:15]})", end="")
        if i % cols == 0:
            print()
    if len(agents) > 30:
        print(f"\n  ... and {len(agents) - 30} more agents")
    print("  0. Skip (all agents)")
    
    choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
    
    if choice == '0' or choice == '':
        return None
    elif choice.isdigit() and 1 <= int(choice) <= min(len(agents), 30):
        return agents[int(choice) - 1]['user']
    else:
        return None


def select_date_range():
    """Interactive date range selection"""
    print("\n📅 SELECT DATE RANGE:")
    print("  1. Today")
    print("  2. Yesterday")
    print("  3. Last 3 days")
    print("  4. Last 7 days")
    print("  5. Last 14 days")
    print("  6. Last 30 days")
    print("  7. Custom range")
    
    choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
    
    if choice == '1':
        return 1
    elif choice == '2':
        return 1
    elif choice == '3':
        return 3
    elif choice == '4':
        return 7
    elif choice == '5':
        return 14
    elif choice == '6':
        return 30
    elif choice == '7':
        days = input("Number of days: ").strip()
        return int(days) if days.isdigit() else 7
    else:
        return 7


def display_calls_table(calls, page, total_calls, page_size):
    """Display calls in a clean table with pagination"""
    if not calls:
        print_warning("No calls available for evaluation")
        return None
    
    total_pages = (total_calls + page_size - 1) // page_size if total_calls > 0 else 1
    
    print("\n" + "=" * 110)
    print(f"{'#':<4} {'Date/Time':<20} {'Campaign':<15} {'Agent':<18} {'Phone':<12} {'Duration':<10}")
    print("=" * 110)
    
    for i, call in enumerate(calls, 1):
        # Safe date formatting
        call_date = call.get('call_date')
        if call_date and hasattr(call_date, 'strftime'):
            date_str = call_date.strftime('%Y-%m-%d %H:%M')
        else:
            date_str = str(call_date)[:16] if call_date else 'Unknown'
        
        duration_sec = call.get('length_in_sec', 0) or 0
        duration = f"{duration_sec // 60}:{duration_sec % 60:02d}"
        
        phone = str(call.get('phone_number', 'Unknown'))[-10:] if call.get('phone_number') else 'Unknown'
        
        agent_name_raw = call.get('agent_name') or call.get('agent_user') or 'Unknown'
        agent_name = str(agent_name_raw)[:18]
        
        campaign = str(call.get('campaign_id', 'Unknown'))[:15]
        
        if duration_sec > 300:
            color = Colors.GREEN
        elif duration_sec > 60:
            color = Colors.CYAN
        else:
            color = Colors.YELLOW
        
        print_color(f"{i:<4} {date_str:<20} {campaign:<15} {agent_name:<18} {phone:<12} {duration:<10}", color)
    
    print("=" * 110)
    print(f"\n📄 Page {page} of {total_pages} | Showing {len(calls)} of {total_calls} calls")
    print("   [N] Next page | [P] Previous page | [0] Cancel")
    
    return calls


# =============================================================================
# Main AI Assistant Function
# =============================================================================

def show_ai_assistant():
    """Main AI Assistant function - Professional Interface with Clean Progress"""
    
    print_header("🤖 AI ASSISTANT - Automated QC Analysis", Colors.CYAN)
    print("\nThis tool analyzes call recordings and suggests quality scores.")
    print("All evaluations include AI confidence scores and full audit trail.\n")
    
    # Step 1: Select Campaign
    campaign = select_campaign()
    if campaign is None:
        print_info("Campaign selection cancelled")
        input("\nPress Enter to continue...")
        return
    
    # Step 2: Select Agent (optional)
    agent = select_agent(campaign)
    
    # Step 3: Select Date Range
    days = select_date_range()
    
    # Step 4: Paginated call selection
    page = 1
    page_size = 50
    
    while True:
        print_info(f"\n🔍 Searching for calls (page {page})...")
        calls, total_calls = get_calls_for_evaluation(campaign, agent, days, page, page_size)
        
        if not calls:
            print_warning(f"No calls found matching your criteria")
            input("\nPress Enter to continue...")
            return
        
        calls = display_calls_table(calls, page, total_calls, page_size)
        
        if not calls:
            return
        
        total_pages = (total_calls + page_size - 1) // page_size if total_calls > 0 else 1
        
        call_choice = input(f"\n{Colors.CYAN}Select call number, [N]ext, [P]revious, or [0] to cancel: {Colors.RESET}").strip().lower()
        
        if call_choice == '0':
            return
        elif call_choice == 'n':
            if page < total_pages:
                page += 1
                continue
            else:
                print_warning("Already on last page")
                continue
        elif call_choice == 'p':
            if page > 1:
                page -= 1
                continue
            else:
                print_warning("Already on first page")
                continue
        elif call_choice.isdigit():
            idx = int(call_choice) - 1
            if 0 <= idx < len(calls):
                selected_call = calls[idx]
                break
            else:
                print_error(f"Invalid selection. Choose 1-{len(calls)}")
        else:
            print_error("Invalid input. Enter number, N, P, or 0")
    
    # Step 5: Process the call
    print_header(f"📞 ANALYZING CALL", Colors.MAGENTA)
    print(f"  Campaign: {selected_call.get('campaign_id', 'Unknown')}")
    agent_display = selected_call.get('agent_name') or selected_call.get('agent_user') or 'Unknown'
    print(f"  Agent: {agent_display}")
    print(f"  Date: {selected_call.get('call_date', 'Unknown')}")
    phone_number = selected_call.get('phone_number', 'Unknown')
    print(f"  Phone: {phone_number}")
    duration_sec = selected_call.get('length_in_sec', 0) or 0
    print(f"  Duration: {duration_sec // 60}:{duration_sec % 60:02d}")
    
    # Download recording
    audio_path = download_recording(
        selected_call['uniqueid'],
        selected_call.get('phone_number'),
        selected_call.get('call_date')
    )
    if not audio_path:
        input("\nPress Enter to continue...")
        return
    
    transcript = transcribe_audio(audio_path)
    if not transcript:
        print_error("Transcription failed")
        input("\nPress Enter to continue...")
        return
    
    print_success("Transcription complete")

    # Ghost call detection
    ghost_info = detect_ghost_call(transcript, duration_sec)
    call_type = ghost_info["call_type"]

    # Show transcript preview
    print("\n" + "=" * 80)
    print("📝 CALL TRANSCRIPT (preview):")
    print("=" * 80)
    print(transcript[:800] + ("..." if len(transcript) > 800 else ""))
    print("=" * 80)

    # Show ghost/short/suspicious banner
    if call_type in ("GHOST", "SHORT_REVIEW", "SUSPICIOUS"):
        if call_type == "GHOST":
            banner_color = Colors.RED
            label = "⚠️  GHOST CALL DETECTED"
            action = "Only CP1 (Greeting) and CP5 (Closing) scored — set to 0 for manual QA review."
        elif call_type == "SUSPICIOUS":
            banner_color = Colors.YELLOW
            label = "⚠️  SUSPICIOUS CALL — QA REVIEW REQUIRED"
            action = "Full scorecard shown. Use option 5 to confirm as GHOST if no real interaction."
        else:
            banner_color = Colors.YELLOW
            label = "⚠️  SHORT CALL — REVIEW REQUIRED"
            action = "Only CP1 (Greeting) and CP5 (Closing) scored — set to 0 for manual QA review."
        print("\n" + "=" * 80)
        print_color(f"  {label}", banner_color)
        print_color(f"  Reason  : {ghost_info['reason']}", banner_color)
        print_color(f"  Words   : {ghost_info['word_count']}", banner_color)
        print_color(f"  Duration: {duration_sec // 60}:{duration_sec % 60:02d}", banner_color)
        print_color(f"  Action  : {action}", banner_color)
        print("=" * 80)
    
    # Analyze
    analysis = analyze_transcript(transcript)
    analysis['transcript_preview'] = transcript[:500] + ("..." if len(transcript) > 500 else "")
    
    # Get checkpoints
    checkpoints = get_checkpoints()
    
    # Build AI-suggested scores
    ai_scores = {}
    na_checkpoints = set()

    for cp in checkpoints:
        cp_id = cp['checkpoint_id']
        max_pts = cp['max_points']
        order = cp.get('display_order', 0)

        if call_type in ("GHOST", "SHORT_REVIEW"):
            if order not in GHOST_APPLICABLE_CHECKPOINTS:
                ai_scores[cp_id] = 0
                na_checkpoints.add(cp_id)
            else:
                ai_scores[cp_id] = 0
        else:
            raw_score = analysis['scores'].get(cp_id, 7)
            scaled_score = round(raw_score * max_pts / 10)
            ai_scores[cp_id] = min(max_pts, max(0, scaled_score))
    
    final_scores = ai_scores.copy()
    
    # Calculate totals
    if na_checkpoints:
        total_max = sum(c['max_points'] for c in checkpoints if c['checkpoint_id'] not in na_checkpoints)
        ai_total_score = sum(v for cid, v in ai_scores.items() if cid not in na_checkpoints)
    else:
        total_max = sum(c['max_points'] for c in checkpoints)
        ai_total_score = sum(ai_scores.values())

    total_score = ai_total_score
    percentage = (total_score / total_max * 100) if total_max > 0 else 0
    
    # Store ghost info back into analysis for PDF
    analysis['call_type'] = call_type
    analysis['ghost_reason'] = ghost_info['reason']
    analysis['word_count'] = ghost_info['word_count']
    
    # Display AI suggestions
    print_header("🤖 AI SUGGESTED SCORES", Colors.GREEN)
    if call_type == "GHOST":
        print_color(f"  ⚠️  Call type: GHOST CALL — Partial scorecard applied", Colors.RED)
    elif call_type == "SHORT_REVIEW":
        print_color(f"  ⚠️  Call type: SHORT CALL REVIEW — Partial scorecard applied", Colors.YELLOW)
    elif call_type == "SUSPICIOUS":
        print_color(f"  ⚠️  Call type: SUSPICIOUS — Full scorecard shown, QA review required", Colors.YELLOW)
    print(f"  AI Confidence: {analysis['confidence']:.0f}% - {get_confidence_text(analysis['confidence'])}")
    print("-" * 80)
    
    for cp in checkpoints:
        cp_id = cp['checkpoint_id']
        score = final_scores[cp_id]
        max_pts = cp['max_points']
        order = cp.get('display_order', 0)

        if cp_id in na_checkpoints:
            print_color(f"  {order:2}. {cp['checkpoint_text'][:45]:<45}  N/A    {'░' * 20}  (not applicable)", Colors.YELLOW)
            continue

        if call_type in ("GHOST", "SHORT_REVIEW") and order in GHOST_APPLICABLE_CHECKPOINTS:
            print_color(f"  {order:2}. {cp['checkpoint_text'][:45]:<45}  0/{max_pts:<2}  {'░' * 20}  ← QA: enter score manually", Colors.CYAN)
            continue

        bar_length = int(score / max_pts * 20)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        pct = score / max_pts * 100
        color = Colors.GREEN if pct >= 80 else Colors.YELLOW if pct >= 60 else Colors.RED
        print_color(f"  {order:2}. {cp['checkpoint_text'][:45]:<45} {score:>2}/{max_pts:<2} {bar}", color)
    
    print("-" * 80)
    if na_checkpoints:
        scored_max = sum(c['max_points'] for c in checkpoints if c['checkpoint_id'] not in na_checkpoints)
        print_color(f"\n  📊 AI TOTAL: {ai_total_score}/{scored_max} ({percentage:.1f}%)  [{len(na_checkpoints)} checkpoints N/A — use option 2 to enter CP1 + CP5 scores]", Colors.CYAN)
    else:
        print_color(f"\n  📊 AI TOTAL: {ai_total_score}/{total_max} ({percentage:.1f}%)", Colors.CYAN)
    print_color(f"  🤖 Confidence: {analysis['confidence']:.0f}%", Colors.MAGENTA)

    print(f"\n📝 AI NOTES:")
    print(f"  {analysis['notes']}")

    if analysis['compliance'] != "None":
        print_warning(f"\n⚠️ COMPLIANCE ISSUES:")
        print(f"  {analysis['compliance']}")

    # Options
    print("\n" + "=" * 80)
    print("OPTIONS:")
    if call_type == "GHOST":
        print_color("  ★ GHOST CALL: Use option 2 to enter CP1 (Greeting) and CP5 (Closing) scores manually", Colors.RED)
    elif call_type == "SUSPICIOUS":
        print_color("  ★ SUSPICIOUS: Review the recording. Accept AI scores (opt 1/2) OR confirm as ghost (opt 5)", Colors.YELLOW)
    elif call_type == "SHORT_REVIEW":
        print_color("  ★ SHORT CALL: Use option 2 to enter CP1 (Greeting) and CP5 (Closing) scores manually", Colors.YELLOW)
    print("  1. ✅ Accept AI scores, save, and generate PDF")
    print("  2. ✏️  Edit scores manually, then save")
    print("  3. 📄 Generate PDF without saving (review only)")
    print("  4. ❌ Cancel")
    if call_type == "SUSPICIOUS":
        print_color("  5. 👻 Confirm as GHOST (override — no real interaction detected)", Colors.YELLOW)

    choice = input(f"\n{Colors.CYAN}Choice (1-{'5' if call_type == 'SUSPICIOUS' else '4'}): {Colors.RESET}").strip()

    # Option 5: QA overrides SUSPICIOUS
    if choice == '5' and call_type == "SUSPICIOUS":
        print_color("\n  Confirmed as GHOST — switching to partial scorecard (CP1 + CP5 only)", Colors.YELLOW)
        call_type = "GHOST"
        analysis['call_type'] = "GHOST"
        analysis['ghost_reason'] = ghost_info['reason'] + " [QA confirmed as GHOST]"
        na_checkpoints = set()
        for cp in checkpoints:
            cp_id = cp['checkpoint_id']
            order = cp.get('display_order', 0)
            if order not in GHOST_APPLICABLE_CHECKPOINTS:
                na_checkpoints.add(cp_id)
            ai_scores[cp_id] = 0
        final_scores = ai_scores.copy()
        total_max = sum(c['max_points'] for c in checkpoints if c['checkpoint_id'] not in na_checkpoints)
        ai_total_score = 0
        total_score = 0
        percentage = 0.0
        choice = '2'
    
    if choice == '1':
        notes = input("\n📝 Add coaching notes (optional): ").strip() or analysis['notes']
        
        success, result = save_evaluation(
            selected_call['uniqueid'], final_scores, ai_scores,
            notes, total_score, ai_total_score, analysis, user='6668'
        )
        if success:
            print_success(f"✅ Evaluation saved! (ID: {result})")
            print_info(f"   AI Confidence: {analysis['confidence']:.0f}%")
            print_info(f"   Final Score: {total_score}/{total_max} ({percentage:.1f}%)")
            
            pdf_path = generate_pdf_report(selected_call, final_scores, checkpoints, total_score, total_max, percentage, analysis, result, na_checkpoints)
            if pdf_path:
                print_success(f"📄 PDF Report saved to: {pdf_path}")
                print_info(f"   Filename: {pdf_path.name}")
                
                open_file = input(f"\n{Colors.CYAN}Open PDF report? (y/N): {Colors.RESET}").strip().lower()
                if open_file == 'y':
                    os.startfile(str(pdf_path))
        else:
            print_error(f"❌ Failed to save: {result}")
    
    elif choice == '2':
        print("\n✏️  EDIT SCORES (press Enter to keep AI suggestion):")
        for cp in checkpoints:
            cp_id = cp['checkpoint_id']
            current = final_scores.get(cp_id, 0)
            max_pts = cp['max_points']
            new_score = input(f"  {cp['checkpoint_text'][:50]} [{current}/{max_pts}]: ").strip()
            if new_score.isdigit():
                final_scores[cp_id] = min(max_pts, int(new_score))
        
        total_score = sum(v for cid, v in final_scores.items() if cid not in na_checkpoints)
        percentage = (total_score / total_max * 100) if total_max > 0 else 0
        notes = input("\n📝 Coaching notes: ").strip() or analysis['notes']
        
        print(f"\n📊 Updated total: {total_score}/{total_max} ({percentage:.1f}%)")
        print(f"   Original AI total: {ai_total_score}/{total_max}")
        
        confirm = input(f"\n{Colors.CYAN}Save this evaluation? (y/N): {Colors.RESET}").strip().lower()
        
        if confirm == 'y':
            success, result = save_evaluation(
                selected_call['uniqueid'], final_scores, ai_scores,
                notes, total_score, ai_total_score, analysis, user='6668'
            )
            if success:
                print_success(f"✅ Evaluation saved! (ID: {result})")
                
                pdf_path = generate_pdf_report(selected_call, final_scores, checkpoints, total_score, total_max, percentage, analysis, result, na_checkpoints)
                if pdf_path:
                    print_success(f"📄 PDF Report saved to: {pdf_path}")
                    
                    open_file = input(f"\n{Colors.CYAN}Open PDF report? (y/N): {Colors.RESET}").strip().lower()
                    if open_file == 'y':
                        os.startfile(str(pdf_path))
            else:
                print_error(f"❌ Failed to save: {result}")
    
    elif choice == '3':
        pdf_path = generate_pdf_report(selected_call, final_scores, checkpoints, total_score, total_max, percentage, analysis, None, na_checkpoints)
        if pdf_path:
            print_success(f"📄 PDF Report saved to: {pdf_path}")
            print_info(f"   Filename: {pdf_path.name}")
            print_info("   Note: Evaluation was NOT saved to database. Use option 1 to save.")
            
            open_file = input(f"\n{Colors.CYAN}Open PDF report? (y/N): {Colors.RESET}").strip().lower()
            if open_file == 'y':
                os.startfile(str(pdf_path))
        else:
            print_error("Failed to generate PDF - reportlab may not be installed")
    
    # Clean up
    if audio_path and audio_path.exists():
        audio_path.unlink()
    
    input("\nPress Enter to continue...")


if __name__ == "__main__":
    show_ai_assistant()