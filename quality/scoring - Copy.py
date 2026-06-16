#!/usr/bin/env python3
"""
AI Assistant for Automated QC Scoring
Professional Interface - Real Agents, Pagination, Campaign/Agent/Date filters
Version: 4.2.0 - With Full Audit Trail, Advanced Analytics, and Calibration Report
"""

import os
import sys
import ssl
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import whisper
from core.database import db
from utils.colors import Colors, print_header, print_success, print_error, print_info, print_warning, print_color

# Try to import PDF libraries
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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

# Add FFmpeg to PATH
FFMPEG_PATH = r"D:\Altria_Ops\ffmpeg\ffmpeg-master-latest-win64-gpl-shared\bin"
os.environ["PATH"] += os.pathsep + FFMPEG_PATH

# Load Whisper model once
whisper_model = None


# =============================================================================
# Helper Functions
# =============================================================================

def get_whisper_model():
    """Load Whisper model lazily"""
    global whisper_model
    if whisper_model is None:
        print_info("Loading AI model (first time takes ~10 seconds)...")
        whisper_model = whisper.load_model("base")
        print_success("AI model ready!")
    return whisper_model


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
    return [r['campaign_id'] for r in results]


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
            'name': name
        })
    return agents


def get_calls_for_evaluation(campaign_id=None, agent=None, days=7, page=1, page_size=50):
    """Get calls ready for evaluation with pagination"""
    
    offset = (page - 1) * page_size
    
    query = """
    SELECT 
        c.uniqueid,
        c.call_date,
        c.campaign_id,
        c.phone_number,
        c.length_in_sec,
        c.queue_seconds,
        a.user as agent_user,
        u.full_name as agent_name,
        r.filename,
        r.location
    FROM vicidial_closer_log c
    LEFT JOIN vicidial_agent_log a ON c.uniqueid = a.uniqueid
    LEFT JOIN vicidial_users u ON a.user = u.user
    LEFT JOIN recording_log r ON c.uniqueid = r.vicidial_id
    WHERE c.call_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
      AND c.length_in_sec >= 5
      AND r.filename IS NOT NULL
    """
    
    params = [days]
    
    if campaign_id:
        query += " AND c.campaign_id = %s"
        params.append(campaign_id)
    
    if agent:
        query += " AND a.user = %s"
        params.append(agent)
    
    query += " AND c.uniqueid NOT IN (SELECT uniqueid FROM qc_results)"
    
    # Get total count
    count_query = query.replace("SELECT \n        c.uniqueid,\n        c.call_date,\n        c.campaign_id,\n        c.phone_number,\n        c.length_in_sec,\n        c.queue_seconds,\n        a.user as agent_user,\n        u.full_name as agent_name,\n        r.filename,\n        r.location", "SELECT COUNT(*) as total")
    count_result = db.execute_query(count_query, params)
    total_calls = count_result[0]['total'] if count_result else 0
    
    # Add pagination
    query += " ORDER BY c.call_date DESC LIMIT %s OFFSET %s"
    params.extend([page_size, offset])
    
    results = db.execute_query(query, params) or []
    
    return results, total_calls


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

def download_recording(uniqueid):
    """Download recording using uniqueid"""
    
    query = "SELECT filename, location FROM recording_log WHERE vicidial_id = %s LIMIT 1"
    result = db.execute_query(query, (uniqueid,))
    
    if not result or not result[0].get('filename'):
        print_error(f"No recording file found for {uniqueid}")
        return None
    
    filename = result[0]['filename']
    location = result[0].get('location', '')
    
    local_path = TEMP_DIR / filename
    
    if local_path.exists():
        print_info(f"Using cached recording...")
        return local_path
    
    if location and location.startswith('http'):
        url = location
    else:
        url = RECORDINGS_BASE_URL + filename
        if not url.endswith('.mp3'):
            url += '.mp3'
    
    print_info(f"Downloading recording...")
    try:
        urllib.request.urlretrieve(url, local_path)
        print_success(f"Download complete")
        return local_path
    except Exception as e:
        print_error(f"Download failed: {e}")
        return None


def transcribe_audio(audio_path):
    """Transcribe audio using Whisper"""
    model = get_whisper_model()
    print_info("Transcribing audio (AI processing)...")
    result = model.transcribe(str(audio_path))
    return result["text"]


# =============================================================================
# Analysis Functions
# =============================================================================

def calculate_confidence(scores, max_points):
    """Calculate AI confidence based on score distribution and completeness"""
    if not scores or not max_points:
        return 70.0  # Default moderate confidence
    
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


def analyze_transcript(transcript):
    """Analyze transcript and suggest scores with confidence"""
    
    transcript_lower = transcript.lower()
    
    keywords = {
        1: {"positive": ["thank you for calling", "how can i help", "good morning", "good afternoon", "welcome"], "negative": [], "weight": 1.0},
        2: {"positive": ["thank you", "appreciate", "apologize", "certainly", "absolutely", "happy to help"], "negative": ["what?!", "can't", "won't", "no way", "why didn't you"], "weight": 1.0},
        3: {"positive": ["can i have your", "verify", "confirm", "first and last name", "email address", "account"], "negative": [], "weight": 1.2},
        4: {"positive": ["let me check", "give me a sec", "processing", "resolve", "fix", "i can help"], "negative": ["please hold", "transferring", "hold on"], "weight": 1.0},
        5: {"positive": ["anything else", "have a great", "thank you for calling", "take care"], "negative": [], "weight": 1.0},
        6: {"positive": ["record", "note", "document", "update", "account"], "negative": [], "weight": 1.0},
        7: {"positive": ["escalated", "back office", "process", "approved", "standard procedure"], "negative": ["bypass", "exception"], "weight": 1.2},
        8: {"positive": ["thank you", "appreciate", "great", "awesome", "perfect", "excellent"], "negative": ["upset", "frustrated", "angry", "unhappy", "disappointed"], "weight": 1.0},
        9: {"positive": ["apologize", "resolve", "refund", "credit", "solution"], "negative": ["can't", "won't", "no refund", "not possible"], "weight": 1.5}
    }
    
    scores = {}
    keyword_matches = {}
    
    for cp_id, kw in keywords.items():
        pos = sum(1 for k in kw.get("positive", []) if k in transcript_lower)
        neg = sum(1 for k in kw.get("negative", []) if k in transcript_lower)
        raw_score = min(10, max(0, 6 + pos - neg * 2))
        
        weighted_score = raw_score * kw.get("weight", 1.0)
        scores[cp_id] = min(10, weighted_score)
        keyword_matches[cp_id] = pos + neg
    
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
        "keyword_matches": keyword_matches
    }


# =============================================================================
# PDF Generation Functions (FIXED - Safe None Handling)
# =============================================================================

