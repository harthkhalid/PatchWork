import { useEffect, useMemo, useState } from "react";
import { fetchJson, postJson } from "./api";

type RepoStat = {
  repo: string;
  false_positive_rate: number;
  false_positives: number;
  correct: number;
  total_labeled: number;
};

type RecentPr = {
  repo: string;
  pr: number;
  health_score: number;
  findings: number;
  prompt_version: string;
  created_at: string | null;
};

type Stars = { stars: number; display: string; message: string };

export default function App() {
  const [repos, setRepos] = useState<RepoStat[]>([]);
  const [recent, setRecent] = useState<RecentPr[]>([]);
  const [stars, setStars] = useState<Stars | null>(null);
  const [fpGlobal, setFpGlobal] = useState<Record<string, number | boolean> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [repoInput, setRepoInput] = useState("org/repo");
  const [prInput, setPrInput] = useState(1);
  const [findingKey, setFindingKey] = useState("src/app.py:42:SQL injection risk");
  const [promptVersion, setPromptVersion] = useState("v2");

  const avgHealth = useMemo(() => {
    if (!recent.length) return null;
    const s = recent.reduce((a, b) => a + b.health_score, 0);
    return Math.round((s / recent.length) * 10) / 10;
  }, [recent]);

  useEffect(() => {
    (async () => {
      try {
        const [r, p, st, fp] = await Promise.all([
          fetchJson<RepoStat[]>("/api/analytics/repos"),
          fetchJson<RecentPr[]>("/api/prs/recent?limit=25"),
          fetchJson<Stars>("/api/stars"),
          fetchJson<Record<string, number | boolean>>("/api/analytics/fp-rate"),
        ]);
        setRepos(r);
        setRecent(p);
        setStars(st);
        setFpGlobal(fp);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  async function submitFeedback(verdict: "correct" | "false_positive") {
    setError(null);
    try {
      await postJson("/api/feedback", {
        repo_full_name: repoInput,
        pr_number: prInput,
        finding_key: findingKey,
        verdict,
        prompt_version: promptVersion,
        installation_id: 0,
      });
      const [r, fp] = await Promise.all([
        fetchJson<RepoStat[]>("/api/analytics/repos"),
        fetchJson<Record<string, number | boolean>>("/api/analytics/fp-rate"),
      ]);
      setRepos(r);
      setFpGlobal(fp);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <div>
          <p className="eyebrow">Patchwork</p>
          <h1>AI code review for GitHub PRs</h1>
          <p className="lede">
            Webhook-driven analysis, line-level comments, and prompt feedback loops tuned for a low false-positive rate.
          </p>
          <div className="actions">
            <a className="btn primary" href="/install">
              Install on GitHub
            </a>
            <a
              className="btn ghost"
              href="https://github.com/apps/patchwork-ai"
              target="_blank"
              rel="noreferrer"
            >
              App docs
            </a>
          </div>
        </div>
        <div className="scorecard">
          <div className="metric">
            <span className="label">Avg PR health (recent)</span>
            <strong>{avgHealth ?? "—"}</strong>
            <span className="hint">0–100, higher is healthier</span>
          </div>
          <div className="metric">
            <span className="label">Global false positive rate</span>
            <strong>
              {fpGlobal ? `${(Number(fpGlobal.false_positive_rate) * 100).toFixed(1)}%` : "—"}
            </strong>
            <span className="hint">Target &lt; 8% on labeled feedback</span>
          </div>
          <div className="metric">
            <span className="label">Community signal</span>
            <strong>{stars?.display ?? "—"}</strong>
            <span className="hint">{stars?.message ?? ""}</span>
          </div>
        </div>
      </header>

      {error && <div className="banner error">{error}</div>}

      <section className="panel">
        <div className="panel-head">
          <h2>Recent PR analyses</h2>
          <p className="muted">Latest health scores from the worker pipeline.</p>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Repository</th>
                <th>PR</th>
                <th>Health</th>
                <th>Findings</th>
                <th>Prompt</th>
              </tr>
            </thead>
            <tbody>
              {recent.length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">
                    No runs yet — open a PR with the installed app to populate this.
                  </td>
                </tr>
              )}
              {recent.map((row) => (
                <tr key={`${row.repo}-${row.pr}-${row.created_at}`}>
                  <td>{row.repo}</td>
                  <td>#{row.pr}</td>
                  <td>
                    <span className="pill">{row.health_score}</span>
                  </td>
                  <td>{row.findings}</td>
                  <td>{row.prompt_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid">
        <div className="panel">
          <div className="panel-head">
            <h2>False positive rate by repo</h2>
            <p className="muted">Uses developer feedback labels (correct vs false positive).</p>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Repo</th>
                  <th>FP rate</th>
                  <th>Labeled</th>
                </tr>
              </thead>
              <tbody>
                {repos.length === 0 && (
                  <tr>
                    <td colSpan={3} className="muted">
                      No feedback yet — submit labels below to build history.
                    </td>
                  </tr>
                )}
                {repos.map((r) => (
                  <tr key={r.repo}>
                    <td>{r.repo}</td>
                    <td>{(r.false_positive_rate * 100).toFixed(1)}%</td>
                    <td>{r.total_labeled}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>Feedback loop</h2>
            <p className="muted">Mark a finding to improve prompt versions and evaluation.</p>
          </div>
          <div className="form">
            <label>
              Repository
              <input value={repoInput} onChange={(e) => setRepoInput(e.target.value)} />
            </label>
            <label>
              PR number
              <input
                type="number"
                min={1}
                value={prInput}
                onChange={(e) => setPrInput(Number(e.target.value))}
              />
            </label>
            <label>
              Finding key
              <input value={findingKey} onChange={(e) => setFindingKey(e.target.value)} />
            </label>
            <label>
              Prompt version
              <input value={promptVersion} onChange={(e) => setPromptVersion(e.target.value)} />
            </label>
            <div className="btn-row">
              <button className="btn primary" type="button" onClick={() => submitFeedback("correct")}>
                Mark correct
              </button>
              <button className="btn danger" type="button" onClick={() => submitFeedback("false_positive")}>
                False positive
              </button>
            </div>
          </div>
        </div>
      </section>

      <footer className="footer">
        <span>Made by Harth Khalid</span>
      </footer>
    </div>
  );
}
