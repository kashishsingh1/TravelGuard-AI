import React, { useState, useEffect } from 'react';
import {
  Shield, Play, CheckCircle2, AlertTriangle, XCircle, Wrench,
  FileCode2, GitBranch, Layers, ExternalLink, Copy, Check,
  RotateCcw, Sparkles, Activity, ChevronRight, ChevronDown, ChevronUp, Terminal,
  TrendingUp, Zap, AlertCircle, Clock,
} from 'lucide-react';
import './travelguard.css';
import {
  AutonomousRunResult, IntelligenceResult,
  BusinessJourney, TestInventoryItem,
} from './types';

interface TravelGuardConsoleProps {
  onSwitchToSut: () => void;
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */
const getRiskColor = (risk: string) => {
  switch (risk?.toLowerCase()) {
    case 'low':      return '#10b981';
    case 'medium':   return '#f59e0b';
    case 'high':     return '#f97316';
    case 'critical': return '#f43f5e';
    default:         return '#6b7280';
  }
};

const getRiskBg = (risk: string) => {
  switch (risk?.toLowerCase()) {
    case 'low':      return 'rgba(16,185,129,0.12)';
    case 'medium':   return 'rgba(245,158,11,0.12)';
    case 'high':     return 'rgba(249,115,22,0.12)';
    case 'critical': return 'rgba(244,63,94,0.12)';
    default:         return 'rgba(107,114,128,0.12)';
  }
};

const getVerdictForRisk = (risk: string) => {
  switch (risk?.toLowerCase()) {
    case 'low':      return { label: 'SAFE TO COMMIT', sub: 'Run recommended tests as a precaution', type: 'safe' };
    case 'medium':   return { label: 'REVIEW BEFORE COMMIT', sub: 'Run P0 and P1 tests before merging', type: 'review' };
    case 'high':     return { label: 'ADDRESS BEFORE COMMIT', sub: 'High-risk changes — run full selected test suite', type: 'blocked' };
    case 'critical': return { label: 'DO NOT COMMIT', sub: 'Critical impact detected — fix and re-analyze', type: 'blocked' };
    default:         return { label: 'ANALYSIS COMPLETE', sub: 'Review the findings below', type: 'review' };
  }
};

const getRunCommand = (file: string) => {
  if (!file) return '';
  if (file.includes('.spec.ts')) {
    const rel = file.replace(/^tests\//, '');
    return `npx playwright test ${rel}`;
  }
  if (file.includes('.py')) return `pytest ${file}`;
  return `npx playwright test`;
};

/* ── Component ───────────────────────────────────────────────────────────── */
export const TravelGuardConsole: React.FC<TravelGuardConsoleProps> = ({ onSwitchToSut }) => {
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null);
  const [mockLlm, setMockLlm]     = useState<boolean>(true);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [runStatusMsg, setRunStatusMsg] = useState<string>('');
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);
  const [copiedCode, setCopiedCode] = useState<boolean>(false);
  const [copiedAll, setCopiedAll] = useState<boolean>(false);
  const [priorityFilter, setPriorityFilter] = useState<'ALL' | 'P0' | 'P1' | 'P2'>('ALL');
  const [expandedDiffs, setExpandedDiffs] = useState<Record<string, boolean>>({});
  const [showSkipped, setShowSkipped] = useState<boolean>(false);

  // Live test execution state
  const [testExecutionResults, setTestExecutionResults] = useState<
    Record<string, { status: 'passed' | 'failed' | 'running'; duration_ms?: number; error?: string; stdout?: string }>
  >({});
  const [runningSingleTestKey, setRunningSingleTestKey] = useState<string | null>(null);
  const [isRunningAllTests, setIsRunningAllTests] = useState<boolean>(false);
  const [runningTestProgress, setRunningTestProgress] = useState<string>('');
  const [isRunningStages4to7, setIsRunningStages4to7] = useState<boolean>(false);

  const toggleDiff = (path: string) => {
    setExpandedDiffs(prev => ({ ...prev, [path]: !prev[path] }));
  };

  const [autonomousResult, setAutonomousResult] = useState<AutonomousRunResult | null>(null);
  const [intelligenceResult, setIntelligenceResult] = useState<IntelligenceResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');

  const [journeys, setJourneys]   = useState<BusinessJourney[]>([]);
  const [inventory, setInventory] = useState<TestInventoryItem[]>([]);

  useEffect(() => {
    fetch('/api/travelguard/config')
      .then(r => r.json())
      .then(d => {
        if (d.journeys)  setJourneys(d.journeys);
        if (d.inventory) setInventory(d.inventory);
      })
      .catch(e => console.warn('Config load failed:', e));
  }, []);

  const resetResults = () => {
    setAutonomousResult(null);
    setIntelligenceResult(null);
    setErrorMsg('');
    setTestExecutionResults({});
  };

  const runAnalyze = async (scenarioKey: string | null) => {
    resetResults();
    setIsRunning(true);
    setRunStatusMsg(
      scenarioKey
        ? 'Analyzing code changes & evaluating test inventory...'
        : 'Reading local git working tree & running quality analysis...'
    );
    try {
      const res = await fetch('/api/travelguard/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioKey, mock_llm: mockLlm }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Analysis failed');
      setIntelligenceResult(await res.json());
    } catch (e: any) {
      setErrorMsg(e.message || 'An error occurred during analysis');
    } finally {
      setIsRunning(false);
      setRunStatusMsg('');
    }
  };

  const runAutonomous = async (scenarioKey: string | null) => {
    resetResults();
    setIsRunning(true);
    setIsRunningStages4to7(true);
    setRunStatusMsg(
      scenarioKey
        ? 'Executing tests, diagnosing failures & checking release gate...'
        : 'Executing selected Playwright tests against local working tree & enforcing release gate...'
    );
    try {
      const res = await fetch('/api/travelguard/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioKey, mock_llm: mockLlm }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Autonomous run failed');
      const data: AutonomousRunResult = await res.json();
      setAutonomousResult(data);

      // Populate testExecutionResults from autonomous run
      if (data.execution_results && Array.isArray(data.execution_results)) {
        const resultsMap: Record<string, any> = {};
        for (const er of data.execution_results) {
          const keys = [er.test_id, er.test_file, er.test_name].filter(Boolean);
          const mapped = {
            status: er.status,
            duration_ms: er.duration_ms,
            error: er.failure?.error_message || (er.status === 'failed' ? (er.stderr || er.stdout || 'Test failed') : undefined),
            stdout: er.stdout,
          };
          keys.forEach(k => { resultsMap[k] = mapped; });
        }
        setTestExecutionResults(prev => ({ ...prev, ...resultsMap }));
      }
    } catch (e: any) {
      setErrorMsg(e.message || 'An error occurred during autonomous run');
    } finally {
      setIsRunning(false);
      setIsRunningStages4to7(false);
      setRunStatusMsg('');
    }
  };