def generate_pdf_report(selected_call, scores, checkpoints, total_score, total_max, percentage, analysis, result_id):
    """Generate professional PDF report for the evaluation with safe None handling"""
    
    if not PDF_AVAILABLE:
        print_warning("PDF export not available. Install reportlab: pip install reportlab")
        return None
    
    # SAFE: Convert everything to strings with proper defaults
    agent_name_raw = selected_call.get('agent_name') or selected_call.get('agent_user') or 'Unknown'
    agent_name = str(agent_name_raw).replace(' ', '_').replace('/', '_').replace('\\', '_')
    
    campaign_raw = selected_call.get('campaign_id') or 'Unknown'
    campaign = str(campaign_raw).replace(' ', '_').replace('/', '_').replace('\\', '_')
    
    # SAFE: Handle call date
    call_date_obj = selected_call.get('call_date')
    if call_date_obj and hasattr(call_date_obj, 'strftime'):
        call_date_str = call_date_obj.strftime('%Y%m%d_%H%M%S')
    else:
        call_date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    phone_raw = selected_call.get('phone_number') or '0000'
    phone = str(phone_raw)[-4:] if len(str(phone_raw)) >= 4 else '0000'
    
    filename = f"QC_{campaign}_{agent_name}_{call_date_str}_{phone}.pdf"
    filepath = EXPORTS_DIR / filename
    
    try:
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )
        
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1,
            textColor=colors.HexColor('#2c3e50')
        )
        
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=12,
            textColor=colors.HexColor('#3498db')
        )
        
        # Company Header
        story.append(Paragraph("ALTRIA OPERATIONS SYSTEM", title_style))
        story.append(Paragraph("Quality Control Evaluation Report", title_style))
        story.append(Spacer(1, 12))
        
        # Call Information - SAFE with str() conversions
        story.append(Paragraph("Call Information", header_style))
        
        campaign_display = str(selected_call.get('campaign_id', 'Unknown'))
        agent_display = str(selected_call.get('agent_name') or selected_call.get('agent_user') or 'Unknown')
        
        call_date_display = ""
        call_date_obj = selected_call.get('call_date')
        if call_date_obj and hasattr(call_date_obj, 'strftime'):
            call_date_display = call_date_obj.strftime('%Y-%m-%d %H:%M:%S')
        else:
            call_date_display = str(call_date_obj) if call_date_obj else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        phone_display = str(selected_call.get('phone_number', 'Unknown'))
        duration_sec = selected_call.get('length_in_sec', 0) or 0
        duration_display = f"{duration_sec // 60}:{duration_sec % 60:02d}"
        queue_sec = selected_call.get('queue_seconds', 0) or 0
        
        call_info_data = [
            ["Campaign:", campaign_display],
            ["Agent:", agent_display],
            ["Date & Time:", call_date_display],
            ["Phone Number:", phone_display],
            ["Call Duration:", duration_display],
            ["Queue Time:", f"{queue_sec} seconds"],
            ["Evaluation ID:", str(result_id) if result_id else "Not saved"],
            ["Evaluator:", "AI Assistant + QA Review"],
            ["AI Confidence:", f"{analysis.get('confidence', 0):.0f}% - {get_confidence_text(analysis.get('confidence', 70))}"],
            ["Evaluation Date:", datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        ]
        
        call_info_table = Table(call_info_data, colWidths=[120, 380])
        call_info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(call_info_table)
        story.append(Spacer(1, 20))
        
        # Score Summary
        story.append(Paragraph("Score Summary", header_style))
        
        if percentage >= 80:
            score_color = colors.HexColor('#27ae60')
        elif percentage >= 60:
            score_color = colors.HexColor('#f39c12')
        else:
            score_color = colors.HexColor('#e74c3c')
        
        score_summary_data = [
            ["Total Score:", f"{total_score} / {total_max}"],
            ["Percentage:", f"{percentage:.1f}%"],
            ["Rating:", get_rating_text(percentage)],
        ]
        
        score_table = Table(score_summary_data, colWidths=[120, 380])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('TEXTCOLOR', (1, 1), (1, 1), score_color),
            ('FONTNAME', (1, 1), (1, 1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(score_table)
        story.append(Spacer(1, 20))
        
        # Checkpoint Details
        story.append(Paragraph("Checkpoint Analysis", header_style))
        
        checkpoint_data = [["#", "Checkpoint", "Score", "Max", "%", "Status"]]
        for cp in checkpoints:
            cp_id = cp['display_order']
            cp_text = cp['checkpoint_text']
            max_pts = cp['max_points']
            score = scores.get(cp['checkpoint_id'], 0)
            pct = (score / max_pts * 100) if max_pts > 0 else 0
            
            if pct >= 80:
                status = "Excellent"
            elif pct >= 60:
                status = "Good"
            else:
                status = "Needs Improvement"
            
            checkpoint_data.append([
                str(cp_id),
                cp_text,
                str(score),
                str(max_pts),
                f"{pct:.0f}%",
                status
            ])
        
        checkpoint_table = Table(checkpoint_data, colWidths=[30, 280, 40, 40, 50, 80])
        checkpoint_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        for i, cp in enumerate(checkpoints, 1):
            score = scores.get(cp['checkpoint_id'], 0)
            max_pts = cp['max_points']
            pct = (score / max_pts * 100) if max_pts > 0 else 0
            if pct >= 80:
                checkpoint_table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), colors.HexColor('#d5f5e3'))]))
            elif pct >= 60:
                checkpoint_table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fef9e7'))]))
            else:
                checkpoint_table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fadbd8'))]))
        
        story.append(checkpoint_table)
        story.append(Spacer(1, 20))
        
        # AI Analysis Notes
        story.append(Paragraph("AI Analysis Notes", header_style))
        notes_style = ParagraphStyle('Notes', parent=styles['Normal'], fontSize=10, spaceAfter=6, leftIndent=10, rightIndent=10)
        ai_notes = analysis.get('notes', 'No notes available')
        story.append(Paragraph(ai_notes.replace(' | ', '<br/>'), notes_style))
        story.append(Spacer(1, 10))
        
        # Compliance Issues
        compliance = analysis.get('compliance', 'None')
        if compliance != "None":
            story.append(Paragraph("⚠️ Compliance Issues", header_style))
            story.append(Paragraph(compliance, notes_style))
            story.append(Spacer(1, 10))
        
        # Transcript Preview
        story.append(Paragraph("Call Transcript (Preview)", header_style))
        transcript_style = ParagraphStyle('Transcript', parent=styles['Normal'], fontSize=9, spaceAfter=6, leftIndent=10, rightIndent=10)
        transcript_preview = analysis.get('transcript_preview', 'Not available')
        story.append(Paragraph(transcript_preview, transcript_style))
        
        # Footer
        story.append(Spacer(1, 30))
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=1, textColor=colors.HexColor('#7f8c8d'))
        story.append(Paragraph(f"Generated by Altria Ops AI Assistant v4.2", footer_style))
        story.append(Paragraph(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
        story.append(Paragraph("This report is for internal quality assurance purposes only.", footer_style))
        
        doc.build(story)
        return filepath
        
    except Exception as e:
        print_error(f"PDF generation error: {e}")
        import traceback
        traceback.print_exc()
        return None


# =============================================================================
# Database Save Functions with Full Audit Trail
# =============================================================================

def save_evaluation(uniqueid, scores, ai_scores, notes, total_score, ai_total_score, analysis, user='6668'):
    """
    Save evaluation to database with full audit trail
    - Stores both AI-suggested and final scores
    - Tracks confidence and analysis
    """
    try:
        # Insert evaluation header with audit columns
        db.execute_query("""
            INSERT INTO qc_results 
            (scorecard_id, uniqueid, evaluation_date, total_score, user, 
             ai_total_score, ai_analysis, source, ai_confidence, reviewed_by, reviewed_at)
            VALUES (1, %s, NOW(), %s, %s, %s, %s, 'HYBRID', %s, %s, NOW())
        """, (uniqueid, total_score, user, ai_total_score, analysis['notes'], analysis['confidence'], user))
        
        # Get the result_id
        result = db.execute_query("""
            SELECT result_id FROM qc_results 
            WHERE uniqueid = %s 
            ORDER BY evaluation_date DESC 
            LIMIT 1
        """, (uniqueid,))
        
        if not result:
            return False, "Could not retrieve result_id"
        
        result_id = result[0]['result_id']
        
        # Insert checkpoint scores (final scores from QA)
        for checkpoint_id, score_given in scores.items():
            db.execute_query("""
                INSERT INTO qc_results_detail (result_id, checkpoint_id, score_given)
                VALUES (%s, %s, %s)
            """, (result_id, checkpoint_id, score_given))
        
        # Save notes to separate table
        try:
            db.execute_query("""
                INSERT INTO altria_qc_notes (result_id, notes, ai_analysis)
                VALUES (%s, %s, %s)
            """, (result_id, notes, analysis['notes']))
        except Exception as e:
            if "Table 'asterisk.altria_qc_notes' doesn't exist" in str(e):
                pass  # Table doesn't exist, skip notes
            else:
                print_warning(f"Could not save notes: {e}")
        
        return True, result_id
        
    except Exception as e:
        print_error(f"Save error: {e}")
        return False, str(e)


# =============================================================================
# Calibration Report Functions (FIXED)
# =============================================================================

def show_calibration_report():
    """Show AI vs QA score calibration report"""
    print_header("📊 AI vs QA CALIBRATION REPORT", Colors.CYAN)
    
    try:
        # First, check if we have enough data
        count_query = """
        SELECT COUNT(*) as total_evaluations, COUNT(DISTINCT a.user) as total_agents
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        WHERE qcr.ai_total_score IS NOT NULL
          AND (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        
        count_result = db.execute_query(count_query) or [{'total_evaluations': 0, 'total_agents': 0}]
        total_evals = count_result[0]['total_evaluations'] if count_result else 0
        total_agents = count_result[0]['total_agents'] if count_result else 0
        
        if total_evals < 3 or total_agents < 1:
            print_warning(f"\nNot enough data for calibration (need at least 3 evaluations total)")
            print_info(f"   Current evaluations with AI scores: {total_evals}")
            print_info("   Continue using the AI Assistant (Option 8) to build your evaluation database.")
            input("\nPress Enter to continue...")
            return
        
        # Main calibration query - FIXED ORDER BY syntax
        query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as total_evaluations,
            ROUND(AVG(qcr.total_score), 1) as avg_final,
            ROUND(AVG(qcr.ai_total_score), 1) as avg_ai,
            ROUND(AVG(qcr.total_score - qcr.ai_total_score), 1) as avg_diff,
            ROUND(AVG(qcr.ai_confidence), 1) as avg_confidence,
            COUNT(CASE WHEN qcr.source = 'HYBRID' THEN 1 END) as reviewed_count
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE qcr.ai_total_score IS NOT NULL
          AND (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY a.user
        HAVING total_evaluations >= 1
        ORDER BY ABS(avg_diff) DESC
        """
        
        results = db.execute_query(query) or []
        
        if not results:
            print_warning("\nNo calibration data found")
            input("\nPress Enter to continue...")
            return
        
        print(f"\n{'=' * 110}")
        print("Calibration Report - Last 30 Days")
        print("Shows agents where AI and QA scores differ significantly")
        print(f"{'=' * 110}")
        
        print(f"{'Agent':<12} {'Name':<20} {'Evals':<8} {'AI Avg':<8} {'QA Avg':<8} {'Diff':<8} {'Confidence':<10} {'Reviewed':<10}")
        print("-" * 110)
        
        # Track overall stats
        agents_with_issues = 0
        
        for r in results:
            diff = r['avg_diff'] if r['avg_diff'] else 0
            
            # Determine status based on difference
            if abs(diff) > 10:
                status = "🔴 Needs Calibration"
                status_color = Colors.RED
                agents_with_issues += 1
            elif abs(diff) > 5:
                status = "🟡 Monitor"
                status_color = Colors.YELLOW
            else:
                status = "🟢 Good"
                status_color = Colors.GREEN
            
            name_display = r['full_name'][:20] if r['full_name'] else r['user']
            
            print_color(
                f"{r['user']:<12} {name_display:<20} {r['total_evaluations']:<8} "
                f"{r['avg_ai']:.1f}%{' ':<4} {r['avg_final']:.1f}%{' ':<4} "
                f"{diff:+.1f}{' ':<5} {r['avg_confidence']:.0f}%{' ':<6} {r['reviewed_count']:<10}",
                status_color
            )
        
        print("-" * 110)
        
        # Summary statistics
        if results:
            avg_diff_overall = sum(abs(r['avg_diff'] or 0) for r in results) / len(results)
            print(f"\n📊 CALIBRATION SUMMARY:")
            print(f"  • Total agents analyzed: {len(results)}")
            print(f"  • Agents needing calibration: {agents_with_issues}")
            print(f"  • Average AI/QA difference: {avg_diff_overall:.1f}%")
            
            if agents_with_issues > 0:
                print_color(f"  • Review the {agents_with_issues} agents marked 'Needs Calibration'", Colors.YELLOW)
            else:
                print_success("  • AI and QA scores are well-aligned across all agents!")
        
        # Show agents with most evaluations
        most_reviewed = sorted(results, key=lambda x: x['total_evaluations'], reverse=True)[:3]
        if most_reviewed:
            print(f"\n📈 AGENTS WITH MOST EVALUATIONS:")
            for r in most_reviewed:
                diff = r['avg_diff'] if r['avg_diff'] else 0
                print(f"  • {r['user']}: {r['total_evaluations']} evaluations, diff: {diff:+.1f}%")
        
        # Instructions
        print(f"\n💡 HOW TO IMPROVE CALIBRATION:")
        print("  1. Run more AI evaluations to build dataset")
        print("  2. QA should review and edit AI-suggested scores")
        print("  3. After 10+ evaluations per agent, run this report again")
        
    except Exception as e:
        print_error(f"Error generating calibration report: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to continue...")


def show_calibration_report_simple():
    """Simple calibration report for when there's not enough data"""
    print_header("📊 AI vs QA CALIBRATION REPORT", Colors.CYAN)
    
    try:
        # Count evaluations per agent
        query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as eval_count
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE qcr.ai_total_score IS NOT NULL
          AND (qcr.status = 'ACTIVE' OR qcr.status IS NULL)
        GROUP BY a.user
        ORDER BY eval_count DESC
        """
        
        results = db.execute_query(query) or []
        
        if not results:
            print_warning("\nNo AI evaluations found yet.")
            print_info("   Use the AI Assistant (Option 8) to start evaluating calls.")
            input("\nPress Enter to continue...")
            return
        
        print(f"\n{'=' * 70}")
        print("Current AI Evaluation Count by Agent")
        print(f"{'=' * 70}")
        print(f"{'Agent':<15} {'Name':<25} {'Evaluations':<12}")
        print("-" * 70)
        
        total_evals = 0
        for r in results:
            name_display = r['full_name'][:25] if r['full_name'] else r['user']
            print(f"{r['user']:<15} {name_display:<25} {r['eval_count']:<12}")
            total_evals += r['eval_count']
        
        print("-" * 70)
        print(f"Total evaluations: {total_evals}")
        
        if total_evals < 10:
            print_warning(f"\n⚠️ Need at least 10 evaluations for meaningful calibration.")
            print_info(f"   Current: {total_evals} evaluations. Keep using the AI Assistant!")
        else:
            print_info(f"\n📊 You have {total_evals} evaluations. Good progress!")
            print_info("   Run more evaluations to get 3+ per agent for full calibration.")
        
        print(f"\n💡 TIP: Continue using the AI Assistant (Option 8) to build your database.")
        print("   Once you have 3+ evaluations per agent, the full calibration report will be available.")
        
    except Exception as e:
        print_error(f"Error: {e}")
    
    input("\nPress Enter to continue...")


# =============================================================================
# Advanced Analytics Functions
# =============================================================================

def show_coaching_opportunities_advanced():
    """
    Advanced coaching opportunities report using AI audit trail data
    Shows agents needing coaching with AI confidence and score trends
    """
    print_header("📈 COACHING OPPORTUNITIES - ADVANCED", Colors.YELLOW)
    
    try:
        # Get agents with low scores, including AI confidence
        query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as total_evaluations,
            COUNT(CASE WHEN qcr.source = 'AI' THEN 1 END) as ai_evaluations,
            COUNT(CASE WHEN qcr.source = 'MANUAL' THEN 1 END) as manual_evaluations,
            COUNT(CASE WHEN qcr.source = 'HYBRID' THEN 1 END) as hybrid_evaluations,
            AVG(qcr.total_score) as avg_score,
            MIN(qcr.total_score) as min_score,
            MAX(qcr.total_score) as max_score,
            AVG(qcr.ai_confidence) as avg_ai_confidence,
            AVG(CASE WHEN qcr.ai_total_score IS NOT NULL THEN qcr.ai_total_score END) as avg_ai_score,
            AVG(CASE WHEN qcr.total_score IS NOT NULL AND qcr.ai_total_score IS NOT NULL 
                THEN ABS(qcr.total_score - qcr.ai_total_score) END) as avg_ai_difference
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY a.user
        HAVING avg_score < 70
        ORDER BY avg_score
        """
        
        results = db.execute_query(query) or []
        
        if not results:
            print_success("✅ No agents currently need coaching!")
            input("\nPress Enter to continue...")
            return
        
        print(f"\n{'=' * 120}")
        print(f"Agents below 70% average quality score (Last 30 days)")
        print(f"{'=' * 120}")
        
        print(f"{'Agent':<15} {'Name':<20} {'Evals':<8} {'AI':<6} {'Manual':<8} {'Hybrid':<8} "
              f"{'Avg%':<8} {'AI Conf':<8} {'AI Diff':<8} {'Priority':<12}")
        print("-" * 120)
        
        for r in results:
            # Determine priority based on multiple factors
            priority = ""
            priority_color = Colors.RESET
            
            if r['avg_score'] < 50:
                priority = "🔴 IMMEDIATE"
                priority_color = Colors.RED
            elif r['avg_score'] < 60:
                priority = "🟡 URGENT"
                priority_color = Colors.YELLOW
            else:
                priority = "🟢 SCHEDULED"
                priority_color = Colors.GREEN
            
            # If AI confidence is high and score is low, flag as AI-confirmed
            if r['avg_ai_confidence'] and r['avg_ai_confidence'] > 80 and r['avg_score'] < 60:
                priority = "🤖 AI-CONFIRMED"
                priority_color = Colors.MAGENTA
            
            # Calculate trend (if enough data)
            trend_query = """
            SELECT 
                total_score,
                evaluation_date
            FROM qc_results qcr
            JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
            WHERE a.user = %s
            ORDER BY evaluation_date DESC
            LIMIT 5
            """
            trend_data = db.execute_query(trend_query, (r['user'],)) or []
            
            trend = ""
            if len(trend_data) >= 3:
                recent_avg = sum(t['total_score'] for t in trend_data[:3]) / 3
                older_avg = sum(t['total_score'] for t in trend_data[-3:]) / 3
                if recent_avg > older_avg + 5:
                    trend = "📈 Improving"
                elif recent_avg < older_avg - 5:
                    trend = "📉 Declining"
                    priority = "⚠️ " + priority
                    priority_color = Colors.RED
                else:
                    trend = "➡️ Stable"
            
            name_display = r['full_name'][:20] if r['full_name'] else 'Unknown'
            ai_diff = r['avg_ai_difference'] if r['avg_ai_difference'] else 0
            
            print_color(
                f"{r['user']:<15} {name_display:<20} {r['total_evaluations']:<8} "
                f"{r['ai_evaluations']:<6} {r['manual_evaluations']:<8} {r['hybrid_evaluations']:<8} "
                f"{r['avg_score']:.1f}%{' ':<4} {r['avg_ai_confidence']:.0f}%{' ':<4} "
                f"{ai_diff:.1f}{' ':<5} {priority}",
                priority_color
            )
            if trend:
                print_color(f"      Trend: {trend}", Colors.CYAN)
        
        print("-" * 120)
        
        # Summary statistics
        avg_overall = sum(r['avg_score'] for r in results) / len(results)
        print(f"\n📊 COACHING SUMMARY:")
        print(f"  • Agents needing coaching: {len(results)}")
        print(f"  • Average score among these agents: {avg_overall:.1f}%")
        print(f"  • AI confidence on flagged agents: {sum(r['avg_ai_confidence'] for r in results if r['avg_ai_confidence']) / len([r for r in results if r['avg_ai_confidence']]):.0f}%")
        
        # Action recommendations
        print(f"\n💡 RECOMMENDED ACTIONS:")
        for r in results[:5]:
            if r['avg_score'] < 50:
                print(f"  • {r['user']}: Immediate coaching session required")
            elif r['avg_score'] < 60:
                print(f"  • {r['user']}: Schedule coaching within 5 days")
            else:
                print(f"  • {r['user']}: Monitor and provide feedback")
        
    except Exception as e:
        print_error(f"Error in coaching opportunities: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to continue...")


def show_top_performers_advanced():
    """
    Advanced top performers report with AI confidence and score stability
    """
    print_header("🏆 TOP PERFORMERS - ADVANCED", Colors.GREEN)
    
    print("\nSelect period:")
    print("  1. Last 7 days")
    print("  2. Last 30 days")
    print("  3. Last 90 days")
    print("  4. Custom")
    
    period_choice = input("\nChoice (1-4): ").strip()
    
    if period_choice == '1':
        days = 7
    elif period_choice == '2':
        days = 30
    elif period_choice == '3':
        days = 90
    elif period_choice == '4':
        days = input("Number of days: ").strip()
        days = int(days) if days.isdigit() else 30
    else:
        days = 30
    
    try:
        # Get top performers with AI metrics
        query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as evaluations,
            AVG(qcr.total_score) as avg_score,
            STDDEV(qcr.total_score) as score_stddev,
            COUNT(CASE WHEN qcr.source = 'AI' THEN 1 END) as ai_count,
            COUNT(CASE WHEN qcr.source = 'MANUAL' THEN 1 END) as manual_count,
            COUNT(CASE WHEN qcr.source = 'HYBRID' THEN 1 END) as hybrid_count,
            AVG(qcr.ai_confidence) as avg_confidence,
            AVG(CASE WHEN qcr.ai_total_score IS NOT NULL THEN qcr.ai_total_score END) as avg_ai_score
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY a.user
        HAVING evaluations >= 5
        ORDER BY avg_score DESC
        LIMIT 10
        """
        
        results = db.execute_query(query, (days,)) or []
        
        if not results:
            print_warning(f"No data available for last {days} days")
            input("\nPress Enter to continue...")
            return
        
        print(f"\n{'=' * 120}")
        print(f"Top 10 Performers (Last {days} days)")
        print(f"{'=' * 120}")
        
        print(f"{'Rank':<6} {'Agent':<12} {'Name':<20} {'Evals':<8} {'Avg%':<8} "
              f"{'AI%':<8} {'Confidence':<10} {'Stability':<10} {'Trend':<10}")
        print("-" * 120)
        
        for i, r in enumerate(results, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:2d}."
            
            ai_percent = (r['ai_count'] / r['evaluations'] * 100) if r['evaluations'] > 0 else 0
            
            # Calculate stability (lower stddev = more consistent)
            stddev = r['score_stddev'] if r['score_stddev'] else 0
            if stddev < 5:
                stability = "🌟 Very Stable"
                stability_color = Colors.GREEN
            elif stddev < 10:
                stability = "📊 Stable"
                stability_color = Colors.CYAN
            else:
                stability = "⚠️ Variable"
                stability_color = Colors.YELLOW
            
            # Calculate trend (improving/declining)
            trend_query = """
            SELECT 
                total_score,
                evaluation_date
            FROM qc_results qcr
            JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
            WHERE a.user = %s
            ORDER BY evaluation_date DESC
            LIMIT 5
            """
            trend_data = db.execute_query(trend_query, (r['user'],)) or []
            
            trend = ""
            if len(trend_data) >= 3:
                recent_avg = sum(t['total_score'] for t in trend_data[:3]) / 3
                older_avg = sum(t['total_score'] for t in trend_data[-3:]) / 3
                if recent_avg > older_avg + 3:
                    trend = "📈 Improving"
                    trend_color = Colors.GREEN
                elif recent_avg < older_avg - 3:
                    trend = "📉 Declining"
                    trend_color = Colors.RED
                else:
                    trend = "➡️ Stable"
                    trend_color = Colors.YELLOW
            else:
                trend = "Insufficient"
                trend_color = Colors.RESET
            
            name_display = r['full_name'][:20] if r['full_name'] else 'Unknown'
            
            print_color(
                f"{medal:<6} {r['user']:<12} {name_display:<20} {r['evaluations']:<8} "
                f"{r['avg_score']:.1f}%{' ':<4} {ai_percent:.0f}%{' ':<4} "
                f"{r['avg_confidence']:.0f}%{' ':<6}",
                Colors.GREEN
            )
            print_color(f"      {stability:<10} {trend:<10}", stability_color)
        
        print("-" * 120)
        
        # Additional insights
        print(f"\n📊 PERFORMANCE INSIGHTS:")
        print(f"  • Top performer: {results[0]['user']} ({results[0]['avg_score']:.1f}%)")
        print(f"  • Average score of top 10: {sum(r['avg_score'] for r in results) / 10:.1f}%")
        print(f"  • Most consistent: {min(results, key=lambda x: x['score_stddev'] or 100)['user']}")
        
        # AI vs Manual comparison
        ai_scores = [r['avg_ai_score'] for r in results if r['avg_ai_score']]
        manual_scores = [r['avg_score'] for r in results if r['manual_count'] > 0]
        
        if ai_scores and manual_scores:
            avg_ai = sum(ai_scores) / len(ai_scores)
            avg_manual = sum(manual_scores) / len(manual_scores)
            diff = avg_manual - avg_ai
            
            print(f"\n🤖 AI ACCURACY INSIGHTS:")
            if diff > 0:
                print(f"  • AI scores are {diff:.1f}% LOWER than QA scores (AI may be too strict)")
            elif diff < 0:
                print(f"  • AI scores are {abs(diff):.1f}% HIGHER than QA scores (AI may be too generous)")
            else:
                print(f"  • AI and QA scores are well-aligned")
        
    except Exception as e:
        print_error(f"Error in top performers: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to continue...")


def show_agent_quality_detail_advanced(agent=None):
    """
    Advanced agent quality report with AI vs QA comparison
    """
    if not agent:
        # Show agent list
        agents = get_agents()
        if not agents:
            print_warning("No agents found")
            input("\nPress Enter to continue...")
            return
        
        print("\n👤 SELECT AGENT:")
        print("-" * 50)
        for i, a in enumerate(agents[:30], 1):
            print(f"  {i:3}. {a['user']:<15} ({a['name'][:20]})")
        if len(agents) > 30:
            print(f"\n  ... and {len(agents) - 30} more agents")
        print("  0. Cancel")
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '0' or not choice.isdigit():
            return
        
        idx = int(choice) - 1
        if 0 <= idx < len(agents):
            agent = agents[idx]['user']
        else:
            return
    
    # Get period
    print("\nSelect period:")
    print("  1. Last 7 days")
    print("  2. Last 30 days")
    print("  3. Last 90 days")
    print("  4. All time")
    
    period_choice = input("\nChoice (1-4): ").strip()
    
    if period_choice == '1':
        days = 7
        period_name = "Last 7 days"
    elif period_choice == '2':
        days = 30
        period_name = "Last 30 days"
    elif period_choice == '3':
        days = 90
        period_name = "Last 90 days"
    else:
        days = 999
        period_name = "All time"
    
    try:
        # Get agent details with AI metrics
        agent_query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as total_evaluations,
            AVG(qcr.total_score) as avg_score,
            STDDEV(qcr.total_score) as score_stddev,
            MIN(qcr.total_score) as min_score,
            MAX(qcr.total_score) as max_score,
            COUNT(CASE WHEN qcr.source = 'AI' THEN 1 END) as ai_count,
            COUNT(CASE WHEN qcr.source = 'MANUAL' THEN 1 END) as manual_count,
            COUNT(CASE WHEN qcr.source = 'HYBRID' THEN 1 END) as hybrid_count,
            AVG(qcr.ai_confidence) as avg_confidence,
            AVG(CASE WHEN qcr.ai_total_score IS NOT NULL THEN qcr.ai_total_score END) as avg_ai_score
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE a.user = %s
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY a.user
        """
        
        agent_data = db.execute_query(agent_query, (agent, days)) or []
        
        if not agent_data:
            print_warning(f"No QC data found for agent {agent} in {period_name}")
            input("\nPress Enter to continue...")
            return
        
        data = agent_data[0]
        
        print_header(f"📊 AGENT QUALITY DETAIL: {agent} ({data['full_name'] or 'Unknown'})", Colors.MAGENTA)
        print(f"Period: {period_name}")
        print(f"{'=' * 100}")
        
        # Overall stats
        print(f"\n📈 OVERALL PERFORMANCE:")
        print(f"  • Evaluations: {data['total_evaluations']}")
        print(f"  • Average Score: {data['avg_score']:.1f}%")
        print(f"  • Range: {data['min_score']}% - {data['max_score']}%")
        print(f"  • Consistency (std dev): {data['score_stddev']:.1f}" if data['score_stddev'] else "  • Consistency: N/A")
        
        # Score distribution
        distribution_query = """
        SELECT 
            CASE 
                WHEN total_score >= 90 THEN 'Excellent (90-100)'
                WHEN total_score >= 80 THEN 'Good (80-89)'
                WHEN total_score >= 70 THEN 'Satisfactory (70-79)'
                WHEN total_score >= 60 THEN 'Needs Work (60-69)'
                ELSE 'Poor (<60)'
            END as rating,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM qc_results qcr2 
                                       JOIN vicidial_agent_log a2 ON qcr2.uniqueid = a2.uniqueid 
                                       WHERE a2.user = %s AND qcr2.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)), 1) as percentage
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        WHERE a.user = %s
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY rating
        ORDER BY MIN(total_score) DESC
        """
        
        distribution = db.execute_query(distribution_query, (agent, days, agent, days)) or []
        
        if distribution:
            print(f"\n📊 SCORE DISTRIBUTION:")
            for d in distribution:
                bar_length = int(d['percentage'] / 2)
                bar = "█" * bar_length + "░" * (50 - bar_length)
                if 'Excellent' in d['rating']:
                    color = Colors.GREEN
                elif 'Good' in d['rating']:
                    color = Colors.CYAN
                elif 'Satisfactory' in d['rating']:
                    color = Colors.YELLOW
                else:
                    color = Colors.RED
                print_color(f"  {d['rating']:<25} {d['count']:>3} ({d['percentage']:>5.1f}%) {bar}", color)
        
        # AI vs Manual comparison
        print(f"\n🤖 AI vs MANUAL COMPARISON:")
        print(f"  • AI-only evaluations: {data['ai_count']}")
        print(f"  • Manual-only evaluations: {data['manual_count']}")
        print(f"  • Hybrid (AI + QA review): {data['hybrid_count']}")
        
        if data['avg_ai_score'] and data['avg_score']:
            diff = data['avg_score'] - data['avg_ai_score']
            if diff > 5:
                print_color(f"  • QA scores are {diff:.1f}% HIGHER than AI", Colors.YELLOW)
                print(f"    (AI may be too strict - consider adjusting thresholds)")
            elif diff < -5:
                print_color(f"  • QA scores are {abs(diff):.1f}% LOWER than AI", Colors.YELLOW)
                print(f"    (AI may be too generous - consider calibration)")
            else:
                print_color(f"  • AI and QA scores are well-aligned (diff: {diff:.1f}%)", Colors.GREEN)
        
        print(f"  • Avg AI Confidence: {data['avg_confidence']:.0f}%" if data['avg_confidence'] else "  • Avg AI Confidence: N/A")
        
        # Recent evaluations with AI comparison
        recent_query = """
        SELECT 
            qcr.result_id,
            qcr.evaluation_date,
            qcr.total_score as final_score,
            qcr.ai_total_score as ai_score,
            qcr.ai_confidence,
            qcr.source,
            qcr.reviewed_by,
            c.campaign_id,
            c.phone_number,
            c.length_in_sec
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        JOIN vicidial_closer_log c ON qcr.uniqueid = c.uniqueid
        WHERE a.user = %s
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY qcr.evaluation_date DESC
        LIMIT 15
        """
        
        recent = db.execute_query(recent_query, (agent, days)) or []
        
        if recent:
            print(f"\n📋 RECENT EVALUATIONS (Last 15):")
            print("-" * 110)
            print(f"{'Date':<12} {'Campaign':<12} {'Final':<8} {'AI':<8} {'Diff':<8} {'Conf':<8} {'Source':<10} {'Duration':<10}")
            print("-" * 110)
            
            for r in recent:
                date_str = r['evaluation_date'].strftime('%Y-%m-%d') if hasattr(r['evaluation_date'], 'strftime') else str(r['evaluation_date'])[:10]
                duration = f"{r['length_in_sec'] // 60}:{r['length_in_sec'] % 60:02d}" if r['length_in_sec'] else "0:00"
                diff = r['final_score'] - (r['ai_score'] or r['final_score'])
                
                if diff > 5:
                    diff_color = Colors.YELLOW
                    diff_symbol = "▲"
                elif diff < -5:
                    diff_color = Colors.YELLOW
                    diff_symbol = "▼"
                else:
                    diff_color = Colors.GREEN
                    diff_symbol = "="
                
                source_color = Colors.CYAN if r['source'] == 'HYBRID' else Colors.RESET
                
                print(f"{date_str:<12} {r['campaign_id']:<12} {r['final_score']}%{' ':<4} ", end='')
                print(f"{r['ai_score'] or 'N/A':<8} ", end='')
                print_color(f"{diff_symbol} {abs(diff):.0f}{' ':<5}", diff_color, end=False)
                print(f"{r['ai_confidence']:.0f}%{' ':<4} ", end='')
                print_color(f"{r['source']:<10}", source_color, end=False)
                print(f"{duration:<10}")
            
            print("-" * 110)
        
        # Trend analysis
        trend_query = """
        SELECT 
            DATE(qcr.evaluation_date) as eval_date,
            AVG(qcr.total_score) as daily_avg,
            COUNT(*) as daily_count
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        WHERE a.user = %s
          AND qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY DATE(qcr.evaluation_date)
        ORDER BY eval_date
        """
        
        trend = db.execute_query(trend_query, (agent, days)) or []
        
        if len(trend) >= 3:
            print(f"\n📈 PERFORMANCE TREND:")
            # Simple trend line
            first_avg = trend[0]['daily_avg']
            last_avg = trend[-1]['daily_avg']
            trend_change = last_avg - first_avg
            
            # Create simple ASCII trend chart
            max_avg = max(t['daily_avg'] for t in trend)
            min_avg = min(t['daily_avg'] for t in trend)
            range_avg = max_avg - min_avg if max_avg > min_avg else 1
            
            for t in trend[-10:]:  # Show last 10 days
                date_str = t['eval_date'].strftime('%m/%d') if hasattr(t['eval_date'], 'strftime') else str(t['eval_date'])[5:10]
                bar_length = int((t['daily_avg'] - min_avg) / range_avg * 30) if range_avg > 0 else 15
                bar = "█" * bar_length + "░" * (30 - bar_length)
                
                if t['daily_avg'] >= 80:
                    color = Colors.GREEN
                elif t['daily_avg'] >= 60:
                    color = Colors.YELLOW
                else:
                    color = Colors.RED
                
                print_color(f"  {date_str}: {t['daily_avg']:.0f}% {bar} ({t['daily_count']} evals)", color)
            
            if trend_change > 5:
                print_color(f"\n  📈 Overall trend: +{trend_change:.1f}% (improving)", Colors.GREEN)
            elif trend_change < -5:
                print_color(f"\n  📉 Overall trend: {trend_change:.1f}% (declining)", Colors.RED)
            else:
                print(f"\n  ➡️ Overall trend: {trend_change:.1f}% (stable)")
        
        # Recommendations based on data
        print(f"\n💡 RECOMMENDATIONS:")
        
        if data['avg_score'] < 60:
            print_color(f"  • Immediate coaching session recommended", Colors.RED)
        elif data['avg_score'] < 70:
            print_color(f"  • Schedule coaching session within 2 weeks", Colors.YELLOW)
        
        if data['score_stddev'] and data['score_stddev'] > 15:
            print(f"  • High variability in scores - focus on consistency")
        
        if data['avg_ai_score'] and abs(data['avg_score'] - data['avg_ai_score']) > 10:
            print(f"  • AI and QA scores differ significantly - review calibration")
        
        if data['hybrid_count'] == 0 and data['ai_count'] > 0:
            print(f"  • All evaluations are AI-only - consider QA review for calibration")
        
    except Exception as e:
        print_error(f"Error in agent quality detail: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to continue...")


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
    
    total_pages = (total_calls + page_size - 1) // page_size
    
    print("\n" + "=" * 110)
    print(f"{'#':<4} {'Date/Time':<20} {'Campaign':<15} {'Agent':<18} {'Phone':<12} {'Duration':<10}")
    print("=" * 110)
    
    for i, call in enumerate(calls, 1):
        date_str = call['call_date'].strftime('%Y-%m-%d %H:%M') if hasattr(call['call_date'], 'strftime') else str(call['call_date'])[:16]
        duration = f"{call['length_in_sec'] // 60}:{call['length_in_sec'] % 60:02d}" if call['length_in_sec'] else "0:00"
        phone = call['phone_number'][-10:] if call['phone_number'] else 'Unknown'
        agent_name = call.get('agent_name', call.get('agent_user', 'Unknown'))[:18] if call.get('agent_name') else (call.get('agent_user', 'Unknown')[:18] if call.get('agent_user') else 'Unknown')
        
        if call['length_in_sec'] > 300:
            color = Colors.GREEN
        elif call['length_in_sec'] > 60:
            color = Colors.CYAN
        else:
            color = Colors.YELLOW
        
        print_color(f"{i:<4} {date_str:<20} {call['campaign_id']:<15} {agent_name:<18} {phone:<12} {duration:<10}", color)
    
    print("=" * 110)
    print(f"\n📄 Page {page} of {total_pages} | Showing {len(calls)} of {total_calls} calls")
    print("   [N] Next page | [P] Previous page | [0] Cancel")
    
    return calls


# =============================================================================
# Main AI Assistant Function
# =============================================================================

def show_ai_assistant():
    """Main AI Assistant function - Professional Interface with Full Audit Trail"""
    
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
        
        total_pages = (total_calls + page_size - 1) // page_size
        
        call_choice = input(f"\n{Colors.CYAN}Select call number, [N]ext, [P]revious, or [0] to cancel: {Colors.RESET}").strip().lower()
        
        if call_choice == '0':
            return
        elif call_choice == 'n' and page < total_pages:
            page += 1
            continue
        elif call_choice == 'p' and page > 1:
            page -= 1
            continue
        elif call_choice.isdigit():
            idx = int(call_choice) - 1
            if 0 <= idx < len(calls):
                selected_call = calls[idx]
                break
            else:
                print_error(f"Invalid selection. Choose 1-{len(calls)}")
        else:
            print_error("Invalid input")
    
    # Step 5: Process the call
    print_header(f"📞 ANALYZING CALL", Colors.MAGENTA)
    print(f"  Campaign: {selected_call['campaign_id']}")
    print(f"  Agent: {selected_call.get('agent_name', selected_call.get('agent_user', 'Unknown'))}")
    print(f"  Date: {selected_call['call_date']}")
    print(f"  Phone: {selected_call['phone_number']}")
    print(f"  Duration: {selected_call['length_in_sec'] // 60}:{selected_call['length_in_sec'] % 60:02d}")
    
    # Download and transcribe
    audio_path = download_recording(selected_call['uniqueid'])
    if not audio_path:
        input("\nPress Enter to continue...")
        return
    
    transcript = transcribe_audio(audio_path)
    print_success("Transcription complete")
    
    # Show preview
    print("\n" + "=" * 80)
    print("📝 CALL TRANSCRIPT (preview):")
    print("=" * 80)
    print(transcript[:800] + ("..." if len(transcript) > 800 else ""))
    print("=" * 80)
    
    # Analyze with confidence
    analysis = analyze_transcript(transcript)
    analysis['transcript_preview'] = transcript[:500] + ("..." if len(transcript) > 500 else "")
    
    # Get checkpoints
    checkpoints = get_checkpoints()
    
    # Build AI-suggested scores (raw)
    ai_scores = {}
    for cp in checkpoints:
        cp_id = cp['checkpoint_id']
        max_pts = cp['max_points']
        raw_score = analysis['scores'].get(cp_id, 7)
        scaled_score = round(raw_score * max_pts / 10)
        ai_scores[cp_id] = min(max_pts, max(0, scaled_score))
    
    # Start with AI scores as final (QA can edit)
    final_scores = ai_scores.copy()
    
    total_max = sum(c['max_points'] for c in checkpoints)
    ai_total_score = sum(ai_scores.values())
    total_score = ai_total_score
    percentage = (total_score / total_max * 100) if total_max > 0 else 0
    
    # Display AI suggestions with confidence
    print_header("🤖 AI SUGGESTED SCORES", Colors.GREEN)
    print(f"  AI Confidence: {analysis['confidence']:.0f}% - {get_confidence_text(analysis['confidence'])}")
    print("-" * 80)
    
    for cp in checkpoints:
        score = final_scores[cp['checkpoint_id']]
        max_pts = cp['max_points']
        bar_length = int(score / max_pts * 20)
        bar = "█" * bar_length + "░" * (20 - bar_length)
        
        pct = score / max_pts * 100
        if pct >= 80:
            color = Colors.GREEN
        elif pct >= 60:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        
        print_color(f"  {cp['display_order']:2}. {cp['checkpoint_text'][:45]:<45} {score:>2}/{max_pts:<2} {bar}", color)
    
    print("-" * 80)
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
    print("  1. ✅ Accept AI scores, save, and generate PDF")
    print("  2. ✏️  Edit scores manually, then save")
    print("  3. 📄 Generate PDF without saving (review only)")
    print("  4. ❌ Cancel")
    
    choice = input(f"\n{Colors.CYAN}Choice (1-4): {Colors.RESET}").strip()
    
    if choice == '1':
        # Accept AI scores and save with full audit trail
        notes = input("\n📝 Add coaching notes (optional): ").strip() or analysis['notes']
        
        success, result = save_evaluation(
            selected_call['uniqueid'], 
            final_scores, 
            ai_scores,
            notes, 
            total_score, 
            ai_total_score, 
            analysis
        )
        if success:
            print_success(f"✅ Evaluation saved! (ID: {result})")
            print_info(f"   AI Confidence: {analysis['confidence']:.0f}%")
            print_info(f"   Final Score: {total_score}/{total_max} ({percentage:.1f}%)")
            
            # Generate PDF
            pdf_path = generate_pdf_report(selected_call, final_scores, checkpoints, total_score, total_max, percentage, analysis, result)
            if pdf_path:
                print_success(f"📄 PDF Report saved to: {pdf_path}")
                print_info(f"   Filename: {pdf_path.name}")
                
                open_file = input(f"\n{Colors.CYAN}Open PDF report? (y/N): {Colors.RESET}").strip().lower()
                if open_file == 'y':
                    os.startfile(str(pdf_path))
        else:
            print_error(f"❌ Failed to save: {result}")
    
    elif choice == '2':
        # Edit mode
        print("\n✏️  EDIT SCORES (press Enter to keep AI suggestion):")
        for cp in checkpoints:
            cp_id = cp['checkpoint_id']
            current = final_scores[cp_id]
            max_pts = cp['max_points']
            new_score = input(f"  {cp['checkpoint_text'][:50]} [{current}/{max_pts}]: ").strip()
            if new_score.isdigit():
                final_scores[cp_id] = min(max_pts, int(new_score))
        
        total_score = sum(final_scores.values())
        percentage = (total_score / total_max * 100) if total_max > 0 else 0
        notes = input("\n📝 Coaching notes: ").strip() or analysis['notes']
        
        print(f"\n📊 Updated total: {total_score}/{total_max} ({percentage:.1f}%)")
        print(f"   Original AI total: {ai_total_score}/{total_max}")
        
        confirm = input(f"\n{Colors.CYAN}Save this evaluation? (y/N): {Colors.RESET}").strip().lower()
        
        if confirm == 'y':
            success, result = save_evaluation(
                selected_call['uniqueid'], 
                final_scores, 
                ai_scores,
                notes, 
                total_score, 
                ai_total_score, 
                analysis
            )
            if success:
                print_success(f"✅ Evaluation saved! (ID: {result})")
                
                # Generate PDF
                pdf_path = generate_pdf_report(selected_call, final_scores, checkpoints, total_score, total_max, percentage, analysis, result)
                if pdf_path:
                    print_success(f"📄 PDF Report saved to: {pdf_path}")
                    
                    open_file = input(f"\n{Colors.CYAN}Open PDF report? (y/N): {Colors.RESET}").strip().lower()
                    if open_file == 'y':
                        os.startfile(str(pdf_path))
            else:
                print_error(f"❌ Failed to save: {result}")
    
    elif choice == '3':
        # Generate PDF without saving
        pdf_path = generate_pdf_report(selected_call, final_scores, checkpoints, total_score, total_max, percentage, analysis, None)
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


# =============================================================================
# Quality Dashboard Functions
# =============================================================================

def show_quality_dashboard():
    """Show comprehensive quality dashboard with AI metrics"""
    print_header("📊 QUALITY DASHBOARD - AI Powered Analytics", Colors.CYAN)
    
    try:
        # Get overall statistics
        stats_query = """
        SELECT 
            COUNT(*) as total_evaluations,
            AVG(total_score) as avg_score,
            MIN(total_score) as min_score,
            MAX(total_score) as max_score,
            COUNT(CASE WHEN source = 'AI' THEN 1 END) as ai_count,
            COUNT(CASE WHEN source = 'MANUAL' THEN 1 END) as manual_count,
            COUNT(CASE WHEN source = 'HYBRID' THEN 1 END) as hybrid_count,
            AVG(ai_confidence) as avg_confidence,
            COUNT(CASE WHEN ai_confidence > 80 THEN 1 END) as high_confidence,
            COUNT(CASE WHEN ai_confidence < 60 THEN 1 END) as low_confidence
        FROM qc_results
        WHERE evaluation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        
        stats = db.execute_query(stats_query) or []
        
        if stats and stats[0]['total_evaluations'] > 0:
            s = stats[0]
            print(f"\n📈 30-DAY SUMMARY:")
            print(f"  • Total Evaluations: {s['total_evaluations']}")
            print(f"  • Average Score: {s['avg_score']:.1f}%")
            print(f"  • Score Range: {s['min_score']}% - {s['max_score']}%")
            print(f"  • AI-Powered Evaluations: {s['ai_count'] + s['hybrid_count']} ({((s['ai_count'] + s['hybrid_count']) / s['total_evaluations'] * 100):.0f}%)")
            print(f"  • Manual Evaluations: {s['manual_count']}")
            print(f"  • Avg AI Confidence: {s['avg_confidence']:.0f}%")
            print(f"  • High Confidence (>80%): {s['high_confidence']}")
            print(f"  • Low Confidence (<60%): {s['low_confidence']}")
        
        # Get top agents
        top_agents_query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as evals,
            AVG(qcr.total_score) as avg_score
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY a.user
        HAVING evals >= 3
        ORDER BY avg_score DESC
        LIMIT 5
        """
        
        top_agents = db.execute_query(top_agents_query) or []
        
        if top_agents:
            print(f"\n🏆 TOP 5 AGENTS (Last 30 days):")
            for i, a in enumerate(top_agents, 1):
                name = a['full_name'][:20] if a['full_name'] else a['user']
                print(f"  {i}. {a['user']:<12} {name:<20} {a['avg_score']:.1f}% ({a['evals']} evals)")
        
        # Get bottom agents needing coaching
        bottom_agents_query = """
        SELECT 
            a.user,
            u.full_name,
            COUNT(*) as evals,
            AVG(qcr.total_score) as avg_score,
            AVG(qcr.ai_confidence) as avg_confidence
        FROM qc_results qcr
        JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
        LEFT JOIN vicidial_users u ON a.user = u.user
        WHERE qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY a.user
        HAVING evals >= 3 AND avg_score < 70
        ORDER BY avg_score
        LIMIT 5
        """
        
        bottom_agents = db.execute_query(bottom_agents_query) or []
        
        if bottom_agents:
            print(f"\n⚠️ AGENTS NEEDING COACHING (Last 30 days):")
            for i, a in enumerate(bottom_agents, 1):
                name = a['full_name'][:20] if a['full_name'] else a['user']
                conf = f" (AI Conf: {a['avg_confidence']:.0f}%)" if a['avg_confidence'] else ""
                print(f"  {i}. {a['user']:<12} {name:<20} {a['avg_score']:.1f}%{conf}")
        
        # Campaign performance
        campaign_query = """
        SELECT 
            campaign_id,
            COUNT(*) as evals,
            AVG(total_score) as avg_score
        FROM qc_results qcr
        JOIN vicidial_closer_log c ON qcr.uniqueid = c.uniqueid
        WHERE qcr.evaluation_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY campaign_id
        ORDER BY avg_score DESC
        """
        
        campaigns = db.execute_query(campaign_query) or []
        
        if campaigns:
            print(f"\n📊 CAMPAIGN PERFORMANCE:")
            for c in campaigns[:10]:
                print(f"  • {c['campaign_id']:<15} {c['avg_score']:.1f}% ({c['evals']} evals)")
        
    except Exception as e:
        print_error(f"Error loading dashboard: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress Enter to continue...")


# =============================================================================
# Module Entry Point
# =============================================================================

def show_quality_menu():
    """Show quality scoring main menu"""
    while True:
        print_header("🎯 CALL QUALITY SCORING", Colors.CYAN)
        print("  ────────────────────────────────────────────────────────────")
        print("   1. 📊 Quality Dashboard")
        print("   2. 👤 Agent Quality Report")
        print("   3. 🏆 Top Performers by Quality")
        print("   4. 📈 Coaching Opportunities")
        print("   5. 📋 VICIdial QC Dashboard")
        print("   6. 📋 SOP Compliance Analysis")
        print("   7. 📊 AI Calibration Report")
        print("   8. ✨ Add QC Evaluation")
        print("   9. 🤖 AI Assistant (Auto-Score)")
        print("  10. ⚙️ Configure Quality Settings")
        print("   0. 🔙 Back to Main Menu")
        print("  ────────────────────────────────────────────────────────────")
        
        choice = input(f"\n{Colors.CYAN}Choice: {Colors.RESET}").strip()
        
        if choice == '1':
            show_quality_dashboard()
        elif choice == '2':
            show_agent_quality_detail_advanced()
        elif choice == '3':
            show_top_performers_advanced()
        elif choice == '4':
            show_coaching_opportunities_advanced()
        elif choice == '5':
            print_info("VICIdial QC Dashboard - Coming Soon")
            input("\nPress Enter to continue...")
        elif choice == '6':
            print_info("SOP Compliance Analysis - Coming Soon")
            input("\nPress Enter to continue...")
        elif choice == '7':
            # Smart calibration report - uses advanced if data available, otherwise simple
            # Check if there's enough data for advanced report
            check_query = """
            SELECT COUNT(DISTINCT a.user) as agent_count,
                   MIN(total_evaluations) as min_evals
            FROM (
                SELECT a.user, COUNT(*) as total_evaluations
                FROM qc_results qcr
                JOIN vicidial_agent_log a ON qcr.uniqueid = a.uniqueid
                WHERE qcr.ai_total_score IS NOT NULL
                GROUP BY a.user
                HAVING total_evaluations >= 3
            ) t
            """
            check_result = db.execute_query(check_query) or []
            if check_result and check_result[0]['agent_count'] >= 1:
                show_calibration_report()
            else:
                show_calibration_report_simple()
        elif choice == '8':
            print_info("Add QC Evaluation - Coming Soon")
            input("\nPress Enter to continue...")
        elif choice == '9':
            show_ai_assistant()
        elif choice == '10':
            print_info("Configure Quality Settings - Coming Soon")
            input("\nPress Enter to continue...")
        elif choice == '0':
            break
        else:
            print_error("Invalid choice")


if __name__ == "__main__":
    show_quality_menu()