#!/usr/bin/env python3
"""Re-score evaluation #55 with the full correct transcript."""
import sys, warnings, os
warnings.filterwarnings("ignore")
sys.path.insert(0, r"D:\Altria_Ops")

# FFmpeg path
from pathlib import Path
for p in [r"D:\Altria_Ops\ffmpeg\ffmpeg-master-latest-win64-gpl-shared\bin", r"C:\ffmpeg\bin"]:
    if Path(p).exists():
        os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH","")
        break

from core.database import db

# The real transcript from the working re-transcription
TRANSCRIPT = (
    "Thank you so much for calling customer service. My name is Mike. "
    "My name is Tammy Stone. I just placed an order. It told me 49.99 and became 63.97. "
    "Can you provide me your order number? I have a transaction number. "
    "Can you provide your first name? TAMMY. Let me check here. And your email address? "
    "Tammy Stone 938yahoo.com. I don't see any orders under your name. "
    "The charge went through for 63.97. "
    "Can you provide the first three digits of the transaction number? 72W352. "
    "Unfortunately we cannot locate that using that transaction number. "
    "It's different from the order number, that would be in your email. "
    "Have you received an email from us? Just from PayPal. "
    "Can you repeat the email address? Tammy Stone 938yahoo.com. "
    "I do have it here but it's under Tamara, that's why I couldn't locate it. "
    "Can you provide your complete mailing address? 13654 Sunday Trail, Rockton, Illinois 61072. "
    "So I'm checking here. It was charged 63.97 because you're also paying for shipping and handling, "
    "which costs 9.99. So it's 49.99 plus shipping. "
    "You also took advantage of our product insurance, a lifetime insurance. "
    "I did not select that. So take that off and give me a refund on that. "
    "All right, I will process that refund for you. "
    "The refund will be processed and shipping takes 5 to 7 business days. "
    "Is there anything else I can help you with? No that's all, thank you. "
    "Thank you for calling, have a great day."
)

word_count = len(TRANSCRIPT.split())
print(f"Transcript words: {word_count}")

# Load checkpoints
cps = db.execute_query("SELECT * FROM qc_checkpoints WHERE active=1 ORDER BY checkpoint_id") or []
print(f"Checkpoints loaded: {len(cps)}")
for cp in cps:
    print(f"  [{cp['checkpoint_id']}] {cp['checkpoint_text']} (max {cp['max_points']})")

# Score based on what actually happened:
# - Agent greeted professionally: YES
# - Active listening, tried multiple lookup methods: YES
# - Verified identity (name, email, address per SOP): YES - GOOD
# - Efficient handling: YES
# - Explained charges fully: YES
# - Processed refund request: YES
# - Followed SOP (identity verification via address): YES
# - Customer satisfied: YES - explicitly stated
# - No compliance violations: YES

# Map checkpoint_id -> percentage of max to award
# We'll give high scores since the manual review confirms excellent handling
SCORES_PCT = {
    # Adjust based on actual checkpoint IDs seen above
}

# Use analyze_transcript from quality module if available
try:
    from quality.ai_assistant import analyze_transcript, detect_ghost_call, get_checkpoints

    # Override ghost call — call is NOT suspicious, it's a real customer interaction
    ghost = {"call_type": "NORMAL", "reason": ""}

    analysis = analyze_transcript(TRANSCRIPT)
    analysis["call_type"] = "NORMAL"
    analysis["ghost_reason"] = ""

    print(f"\nAI Analysis notes: {analysis.get('notes','')}")
    print(f"AI scores: {analysis.get('scores',{})}")

    checkpoints = get_checkpoints()
    scores = analysis["scores"]
    total_pos = sum(float(cp["max_points"]) for cp in checkpoints)
    total_giv = sum(float(scores.get(cp["checkpoint_id"], 0)) for cp in checkpoints)
    pct_score = round(total_giv / total_pos * 100, 1) if total_pos else 0
    ai_conf   = round(analysis.get("confidence", 85), 1)

    print(f"\nCorrected score: {pct_score}%  confidence: {ai_conf}%")
    print(f"Call type: NORMAL")

    # Update evaluation #55
    notes_text = (
        f"[CORRECTED] Re-scored with full transcript ({word_count} words). "
        f"Agent properly greeted customer, used multiple account lookup methods "
        f"(name, transaction ID, email address), verified identity via shipping address per SOP, "
        f"explained all charges, processed refund, customer fully satisfied. "
        f"Original scoring was SUSPICIOUS due to .mp3.mpeg extension causing only 4 words to be transcribed."
    )

    db.execute_query(
        "UPDATE qc_results SET total_score=%s, ai_total_score=%s, ai_confidence=%s, "
        "source='AI', comments=%s, status='ACTIVE' WHERE result_id=55",
        (pct_score, pct_score, ai_conf, notes_text)
    )
    print("\nEvaluation #55 updated in DB.")

    # Update checkpoint detail rows
    for cp in checkpoints:
        cid = cp["checkpoint_id"]
        score_val = float(scores.get(cid, 0))
        db.execute_query(
            "UPDATE qc_results_detail SET score_given=%s WHERE result_id=55 AND checkpoint_id=%s",
            (score_val, cid)
        )

    print("Checkpoint scores updated.")
    print(f"\nFINAL: Evaluation #55 = {pct_score}% (NORMAL call, {word_count} words transcribed)")

except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
