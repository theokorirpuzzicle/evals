"""
Evaluation logic for scenario-specific criteria.
Analyzes transcripts to determine pass/fail for each criterion.

Uses hybrid approach:
- Pattern-based evaluation for objective criteria (fast, deterministic)
- LLM-based evaluation for subjective criteria (accurate, contextual)
"""

from typing import Dict, List, Optional
import os
import logging

logger = logging.getLogger("criteria-evaluator")

# LLM evaluation settings
USE_LLM_EVALUATION = os.getenv("USE_LLM_EVAL", "true").lower() == "true"
LLM_CRITERIA_KEYWORDS = ["empathy", "patience", "retention", "sensitivity", "courteous"]


def _evaluate_with_llm(criterion_name: str, criterion_def: Dict, conversation: str, customer_info: Dict) -> Optional[str]:
    """
    Use LLM to evaluate subjective criteria.

    Args:
        criterion_name: Name of criterion being evaluated
        criterion_def: Criterion definition with description
        conversation: Full conversation text
        customer_info: Customer details from scenario

    Returns:
        "PASS", "FAIL", or None if LLM evaluation not available
    """
    if not USE_LLM_EVALUATION:
        return None

    try:
        import google.generativeai as genai

        # Configure Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set, skipping LLM evaluation")
            return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Build evaluation prompt
        prompt = f"""You are an expert evaluator for hotel booking conversations.

Evaluate this conversation based on the following criterion:

**Criterion**: {criterion_name.replace('_', ' ').title()}
**Description**: {criterion_def.get('description', 'N/A')}
**Critical**: {criterion_def.get('critical', False)}

**Customer Context**:
- Name: {customer_info.get('name', 'Unknown')}
- Phone: {customer_info.get('phone', 'Unknown')}
- Email: {customer_info.get('email', 'Unknown')}

**Conversation**:
{conversation}

**Instructions**:
1. Read the entire conversation carefully
2. Evaluate whether the criterion was met
3. Consider context, tone, and appropriateness
4. Respond with ONLY "PASS" or "FAIL" (one word, no explanation)

Your evaluation:"""

        response = model.generate_content(prompt)
        result = response.text.strip().upper()

        if result in ["PASS", "FAIL"]:
            logger.debug(f"LLM evaluated {criterion_name}: {result}")
            return result
        else:
            logger.warning(f"LLM returned unexpected result for {criterion_name}: {result}")
            return None

    except Exception as e:
        logger.warning(f"LLM evaluation failed for {criterion_name}: {e}")
        return None




def _create_detailed_result(criterion_name: str, result: str, method: str, reason: str = None) -> Dict[str, any]:
    """
    Create a detailed evaluation result with metadata.
    
    Args:
        criterion_name: Name of the criterion
        result: "PASS", "FAIL", or "N/A"
        method: "LLM" or "PATTERN"
        reason: Optional explanation of why it passed/failed
        
    Returns:
        Dictionary with result and metadata
    """
    return {
        "result": result,
        "method": method,
        "reason": reason or f"Evaluated using {method.lower()}-based method",
        "criterion": criterion_name
    }


