"""
Conversation quality scoring system.
Evaluates overall conversation quality beyond just completion metrics.
"""

from typing import List, Dict, Optional
import os
import logging

logger = logging.getLogger("quality-scorer")


def score_conversation_quality(transcripts: List[Dict[str, str]], use_llm: bool = True) -> Dict[str, any]:
    """
    Score the overall quality of the conversation.
    
    Args:
        transcripts: List of conversation messages
        use_llm: Whether to use LLM for quality assessment
        
    Returns:
        Dictionary with quality metrics:
        - overall_score: 0-100 score
        - naturalness: 0-100 score for conversation flow
        - professionalism: 0-100 score for agent professionalism
        - clarity: 0-100 score for communication clarity
        - engagement: 0-100 score for customer engagement
        - llm_assessment: Optional LLM-generated quality analysis
    """
    conversation_text = "\n".join([f"{t['role']}: {t['content']}" for t in transcripts])
    
    # Pattern-based scoring
    naturalness = score_naturalness(transcripts)
    professionalism = score_professionalism(transcripts)
    clarity = score_clarity(transcripts)
    engagement = score_engagement(transcripts)
    
    # Calculate overall score (weighted average)
    overall_score = (
        naturalness * 0.25 +
        professionalism * 0.30 +
        clarity * 0.25 +
        engagement * 0.20
    )
    
    result = {
        "overall_score": round(overall_score, 1),
        "naturalness": round(naturalness, 1),
        "professionalism": round(professionalism, 1),
        "clarity": round(clarity, 1),
        "engagement": round(engagement, 1),
    }
    
    # Add LLM assessment if requested
    if use_llm:
        llm_assessment = get_llm_quality_assessment(conversation_text)
        if llm_assessment:
            result["llm_assessment"] = llm_assessment
    
    return result


def score_naturalness(transcripts: List[Dict[str, str]]) -> float:
    """Score conversation naturalness (flow, not robotic)."""
    score = 100.0
    
    agent_messages = [t["content"].lower() for t in transcripts if t["role"] == "agent"]
    
    # Deduct for repetitive patterns
    if len(agent_messages) >= 3:
        unique_starts = len(set(msg[:30] for msg in agent_messages[-5:]))
        if unique_starts < 3:
            score -= 20  # Repetitive opening patterns
    
    # Reward for conversational markers
    conversational_markers = ["wonderful", "great", "perfect", "i understand", "of course"]
    marker_count = sum(1 for msg in agent_messages if any(m in msg for m in conversational_markers))
    score += min(20, marker_count * 5)
    
    # Deduct for overly formal or robotic language
    robotic_patterns = ["as per", "kindly note", "please be informed", "as mentioned"]
    robotic_count = sum(1 for msg in agent_messages if any(p in msg for p in robotic_patterns))
    score -= min(30, robotic_count * 10)
    
    return max(0, min(100, score))


def score_professionalism(transcripts: List[Dict[str, str]]) -> float:
    """Score agent professionalism and courtesy."""
    score = 70.0  # Base score
    
    agent_text = " ".join(t["content"].lower() for t in transcripts if t["role"] == "agent")
    
    # Reward for courtesy
    courtesy_phrases = ["thank you", "please", "you're welcome", "my pleasure", "happy to"]
    courtesy_count = sum(1 for phrase in courtesy_phrases if phrase in agent_text)
    score += min(20, courtesy_count * 5)
    
    # Reward for professionalism markers
    professional_markers = ["may i", "would you like", "i'd be happy", "let me help"]
    prof_count = sum(1 for marker in professional_markers if marker in agent_text)
    score += min(15, prof_count * 5)
    
    # Deduct for unprofessional language
    unprofessional = ["yeah", "nope", "dunno", "gonna", "wanna"]
    unprof_count = sum(1 for word in unprofessional if word in agent_text)
    score -= min(30, unprof_count * 10)
    
    return max(0, min(100, score))


def score_clarity(transcripts: List[Dict[str, str]]) -> float:
    """Score communication clarity."""
    score = 80.0  # Base score
    
    agent_messages = [t["content"] for t in transcripts if t["role"] == "agent"]
    
    # Check for clear pricing communication
    pricing_keywords = ["per night", "total", "inr", "rupees", "comes to"]
    has_clear_pricing = any(any(kw in msg.lower() for kw in pricing_keywords) for msg in agent_messages)
    if has_clear_pricing:
        score += 10
    
    # Check for clear next steps
    next_step_phrases = ["shall i", "would you like me to", "let me", "i'll go ahead"]
    has_clear_next_steps = any(any(phrase in msg.lower() for phrase in next_step_phrases) for msg in agent_messages)
    if has_clear_next_steps:
        score += 10
    
    # Deduct for vague language
    vague_patterns = ["maybe", "perhaps", "not sure", "i think", "probably"]
    vague_count = sum(1 for msg in agent_messages if any(p in msg.lower() for p in vague_patterns))
    score -= min(30, vague_count * 10)
    
    return max(0, min(100, score))


def score_engagement(transcripts: List[Dict[str, str]]) -> float:
    """Score customer engagement level."""
    score = 50.0  # Base score
    
    customer_messages = [t["content"] for t in transcripts if t["role"] == "customer"]
    
    if not customer_messages:
        return 0
    
    # Reward for active participation
    avg_customer_length = sum(len(msg) for msg in customer_messages) / len(customer_messages)
    if avg_customer_length > 50:
        score += 20  # Engaged customer
    elif avg_customer_length < 15:
        score -= 20  # Disengaged customer
    
    # Check for positive sentiment
    positive_words = ["yes", "great", "wonderful", "perfect", "sounds good", "thank you"]
    positive_count = sum(1 for msg in customer_messages if any(word in msg.lower() for word in positive_words))
    score += min(30, positive_count * 10)
    
    return max(0, min(100, score))


def get_llm_quality_assessment(conversation_text: str) -> Optional[str]:
    """Use LLM to assess conversation quality."""
    try:
        import google.generativeai as genai
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""Evaluate this hotel booking conversation and provide a brief quality assessment (2-3 sentences).

Focus on:
- Naturalness and flow
- Agent professionalism
- Communication clarity
- Overall customer experience

Conversation:
{conversation_text}

Your assessment:"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.warning(f"LLM quality assessment failed: {e}")
        return None
