"""
Call Center Automation Agent
============================
Uses Claude Opus 4.6 with:
  - Beta tool runner (auto-handles the agentic loop)
  - Adaptive thinking for complex queries
  - Streaming for real-time output
  - Prompt caching on the system prompt
  - Tools: customer lookup, knowledge base, ticket creation, escalation, call summary
"""

import json
import anthropic
from anthropic import beta_tool
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

# ---------------------------------------------------------------------------
# Mock data stores (replace with real DB / CRM calls)
# ---------------------------------------------------------------------------
CUSTOMERS = {
    "C001": {
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "plan": "Enterprise",
        "account_status": "Active",
        "open_tickets": 1,
        "last_contact": "2026-04-10",
    },
    "C002": {
        "name": "Bob Smith",
        "email": "bob@example.com",
        "plan": "Starter",
        "account_status": "Past Due",
        "open_tickets": 0,
        "last_contact": "2026-03-28",
    },
    "C999": {
        "name": "Unknown Caller",
        "email": None,
        "plan": None,
        "account_status": "Unknown",
        "open_tickets": 0,
        "last_contact": None,
    },
}

KNOWLEDGE_BASE = {
    "reset password": "Visit account.example.com/reset and enter your email. A reset link is emailed within 2 minutes. Links expire after 15 minutes.",
    "billing cycle": "Bills generate on the 1st of each month. Payment is due by the 15th. Past-due accounts are suspended after 30 days.",
    "cancel subscription": "Subscriptions can be cancelled anytime from Account Settings > Billing > Cancel Plan. Service continues until end of the billing period.",
    "upgrade plan": "Upgrades take effect immediately and are prorated. Visit Account Settings > Billing > Change Plan, or ask an agent to upgrade for you.",
    "api rate limit": "Starter: 100 req/min. Professional: 1000 req/min. Enterprise: custom limits. Contact sales for an increase.",
    "data export": "Export all data via Settings > Data > Export. GDPR deletion requests are processed within 30 days.",
    "refund policy": "Refunds are available within 7 days of charge for annual plans, and within 24 hours for monthly plans.",
    "two factor auth": "Enable 2FA in Account Settings > Security. Supports TOTP apps (Authy, Google Authenticator) and hardware keys.",
}

TICKET_STORE: list[dict] = []  # in-memory ticket log

# ---------------------------------------------------------------------------
# Tool definitions using @beta_tool
# ---------------------------------------------------------------------------

@beta_tool
def lookup_customer(customer_id: str) -> str:
    """Look up a customer account by their customer ID.

    Args:
        customer_id: The customer's unique identifier (e.g. 'C001').
    """
    record = CUSTOMERS.get(customer_id.upper())
    if not record:
        return json.dumps({"error": f"No customer found with ID '{customer_id}'."})
    return json.dumps({"customer_id": customer_id.upper(), **record})