  const handleAnalyzeLocal = () => {
    setSelectedScenario(null);
    runAnalyze(null);
  };

  const handleRunStages4to7 = () => {
    setSelectedScenario(null);
    runAutonomous(null);
  };

  const handleScenario = (key: string) => {
    setSelectedScenario(key);
    key === 'scenario_d' ? runAnalyze(key) : runAutonomous(key);
  };

  const handleRunSingleTest = async (t: any) => {
    const testKey = t.test_id || t.id || t.file || t.test_file || t.name;
    const testFile = t.file || t.test_file;
    const testId = t.test_id || t.id || 'test';
    const testName = t.name || t.test_name || 'Test';

    setRunningSingleTestKey(testKey);
    setTestExecutionResults(prev => ({
      ...prev,
      [testKey]: { status: 'running' },
      [testFile]: { status: 'running' },
      [testId]: { status: 'running' },
    }));

    try {
      const res = await fetch('/api/travelguard/test-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          test_file: testFile,
          test_id: testId,
          test_name: testName,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Test execution failed');
      const data = await res.json();
      const mapped = {
        status: data.status,
        duration_ms: data.duration_ms,
        error: data.failure?.error_message || (data.status === 'failed' ? (data.stderr || data.stdout || 'Test failed') : undefined),
        stdout: data.stdout,
      };
      setTestExecutionResults(prev => ({
        ...prev,
        [testKey]: mapped,
        [testFile]: mapped,
        [testId]: mapped,
      }));
    } catch (err: any) {
      const mapped = {
        status: 'failed' as const,
        error: err.message || 'Execution error',
      };
      setTestExecutionResults(prev => ({
        ...prev,
        [testKey]: mapped,
        [testFile]: mapped,
        [testId]: mapped,
      }));
    } finally {
      setRunningSingleTestKey(null);
    }
  };

  const copyCmd = (cmd: string) => {
    navigator.clipboard.writeText(cmd);
    setCopiedCmd(cmd);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  const copyCode = () => {
    const code = intelligenceResult?.generated_test?.code;
    if (!code) return;
    navigator.clipboard.writeText(code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  /* ── Derived values ────────────────────────────────────────────────────── */
  const hasResult   = !!(autonomousResult || intelligenceResult);
  const impact      = intelligenceResult?.impact || autonomousResult?.impact;
  const qr          = autonomousResult?.quality_report;
  const riskLevel   = impact?.risk?.level || impact?.ai_risk_level || (qr?.quality_gate_passed ? 'LOW' : qr ? 'HIGH' : '');
  const riskScore   = impact?.risk?.score ?? impact?.ai_risk_score;
  const riskReason  = impact?.risk?.reason || impact?.ai_risk_reason || impact?.summary || qr?.summary || '';
  const isGatePass  = qr?.quality_gate_passed ?? false;

  let verdict: { label: string; sub: string; type: string } | null = null;
  if (autonomousResult) {
    verdict = {
      label: isGatePass ? 'RELEASE ALLOWED' : 'RELEASE BLOCKED',
      sub:   qr?.summary || '',
      type:  isGatePass ? 'safe' : 'blocked',
    };
  } else if (intelligenceResult) {
    verdict = getVerdictForRisk(riskLevel);
  }

  const selectedTests = intelligenceResult?.selected_tests || autonomousResult?.selected_tests || [];
  const skippedTests  = intelligenceResult?.skipped_tests  || autonomousResult?.skipped_tests  || [];

  const filteredSelectedTests = selectedTests.filter((t: any) => {
    if (priorityFilter === 'ALL') return true;
    return t.priority === priorityFilter;
  });

  const p0Count = selectedTests.filter((t: any) => t.priority === 'P0').length;
  const p1Count = selectedTests.filter((t: any) => t.priority === 'P1').length;

  const handleRunAllTests = async () => {
    if (!selectedTests.length) return;
    setIsRunningAllTests(true);
    for (let i = 0; i < selectedTests.length; i++) {
      const t = selectedTests[i];
      setRunningTestProgress(`${i + 1}/${selectedTests.length}`);
      await handleRunSingleTest(t);
    }
    setIsRunningAllTests(false);
    setRunningTestProgress('');
  };

  const copyAllCmds = () => {
    const specs = selectedTests
      .map((t: any) => (t.file || t.test_file || '').replace(/^tests\//, ''))
      .filter(Boolean);
    if (!specs.length) return;
    const combined = `npx playwright test ${specs.join(' ')}`;
    navigator.clipboard.writeText(combined);
    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 2000);
  };

  /* ── Pipeline stepper stage logic ─────────────────────────────────────── */
  const steps = [
    { icon: <GitBranch size={12} />, label: '1. Change Detect' },
    { icon: <Layers size={12} />,    label: '2. Journey Mapping' },
    { icon: <FileCode2 size={12} />, label: '3. Test Selection' },
    { icon: <Activity size={12} />,  label: '4. Execution' },
    { icon: <AlertTriangle size={12} />, label: '5. AI Diagnosis' },
    { icon: <Wrench size={12} />,    label: '6. Self-Healing' },
    { icon: <Shield size={12} />,    label: '7. Release Gate' },
  ];

  const getStepClass = (i: number): string => {
    if (!isRunning && !hasResult) return '';
    if (isRunning) {
      if (isRunningStages4to7) {
        if (i <= 2) return 'done';
        if (i === 3) return 'active';
        return '';
      }
      return 'active';
    }
    // result is present
    if (i <= 2) return 'done'; // change detect, journey, test selection always done
    if (!autonomousResult) {
      const ranCount = Object.keys(testExecutionResults).length;
      if (ranCount > 0 && i === 3) {
        const anyFailed = Object.values(testExecutionResults).some(r => r.status === 'failed');
        return anyFailed ? 'blocked' : 'done';
      }
      return ''; // analyze-only: stages 4–7 not run
    }
    // autonomous run: all 7 stages ran
    if (i === 3) {
      const hasFailures = (autonomousResult.execution_results || []).some(r => r.status === 'failed');
      return hasFailures ? 'blocked' : 'done';
    }
    if (i === 4) {
      const cls = autonomousResult?.diagnosis_results?.[0]?.classification;
      return cls === 'PRODUCT_DEFECT' || cls === 'ENVIRONMENT_FAILURE' ? 'blocked' : 'done';
    }
    if (i === 5) {
      const h = autonomousResult?.healing_results?.[0];
      return h ? (h.status === 'HEALED_SUCCESSFULLY' ? 'done' : 'blocked') : 'done';
    }
    if (i === 6) return isGatePass ? 'done' : 'blocked';
    return 'done';
  };

  /* ── Render ───────────────────────────────────────────────────────────── */
  return (
    <div className="tg-console">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="tg-header">
        <div className="tg-header-left">
          <div className="tg-brand">
            <div className="tg-logo-shield"><Shield size={22} /></div>
            <div>
              <span className="tg-brand-title">TRAVELGUARD AI</span>
              <div style={{ fontSize: '0.72rem', color: 'var(--tg-text-dim)' }}>
                Autonomous Quality Engineering Platform
              </div>
            </div>
          </div>
          <div className="tg-badge-active">
            <span className="tg-badge-pulse" />
            <span>Live Gate Active</span>
          </div>
        </div>
        <div className="tg-header-actions">
          <button className="tg-sut-switch-btn" onClick={onSwitchToSut}>
            <span>✈️ Switch to SkyBook App</span>
            <ExternalLink size={14} />
          </button>
        </div>
      </header>

      {/* ── Controls ───────────────────────────────────────────────────── */}
      <section className="tg-controls-section">
        <div className="tg-controls-inner">

          {/* Primary CTA */}
          <div className="tg-primary-action">
            <div className="tg-primary-action-info">
              <GitBranch size={20} color="#10b981" />
              <div>
                <div className="tg-primary-action-title">Analyze My Local Changes</div>
                <div className="tg-primary-action-sub">
                  Reads your uncommitted git working tree and generates a full pre-commit quality report
                </div>
              </div>
            </div>
            <button className="tg-btn-analyze-local" disabled={isRunning} onClick={handleAnalyzeLocal}>
              {isRunning && selectedScenario === null
                ? <><RotateCcw size={16} className="spin-animate" /><span>Analyzing...</span></>
                : <><Zap size={16} /><span>Run Pre-Commit Check</span></>}
            </button>
          </div>

          {/* Demo Scenarios (secondary) */}
          <div className="tg-demo-row">
            <div className="tg-demo-label-row">
              <Sparkles size={13} color="var(--tg-text-dim)" />
              <span className="tg-demo-label-text">Try a Demo Scenario</span>
              <label className="tg-mock-toggle">
                <input type="checkbox" checked={mockLlm} onChange={e => setMockLlm(e.target.checked)} />
                <span>Mock LLM</span>
              </label>
            </div>
            <div className="tg-scenario-buttons">
              {[
                { key: 'booking-ui-drift',   icon: <Wrench size={13} color="#f59e0b" />,     label: 'A: UI Drift & Self-Healing' },
                { key: 'booking-api-defect', icon: <XCircle size={13} color="#f43f5e" />,    label: 'B: API Defect (Release Blocker)' },
                { key: 'environment-failure',icon: <AlertTriangle size={13} color="#a855f7" />, label: 'C: Environment Outage' },
                { key: 'scenario_d',         icon: <Sparkles size={13} color="#38bdf8" />,   label: 'D: Promo Code & Test Gen' },
              ].map(({ key, icon, label }) => (
                <button
                  key={key}
                  className={`tg-btn-scenario ${selectedScenario === key && hasResult ? 'active' : ''}`}
                  disabled={isRunning}
                  onClick={() => handleScenario(key)}
                >
                  {icon}<span>{label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Pipeline Stepper */}
          <div className="tg-stepper-container">
            {steps.map((step, i) => (
              <React.Fragment key={i}>
                <div className={`tg-step-pill ${getStepClass(i)}`}>
                  {step.icon}<span>{step.label}</span>
                </div>
                {i < steps.length - 1 && <ChevronRight className="tg-step-arrow" size={14} />}
              </React.Fragment>
            ))}
          </div>

          {/* Stepper helper line */}
          {!isRunning && !autonomousResult && intelligenceResult && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.45rem 0.25rem 0 0.25rem', fontSize: '0.76rem', color: 'var(--tg-text-dim)', flexWrap: 'wrap', gap: '0.6rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: 'var(--tg-emerald)', display: 'inline-block', boxShadow: '0 0 6px var(--tg-emerald)' }} />
                <span><strong style={{ color: 'var(--tg-text-muted)' }}>Pre-Commit Intelligence Ready:</strong> Stages 1–3 Complete (Impact Analysis & Test Selection).</span>
              </div>
              <button
                type="button"
                onClick={handleRunStages4to7}
                disabled={isRunning}
                style={{
                  background: 'rgba(56,189,248,0.15)',
                  border: '1px solid rgba(56,189,248,0.35)',
                  color: 'var(--tg-primary)',
                  borderRadius: '6px',
                  padding: '0.3rem 0.75rem',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  cursor: isRunning ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  transition: 'all 0.15s ease',
                }}
              >
                <Play size={12} fill="currentColor" />
                <span>Proceed to Stages 4–7 (Execution & Release Gate)</span>
              </button>
            </div>
          )}
        </div>
      </section>

      {/* ── Main Report Area ────────────────────────────────────────────── */}
      <main className="tg-main-content">

        {/* Error */}
        {errorMsg && (
          <div className="tg-error-box">{errorMsg}</div>
        )}

        {/* Running */}
        {isRunning && (
          <div className="tg-loading-box">
            <RotateCcw size={36} className="spin-animate" color="#38bdf8" />
            <h3>TravelGuard AI Running</h3>
            <p>{runStatusMsg}</p>
          </div>
        )}

        {/* ── Report ──────────────────────────────────────────────────── */}
        {!isRunning && hasResult && verdict && (
          <div className="tg-report">

            {/* ① Verdict Banner */}
            <div className={`tg-verdict-banner tg-verdict-${verdict.type}`}>
              <div className="tg-verdict-info">
                <div className="tg-verdict-icon-box">
                  {verdict.type === 'safe'
                    ? <CheckCircle2 size={26} />
                    : verdict.type === 'review'
                    ? <AlertCircle size={26} />
                    : <XCircle size={26} />}
                </div>
                <div className="tg-verdict-text">
                  <h2>{verdict.label}</h2>
                  <p>{verdict.sub}</p>
                </div>
              </div>
              <div className="tg-verdict-meta">
                {autonomousResult && <>
                  <div className="tg-meta-item">
                    <span className="tg-meta-item-label">Release Confidence</span>
                    <span className="tg-meta-item-value" style={{ color: isGatePass ? '#34d399' : '#fb7185' }}>
                      {Math.round((qr?.release_confidence || 0) * 100)}%
                    </span>
                  </div>
                  <div className="tg-meta-item">
                    <span className="tg-meta-item-label">Exit Code</span>
                    <span className="tg-meta-item-value" style={{ fontFamily: 'var(--tg-font-mono)' }}>
                      {autonomousResult.quality_gate_decision?.exit_code ?? 0}
                    </span>
                  </div>
                </>}
                {intelligenceResult && <>
                  <div className="tg-meta-item">
                    <span className="tg-meta-item-label">Risk Score</span>
                    <span className="tg-meta-item-value" style={{ color: getRiskColor(riskLevel) }}>
                      {riskScore !== undefined ? `${riskScore}/100` : '—'}
                    </span>
                  </div>
                  <div className="tg-meta-item">
                    <span className="tg-meta-item-label">Selected Tests</span>
                    <span className="tg-meta-item-value" style={{ color: 'var(--tg-cyan)' }}>
                      {selectedTests.length}
                    </span>
                  </div>
                </>}
              </div>

              {/* Next-Step Action Banner when pre-commit check (Stages 1-3) is done */}
              {!autonomousResult && intelligenceResult && (
                <div style={{
                  gridColumn: '1 / -1',
                  marginTop: '0.85rem',
                  paddingTop: '0.85rem',
                  borderTop: '1px solid rgba(255,255,255,0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '0.75rem',
                }}>
                  <div style={{ fontSize: '0.83rem', color: 'var(--tg-text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#38bdf8', boxShadow: '0 0 8px #38bdf8' }} />
                    <span>Run the recommended test suite and enforce the release gate before pushing code.</span>
                  </div>
                  <button
                    type="button"
                    onClick={handleRunStages4to7}
                    disabled={isRunning}
                    style={{
                      background: 'linear-gradient(135deg, #0284c7, #10b981)',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '8px',
                      padding: '0.55rem 1.25rem',
                      fontSize: '0.85rem',
                      fontWeight: 700,
                      cursor: isRunning ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      boxShadow: '0 0 16px rgba(2, 132, 199, 0.4)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <Play size={14} fill="currentColor" />
                    <span>Execute Tests & Enforce Release Gate (Stages 4–7)</span>
                  </button>
                </div>
              )}
            </div>

            {/* ② Risk Assessment + Changed Files */}
            <div className="tg-grid-2">
              {/* Risk Card */}
              <div className="tg-card">
                <div className="tg-card-header">
                  <span className="tg-card-title">
                    <TrendingUp size={16} color={getRiskColor(riskLevel)} />
                    Risk Assessment
                  </span>
                  <span className="tg-pill" style={{
                    background: getRiskBg(riskLevel),
                    color: getRiskColor(riskLevel),
                    border: `1px solid ${getRiskColor(riskLevel)}40`,
                  }}>
                    {riskLevel.toUpperCase() || '—'}
                  </span>
                </div>
                {riskScore !== undefined && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--tg-text-dim)', marginBottom: '0.3rem' }}>
                      <span>Risk Score</span>
                      <span style={{ fontWeight: 700, color: getRiskColor(riskLevel) }}>{riskScore}/100</span>
                    </div>
                    <div style={{ background: 'var(--tg-surface-card)', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                      <div style={{ width: `${riskScore}%`, height: '100%', background: getRiskColor(riskLevel), borderRadius: '4px', transition: 'width 0.8s ease' }} />
                    </div>
                  </div>
                )}
                <p style={{ fontSize: '0.85rem', color: 'var(--tg-text-muted)', margin: 0, lineHeight: 1.55 }}>
                  {riskReason}
                </p>
                {impact && (
                  <div style={{ fontSize: '0.78rem', color: 'var(--tg-text-dim)', display: 'flex', gap: '1rem', marginTop: '0.2rem' }}>
                    <span><strong>Type:</strong> {impact.change_type || '—'}</span>
                    {impact.is_behavioral !== undefined && (
                      <span><strong>Behavioral:</strong> {impact.is_behavioral ? 'Yes' : 'No'}</span>
                    )}
                  </div>
                )}
                {/* Risk Factor Breakdown Pills */}
                {impact?.risk?.factors && (
                  <div style={{ marginTop: '0.45rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', fontWeight: 700, color: 'var(--tg-text-dim)', letterSpacing: '0.04em' }}>
                      Score Factors:
                    </span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                      {impact.risk.factors.journey_criticality && (
                        <span className="tg-pill" style={{ background: 'rgba(139,92,246,0.15)', color: '#c084fc', border: '1px solid rgba(139,92,246,0.3)', textTransform: 'none' }}>
                          +{impact.risk.factors.journey_criticality.points}pts Criticality ({impact.risk.factors.journey_criticality.level})
                        </span>
                      )}
                      {impact.risk.factors.change_type && (
                        <span className="tg-pill" style={{ background: 'rgba(56,189,248,0.15)', color: '#38bdf8', border: '1px solid rgba(56,189,248,0.3)', textTransform: 'none' }}>
                          +{impact.risk.factors.change_type.points}pts {impact.risk.factors.change_type.type.toUpperCase()} Contract
                        </span>
                      )}
                      {impact.risk.factors.behavioral_impact && impact.risk.factors.behavioral_impact.points > 0 && (
                        <span className="tg-pill" style={{ background: 'rgba(245,158,11,0.15)', color: '#f59e0b', border: '1px solid rgba(245,158,11,0.3)', textTransform: 'none' }}>
                          +{impact.risk.factors.behavioral_impact.points}pts Behavioral
                        </span>
                      )}
                      {impact.risk.factors.diff_volume && (
                        <span className="tg-pill" style={{ background: 'rgba(148,163,184,0.12)', color: '#94a3b8', border: '1px solid rgba(148,163,184,0.25)', textTransform: 'none' }}>
                          {impact.risk.factors.diff_volume.lines_changed} lines
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Changed Files */}
              <div className="tg-card">
                <div className="tg-card-header">
                  <span className="tg-card-title">
                    <FileCode2 size={16} color="#06b6d4" />
                    Changed Files
                    {(intelligenceResult?.change_set?.files || intelligenceResult?.change_set?.changed_files || autonomousResult?.change_set?.files || autonomousResult?.change_set?.changed_files) &&
                      ` (${(intelligenceResult?.change_set?.files || intelligenceResult?.change_set?.changed_files || autonomousResult?.change_set?.files || autonomousResult?.change_set?.changed_files || []).length})`}
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                  {(intelligenceResult?.change_set?.files || intelligenceResult?.change_set?.changed_files || autonomousResult?.change_set?.files || autonomousResult?.change_set?.changed_files || []).map((f: any, i: number) => {
                    const filePath = f.path || f.file_path;
                    const isExpanded = !!expandedDiffs[filePath];
                    return (
                      <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', background: 'var(--tg-surface-card)', padding: '0.5rem 0.65rem', borderRadius: '6px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{
                              background: f.status === 'added' ? 'rgba(16,185,129,0.2)' : f.status === 'deleted' ? 'rgba(244,63,94,0.2)' : 'rgba(245,158,11,0.2)',
                              color:      f.status === 'added' ? '#34d399' : f.status === 'deleted' ? '#fb7185' : '#fbbf24',
                              padding: '0 0.35rem', borderRadius: '3px', fontWeight: 700,
                              fontFamily: 'var(--tg-font-mono)', fontSize: '0.7rem',
                            }}>
                              {f.status === 'added' ? 'A' : f.status === 'deleted' ? 'D' : 'M'}
                            </span>
                            <code style={{ color: 'var(--tg-cyan)', fontSize: '0.77rem' }}>{filePath}</code>
                          </div>
                          {f.diff && (
                            <button
                              type="button"
                              onClick={() => toggleDiff(filePath)}
                              style={{
                                background: isExpanded ? 'rgba(56,189,248,0.15)' : 'rgba(255,255,255,0.05)',
                                border: '1px solid ' + (isExpanded ? 'rgba(56,189,248,0.3)' : 'rgba(255,255,255,0.1)'),
                                color: isExpanded ? 'var(--tg-primary)' : 'var(--tg-text-dim)',
                                padding: '0.2rem 0.5rem',
                                borderRadius: '4px',
                                fontSize: '0.72rem',
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                              }}
                            >
                              {isExpanded ? 'Hide Diff' : 'View Diff'}
                            </button>
                          )}
                        </div>
                        {isExpanded && f.diff && (
                          <div className="tg-diff-viewer" style={{ maxHeight: '220px', overflowY: 'auto', marginTop: '0.3rem', fontSize: '0.73rem' }}>
                            {f.diff.split('\n').map((line: string, idx: number) => {
                              if (line.startsWith('+') && !line.startsWith('+++')) {
                                return <div key={idx} className="tg-diff-line-add">{line}</div>;
                              }
                              if (line.startsWith('-') && !line.startsWith('---')) {
                                return <div key={idx} className="tg-diff-line-del">{line}</div>;
                              }
                              return (
                                <div key={idx} style={{ padding: '0.12rem 0.5rem', color: 'var(--tg-text-dim)', fontFamily: 'var(--tg-font-mono)' }}>
                                  {line}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {!(intelligenceResult?.change_set?.files || intelligenceResult?.change_set?.changed_files || autonomousResult?.change_set?.files || autonomousResult?.change_set?.changed_files) && (
                    <p style={{ color: 'var(--tg-text-dim)', fontSize: '0.83rem', margin: 0 }}>File list not available for this run.</p>
                  )}
                </div>
              </div>
            </div>

            {/* ③ Business Journeys Impacted */}
            {impact?.affected_journeys && impact.affected_journeys.length > 0 && (
              <div className="tg-card">
                <div className="tg-card-header">
                  <span className="tg-card-title">
                    <Layers size={16} color="#8b5cf6" />
                    Business Journeys Impacted ({impact.affected_journeys.length})
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '0.75rem' }}>
                  {impact.affected_journeys.map((j: any, i: number) => (
                    <div key={i} style={{
                      background: 'var(--tg-surface-card)', padding: '0.75rem', borderRadius: '8px',
                      borderLeft: `3px solid ${getRiskColor(j.impact_level)}`,
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
                        <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>{j.journey_name}</span>
                        <span style={{ fontSize: '0.7rem', fontWeight: 600, color: getRiskColor(j.impact_level), textTransform: 'uppercase' }}>
                          {j.impact_level}
                        </span>
                      </div>
                      <p style={{ fontSize: '0.78rem', color: 'var(--tg-text-muted)', margin: 0, lineHeight: 1.4 }}>{j.capability}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ④ Test Recommendations */}
            {selectedTests.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                {/* Selected Tests Card */}
                <div className="tg-card">
                  <div className="tg-card-header" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                      <span className="tg-card-title">
                        <CheckCircle2 size={16} color="#10b981" />
                        Tests to Run ({filteredSelectedTests.length} of {selectedTests.length})
                      </span>
                      {/* Filter pills */}
                      <div style={{ display: 'flex', gap: '0.35rem' }}>
                        {[
                          { key: 'ALL', label: `All (${selectedTests.length})` },
                          { key: 'P0',  label: `P0 Critical (${p0Count})` },
                          { key: 'P1',  label: `P1 Regression (${p1Count})` },
                        ].map(f => (
                          <button
                            key={f.key}
                            type="button"
                            onClick={() => setPriorityFilter(f.key as any)}
                            style={{
                              background: priorityFilter === f.key ? 'rgba(56,189,248,0.2)' : 'rgba(255,255,255,0.04)',
                              color: priorityFilter === f.key ? 'var(--tg-primary)' : 'var(--tg-text-dim)',
                              border: '1px solid ' + (priorityFilter === f.key ? 'rgba(56,189,248,0.4)' : 'rgba(255,255,255,0.08)'),
                              borderRadius: '9999px',
                              padding: '0.2rem 0.6rem',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                              transition: 'all 0.15s ease',
                            }}
                          >
                            {f.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Suite Actions: Run in Console + Copy */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        onClick={handleRunAllTests}
                        disabled={isRunning || isRunningAllTests}
                        style={{
                          background: 'linear-gradient(135deg, #0284c7, #06b6d4)',
                          color: '#ffffff',
                          border: 'none',
                          borderRadius: '8px',
                          padding: '0.4rem 0.85rem',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          cursor: isRunning || isRunningAllTests ? 'not-allowed' : 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.45rem',
                          boxShadow: '0 0 12px rgba(6, 182, 212, 0.35)',
                          transition: 'all 0.15s ease',
                        }}
                        title="Run all selected tests sequentially in console"
                      >
                        {isRunningAllTests ? (
                          <><RotateCcw size={12} className="spin-animate" /><span>Running ({runningTestProgress})...</span></>
                        ) : (
                          <><Play size={12} fill="currentColor" /><span>Run Selected Tests</span></>
                        )}
                      </button>

                      <button
                        type="button"
                        onClick={copyAllCmds}
                        className="tg-btn-scenario"
                        style={{ padding: '0.35rem 0.75rem', fontSize: '0.76rem', gap: '0.45rem' }}
                        title="Copy consolidated Playwright CLI command to run all selected tests"
                      >
                        {copiedAll ? <><Check size={13} color="#10b981" /><span>Copied Test Suite!</span></> : <><Copy size={13} /><span>Copy All Test Commands</span></>}
                      </button>
                    </div>
                  </div>

                  {/* Test Cards Grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '0.75rem' }}>
                    {filteredSelectedTests.map((t: any, i: number) => {
                      const testKey = t.test_id || t.id || t.file || t.test_file || t.name;
                      const testFile = t.file || t.test_file || '';
                      const testId = t.test_id || t.id || '';
                      const execRes = testExecutionResults[testKey] || testExecutionResults[testFile] || testExecutionResults[testId];
                      const cmd = getRunCommand(testFile);
                      const isSingleRunning = runningSingleTestKey === testKey || runningSingleTestKey === testFile || runningSingleTestKey === testId;

                      return (
                        <div key={i} style={{
                          background: 'var(--tg-surface-card)',
                          padding: '0.85rem',
                          borderRadius: '8px',
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'space-between',
                          gap: '0.5rem',
                          border: execRes?.status === 'passed' ? '1px solid rgba(16,185,129,0.4)' : execRes?.status === 'failed' ? '1px solid rgba(244,63,94,0.4)' : '1px solid var(--tg-border)',
                          boxShadow: execRes?.status === 'passed' ? '0 0 12px rgba(16,185,129,0.1)' : execRes?.status === 'failed' ? '0 0 12px rgba(244,63,94,0.1)' : 'none',
                          transition: 'all 0.2s ease',
                        }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem', gap: '0.5rem', flexWrap: 'wrap' }}>
                              <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>{t.name || t.test_name}</span>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                {execRes?.status === 'passed' && (
                                  <span className="tg-pill" style={{ background: 'rgba(16,185,129,0.18)', color: '#34d399', border: '1px solid rgba(16,185,129,0.4)', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.7rem', padding: '0.15rem 0.5rem', fontWeight: 700 }}>
                                    <CheckCircle2 size={11} />
                                    <span>PASSED {execRes.duration_ms ? `(${(execRes.duration_ms / 1000).toFixed(1)}s)` : ''}</span>
                                  </span>
                                )}
                                {execRes?.status === 'failed' && (
                                  <span className="tg-pill" style={{ background: 'rgba(244,63,94,0.18)', color: '#fb7185', border: '1px solid rgba(244,63,94,0.4)', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.7rem', padding: '0.15rem 0.5rem', fontWeight: 700 }}>
                                    <XCircle size={11} />
                                    <span>FAILED</span>
                                  </span>
                                )}
                                {execRes?.status === 'running' && (
                                  <span className="tg-pill" style={{ background: 'rgba(56,189,248,0.18)', color: '#38bdf8', border: '1px solid rgba(56,189,248,0.4)', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.7rem', padding: '0.15rem 0.5rem', fontWeight: 700 }}>
                                    <RotateCcw size={11} className="spin-animate" />
                                    <span>RUNNING</span>
                                  </span>
                                )}
                                <span className={`tg-pill ${t.priority === 'P0' ? 'tg-pill-p0' : t.priority === 'P1' ? 'tg-pill-p1' : 'tg-pill-p2'}`}>
                                  {t.priority}
                                </span>
                              </div>
                            </div>
                            <code style={{ fontSize: '0.74rem', color: 'var(--tg-text-dim)' }}>{testFile}</code>
                            <p style={{ fontSize: '0.78rem', color: 'var(--tg-text-muted)', margin: '0.4rem 0 0 0', lineHeight: 1.45 }}>{t.reason}</p>
                            {execRes?.error && (
                              <div style={{ background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.25)', borderRadius: '5px', padding: '0.4rem 0.6rem', fontSize: '0.73rem', color: '#fca5a5', marginTop: '0.45rem', fontFamily: 'var(--tg-font-mono)', maxHeight: '110px', overflowY: 'auto' }}>
                                {execRes.error}
                              </div>
                            )}
                          </div>
                          {cmd && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(0,0,0,0.35)', borderRadius: '5px', padding: '0.35rem 0.55rem', marginTop: '0.25rem' }}>
                              <Terminal size={11} color="var(--tg-text-dim)" />
                              <code style={{ flex: 1, fontSize: '0.72rem', color: 'var(--tg-cyan)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{cmd}</code>
                              <button
                                type="button"
                                onClick={() => handleRunSingleTest(t)}
                                disabled={isRunning || isRunningAllTests || isSingleRunning}
                                style={{
                                  background: isSingleRunning ? 'rgba(56,189,248,0.25)' : 'rgba(56,189,248,0.12)',
                                  border: '1px solid rgba(56,189,248,0.35)',
                                  borderRadius: '4px',
                                  color: '#38bdf8',
                                  fontSize: '0.7rem',
                                  fontWeight: 700,
                                  padding: '0.2rem 0.55rem',
                                  cursor: isRunning || isRunningAllTests || isSingleRunning ? 'not-allowed' : 'pointer',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '0.3rem',
                                  whiteSpace: 'nowrap',
                                  transition: 'all 0.15s ease',
                                }}
                                title="Run this single test in console"
                              >
                                {isSingleRunning ? <RotateCcw size={10} className="spin-animate" /> : <Play size={10} fill="currentColor" />}
                                <span>{isSingleRunning ? 'Running' : 'Run'}</span>
                              </button>
                              <button onClick={() => copyCmd(cmd)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--tg-text-dim)', display: 'flex', padding: 0 }} title="Copy test command">
                                {copiedCmd === cmd ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Safely Skipped Tests Drawer */}
                <div className="tg-card" style={{ padding: '0.85rem 1.25rem' }}>
                  <div
                    onClick={() => setShowSkipped(!showSkipped)}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', userSelect: 'none' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <XCircle size={15} color="var(--tg-text-dim)" />
                      <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--tg-text-muted)' }}>
                        Safely Skipped Tests ({skippedTests.length})
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--tg-text-dim)' }}>
                        — Non-impacted test suites safely bypassed to optimize execution time
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--tg-text-dim)', fontSize: '0.75rem' }}>
                      <span>{showSkipped ? 'Hide' : 'Show'}</span>
                      {showSkipped ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </div>
                  </div>

                  {showSkipped && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '0.6rem', marginTop: '0.85rem', paddingTop: '0.85rem', borderTop: '1px solid var(--tg-border)' }}>
                      {skippedTests.length === 0 ? (
                        <p style={{ color: 'var(--tg-text-dim)', fontSize: '0.82rem', margin: 0 }}>All registered tests are relevant to this change.</p>
                      ) : (
                        skippedTests.map((t: any, i: number) => (
                          <div key={i} style={{ background: 'var(--tg-surface-card)', padding: '0.6rem 0.75rem', borderRadius: '6px', opacity: 0.8 }}>
                            <div style={{ fontWeight: 600, fontSize: '0.82rem' }}>{t.name || t.test_name}</div>
                            <code style={{ fontSize: '0.72rem', color: 'var(--tg-text-dim)' }}>{t.file || t.test_file}</code>
                            <p style={{ fontSize: '0.75rem', color: 'var(--tg-text-muted)', margin: '0.25rem 0 0 0' }}>{t.reason}</p>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ⑤ AI Failure Diagnosis (autonomous runs) */}
            {autonomousResult && autonomousResult.diagnosis_results && autonomousResult.diagnosis_results.length > 0 && (
              <div className="tg-card">
                <div className="tg-card-header">
                  <span className="tg-card-title">
                    <AlertTriangle size={16} color="#38bdf8" />
                    AI Failure Diagnosis
                  </span>
                  <span className={`tg-pill ${
                    autonomousResult.diagnosis_results[0].classification === 'TEST_DRIFT' ? 'tg-pill-drift' :
                    autonomousResult.diagnosis_results[0].classification === 'PRODUCT_DEFECT' ? 'tg-pill-defect' : 'tg-pill-env'
                  }`}>
                    {autonomousResult.diagnosis_results[0].classification}
                  </span>
                </div>
                {autonomousResult.diagnosis_results.map((d, i) => (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <div style={{ fontSize: '0.83rem', color: 'var(--tg-text-muted)' }}>
                      <strong>{d.test_id}</strong> — Confidence:{' '}
                      <span style={{ color: 'var(--tg-cyan)', fontWeight: 700 }}>{Math.round(d.confidence * 100)}%</span>
                    </div>
                    <p style={{ fontSize: '0.84rem', lineHeight: 1.55, margin: 0 }}>{d.summary}</p>
                    <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--tg-border)', padding: '0.5rem 0.75rem', borderRadius: '6px', fontSize: '0.8rem' }}>
                      <strong>Recommended Action:</strong>{' '}
                      <span style={{ color: d.classification === 'TEST_DRIFT' ? 'var(--tg-emerald)' : 'var(--tg-rose)' }}>
                        {d.recommended_action}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ⑥ Self-Healing Inspector (inline) */}
            {autonomousResult && autonomousResult.healing_results && autonomousResult.healing_results.length > 0 && (
              <div className="tg-card">
                <div className="tg-card-header">
                  <span className="tg-card-title">
                    <Wrench size={16} color="#f59e0b" />
                    Self-Healing Inspector
                  </span>
                </div>
                {autonomousResult.healing_results.map((h, i) => (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div><strong>Test:</strong> <code>{h.test_id}</code></div>
                      <span className={`tg-pill ${h.status === 'HEALED_SUCCESSFULLY' ? 'tg-badge-active' : 'tg-pill-defect'}`}>
                        {h.status}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.84rem', color: 'var(--tg-text-muted)', margin: 0 }}>{h.reason}</p>
                    {h.proposal && (
                      <div className="tg-diff-viewer">
                        <div style={{ fontSize: '0.75rem', color: 'var(--tg-text-dim)', fontWeight: 700, marginBottom: '0.25rem' }}>
                          LOCATOR MUTATION DIFF:
                        </div>
                        <div className="tg-diff-line-del">- {h.proposal.original_locator}</div>
                        <div className="tg-diff-line-add">+ {h.proposal.repaired_locator}</div>
                      </div>
                    )}
                    {h.status === 'HEALED_SUCCESSFULLY' && (
                      <div style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', padding: '0.6rem 0.75rem', borderRadius: '6px', fontSize: '0.8rem', color: '#6ee7b7' }}>
                        ✓ Backup created · Patch applied · Re-validation passed
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* ⑦ Release Confidence Arithmetic (autonomous runs) */}
            {autonomousResult?.release_confidence_breakdown && (
              <div className="tg-card">
                <div className="tg-card-header">
                  <span className="tg-card-title">
                    <Shield size={16} color="#10b981" />
                    Release Confidence Arithmetic
                  </span>
                  <span style={{ fontFamily: 'var(--tg-font-mono)', fontSize: '0.9rem', color: isGatePass ? '#34d399' : '#fb7185', fontWeight: 800 }}>
                    {Math.round((qr?.release_confidence || 0) * 100)}%
                  </span>
                </div>
                <p style={{ fontSize: '0.82rem', color: 'var(--tg-text-muted)', lineHeight: 1.55, margin: 0 }}>
                  {autonomousResult.release_confidence_breakdown.formula_explanation || qr?.confidence_explanation}
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '0.5rem', fontSize: '0.78rem' }}>
                  {[
                    { label: 'Base Pass Score', value: autonomousResult.release_confidence_breakdown.base_pass_score ?? 1.0, color: '' },
                    { label: 'Healed Discount', value: `-${((autonomousResult.release_confidence_breakdown.healed_discount ?? 0) * 100).toFixed(0)}%`, color: 'var(--tg-amber)' },
                    { label: 'Tests Run',        value: qr?.selected_tests ?? 0, color: '' },
                    { label: 'Passed',           value: qr?.passed ?? 0, color: 'var(--tg-emerald)' },
                    { label: 'Failed',           value: qr?.failed ?? 0, color: (qr?.failed ?? 0) > 0 ? 'var(--tg-rose)' : '' },
                    { label: 'Self-Healed',      value: qr?.healed ?? 0, color: 'var(--tg-amber)' },
                  ].map((m, i) => (
                    <div key={i} style={{ background: 'var(--tg-surface-card)', padding: '0.5rem 0.75rem', borderRadius: '6px' }}>
                      <div style={{ color: 'var(--tg-text-dim)', marginBottom: '0.2rem' }}>{m.label}</div>
                      <div style={{ fontWeight: 700, fontSize: '0.95rem', color: m.color || 'inherit' }}>{m.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ⑧ Coverage Gap Analysis + AI Generated Test */}
            {intelligenceResult?.coverage && (
              <div className="tg-card">
                <div className="tg-card-header">
                  <span className="tg-card-title">
                    <Activity size={16} color="#8b5cf6" />
                    Coverage Gap Analysis
                  </span>
                  <span className={`tg-pill ${intelligenceResult.coverage.status === 'SUFFICIENT' ? 'tg-pill-drift' : 'tg-pill-defect'}`}>
                    {intelligenceResult.coverage.status}
                  </span>
                </div>
                <p style={{ fontSize: '0.84rem', color: 'var(--tg-text-muted)', margin: 0 }}>
                  {intelligenceResult.coverage.reason}
                </p>
                {intelligenceResult.coverage.missing_scenarios && intelligenceResult.coverage.missing_scenarios.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                    <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--tg-text-dim)' }}>Missing Scenarios:</div>
                    {intelligenceResult.coverage.missing_scenarios.map((s: string, i: number) => (
                      <div key={i} style={{ fontSize: '0.8rem', color: '#fca5a5', padding: '0.2rem 0.5rem', background: 'rgba(244,63,94,0.08)', borderRadius: '4px' }}>
                        — {s}
                      </div>
                    ))}
                  </div>
                )}

                {/* Generated Test */}
                {intelligenceResult.generated_test && (
                  <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                    <div className="tg-card-header" style={{ padding: '0.65rem 0 0 0', marginTop: '0.25rem', borderTop: '1px solid rgba(255,255,255,0.05)', borderBottom: 'none' }}>
                      <span className="tg-card-title">
                        <Sparkles size={15} color="#38bdf8" />
                        AI-Generated Playwright Test
                      </span>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        <span className="tg-badge-active" style={{ fontSize: '0.72rem' }}>
                          {intelligenceResult.generated_test.validation_status}
                        </span>
                        <button onClick={copyCode} className="tg-btn-scenario" style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}>
                          {copiedCode ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                          <span>{copiedCode ? 'Copied!' : 'Copy'}</span>
                        </button>
                      </div>
                    </div>
                    <code style={{ fontSize: '0.77rem', color: 'var(--tg-text-dim)' }}>
                      {intelligenceResult.generated_test.file_path}
                    </code>
                    <div className="tg-code-block">{intelligenceResult.generated_test.code}</div>
                  </div>
                )}
              </div>
            )}

            {/* ⑨ Analysis Meta Footer */}
            {impact && (
              <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.78rem', color: 'var(--tg-text-dim)', paddingBottom: '0.5rem' }}>
                <span>🎯 Analysis Confidence: <strong style={{ color: 'var(--tg-text-muted)' }}>
                  {impact.confidence ? `${Math.round(impact.confidence * 100)}%` : '—'}
                </strong></span>
                {impact.fallback_used && <span style={{ color: 'var(--tg-amber)' }}>⚡ Automated fallback engaged</span>}
              </div>
            )}
          </div>
        )}

        {/* Empty State */}
        {!isRunning && !hasResult && !errorMsg && (
          <div className="tg-empty-state">
            <Shield size={52} color="#06b6d4" style={{ marginBottom: '1.25rem' }} />
            <h3>TravelGuard AI Ready</h3>
            <p>
              Click <strong>Run Pre-Commit Check</strong> above to analyze your uncommitted local changes —
              get risk assessment, journey impact, prioritized test recommendations, coverage gap detection,
              and AI-generated Playwright tests in one report.
            </p>
            <button className="tg-btn-analyze-local" style={{ margin: '0 auto' }} onClick={handleAnalyzeLocal}>
              <Zap size={16} /><span>Run Pre-Commit Check</span>
            </button>
          </div>
        )}

      </main>
    </div>
  );
};