def evaluate_criteria(scenario: Dict, transcripts: List[Dict]) -> Dict[str, str]:
    """
    Evaluate all criteria for a scenario based on the conversation transcripts.

    Args:
        scenario: Scenario dictionary with evaluation_criteria
        transcripts: List of conversation messages

    Returns:
        Dictionary mapping criterion name to "PASS", "FAIL", or "N/A"
    """
    criteria = scenario.get("evaluation_criteria", {})
    results = {}

    # Get full conversation text
    conversation_text = "\n".join([f"{t['role']}: {t['content']}" for t in transcripts])
    conversation_text_lower = conversation_text.lower()

    # Customer info from scenario
    customer = scenario.get("customer", {})
    customer_name = customer.get("name", "")
    customer_phone = customer.get("phone", "")
    customer_email = customer.get("email", "")

    for criterion_name, criterion_def in criteria.items():
        # Check if this is a subjective criterion that should use LLM
        is_subjective = any(keyword in criterion_name.lower() for keyword in LLM_CRITERIA_KEYWORDS)

        # Try LLM evaluation for subjective criteria first
        if is_subjective:
            llm_result = _evaluate_with_llm(criterion_name, criterion_def, conversation_text, customer)
            if llm_result:
                results[criterion_name] = llm_result
                continue

        # Fall back to pattern-based evaluation
        if "name" in criterion_name.lower() and "captured" in criterion_name.lower():
            results[criterion_name] = _evaluate_name_capture(customer_name, conversation_text)

        elif "phone" in criterion_name.lower() and "captured" in criterion_name.lower():
            results[criterion_name] = _evaluate_phone_capture(customer_phone, conversation_text)

        elif "email" in criterion_name.lower() and "captured" in criterion_name.lower():
            results[criterion_name] = _evaluate_email_capture(customer_email, conversation_text)

        elif "empathy" in criterion_name.lower():
            results[criterion_name] = _evaluate_empathy(conversation_text_lower)

        elif "policy" in criterion_name.lower() and "child" in criterion_name.lower():
            results[criterion_name] = _evaluate_child_policy(conversation_text_lower)

        elif "alternative" in criterion_name.lower() and "offered" in criterion_name.lower():
            results[criterion_name] = _evaluate_alternative_offered(conversation_text_lower)

        elif "closing" in criterion_name.lower() and "courteous" in criterion_name.lower():
            results[criterion_name] = _evaluate_courteous_closing(transcripts)

        elif "capacity" in criterion_name.lower() and "superior" in criterion_name.lower():
            results[criterion_name] = _evaluate_superior_capacity(conversation_text_lower)

        elif "suite" in criterion_name.lower() and "suggested" in criterion_name.lower():
            results[criterion_name] = _evaluate_suite_suggested(conversation_text_lower)

        elif "extra_bed" in criterion_name.lower():
            results[criterion_name] = _evaluate_extra_bed_policy(conversation_text_lower)

        elif "activity_pricing" in criterion_name.lower():
            results[criterion_name] = _evaluate_activity_pricing(conversation_text_lower)

        elif "pricing" in criterion_name.lower() and "clear" in criterion_name.lower():
            results[criterion_name] = _evaluate_pricing_clarity(conversation_text_lower)

        elif "meal_plan" in criterion_name.lower():
            results[criterion_name] = _evaluate_meal_plan_explanation(conversation_text_lower)

        elif "budget" in criterion_name.lower() and "sensitivity" in criterion_name.lower():
            results[criterion_name] = _evaluate_budget_sensitivity(conversation_text_lower)

        elif "unrealistic_pricing" in criterion_name.lower():
            results[criterion_name] = _evaluate_no_unrealistic_pricing(conversation_text_lower)

        elif "negotiation" in criterion_name.lower():
            results[criterion_name] = _evaluate_negotiation_handling(conversation_text_lower)

        elif "patience" in criterion_name.lower():
            results[criterion_name] = _evaluate_agent_patience(conversation_text_lower)

        elif "confirmation_sent" in criterion_name.lower():
            results[criterion_name] = _evaluate_booking_confirmation(conversation_text_lower)

        else:
            # Default: mark as N/A if we don't have specific logic
            results[criterion_name] = "N/A"

    return results


def _evaluate_name_capture(customer_name: str, conversation: str) -> str:
    """Check if customer name was captured correctly."""
    # Split name into parts
    name_parts = customer_name.lower().split()

    # Check if all name parts appear in the conversation
    matches = sum(1 for part in name_parts if part in conversation.lower())

    if matches >= len(name_parts) - 1:  # Allow one missing part
        return "PASS"
    return "FAIL"


def _evaluate_phone_capture(customer_phone: str, conversation: str) -> str:
    """Check if phone number was captured."""
    # Remove formatting characters
    phone_digits = ''.join(c for c in customer_phone if c.isdigit())

    # Check if most digits appear in conversation
    if phone_digits[-5:] in conversation:  # Last 5 digits
        return "PASS"
    return "FAIL"


def _evaluate_email_capture(customer_email: str, conversation: str) -> str:
    """Check if email was captured within reasonable attempts."""
    email_lower = customer_email.lower()
    email_username = email_lower.split('@')[0]

    # Check if email username appears
    if email_username in conversation.lower():
        return "PASS"
    return "FAIL"


