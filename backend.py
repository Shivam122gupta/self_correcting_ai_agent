import json
import os
import re
from pathlib import Path
from typing import Literal, TypedDict

from dotenv import load_dotenv
import groq
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, ValidationError

load_dotenv(Path(__file__).parent / ".env", override=True)


# -----------------------------------------------------------------------------
# Groq Cloud AI Inference / Model configuration
# -----------------------------------------------------------------------------


GROQ_BASE_URL = os.getenv(
    "GROQ_BASE_URL",
    os.getenv("DO_INFERENCE_BASE_URL", "https://api.groq.com/openai/v1")
).rstrip("/")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", os.getenv("MODEL_ACCESS_KEY", ""))

DEFAULT_MODEL = os.getenv("GROQ_MODEL", os.getenv("DO_MODEL", "openai/gpt-oss-120b"))
WRITER_MODEL = os.getenv("GROQ_WRITER_MODEL", os.getenv("DO_WRITER_MODEL", DEFAULT_MODEL))
REVIEWER_MODEL = os.getenv("GROQ_REVIEWER_MODEL", os.getenv("DO_REVIEWER_MODEL", DEFAULT_MODEL))
REVISER_MODEL = os.getenv("GROQ_REVISER_MODEL", os.getenv("DO_REVISER_MODEL", DEFAULT_MODEL))

ROUTER_NAME = os.getenv(
    "DO_INFERENCE_ROUTER", os.getenv("DO_INTERFACE_ROUTER", "")
).strip()
MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "3"))




class GroqChatModel:
    """Native, robust wrapper for Groq API using official groq SDK with rate-limit retry."""
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.client = groq.Groq(api_key=api_key)

    def invoke(self, messages):
        formatted = []
        for msg in messages:
            if isinstance(msg, dict):
                formatted.append(msg)
            elif hasattr(msg, "type") and hasattr(msg, "content"):
                role = "assistant" if msg.type in ("ai", "assistant") else ("system" if msg.type == "system" else "user")
                formatted.append({"role": role, "content": msg.content})
            else:
                formatted.append({"role": "user", "content": str(msg)})

        max_attempts = 4
        last_exception = None
        for attempt in range(max_attempts):
            try:
                res = self.client.chat.completions.create(
                    messages=formatted,
                    model=self.model_name,
                    temperature=0,
                )

                class ModelResponse:
                    def __init__(self, text: str):
                        self.content = text

                return ModelResponse(res.choices[0].message.content or "")
            except Exception as exc:
                last_exception = exc
                err_msg = str(exc).lower()
                if ("rate_limit" in err_msg or "429" in err_msg or "otpm" in err_msg) and attempt < max_attempts - 1:
                    import time
                    time.sleep(6 * (attempt + 1))
                else:
                    raise exc

        raise last_exception




def _get_router_name() -> str:
    return os.getenv(
        "DO_INFERENCE_ROUTER", os.getenv("DO_INTERFACE_ROUTER", "")
    ).strip()


def _effective_model(direct_model: str) -> str:
    router = _get_router_name()
    return f"router:{router}" if router else direct_model


def _build_model(model_name: str) -> GroqChatModel:
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("MODEL_ACCESS_KEY", "")
    if not api_key or api_key == "gsk_your_groq_api_key_here":
        raise RuntimeError(
            "GROQ_API_KEY is missing or default placeholder. Please add your Groq API key "
            "to your .env file (e.g. GROQ_API_KEY=\"gsk_...\")."
        )

    return GroqChatModel(model_name=model_name, api_key=api_key)


# Models are created lazily so the web UI can start even before a local .env is
# configured. This also produces a friendlier error when the first run happens.
def _writer_model() -> GroqChatModel:
    return _build_model(WRITER_MODEL)


def _reviewer_model() -> GroqChatModel:
    return _build_model(REVIEWER_MODEL)


