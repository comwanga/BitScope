"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  ChallengeDefinition,
  ChallengeHint,
  ChallengeVerificationResult,
  CurriculumEntry,
  fetchChallengeHint,
  fetchChallenges,
  fetchCurriculum,
  verifyChallenge
} from "@/lib/api";

export function CurriculumChallengeHub() {
  const [chapters, setChapters] = useState<CurriculumEntry[]>([]);
  const [courseUrl, setCourseUrl] = useState("");
  const [curriculumExplanation, setCurriculumExplanation] = useState("");
  const [challenges, setChallenges] = useState<ChallengeDefinition[]>([]);
  const [challengeExplanation, setChallengeExplanation] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [curriculum, catalog] = await Promise.all([fetchCurriculum(), fetchChallenges()]);
        if (!active) return;
        setChapters(curriculum.chapters);
        setCourseUrl(curriculum.course_url);
        setCurriculumExplanation(curriculum.explanation);
        setChallenges(catalog.challenges);
        setChallengeExplanation(catalog.explanation);
        setSelectedId(catalog.challenges[0]?.challenge_id ?? "");
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : "The curriculum could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  const selectedChallenge = useMemo(
    () => challenges.find((challenge) => challenge.challenge_id === selectedId) ?? challenges[0] ?? null,
    [challenges, selectedId]
  );

  return (
    <div className="space-y-10">
      <header className="max-w-4xl">
        <p className="text-sm font-semibold uppercase text-forest">Curriculum and Challenge Mode</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal text-ink sm:text-4xl">Learn the concept, then prove the result</h1>
        <p className="mt-4 text-base leading-7 text-stone-700 sm:text-lg sm:leading-8">
          Chapters 3–13 are mapped only to BitScope features that exist. Challenges keep solutions locked and validate completed work from backend-owned Bitcoin Core evidence.
        </p>
        <nav aria-label="Page sections" className="mt-5 flex flex-wrap gap-3">
          <a href="#curriculum" className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-ink hover:border-forest">Curriculum mapping</a>
          <a href="#challenges" className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-ink hover:border-forest">Challenge Mode</a>
          <Link href="/learn" className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-ink hover:border-forest">Concept library</Link>
        </nav>
      </header>

      {error ? <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700">{error}</p> : null}
      {loading ? <p role="status" className="text-sm text-stone-600">Loading curriculum and challenges…</p> : null}

      <section id="curriculum" aria-labelledby="curriculum-title" className="scroll-mt-6 space-y-5">
        <div className="max-w-4xl">
          <p className="text-sm font-semibold uppercase text-forest">Learning path</p>
          <h2 id="curriculum-title" className="mt-2 text-2xl font-semibold text-ink">Chapters 3–13</h2>
          {curriculumExplanation ? <p className="mt-3 text-sm leading-6 text-stone-700">{curriculumExplanation}</p> : null}
          {courseUrl ? <a href={courseUrl} target="_blank" rel="noreferrer" className="mt-3 inline-block text-sm font-semibold text-forest underline underline-offset-4">Open the original course repository <span className="sr-only">in a new tab</span></a> : null}
        </div>
        <div className="grid gap-4">
          {chapters.map((entry) => <CurriculumChapter key={entry.chapter} entry={entry} />)}
        </div>
      </section>

      <section id="challenges" aria-labelledby="challenges-title" className="scroll-mt-6 space-y-5">
        <div className="max-w-4xl">
          <p className="text-sm font-semibold uppercase text-forest">Core-validated practice</p>
          <h2 id="challenges-title" className="mt-2 text-2xl font-semibold text-ink">Challenge Mode</h2>
          {challengeExplanation ? <p className="mt-3 text-sm leading-6 text-stone-700">{challengeExplanation}</p> : null}
        </div>
        <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(17rem,22rem)_1fr]">
          <div className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm" aria-label="Available challenges">
            <p className="font-semibold text-ink">Choose a challenge</p>
            <div className="mt-3 space-y-2">
              {challenges.map((challenge) => (
                <button
                  key={challenge.challenge_id}
                  type="button"
                  aria-pressed={challenge.challenge_id === selectedChallenge?.challenge_id}
                  onClick={() => setSelectedId(challenge.challenge_id)}
                  className={`w-full rounded-md border px-3 py-3 text-left ${challenge.challenge_id === selectedChallenge?.challenge_id ? "border-forest bg-forest text-white" : "border-stone-300 bg-white text-ink hover:bg-stone-50"}`}
                >
                  <span className="block text-sm font-semibold">{challenge.title}</span>
                  <span className={`mt-1 block text-xs ${challenge.challenge_id === selectedChallenge?.challenge_id ? "text-stone-100" : "text-stone-500"}`}>{challenge.difficulty} · {challenge.scenario_id}</span>
                </button>
              ))}
            </div>
          </div>
          {selectedChallenge ? <ChallengeWorkspace key={selectedChallenge.challenge_id} challenge={selectedChallenge} /> : null}
        </div>
      </section>
    </div>
  );
}