def _evaluate_empathy(conversation: str) -> str:
    """Check if agent expressed empathy with context awareness."""
    empathy_phrases = [
        "i understand", "i appreciate", "i'm sorry", "unfortunately",
        "apologize", "disappointing", "sympathize", "regret",
        "appreciate your", "understand this", "understand that"
    ]

    # Negative patterns that invalidate empathy
    invalidating_patterns = [
        "but we cannot", "but i cannot", "however we cannot",
        "unfortunately we cannot help", "i understand but no"
    ]

    conversation_lower = conversation.lower()
    empathy_count = 0

    for phrase in empathy_phrases:
        if phrase in conversation_lower:
            # Check if it's not followed by invalidating pattern
            phrase_pos = conversation_lower.find(phrase)
            context = conversation_lower[phrase_pos:phrase_pos + 100]

            # Check if invalidating pattern appears right after
            invalidated = any(inv in context for inv in invalidating_patterns)
            if not invalidated:
                empathy_count += 1

    # Require at least 2 empathy indicators for robustness
    return "PASS" if empathy_count >= 2 else "FAIL"


def _evaluate_child_policy(conversation: str) -> str:
    """Check if child policy was communicated."""
    policy_keywords = ["children", "child", "policy", "not permitted", "not allowed", "under"]

    matches = sum(1 for keyword in policy_keywords if keyword in conversation)
    if matches >= 2:
        return "PASS"
    return "FAIL"


def _evaluate_alternative_offered(conversation: str) -> str:
    """Check if alternative property was offered."""
    alternatives = ["kodaikanal", "kodai", "other property", "alternative"]

    for alt in alternatives:
        if alt in conversation:
            return "PASS"
    return "FAIL"


def _evaluate_courteous_closing(transcripts: List[Dict]) -> str:
    """Check if call ended courteously."""
    if not transcripts:
        return "FAIL"

    # Check last few agent messages
    agent_messages = [t['content'].lower() for t in transcripts if t['role'] == 'agent']
    last_messages = ' '.join(agent_messages[-3:]) if len(agent_messages) >= 3 else ' '.join(agent_messages)

    courteous_phrases = ["thank you", "thanks", "help you", "assist you", "pleasure", "welcome"]

    for phrase in courteous_phrases:
        if phrase in last_messages:
            return "PASS"
    return "FAIL"


def _evaluate_superior_capacity(conversation: str) -> str:
    """Check if agent correctly stated Superior Cottage capacity."""
    # Look for mentions of Superior Cottage NOT accommodating 3 adults
    if "superior" in conversation and ("cannot" in conversation or "can't" in conversation or "not accommodate" in conversation):
        return "PASS"
    # If Superior was incorrectly said to accommodate 3 adults
    if "superior" in conversation and ("3 adults" in conversation or "three adults" in conversation):
        return "FAIL"
    return "N/A"


def _evaluate_suite_suggested(conversation: str) -> str:
    """Check if Suite Cottage was suggested for 3 adults."""
    if "suite" in conversation and ("3 adults" in conversation or "three adults" in conversation):
        return "PASS"
    return "FAIL"


def _evaluate_extra_bed_policy(conversation: str) -> str:
    """Check if extra bed policy was stated correctly."""
    if "extra bed" in conversation:
        if "not available" in conversation or "no extra" in conversation or "cannot provide" in conversation:
            return "PASS"
        # If incorrectly said extra beds are available
        if "available" in conversation or "can arrange" in conversation:
            return "FAIL"
    return "N/A"


def _evaluate_activity_pricing(conversation: str) -> str:
    """Check if activity pricing is accurate (bird watching = chargeable)."""
    if "bird" in conversation and "watching" in conversation:
        # Should mention charge/chargeable/additional cost
        if "chargeable" in conversation or "charge" in conversation or "additional" in conversation or "cost" in conversation:
            return "PASS"
        # If incorrectly said complimentary
        if "complimentary" in conversation or "free" in conversation or "included" in conversation:
            return "FAIL"
    return "N/A"


def _evaluate_pricing_clarity(conversation: str) -> str:
    """Check if pricing was clearly stated as per night or total."""
    clarity_phrases = ["per night", "per day", "each night", "total", "for the stay", "entire stay"]

    for phrase in clarity_phrases:
        if phrase in conversation:
            return "PASS"
    return "FAIL"