def _reviser_model() -> GroqChatModel:
    return _build_model(REVISER_MODEL)




# Threshold configuration for strict programmatic pass condition
MIN_FACTUAL_SCORE = float(os.getenv("MIN_FACTUAL_SCORE", "0.85"))
MIN_COMPLETENESS_SCORE = float(os.getenv("MIN_COMPLETENESS_SCORE", "0.85"))
MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.85"))
MIN_CONFIDENCE_SCORE = float(os.getenv("MIN_CONFIDENCE_SCORE", "0.85"))
ALLOW_HALLUCINATIONS = os.getenv("ALLOW_HALLUCINATIONS", "false").lower() in ("true", "1")
MAX_CRITICAL_ISSUES = int(os.getenv("MAX_CRITICAL_ISSUES", "0"))




class Review(BaseModel):
    decision: Literal["PASS", "REVISE"] = Field(
        description="PASS only if every score threshold is met, no hallucination detected, and no critical issues exist; otherwise REVISE."
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Overall evaluation confidence from 0.0 to 1.0."
    )
    factual_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Factual correctness and accuracy score from 0.0 to 1.0."
    )
    completeness_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Completeness score covering all parts of the user question from 0.0 to 1.0."
    )
    relevance_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Direct relevance score from 0.0 to 1.0."
    )
    hallucination_detected: bool = Field(
        default=False, description="True if unsupported claims, unverified technical assertions, or false statements are detected."
    )
    issues: list[str] = Field(
        default_factory=list, description="List of specific flaws, unsupported claims, missing information, or contradictions."
    )
    feedback: str = Field(
        default="", description="Specific actionable instructions for the Reviser."
    )




class State(TypedDict):
    topic: str
    draft: str
    feedback: str
    decision: str
    revision_count: int
    confidence: float
    factual_score: float
    completeness_score: float
    relevance_score: float
    hallucination_detected: bool
    issues: list[str]