function CurriculumChapter({ entry }: { entry: CurriculumEntry }) {
  return (
    <details className="rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <summary className="cursor-pointer list-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-forest">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><p className="text-xs font-semibold uppercase text-forest">Chapter {entry.chapter}</p><h3 className="mt-1 text-lg font-semibold text-ink">{entry.title}</h3><p className="mt-2 text-sm leading-6 text-stone-700">{entry.learning_objective}</p></div>
          <span aria-hidden="true" className="rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold text-stone-600">Open mapping</span>
        </div>
      </summary>
      <div className="mt-5 grid gap-5 border-t border-stone-200 pt-5 lg:grid-cols-2">
        <ChapterList title="Prerequisites" values={entry.prerequisites} />
        <ChapterList title="Core RPC methods" values={entry.rpc_methods} mono />
        <ChapterList title="Verification criteria" values={entry.verification_criteria} />
        <div><h4 className="font-semibold text-ink">Implemented links</h4><div className="mt-2 flex flex-wrap gap-2">{entry.relevant_pages.map((page) => <Link key={page} href={page} className="rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-sm text-ink hover:border-forest">{page}</Link>)}</div>{entry.relevant_scenarios.length ? <p className="mt-3 text-sm text-stone-700"><span className="font-semibold">Verified Scenarios:</span> {entry.relevant_scenarios.join(", ")}</p> : null}</div>
        <div><h4 className="font-semibold text-ink">Guided exercise</h4><p className="mt-2 text-sm leading-6 text-stone-700">{entry.guided_exercise}</p></div>
        <div><h4 className="font-semibold text-ink">Independent challenge</h4><p className="mt-2 text-sm leading-6 text-stone-700">{entry.independent_challenge}</p></div>
      </div>
      {entry.implementation_note ? <p className="mt-5 rounded-md border border-brass bg-stone-50 p-3 text-sm leading-6 text-stone-700"><span className="font-semibold">Implementation boundary:</span> {entry.implementation_note}</p> : null}
      <a href={entry.source_url} target="_blank" rel="noreferrer" className="mt-4 inline-block text-sm font-semibold text-forest underline underline-offset-4">Read the original chapter <span className="sr-only">in a new tab</span></a>
    </details>
  );
}

function ChapterList({ title, values, mono = false }: { title: string; values: string[]; mono?: boolean }) {
  return <div><h4 className="font-semibold text-ink">{title}</h4><ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-stone-700">{values.map((value) => <li key={value} className={mono ? "font-mono text-xs" : ""}>{value}</li>)}</ul></div>;
}