def _evaluate_meal_plan_explanation(conversation: str) -> str:
    """Check if meal plan differences were explained."""
    if ("ap" in conversation or "all inclusive" in conversation) and ("cp" in conversation or "breakfast" in conversation):
        # Check if explanation was provided
        if "includes" in conversation or "included" in conversation or "meals" in conversation:
            return "PASS"
    return "FAIL"


def _evaluate_budget_sensitivity(conversation: str) -> str:
    """Check if agent respected budget constraints."""
    # Look for budget mentions
    if "budget" in conversation or "31000" in conversation or "31,000" in conversation:
        # Check if agent didn't suggest significantly higher prices (40000+)
        if "40000" in conversation or "40,000" in conversation:
            return "FAIL"
        return "PASS"
    return "N/A"


def _evaluate_no_unrealistic_pricing(conversation: str) -> str:
    """Check for unrealistically low pricing."""
    # Look for suspiciously low prices like 9000 for 2 nights
    if "9000" in conversation or "9,000" in conversation:
        return "FAIL"
    return "PASS"


def _evaluate_negotiation_handling(conversation: str) -> str:
    """Check if rate negotiation was handled well."""
    if "rate" in conversation or "price" in conversation or "negotiate" in conversation:
        # Should provide value explanation, not just repeat price
        if "value" in conversation or "includes" in conversation or "offer" in conversation:
            return "PASS"
        # Repetition without explanation
        agent_messages = conversation.split("agent:")
        if len(agent_messages) > 3:
            # Simple heuristic: if same numbers repeat multiple times
            return "FAIL"
    return "N/A"


def _evaluate_agent_patience(conversation: str) -> str:
    """Check if agent showed patience."""
    patience_phrases = ["happy to repeat", "let me repeat", "no problem", "of course", "certainly"]

    for phrase in patience_phrases:
        if phrase in conversation:
            return "PASS"
    return "N/A"  # Can't definitively fail without evidence


def _evaluate_booking_confirmation(conversation: str) -> str:
    """Check if booking confirmation was mentioned."""
    confirmation_phrases = ["confirmation", "confirm", "send you", "email you"]

    for phrase in confirmation_phrases:
        if phrase in conversation and "email" in conversation:
            return "PASS"
    return "FAIL"