@beta_tool
def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base for answers to common customer questions.

    Args:
        query: The topic or question to search for (e.g. 'reset password', 'billing cycle').
    """
    query_lower = query.lower()
    results = []
    for topic, answer in KNOWLEDGE_BASE.items():
        if any(word in query_lower for word in topic.split()):
            results.append({"topic": topic, "answer": answer})
    if not results:
        return json.dumps({"results": [], "note": "No articles found. Consider escalating to a specialist."})
    return json.dumps({"results": results})


@beta_tool
def create_support_ticket(
    customer_id: str,
    issue_summary: str,
    priority: str,
    category: str,
) -> str:
    """Create a new support ticket for a customer issue.

    Args:
        customer_id: The customer's unique identifier.
        issue_summary: A concise summary of the customer's issue.
        priority: Ticket priority — one of 'low', 'medium', 'high', 'critical'.
        category: Issue category — one of 'billing', 'technical', 'account', 'general'.
    """
    valid_priorities = {"low", "medium", "high", "critical"}
    valid_categories = {"billing", "technical", "account", "general"}

    if priority.lower() not in valid_priorities:
        return json.dumps({"error": f"Invalid priority '{priority}'. Choose from: {valid_priorities}"})
    if category.lower() not in valid_categories:
        return json.dumps({"error": f"Invalid category '{category}'. Choose from: {valid_categories}"})

    ticket_id = f"TKT-{len(TICKET_STORE) + 1001}"
    ticket = {
        "ticket_id": ticket_id,
        "customer_id": customer_id.upper(),
        "issue_summary": issue_summary,
        "priority": priority.lower(),
        "category": category.lower(),
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    TICKET_STORE.append(ticket)
    return json.dumps({"success": True, "ticket": ticket})


@beta_tool
def escalate_to_human(
    customer_id: str,
    reason: str,
    department: str,
) -> str:
    """Escalate the call to a human agent in the specified department.

    Args:
        customer_id: The customer's unique identifier.
        reason: Brief explanation of why escalation is needed.
        department: Department to escalate to — one of 'billing', 'technical', 'sales', 'management'.
    """
    valid_departments = {"billing", "technical", "sales", "management"}
    if department.lower() not in valid_departments:
        return json.dumps({"error": f"Invalid department '{department}'. Choose from: {valid_departments}"})

    escalation = {
        "escalation_id": f"ESC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "customer_id": customer_id.upper(),
        "reason": reason,
        "department": department.lower(),
        "estimated_wait_minutes": {"billing": 3, "technical": 5, "sales": 2, "management": 8}[department.lower()],
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps({"success": True, "escalation": escalation})


@beta_tool
def generate_call_summary(
    customer_id: str,
    issue_description: str,
    resolution: str,
    follow_up_required: bool,
) -> str:
    """Generate and save a post-call summary for CRM records.

    Args:
        customer_id: The customer's unique identifier.
        issue_description: What the customer's issue was.
        resolution: How the issue was resolved (or why it was escalated).
        follow_up_required: Whether a follow-up action is needed.
    """
    summary = {
        "summary_id": f"SUM-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "customer_id": customer_id.upper(),
        "issue_description": issue_description,
        "resolution": resolution,
        "follow_up_required": follow_up_required,
        "call_timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "AI Agent (Claude Opus 4.6)",
    }
    return json.dumps({"success": True, "summary": summary})


# ---------------------------------------------------------------------------
# System prompt (cached — stable across all calls in this session)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a professional call center AI agent for Example Corp. Your role is to assist customers efficiently and empathetically.

## Core Responsibilities
- Greet callers warmly and identify their account using their customer ID.
- Understand and resolve the customer's issue using the available tools.
- Search the knowledge base before attempting to answer technical questions from memory.
- Create a support ticket for any unresolved issue.
- Escalate to a human agent when the issue is beyond your scope or the customer is upset.
- Always end by generating a call summary for CRM records.

## Escalation Triggers
Escalate immediately if:
- The customer is highly frustrated or threatening legal action.
- The issue involves fraud, security breach, or data loss.
- The requested refund exceeds $500.
- Three tool searches have not resolved the problem.

## Communication Style
- Be concise but warm. Avoid jargon.
- Confirm understanding before acting: "Let me look that up for you."
- When creating tickets or escalating, inform the customer of the ticket ID / wait time.
- Never promise outcomes you cannot guarantee.

## Tool Usage Order
1. lookup_customer → verify who you're speaking with.
2. search_knowledge_base → find the answer if it's a common question.
3. create_support_ticket → if the issue needs tracking.
4. escalate_to_human → if you cannot resolve it.
5. generate_call_summary → always at the end of every call.

Today's date: """ + datetime.now(timezone.utc).strftime("%Y-%m-%d") + "."


# ---------------------------------------------------------------------------
# Call center agent — streaming + tool runner
# ---------------------------------------------------------------------------

def run_call(customer_message: str, conversation_history: list[dict]) -> tuple[str, list[dict]]:
    """
    Process one customer turn. Returns (agent_reply_text, updated_history).
    Uses the beta tool runner with streaming and adaptive thinking.
    """
    # Append the customer message
    conversation_history.append({"role": "user", "content": customer_message})

    # Stream via the tool runner; it handles the tool-call loop automatically
    full_response = ""

    with client.beta.messages.tool_runner(
        model="claude-opus-4-6",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # cache the stable system prompt
            }
        ],
        tools=[
            lookup_customer,
            search_knowledge_base,
            create_support_ticket,
            escalate_to_human,
            generate_call_summary,
        ],
        messages=conversation_history,
    ).stream() as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_response += text

    print()  # newline after streaming ends

    # Append the assistant turn so history stays consistent
    conversation_history.append({"role": "assistant", "content": full_response})
    return full_response, conversation_history


# ---------------------------------------------------------------------------
# Interactive CLI session
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Example Corp — AI Call Center Agent")
    print("  (type 'quit' or 'exit' to end the call)")
    print("=" * 60)
    print()

    conversation: list[dict] = []

    # Kick off with a greeting from the agent
    greeting_prompt = "A customer has connected. Greet them warmly and ask for their customer ID to get started."
    print("[Agent]: ", end="", flush=True)
    _, conversation = run_call(greeting_prompt, conversation)

    while True:
        try:
            user_input = input("\n[Customer]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n[Session ended by operator]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "bye", "goodbye"}:
            print("\n[Agent]: ", end="", flush=True)
            run_call("The customer is ending the call. Thank them warmly and generate a call summary.", conversation)
            print("\n[Call ended]")
            break

        print("\n[Agent]: ", end="", flush=True)
        _, conversation = run_call(user_input, conversation)

    # Print any tickets created during the session
    if TICKET_STORE:
        print("\n" + "=" * 60)
        print("  Tickets Created This Session")
        print("=" * 60)
        for ticket in TICKET_STORE:
            print(json.dumps(ticket, indent=2))


if __name__ == "__main__":
    main()
