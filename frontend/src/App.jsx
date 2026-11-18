import { useEffect, useState } from "react";

const api = async (path, options = {}, token = "") => {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { ...options, headers });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Request failed");
  return body;
};

function Login({ onLogin }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault(); setError("");
    try { onLogin(await api("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) })); }
    catch (requestError) { setError(requestError.message); }
  }
  return <main className="login-page"><form className="login-card" onSubmit={submit}><div className="welcome-icon">✦</div><p className="eyebrow">SUPPORTOS PORTFOLIO DEMO</p><h1>Sign in to SupportOS</h1><p className="muted">Use the demo accounts from the project README.</p><label>Username<input value={username} onChange={(event) => setUsername(event.target.value)} /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>{error && <div className="error">{error}</div>}<button className="primary-button">Sign in</button><small>admin / admin123 · customer / customer123</small></form></main>;
}

function Chat({ token, user, onTicket }) {
  const [conversationId, setConversationId] = useState(null); const [messages, setMessages] = useState([]); const [draft, setDraft] = useState(""); const [sending, setSending] = useState(false); const [error, setError] = useState("");
  useEffect(() => { newConversation(); }, []);
  async function newConversation() { try { const conversation = await api("/api/conversations", { method: "POST" }, token); setConversationId(conversation.id); setMessages([]); } catch (requestError) { setError(requestError.message); } }
  async function sendMessage(event) {
    event.preventDefault(); if (!draft.trim() || !conversationId || sending) return;
    const question = draft.trim(); setDraft(""); setError(""); setMessages((current) => [...current, { role: "user", content: question }]); setSending(true);
    try { const response = await api(`/api/conversations/${conversationId}/messages`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: question }) }, token); setMessages((current) => [...current, { ...response, role: "assistant" }]); if (response.ticket_id) onTicket?.(); }
    catch (requestError) { setError(requestError.message); } finally { setSending(false); }
  }
  async function rate(rating) { try { await api(`/api/conversations/${conversationId}/feedback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rating }) }, token); } catch (requestError) { setError(requestError.message); } }
  return <section className="chat-area"><header className="chat-header"><div><p className="eyebrow">CUSTOMER SUPPORT · {user.role.toUpperCase()}</p><h1>Ask your knowledge base</h1></div><button className="new-button" onClick={newConversation}>New conversation</button></header><div className="chat-scroll">{messages.length === 0 && <div className="welcome"><div className="welcome-icon">✦</div><h2>Grounded answers, not guesses.</h2><p>Ask a question about the indexed support documents. Every answer includes its retrieved sources.</p><div className="suggestions"><button onClick={() => setDraft("How can I reset my password?")}>How can I reset my password?</button><button onClick={() => setDraft("What is the refund policy?")}>What is the refund policy?</button></div></div>}{messages.map((message, index) => <article className={`message ${message.role}`} key={index}><div className="avatar">{message.role === "user" ? "You" : "✦"}</div><div className="message-body"><div className="message-content">{message.content || message.answer}</div>{message.needs_human && <div className="handoff">Needs human review · confidence {((message.confidence || 0) * 100).toFixed(0)}%</div>}{message.role === "assistant" && message.sources?.length > 0 && <div className="sources"><strong>Sources</strong>{message.sources.map((source) => <div className="source" key={source.chunk_id}><span>↗</span><div><strong>{source.filename}</strong><small>{source.excerpt}…</small></div></div>)}<div className="feedback"><button onClick={() => rate(1)}>Helpful</button><button onClick={() => rate(-1)}>Needs work</button></div></div>}</div></article>)}{sending && <article className="message assistant"><div className="avatar">✦</div><div className="typing"><span /><span /><span /></div></article>}</div><form className="composer" onSubmit={sendMessage}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask a question about your support documentation…" rows="2" onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(event); } }} /><button type="submit" disabled={sending || !draft.trim()}>Send<span>↗</span></button><small>Enter to send · Shift + Enter for a new line</small></form>{error && <div className="error">{error}</div>}</section>;
}

function Knowledge({ token }) {
  const [documents, setDocuments] = useState([]); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function load() { try { setDocuments(await api("/api/documents", {}, token)); } catch (requestError) { setError(requestError.message); } }
  useEffect(() => { load(); }, []);
  async function upload(event) { const file = event.target.files?.[0]; if (!file) return; setBusy(true); const data = new FormData(); data.append("file", file); try { await api("/api/documents", { method: "POST", body: data }, token); await load(); } catch (requestError) { setError(requestError.message); } finally { setBusy(false); event.target.value = ""; } }
  async function remove(id) { if (!window.confirm("Delete this document and its indexed chunks?")) return; try { await api(`/api/documents/${id}`, { method: "DELETE" }, token); await load(); } catch (requestError) { setError(requestError.message); } }
  return <div className="admin-panel"><div className="section-heading"><div><p className="eyebrow">ADMIN</p><h2>Knowledge base</h2></div><label className="upload-button">{busy ? "Indexing…" : "+ Upload document"}<input type="file" accept=".txt,.md,.pdf" onChange={upload} disabled={busy} /></label></div>{error && <div className="error">{error}</div>}<div className="admin-list">{documents.length === 0 && <p className="muted">No documents indexed yet.</p>}{documents.map((document) => <div className="admin-row" key={document.id}><div><strong>{document.filename}</strong><small>{document.chunk_count} indexed chunks · {new Date(document.created_at).toLocaleString()}</small></div><button className="danger-button" onClick={() => remove(document.id)}>Delete</button></div>)}</div></div>;
}

function Inbox({ token }) {
  const [tickets, setTickets] = useState([]); const [selected, setSelected] = useState(null); const [conversation, setConversation] = useState(null); const [reply, setReply] = useState(""); const [error, setError] = useState("");
  async function load() { try { setTickets(await api("/api/tickets", {}, token)); } catch (requestError) { setError(requestError.message); } }
  useEffect(() => { load(); }, []);
  async function select(ticket) { setSelected(ticket); try { setConversation(await api(`/api/conversations/${ticket.conversation_id}`, {}, token)); } catch (requestError) { setError(requestError.message); } }
  async function sendReply(event) { event.preventDefault(); if (!reply.trim() || !selected) return; try { await api(`/api/tickets/${selected.id}/reply`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: reply }) }, token); setReply(""); await load(); await select(selected); } catch (requestError) { setError(requestError.message); } }
  async function setStatus(status) { try { await api(`/api/tickets/${selected.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) }, token); await load(); } catch (requestError) { setError(requestError.message); } }
  return <div className="admin-panel"><div className="section-heading"><div><p className="eyebrow">STAFF WORKSPACE</p><h2>Agent inbox</h2></div><button className="new-button" onClick={load}>Refresh</button></div>{error && <div className="error">{error}</div>}<div className="inbox-grid"><div className="ticket-list">{tickets.length === 0 && <p className="muted">No escalated conversations yet.</p>}{tickets.map((ticket) => <button className={`ticket-card ${selected?.id === ticket.id ? "selected" : ""}`} key={ticket.id} onClick={() => select(ticket)}><strong>{ticket.subject}</strong><small>{ticket.status.replace("_", " ")} · {new Date(ticket.created_at).toLocaleString()}</small></button>)}</div><div className="ticket-detail">{!conversation && <p className="muted">Select a ticket to continue the conversation.</p>}{conversation && <><div className="ticket-actions"><span className="pill">{selected.status.replace("_", " ")}</span><button onClick={() => setStatus("in_progress")}>In progress</button><button onClick={() => setStatus("resolved")}>Resolve</button></div>{conversation.messages.map((message, index) => <div className={`ticket-message ${message.role}`} key={index}><small>{message.role}</small><p>{message.content}</p></div>)}<form className="reply-form" onSubmit={sendReply}><textarea value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Reply as a support agent…" rows="3" /><button className="primary-button">Send reply</button></form></>}</div></div></div>;
}