def evaluate_criteria_detailed(scenario: Dict, transcripts: List[Dict]) -> Dict[str, Dict]:
    """
    Evaluate all criteria with detailed results including evaluation method and reasoning.
    
    Args:
        scenario: Scenario dictionary with evaluation_criteria
        transcripts: List of conversation messages
        
    Returns:
        Dictionary mapping criterion name to detailed result dict with keys:
        - result: "PASS", "FAIL", or "N/A"
        - method: "LLM" or "PATTERN"
        - reason: Explanation of the evaluation
    """
    criteria = scenario.get("evaluation_criteria", {})
    results = {}

    # Get full conversation text
    conversation_text = "\n".join([f"{t['role']}: {t['content']}" for t in transcripts])
    conversation_text_lower = conversation_text.lower()

    # Customer info from scenario
    customer = scenario.get("customer", {})
    customer_name = customer.get("name", "")
    customer_phone = customer.get("phone", "")
    customer_email = customer.get("email", "")

    for criterion_name, criterion_def in criteria.items():
        # Check if this is a subjective criterion that should use LLM
        is_subjective = any(keyword in criterion_name.lower() for keyword in LLM_CRITERIA_KEYWORDS)

        # Try LLM evaluation for subjective criteria first
        if is_subjective:
            llm_result = _evaluate_with_llm(criterion_name, criterion_def, conversation_text, customer)
            if llm_result:
                results[criterion_name] = _create_detailed_result(
                    criterion_name,
                    llm_result,
                    "LLM",
                    f"AI-evaluated based on conversation context and {criterion_def.get('description', 'criterion definition')}"
                )
                continue

        # Fall back to pattern-based evaluation
        result = None
        reason = None
        
        if "name" in criterion_name.lower() and "captured" in criterion_name.lower():
            result = _evaluate_name_capture(customer_name, conversation_text)
            reason = f"Checked if customer name '{customer_name}' appears in conversation"

        elif "phone" in criterion_name.lower() and "captured" in criterion_name.lower():
            result = _evaluate_phone_capture(customer_phone, conversation_text)
            reason = f"Checked if phone number ending in {customer_phone[-5:]} appears in conversation"

        elif "email" in criterion_name.lower() and "captured" in criterion_name.lower():
            result = _evaluate_email_capture(customer_email, conversation_text)
            email_username = customer_email.split('@')[0]
            reason = f"Checked if email username '{email_username}' appears in conversation"

        elif "empathy" in criterion_name.lower():
            result = _evaluate_empathy(conversation_text_lower)
            reason = "Checked for empathy phrases like 'I understand', 'I appreciate', 'I'm sorry'"

        elif "policy" in criterion_name.lower() and "child" in criterion_name.lower():
            result = _evaluate_child_policy(conversation_text_lower)
            reason = "Checked if child policy keywords (children, policy, not permitted) were mentioned"

        elif "alternative" in criterion_name.lower() and "offered" in criterion_name.lower():
            result = _evaluate_alternative_offered(conversation_text_lower)
            reason = "Checked if alternative property (Kodaikanal) was offered"

        elif "closing" in criterion_name.lower() and "courteous" in criterion_name.lower():
            result = _evaluate_courteous_closing(transcripts)
            reason = "Checked for courteous closing phrases in last few agent messages"

        elif "capacity" in criterion_name.lower() and "superior" in criterion_name.lower():
            result = _evaluate_superior_capacity(conversation_text_lower)
            reason = "Checked if Superior Cottage capacity was correctly stated"

        elif "suite" in criterion_name.lower() and "suggested" in criterion_name.lower():
            result = _evaluate_suite_suggested(conversation_text_lower)
            reason = "Checked if Suite Cottage was suggested for 3 adults"

        elif "extra_bed" in criterion_name.lower():
            result = _evaluate_extra_bed_policy(conversation_text_lower)
            reason = "Checked if extra bed policy was correctly stated"

        elif "activity_pricing" in criterion_name.lower():
            result = _evaluate_activity_pricing(conversation_text_lower)
            reason = "Checked if bird watching was correctly marked as chargeable"

        elif "pricing" in criterion_name.lower() and "clear" in criterion_name.lower():
            result = _evaluate_pricing_clarity(conversation_text_lower)
            reason = "Checked for pricing clarity phrases (per night, total, etc.)"

        elif "meal_plan" in criterion_name.lower():
            result = _evaluate_meal_plan_explanation(conversation_text_lower)
            reason = "Checked if meal plan differences (AP vs CP) were explained"

        elif "budget" in criterion_name.lower() and "sensitivity" in criterion_name.lower():
            result = _evaluate_budget_sensitivity(conversation_text_lower)
            reason = "Checked if agent respected budget constraints"

        elif "unrealistic_pricing" in criterion_name.lower():
            result = _evaluate_no_unrealistic_pricing(conversation_text_lower)
            reason = "Checked for unrealistically low pricing"

        elif "negotiation" in criterion_name.lower():
            result = _evaluate_negotiation_handling(conversation_text_lower)
            reason = "Checked if rate negotiation included value explanation"

        elif "patience" in criterion_name.lower():
            result = _evaluate_agent_patience(conversation_text_lower)
            reason = "Checked for patience indicators (happy to repeat, no problem, etc.)"

        elif "confirmation_sent" in criterion_name.lower():
            result = _evaluate_booking_confirmation(conversation_text_lower)
            reason = "Checked if booking confirmation email was mentioned"

        else:
            # Default: mark as N/A if we don't have specific logic
            result = "N/A"
            reason = "No specific evaluation logic implemented for this criterion"

        results[criterion_name] = _create_detailed_result(
            criterion_name,
            result,
            "PATTERN",
            reason
        )

    return results


def get_criteria_summary(detailed_results: Dict[str, Dict]) -> Dict[str, str]:
    """
    Convert detailed results to simple result format for backward compatibility.
    
    Args:
        detailed_results: Results from evaluate_criteria_detailed()
        
    Returns:
        Dictionary mapping criterion name to result string ("PASS"/"FAIL"/"N/A")
    """
    return {name: result["result"] for name, result in detailed_results.items()}