def _content_to_text(content) -> str:
    """Normalize LangChain response content to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content)




def _apply_strict_pass_rules(review: Review) -> Review:
    """Enforce strict quantitative thresholds programmatically regardless of LLM decision."""
    rejection_reasons = []

    if review.factual_score < MIN_FACTUAL_SCORE:
        rejection_reasons.append(
            f"Factual score ({review.factual_score:.2f}) is below threshold ({MIN_FACTUAL_SCORE:.2f})."
        )
    if review.completeness_score < MIN_COMPLETENESS_SCORE:
        rejection_reasons.append(
            f"Completeness score ({review.completeness_score:.2f}) is below threshold ({MIN_COMPLETENESS_SCORE:.2f})."
        )
    if review.relevance_score < MIN_RELEVANCE_SCORE:
        rejection_reasons.append(
            f"Relevance score ({review.relevance_score:.2f}) is below threshold ({MIN_RELEVANCE_SCORE:.2f})."
        )
    if review.confidence < MIN_CONFIDENCE_SCORE:
        rejection_reasons.append(
            f"Evaluation confidence ({review.confidence:.2f}) is below threshold ({MIN_CONFIDENCE_SCORE:.2f})."
        )
    if review.hallucination_detected and not ALLOW_HALLUCINATIONS:
        rejection_reasons.append("Hallucination or unsupported claim detected.")
    if len(review.issues) > MAX_CRITICAL_ISSUES:
        rejection_reasons.append(
            f"Found {len(review.issues)} critical issues (max allowed: {MAX_CRITICAL_ISSUES})."
        )

    if rejection_reasons:
        review.decision = "REVISE"
        combined_issues = list(dict.fromkeys(review.issues + rejection_reasons))
        review.issues = combined_issues
        instructions = " ".join(rejection_reasons)
        if review.feedback:
            review.feedback = f"{instructions} Additional reviewer notes: {review.feedback}"
        else:
            review.feedback = instructions
    elif review.decision == "PASS":
        review.feedback = ""

    return review




def _parse_review(raw_text: str) -> Review:
    """Parse strict reviewer JSON with robust error handling and fallback."""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    payload = None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                payload = None

    if not isinstance(payload, dict):
        fallback_review = Review(
            decision="REVISE",
            confidence=0.5,
            factual_score=0.5,
            completeness_score=0.5,
            relevance_score=0.5,
            hallucination_detected=False,
            issues=["Reviewer returned malformed JSON or unparseable output."],
            feedback="The review output could not be parsed as valid JSON. Please review the answer for factual accuracy, completeness, and clarity."
        )
        return _apply_strict_pass_rules(fallback_review)

    try:
        review = Review.model_validate(payload)
    except ValidationError as exc:
        fallback_review = Review(
            decision="REVISE",
            confidence=0.5,
            factual_score=0.5,
            completeness_score=0.5,
            relevance_score=0.5,
            hallucination_detected=False,
            issues=[f"Reviewer output failed schema validation: {exc}"],
            feedback="Reviewer returned schema-invalid data. Please review the draft for factual correctness, completeness, and technical consistency."
        )
        return _apply_strict_pass_rules(fallback_review)

    return _apply_strict_pass_rules(review)




# -----------------------------------------------------------------------------
# Agent 1: Writer
# -----------------------------------------------------------------------------
def writer(state: State):
    response = _writer_model().invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are the WRITER agent in a self-correcting multi-agent system.\n"
                    "Provide a thorough, factually accurate, logically consistent, and complete answer to the user's prompt.\n"
                    "- For simple topics: explain clearly and concisely.\n"
                    "- For complex, architectural, or multi-part questions: cover ALL requested components, edge cases, failure prevention mechanisms, trade-offs, and quantitative comparisons in depth.\n"
                    "- Do NOT invent false facts, unsupported technical assertions, or hallucinations.\n"
                    "- Organize your response clearly with markdown headings and structured bullet points."
                ),
            },
            {"role": "user", "content": f"Explain/Answer: {state['topic']}"},
        ]
    )
    return {
        "draft": _content_to_text(response.content),
        "feedback": "",
        "decision": "",
        "revision_count": 0,
        "confidence": 0.0,
        "factual_score": 0.0,
        "completeness_score": 0.0,
        "relevance_score": 0.0,
        "hallucination_detected": False,
        "issues": [],
    }




# -----------------------------------------------------------------------------
# Agent 2: Reviewer / verifier in the loop
# -----------------------------------------------------------------------------
def reviewer(state: State):
    prompt_text = (
        "You are an adversarial, highly vigilant REVIEWER agent in a self-correcting multi-agent system.\n"
        "Your task is to independently evaluate the draft answer against the user's prompt.\n\n"
        "EVALUATION CRITERIA:\n"
        "1. Factual correctness & technical accuracy.\n"
        "2. Logical consistency & freedom from contradictions.\n"
        "3. Completeness: Does it answer EVERY sub-question and explicit requirement in the user prompt?\n"
        "4. Relevance: Is it directly answering what was asked?\n"
        "5. Hallucinations & unsupported claims: Are there unverified assertions or false facts?\n"
        "6. Missing technical details, stopping conditions, or trade-offs.\n\n"
        "CRITICAL REVIEW RULES:\n"
        "- Do NOT approve an answer just because it sounds polished, confident, or uses analogies.\n"
        "- Actively look for missing architectural details, shallow generalizations, unaddressed sub-questions, or unverified claims.\n"
        "- If the user prompt asks for multiple specific architectural points (e.g. preventing infinite loops, detecting reviewer failure, handling document conflicts, quantitative trade-offs), verify that EVERY point is thoroughly explained.\n\n"
        "Return ONLY valid JSON matching this exact shape:\n"
        "{\n"
        '  "decision": "PASS|REVISE",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "factual_score": 0.0-1.0,\n'
        '  "completeness_score": 0.0-1.0,\n'
        '  "relevance_score": 0.0-1.0,\n'
        '  "hallucination_detected": true|false,\n'
        '  "issues": ["issue 1", "issue 2"],\n'
        '  "feedback": "Actionable, precise instructions for the Reviser..."\n'
        "}\n"
    )

    response = _reviewer_model().invoke(
        [
            {"role": "system", "content": prompt_text},
            {
                "role": "user",
                "content": f"User Prompt:\n{state['topic']}\n\nCurrent Draft Answer:\n{state['draft']}",
            },
        ]
    )

    review = _parse_review(_content_to_text(response.content))
    return {
        "decision": review.decision,
        "feedback": review.feedback,
        "confidence": review.confidence,
        "factual_score": review.factual_score,
        "completeness_score": review.completeness_score,
        "relevance_score": review.relevance_score,
        "hallucination_detected": review.hallucination_detected,
        "issues": review.issues,
    }




# -----------------------------------------------------------------------------
# Agent 3: Reviser
# -----------------------------------------------------------------------------
def reviser(state: State):
    issues_text = "\n".join([f"- {issue}" for issue in state.get("issues", [])]) or "None specified."
    response = _reviser_model().invoke(
        [
            {
                "role": "system",
                "content": (
                    "You are the REVISER agent in a self-correcting multi-agent system.\n"
                    "Your task is to improve the draft answer by explicitly fixing the reviewer's feedback and identified issues.\n\n"
                    "CRITICAL REVISION RULES:\n"
                    "- Do NOT blindly rewrite or discard correct portions of the answer.\n"
                    "- Preserve all accurate, well-explained information and fix ONLY the identified flaws, missing technical details, or unsupported claims.\n"
                    "- Address EVERY identified issue directly.\n"
                    "- Do NOT introduce new hallucinations, unverified claims, or off-topic information.\n"
                    "Return ONLY the complete, improved answer text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original Prompt:\n{state['topic']}\n\n"
                    f"Current Answer:\n{state['draft']}\n\n"
                    f"Reviewer Evaluation:\n"
                    f"- Decision: {state['decision']}\n"
                    f"- Factual Score: {state.get('factual_score', 0):.2f}\n"
                    f"- Completeness Score: {state.get('completeness_score', 0):.2f}\n"
                    f"- Relevance Score: {state.get('relevance_score', 0):.2f}\n"
                    f"- Hallucination Detected: {state.get('hallucination_detected', False)}\n\n"
                    f"Identified Issues:\n{issues_text}\n\n"
                    f"Actionable Feedback:\n{state['feedback']}"
                ),
            },
        ]
    )
    return {
        "draft": _content_to_text(response.content),
        "revision_count": state["revision_count"] + 1,
    }




def route_after_review(state: State):
    """The self-correction loop controller."""
    if state["decision"] == "PASS":
        return "done"
    if state["revision_count"] >= MAX_REVISIONS:
        return "done"
    return "revise"




builder = StateGraph(State)
builder.add_node("writer", writer)
builder.add_node("reviewer", reviewer)
builder.add_node("reviser", reviser)
builder.add_edge(START, "writer")
builder.add_edge("writer", "reviewer")
builder.add_conditional_edges(
    "reviewer",
    route_after_review,
    {"revise": "reviser", "done": END},
)
builder.add_edge("reviser", "reviewer")
graph = builder.compile()




def get_runtime_info() -> dict:
    """Return non-secret model/provider information for the demo UI."""
    router = _get_router_name()
    router_enabled = bool(router)
    base_url = os.getenv(
        "GROQ_BASE_URL",
        os.getenv("DO_INFERENCE_BASE_URL", "https://api.groq.com/openai/v1")
    ).rstrip("/")
    provider_name = "Groq Cloud Inference" if ("groq" in base_url.lower() or os.getenv("GROQ_API_KEY")) else "DigitalOcean Serverless Inference"

    return {
        "provider": provider_name,
        "endpoint": base_url,
        "router_enabled": router_enabled,
        "router": router if router_enabled else None,
        "writer_model": _effective_model(WRITER_MODEL),
        "reviewer_model": _effective_model(REVIEWER_MODEL),
        "reviser_model": _effective_model(REVISER_MODEL),
        "max_revisions": MAX_REVISIONS,
        "min_factual_score": MIN_FACTUAL_SCORE,
        "min_completeness_score": MIN_COMPLETENESS_SCORE,
        "min_relevance_score": MIN_RELEVANCE_SCORE,
        "min_confidence_score": MIN_CONFIDENCE_SCORE,
    }




def run_workflow(topic: str):
    """Run the graph and return data that both the CLI and FastAPI UI can use."""
    initial_state: State = {
        "topic": topic,
        "draft": "",
        "feedback": "",
        "decision": "",
        "revision_count": 0,
        "confidence": 0.0,
        "factual_score": 0.0,
        "completeness_score": 0.0,
        "relevance_score": 0.0,
        "hallucination_detected": False,
        "issues": [],
    }

    final_state = initial_state.copy()
    events = []
    info = get_runtime_info()

    for update in graph.stream(initial_state, stream_mode="updates"):
        for node_name, values in update.items():
            final_state.update(values)
            model_for_agent = {
                "writer": _effective_model(WRITER_MODEL),
                "reviewer": _effective_model(REVIEWER_MODEL),
                "reviser": _effective_model(REVISER_MODEL),
            }.get(node_name, DEFAULT_MODEL)

            event_data = {
                "agent": node_name,
                "draft": values.get("draft", final_state.get("draft", "")),
                "decision": values.get("decision", final_state.get("decision", "")),
                "feedback": values.get("feedback", final_state.get("feedback", "")),
                "revision_count": final_state["revision_count"],
                "provider": info["provider"],
                "model": model_for_agent,
            }

            if node_name == "reviewer":
                event_data.update({
                    "confidence": final_state.get("confidence", 0.0),
                    "factual_score": final_state.get("factual_score", 0.0),
                    "completeness_score": final_state.get("completeness_score", 0.0),
                    "relevance_score": final_state.get("relevance_score", 0.0),
                    "hallucination_detected": final_state.get("hallucination_detected", False),
                    "issues": final_state.get("issues", []),
                })

            events.append(event_data)

    return {
        "topic": topic,
        "events": events,
        "final_answer": final_state["draft"],
        "final_decision": final_state["decision"],
        "revision_count": final_state["revision_count"],
        **info,
    }











def run_demo(topic: str):
    """Small CLI version, useful if you want to demo without the browser."""
    result = run_workflow(topic)
    print("\n=== SELF-CORRECTING MULTI-AGENT DEMO ===")
    print(f"Provider: {result['provider']}")
    if result["router_enabled"]:
        print(f"Inference Router: {result['router']}")
    else:
        print(f"Writer model: {result['writer_model']}")
        print(f"Reviewer model: {result['reviewer_model']}")
        print(f"Reviser model: {result['reviser_model']}")
    print(f"Topic: {topic}\n")

    for event in result["events"]:
        print(f"\n--- {event['agent'].upper()} ({event['model']}) ---")
        if event["agent"] in {"writer", "reviser"}:
            print(event["draft"])
        elif event["agent"] == "reviewer":
            print("Decision:", event["decision"])
            print("Feedback:", event["feedback"] or "No changes needed")

    print("\n=== FINAL ANSWER ===")
    print(result["final_answer"])
    print(f"\nFinal decision: {result['final_decision']}")
    print(f"Revisions used: {result['revision_count']}")


if __name__ == "__main__":
    topic = input("Enter a topic (example: What is an AI agent?): ").strip()
    if not topic:
        topic = "What is an AI agent?"
    run_demo(topic)