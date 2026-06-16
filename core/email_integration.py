#!/usr/bin/env python3
# core/email_integration.py - Pinktools email stats for Altria_Ops daily reports
#
# Agent name mapping: pinktools uses agent_name strings, VICIdial uses short usernames.
# The tbl_agent_map table (in altriaca_email) bridges them. Any unmapped agent
# appears as "Unlinked" so gaps are always visible rather than silently dropped.

from core.email_database import email_db
from datetime import date, datetime


def _server_today() -> date:
    """Return TODAY from the email DB server clock — avoids Windows local clock skew."""
    try:
        row = email_db.execute_query("SELECT DATE(NOW()) AS d")
        if row and row[0]['d']:
            return row[0]['d']
    except Exception:
        pass
    return date.today()


# =============================================================================
# Mapping table bootstrap
# =============================================================================

MAPPING_DDL = """
CREATE TABLE IF NOT EXISTS tbl_agent_map (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    pinktools_agent_name VARCHAR(100) NOT NULL,
    altria_username      VARCHAR(100) NOT NULL,
    active               TINYINT(1)  NOT NULL DEFAULT 1,
    UNIQUE KEY uq_pinktools (pinktools_agent_name)
);
"""

def ensure_mapping_table():
    """Create tbl_agent_map if it does not exist yet."""
    email_db.execute_query(MAPPING_DDL)


# =============================================================================
# Mapping helpers
# =============================================================================

def get_all_mappings():
    """Return {pinktools_agent_name: altria_username} for active mappings."""
    rows = email_db.execute_query(
        "SELECT pinktools_agent_name, altria_username FROM tbl_agent_map WHERE active = 1"
    )
    return {r['pinktools_agent_name']: r['altria_username'] for r in rows}


def add_mapping(pinktools_name: str, altria_username: str):
    """Insert or update a single agent mapping."""
    email_db.execute_query(
        """
        INSERT INTO tbl_agent_map (pinktools_agent_name, altria_username)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE altria_username = VALUES(altria_username), active = 1
        """,
        (pinktools_name, altria_username)
    )


def list_unmapped_agents(target_date: date = None):
    """Return pinktools agent names that have no mapping entry."""
    if target_date is None:
        target_date = _server_today()

    rows = email_db.execute_query(
        """
        SELECT DISTINCT e.agent_name
        FROM tbl_email e
        LEFT JOIN tbl_agent_map m ON e.agent_name = m.pinktools_agent_name
        WHERE DATE(e.created_2) = %s
          AND m.pinktools_agent_name IS NULL
        ORDER BY e.agent_name
        """,
        (target_date,)
    )
    return [r['agent_name'] for r in rows]


# =============================================================================
# Core stats query
# =============================================================================

def get_email_stats_by_agent(target_date: date = None):
    """
    Return email performance stats per agent for target_date.

    Each row in the result dict:
      pinktools_name  – raw name from pinktools
      altria_username – mapped VICIdial username, or None if unmapped
      total_emails    – all emails handled that day
      by_type         – dict of {email_type: count}
      refund_count    – emails where refund > 0
      refund_total    – sum of refund amounts
      cancellations   – CANCELATION REQ count
      campaign_counts – dict of {campaign: count}
    """
    if target_date is None:
        target_date = _server_today()

    rows = email_db.execute_query(
        """
        SELECT
            agent_name,
            email_type,
            campaign,
            COUNT(*)          AS cnt,
            SUM(refund)       AS refund_sum,
            SUM(refund > 0)   AS refund_count
        FROM tbl_email
        WHERE DATE(created_2) = %s
        GROUP BY agent_name, email_type, campaign
        ORDER BY agent_name, email_type
        """,
        (target_date,)
    )

    mapping = get_all_mappings()

    agents = {}
    for r in rows:
        name = r['agent_name'] or 'Unknown'
        if name not in agents:
            agents[name] = {
                'pinktools_name':  name,
                'altria_username': mapping.get(name),
                'total_emails':    0,
                'by_type':         {},
                'refund_count':    0,
                'refund_total':    0.0,
                'cancellations':   0,
                'campaign_counts': {}
            }

        a = agents[name]
        cnt       = int(r['cnt'] or 0)
        ref_sum   = float(r['refund_sum'] or 0)
        ref_cnt   = int(r['refund_count'] or 0)
        etype     = r['email_type'] or 'OTHER'
        campaign  = r['campaign'] or 'UNKNOWN'

        a['total_emails']            += cnt
        a['by_type'][etype]           = a['by_type'].get(etype, 0) + cnt
        a['refund_count']            += ref_cnt
        a['refund_total']            += ref_sum
        a['campaign_counts'][campaign] = a['campaign_counts'].get(campaign, 0) + cnt

        if etype.upper() == 'CANCELATION REQ':
            a['cancellations'] += cnt

    return list(agents.values())


def get_email_summary(target_date: date = None):
    """
    Return a single-row summary dict for the whole day (all agents combined).
    Useful for the dashboard overview card.
    """
    if target_date is None:
        target_date = _server_today()

    row = email_db.execute_query(
        """
        SELECT
            COUNT(*)                                        AS total_emails,
            COUNT(DISTINCT agent_name)                      AS agents_active,
            SUM(refund > 0)                                 AS refund_count,
            COALESCE(SUM(refund), 0)                        AS refund_total,
            SUM(email_type = 'CANCELATION REQ')             AS cancellations,
            SUM(email_type = 'FULL REFUND')                 AS full_refunds,
            SUM(email_type = 'PARTIAL REFUND')              AS partial_refunds,
            SUM(email_type = 'ORDER STATUS')                AS order_status,
            SUM(email_type = 'GEN INQUIRY')                 AS gen_inquiry,
            SUM(email_type = 'RESHIPMENT')                  AS reshipments
        FROM tbl_email
        WHERE DATE(created_2) = %s
        """,
        (target_date,)
    )

    if not row or row[0]['total_emails'] is None:
        return {
            'total_emails': 0, 'agents_active': 0,
            'refund_count': 0, 'refund_total': 0.0,
            'cancellations': 0, 'full_refunds': 0,
            'partial_refunds': 0, 'order_status': 0,
            'gen_inquiry': 0, 'reshipments': 0,
            'date': str(target_date)
        }

    result = dict(row[0])
    result['date'] = str(target_date)
    for k in result:
        if result[k] is None:
            result[k] = 0
    result['refund_total'] = float(result['refund_total'])
    return result