function ChallengeWorkspace({ challenge }: { challenge: ChallengeDefinition }) {
  const [hints, setHints] = useState<ChallengeHint[]>([]);
  const [runId, setRunId] = useState("");
  const [labSessionId, setLabSessionId] = useState("");
  const [result, setResult] = useState<ChallengeVerificationResult | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState<"hint" | "verify" | null>(null);
  const statusRef = useRef<HTMLDivElement>(null);

  async function requestHint() {
    if (hints.length >= challenge.hint_count) return;
    setWorking("hint");
    setError("");
    try {
      const hint = await fetchChallengeHint(challenge.challenge_id, hints.length + 1);
      setHints((current) => [...current, hint]);
      window.requestAnimationFrame(() => statusRef.current?.focus());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The hint could not be loaded.");
    } finally {
      setWorking(null);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!runId.trim() || !labSessionId.trim()) {
      setError("Provide both the completed scenario run ID and its lab session ID.");
      return;
    }
    setWorking("verify");
    setError("");
    try {
      setResult(await verifyChallenge(challenge.challenge_id, runId.trim(), labSessionId.trim()));
      window.requestAnimationFrame(() => statusRef.current?.focus());
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "Challenge verification failed.");
    } finally {
      setWorking(null);
    }
  }

  return (
    <article className="min-w-0 space-y-5 rounded-lg border border-stone-300 bg-panel p-4 shadow-sm sm:p-5">
      <header><div className="flex flex-wrap gap-2 text-xs font-semibold"><span className="rounded-full bg-stone-100 px-3 py-1 text-stone-700">{challenge.difficulty}</span><span className="rounded-full bg-stone-100 px-3 py-1 text-stone-700">{challenge.scenario_id}</span></div><h3 className="mt-3 text-2xl font-semibold text-ink">{challenge.title}</h3><p className="mt-3 text-sm leading-6 text-stone-700">{challenge.objective}</p></header>
      <div className="grid gap-4 md:grid-cols-2">
        <ChapterList title="Allowed actions" values={challenge.allowed_actions} />
        <div><h4 className="font-semibold text-ink">Relevant pages</h4><div className="mt-2 flex flex-wrap gap-2">{challenge.relevant_pages.map((page) => <Link key={page} href={page} className="rounded-md border border-stone-300 bg-white px-2.5 py-1.5 text-sm text-ink hover:border-forest">{page}</Link>)}</div></div>
      </div>
      <div className="rounded-md border border-stone-300 p-4"><h4 className="font-semibold text-ink">Verification boundary</h4><p className="mt-2 text-sm leading-6 text-stone-700">{challenge.verification_summary}</p><p className="mt-2 text-xs font-semibold uppercase text-stone-500">The solution remains locked until backend completion.</p></div>

      <section aria-labelledby={`hints-${challenge.challenge_id}`}>
        <div className="flex flex-wrap items-center justify-between gap-3"><h4 id={`hints-${challenge.challenge_id}`} className="font-semibold text-ink">Progressive hints</h4><button type="button" onClick={() => void requestHint()} disabled={working !== null || hints.length >= challenge.hint_count} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-ink hover:border-forest disabled:cursor-not-allowed disabled:opacity-60">{hints.length >= challenge.hint_count ? "All hints requested" : working === "hint" ? "Loading hint" : `Request hint ${hints.length + 1}`}</button></div>
        {hints.length ? <ol className="mt-3 space-y-2">{hints.map((hint) => <li key={hint.level} className="rounded-md bg-stone-100 p-3 text-sm leading-6 text-stone-700"><span className="font-semibold">Hint {hint.level}:</span> {hint.hint}</li>)}</ol> : <p className="mt-2 text-sm text-stone-600">No hints revealed.</p>}
      </section>

      <form onSubmit={submit} className="space-y-3 rounded-md border border-stone-300 p-4">
        <h4 className="font-semibold text-ink">Submit Core-backed evidence</h4>
        <p className="text-sm leading-6 text-stone-600">Challenge validation reads the scenario run and canonical evidence artifacts from the backend. Browser state cannot complete a challenge.</p>
        <div className="grid gap-3 md:grid-cols-2"><label className="grid gap-1 text-sm font-medium text-stone-700">Scenario run ID<input value={runId} onChange={(event) => setRunId(event.target.value)} className="rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest" placeholder="UUID" /></label><label className="grid gap-1 text-sm font-medium text-stone-700">Lab session ID<input value={labSessionId} onChange={(event) => setLabSessionId(event.target.value)} className="rounded-md border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-forest" placeholder="Owning session" /></label></div>
        <button type="submit" disabled={working !== null} className="rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink disabled:cursor-wait disabled:opacity-70">{working === "verify" ? "Verifying with backend" : "Verify challenge"}</button>
      </form>

      {error ? <p role="alert" className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
      <div ref={statusRef} tabIndex={-1} aria-live="polite" className="focus:outline-none">
        {result ? <ChallengeResult result={result} /> : hints.length ? <p className="sr-only">Hint {hints.length} is now available.</p> : null}
      </div>
    </article>
  );
}

function ChallengeResult({ result }: { result: ChallengeVerificationResult }) {
  return (
    <section aria-labelledby="challenge-result-title" className={`rounded-md border p-4 ${result.completed ? "border-forest" : "border-brass"}`}>
      <p className="text-xs font-semibold uppercase text-stone-500">Backend verification result</p>
      <h4 id="challenge-result-title" className="mt-1 text-lg font-semibold text-ink">{result.completed ? "Challenge completed" : "Completion still locked"}</h4>
      <p className="mt-2 text-sm leading-6 text-stone-700">{result.final_explanation}</p>
      <ul className="mt-4 space-y-2">{result.checks.map((check) => <li key={check.check_id} className="flex gap-2 text-sm"><span aria-hidden="true" className={check.passed ? "text-forest" : "text-rust"}>{check.passed ? "✓" : "×"}</span><span><span className="font-mono text-xs">{check.check_id}</span><span className="block text-stone-700">{check.explanation}</span></span><span className="sr-only">{check.passed ? "passed" : "not passed"}</span></li>)}</ul>
      {result.completed ? <button type="button" onClick={() => downloadEvidence(result)} className="mt-4 rounded-md bg-forest px-4 py-2 text-sm font-semibold text-white hover:bg-ink">Export completion evidence</button> : null}
    </section>
  );
}

function downloadEvidence(result: ChallengeVerificationResult) {
  const blob = new Blob([`${JSON.stringify(result, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `bitscope-challenge-${result.challenge_id}-${result.run_id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}
