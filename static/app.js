const topicInput = document.getElementById("topic");
const runButton = document.getElementById("runButton");
const statusBox = document.getElementById("status");
const results = document.getElementById("results");
const timeline = document.getElementById("timeline");
const finalAnswer = document.getElementById("finalAnswer");
const finalDecision = document.getElementById("finalDecision");
const summaryBadge = document.getElementById("summaryBadge");

function escapeHtml(value = "") {
    const div = document.createElement("div");
    div.textContent = value;
    return div.innerHTML;
}

function setStatus(message, isError = false) {
    let text = message;
    if (typeof text === "object" && text !== null) {
        try {
            text = JSON.stringify(text, null, 2);
        } catch (e) {
            text = String(text);
        }
    }
    statusBox.textContent = String(text || "An unknown error occurred.");
    statusBox.classList.remove("hidden", "error");
    if (isError) statusBox.classList.add("error");
}

function renderEvent(event, index) {
    const isReview = event.agent === "reviewer";
    const decision = event.decision || "";
    const revisionText = event.revision_count > 0 ? `Revision ${event.revision_count}` : "Initial draft";
    const modelText = event.model ? ` · ${event.model}` : "";

    let body = "";
    if (isReview) {
        const factual = typeof event.factual_score === 'number' ? (event.factual_score * 100).toFixed(0) + '%' : 'N/A';
        const completeness = typeof event.completeness_score === 'number' ? (event.completeness_score * 100).toFixed(0) + '%' : 'N/A';
        const relevance = typeof event.relevance_score === 'number' ? (event.relevance_score * 100).toFixed(0) + '%' : 'N/A';
        const confidence = typeof event.confidence === 'number' ? (event.confidence * 100).toFixed(0) + '%' : 'N/A';
        const hallucination = event.hallucination_detected ? '⚠️ YES' : '✓ None';

        let issuesHtml = '';
        if (Array.isArray(event.issues) && event.issues.length > 0) {
            const listItems = event.issues.map(issue => `<li>${escapeHtml(issue)}</li>`).join('');
            issuesHtml = `<div class="issues-box"><strong>Identified Issues:</strong><ul>${listItems}</ul></div>`;
        }

        const feedback = event.feedback || "No changes needed — all strict evaluation rules passed.";
        body = `
            <div class="scores-grid">
                <div><span>Factual:</span> <strong>${factual}</strong></div>
                <div><span>Completeness:</span> <strong>${completeness}</strong></div>
                <div><span>Relevance:</span> <strong>${relevance}</strong></div>
                <div><span>Confidence:</span> <strong>${confidence}</strong></div>
                <div><span>Hallucination:</span> <strong>${hallucination}</strong></div>
            </div>
            ${issuesHtml}
            <div class="feedback"><strong>Feedback:</strong> ${escapeHtml(feedback)}</div>
        `;
    } else {
        body = `<div class="answer">${escapeHtml(event.draft)}</div>`;
    }

    const decisionBadge = decision
        ? `<span class="decision ${decision.toLowerCase()}">${escapeHtml(decision)}</span>`
        : "";

    return `
        <article class="event">
            <div class="event-dot">${index + 1}</div>
            <div class="event-card">
                <div class="event-top">
                    <div>
                        <div class="event-name">${escapeHtml(event.agent)} Agent</div>
                        <div class="event-meta">${escapeHtml(revisionText + modelText)}</div>
                    </div>
                    ${decisionBadge}
                </div>
                ${body}
            </div>
        </article>
    `;
}

async function runAgentLoop() {
    const topic = topicInput.value.trim();
    if (!topic) {
        setStatus("Please enter a topic first.", true);
        return;
    }

    runButton.disabled = true;
    runButton.textContent = "Agents are working…";
    results.classList.add("hidden");
    setStatus("Running Writer → Reviewer → Reviser through Groq Cloud Inference…");

    try {
        const response = await fetch("/api/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ topic }),
        });

        let data = {};
        try {
            data = await response.json();
        } catch (e) {
            data = { detail: "Failed to parse server response." };
        }

        if (!response.ok) {
            let errorMsg = "Something went wrong.";
            if (typeof data.detail === "string") {
                errorMsg = data.detail;
            } else if (data.detail && typeof data.detail === "object") {
                errorMsg = JSON.stringify(data.detail, null, 2);
            } else if (data.error) {
                errorMsg = typeof data.error === "string" ? data.error : JSON.stringify(data.error, null, 2);
            } else {
                errorMsg = JSON.stringify(data, null, 2);
            }
            throw new Error(errorMsg);
        }

        timeline.innerHTML = data.events.map(renderEvent).join("");
        finalAnswer.textContent = data.final_answer;
        finalDecision.textContent = data.final_decision || "DONE";
        finalDecision.className = `decision ${(data.final_decision || "pass").toLowerCase()}`;

        const routing = data.router_enabled
            ? ` · router:${data.router}`
            : ` · ${data.writer_model}`;
        summaryBadge.textContent = `${data.revision_count} revision${data.revision_count === 1 ? "" : "s"} used${routing}`;

        statusBox.classList.add("hidden");
        results.classList.remove("hidden");
        results.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
        let msg = error && error.message ? error.message : error;
        if (typeof msg === "object" && msg !== null) {
            try { msg = JSON.stringify(msg, null, 2); } catch (e) { msg = String(msg); }
        }
        setStatus(msg, true);
    } finally {
        runButton.disabled = false;
        runButton.textContent = "Run Agent Loop";
    }
}

runButton.addEventListener("click", runAgentLoop);
topicInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") runAgentLoop();
});