function Retrieval({ token }) {
  const [question, setQuestion] = useState(""); const [results, setResults] = useState([]); const [error, setError] = useState("");
  async function search(event) { event.preventDefault(); if (!question.trim()) return; try { setResults(await api("/api/retrieval/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: question }) }, token)); } catch (requestError) { setError(requestError.message); } }
  return <div className="admin-panel"><div className="section-heading"><div><p className="eyebrow">RAG DEBUGGER</p><h2>Retrieval testing</h2></div></div><form className="tool-form" onSubmit={search}><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Test a retrieval question…" /><button className="primary-button">Search</button></form>{error && <div className="error">{error}</div>}<div className="result-list">{results.map((result) => <div className="result-card" key={result.chunk_id}><div><strong>{result.filename}</strong><small>combined {result.score} · vector {result.vector_score} · keyword {result.keyword_score}</small></div><p>{result.excerpt}</p></div>)}</div></div>;
}

function Evaluation({ token }) {
  const [results, setResults] = useState([]); const [error, setError] = useState("");
  async function run() { try { setResults(await api("/api/evaluation/run", { method: "POST" }, token)); } catch (requestError) { setError(requestError.message); } }
  return <div className="admin-panel"><div className="section-heading"><div><p className="eyebrow">QUALITY CHECK</p><h2>Retrieval evaluation</h2></div><button className="primary-button" onClick={run}>Run evaluation</button></div><p className="muted">Runs <code>evaluation/questions.json</code> and checks whether each expected document appears in the top three results.</p>{error && <div className="error">{error}</div>}<div className="admin-list">{results.map((result) => <div className="admin-row" key={result.question}><div><strong>{result.question}</strong><small>Expected: {result.expected_filename} · Retrieved: {result.retrieved_filenames.join(", ") || "none"}</small></div><span className={result.passed ? "pass" : "fail"}>{result.passed ? "PASS" : "REVIEW"}</span></div>)}</div></div>;
}

function Feedback({ token }) {
  const [items, setItems] = useState([]); const [error, setError] = useState("");
  useEffect(() => { api("/api/feedback", {}, token).then(setItems).catch((requestError) => setError(requestError.message)); }, []);
  return <div className="admin-panel"><div className="section-heading"><div><p className="eyebrow">QUALITY SIGNALS</p><h2>Answer feedback</h2></div></div>{error && <div className="error">{error}</div>}<div className="admin-list">{items.length === 0 && <p className="muted">No feedback has been submitted yet.</p>}{items.map((item) => <div className="feedback-row" key={item.id}><span className={item.rating === 1 ? "pass" : "fail"}>{item.rating === 1 ? "Helpful" : "Needs work"}</span><div><strong>{item.content}</strong><small>{item.comment || "No comment"}</small></div></div>)}</div></div>;
}

function App() {
  const [session, setSession] = useState(() => JSON.parse(localStorage.getItem("support_session") || "null")); const [view, setView] = useState("chat");
  function login(value) { localStorage.setItem("support_session", JSON.stringify(value)); setSession(value); }
  function logout() { localStorage.removeItem("support_session"); setSession(null); }
  if (!session) return <Login onLogin={login} />;
  const staff = session.role === "admin";
  return <main className="app-shell"><aside className="sidebar"><div className="brand"><span className="brand-mark">✦</span><div><strong>SupportOS</strong><small>{session.role} workspace</small></div></div><nav className="side-nav"><button className={view === "chat" ? "active" : ""} onClick={() => setView("chat")}>✦ Support chat</button>{staff && <><button className={view === "inbox" ? "active" : ""} onClick={() => setView("inbox")}>▣ Agent inbox</button>{session.role === "admin" && <><button className={view === "knowledge" ? "active" : ""} onClick={() => setView("knowledge")}>▤ Knowledge base</button><button className={view === "feedback" ? "active" : ""} onClick={() => setView("feedback")}>♡ Feedback</button></>}<button className={view === "retrieval" ? "active" : ""} onClick={() => setView("retrieval")}>⌕ Retrieval testing</button><button className={view === "evaluation" ? "active" : ""} onClick={() => setView("evaluation")}>✓ Evaluation</button></>}</nav><div className="sidebar-footer"><span className="status-dot" /> Gemini connected<button className="logout-button" onClick={logout}>Sign out</button></div></aside>{view === "chat" && <Chat token={session.token} user={session} onTicket={() => staff && setView("inbox")} />}{view === "inbox" && <Inbox token={session.token} />}{view === "knowledge" && <Knowledge token={session.token} />}{view === "feedback" && <Feedback token={session.token} />}{view === "retrieval" && <Retrieval token={session.token} />}{view === "evaluation" && <Evaluation token={session.token} />}</main>;
}

export default App;
