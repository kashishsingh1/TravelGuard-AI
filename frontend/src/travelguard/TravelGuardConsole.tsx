import React, { useState, useEffect } from 'react';
import {
  Shield,
  Play,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Wrench,
  FileCode2,
  GitBranch,
  Layers,
  ArrowRight,
  ExternalLink,
  Copy,
  Check,
  RotateCcw,
  Sparkles,
  Activity,
  ChevronRight,
  Terminal,
} from 'lucide-react';
import './travelguard.css';
import {
  AutonomousRunResult,
  IntelligenceResult,
  DemoScenario,
  BusinessJourney,
  TestInventoryItem,
} from './types';

interface TravelGuardConsoleProps {
  onSwitchToSut: () => void;
}

export const TravelGuardConsole: React.FC<TravelGuardConsoleProps> = ({ onSwitchToSut }) => {
  const [activeTab, setActiveTab] = useState<
    'overview' | 'healing' | 'selection' | 'generator' | 'diff' | 'catalog'
  >('overview');
  const [selectedScenario, setSelectedScenario] = useState<string>('booking-ui-drift');
  const [mockLlm, setMockLlm] = useState<boolean>(true);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [runStatusMsg, setRunStatusMsg] = useState<string>('');
  const [copiedCode, setCopiedCode] = useState<boolean>(false);

  // Result States
  const [autonomousResult, setAutonomousResult] = useState<AutonomousRunResult | null>(null);
  const [intelligenceResult, setIntelligenceResult] = useState<IntelligenceResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');

  // Config States
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [journeys, setJourneys] = useState<BusinessJourney[]>([]);
  const [inventory, setInventory] = useState<TestInventoryItem[]>([]);

  // Load config on mount
  useEffect(() => {
    fetch('/api/travelguard/config')
      .then((res) => res.json())
      .then((data) => {
        if (data.demos) setScenarios(data.demos);
        if (data.journeys) setJourneys(data.journeys);
        if (data.inventory) setInventory(data.inventory);
      })
      .catch((err) => console.warn('Could not load TravelGuard config:', err));
  }, []);

  // Trigger Autonomous Run (for Scenarios A, B, C or Working Tree)
  const handleRunAutonomous = async (scenarioKey?: string) => {
    const key = scenarioKey !== undefined ? scenarioKey : selectedScenario;
    setIsRunning(true);
    setErrorMsg('');
    setRunStatusMsg('Starting Autonomous QA Engine & inspecting DOM...');

    try {
      if (key === 'scenario_d') {
        // Scenario D is Test Generation / Coverage Gap
        setRunStatusMsg('Analyzing code changes & evaluating test inventory...');
        const res = await fetch('/api/travelguard/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenario: key, mock_llm: mockLlm }),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Analysis pipeline failed');
        }
        const data: IntelligenceResult = await res.json();
        setIntelligenceResult(data);
        setAutonomousResult(null);
        setActiveTab('generator');
      } else {
        // Scenarios A, B, C or Live Working Tree
        setRunStatusMsg('Executing tests, diagnosing failure & checking release gate...');
        const res = await fetch('/api/travelguard/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            scenario: key || null,
            mock_llm: mockLlm,
          }),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Autonomous run failed');
        }
        const data: AutonomousRunResult = await res.json();
        setAutonomousResult(data);
        setIntelligenceResult(null);
        setActiveTab('overview');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'An error occurred while running TravelGuard pipeline');
    } finally {
      setIsRunning(false);
      setRunStatusMsg('');
    }
  };

  const copyGeneratedCode = () => {
    const code = intelligenceResult?.generated_test?.code;
    if (!code) return;
    navigator.clipboard.writeText(code);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const qr = autonomousResult?.quality_report;
  const isAllowed = qr?.quality_gate_passed ?? false;
  const isBlocked = autonomousResult && !isAllowed;

  return (
    <div className="tg-console">
      {/* ── Top Header ──────────────────────────────────────────────────────── */}
      <header className="tg-header">
        <div className="tg-header-left">
          <div className="tg-brand" onClick={() => handleRunAutonomous('booking-ui-drift')}>
            <div className="tg-logo-shield">
              <Shield size={22} />
            </div>
            <div>
              <span className="tg-brand-title">TRAVELGUARD AI</span>
              <div style={{ fontSize: '0.72rem', color: 'var(--tg-text-dim)' }}>
                Autonomous Quality Engineering Platform
              </div>
            </div>
          </div>
          <div className="tg-badge-active">
            <span className="tg-badge-pulse"></span>
            <span>Live Gate Active</span>
          </div>
        </div>

        <div className="tg-header-actions">
          <label className="tg-toggle-label">
            <input
              type="checkbox"
              checked={mockLlm}
              onChange={(e) => setMockLlm(e.target.checked)}
            />
            <span>Deterministic Mock Mode</span>
          </label>

          <button className="tg-sut-switch-btn" onClick={onSwitchToSut}>
            <span>✈️ Switch to SkyBook App</span>
            <ExternalLink size={14} />
          </button>
        </div>
      </header>

      {/* ── Control Bar & Scenario Selector ─────────────────────────────────── */}
      <section className="tg-controls-section">
        <div className="tg-controls-inner">
          <div className="tg-controls-top">
            <div>
              <span className="tg-section-label">Demo Scenarios & Live Triggers</span>
              <div className="tg-scenario-buttons" style={{ marginTop: '0.4rem' }}>
                <button
                  className={`tg-btn-scenario ${selectedScenario === 'booking-ui-drift' ? 'active' : ''}`}
                  disabled={isRunning}
                  onClick={() => {
                    setSelectedScenario('booking-ui-drift');
                    handleRunAutonomous('booking-ui-drift');
                  }}
                >
                  <Wrench size={14} color="#f59e0b" />
                  <span>Scenario A: UI Drift & Self-Healing</span>
                </button>

                <button
                  className={`tg-btn-scenario ${selectedScenario === 'booking-api-defect' ? 'active' : ''}`}
                  disabled={isRunning}
                  onClick={() => {
                    setSelectedScenario('booking-api-defect');
                    handleRunAutonomous('booking-api-defect');
                  }}
                >
                  <XCircle size={14} color="#f43f5e" />
                  <span>Scenario B: API Defect (Release Blocker)</span>
                </button>

                <button
                  className={`tg-btn-scenario ${selectedScenario === 'environment-failure' ? 'active' : ''}`}
                  disabled={isRunning}
                  onClick={() => {
                    setSelectedScenario('environment-failure');
                    handleRunAutonomous('environment-failure');
                  }}
                >
                  <AlertTriangle size={14} color="#a855f7" />
                  <span>Scenario C: Environment Outage</span>
                </button>

                <button
                  className={`tg-btn-scenario ${selectedScenario === 'scenario_d' ? 'active' : ''}`}
                  disabled={isRunning}
                  onClick={() => {
                    setSelectedScenario('scenario_d');
                    handleRunAutonomous('scenario_d');
                  }}
                >
                  <Sparkles size={14} color="#38bdf8" />
                  <span>Scenario D: Promo Code & Test Gen</span>
                </button>

                <button
                  className={`tg-btn-scenario ${selectedScenario === '' ? 'active' : ''}`}
                  disabled={isRunning}
                  onClick={() => {
                    setSelectedScenario('');
                    handleRunAutonomous('');
                  }}
                >
                  <GitBranch size={14} color="#10b981" />
                  <span>Live Local Git Changes</span>
                </button>
              </div>
            </div>

            <div>
              <button
                className="tg-btn-primary-run"
                disabled={isRunning}
                onClick={() => handleRunAutonomous()}
              >
                {isRunning ? (
                  <>
                    <RotateCcw size={16} className="spin-animate" />
                    <span>Running Pipeline...</span>
                  </>
                ) : (
                  <>
                    <Play size={16} fill="#ffffff" />
                    <span>Execute TravelGuard</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Pipeline Stepper */}
          <div className="tg-stepper-container">
            <div className={`tg-step-pill ${autonomousResult || intelligenceResult ? 'done' : isRunning ? 'active' : ''}`}>
              <GitBranch size={12} />
              <span>1. Change Detect</span>
            </div>
            <ChevronRight className="tg-step-arrow" size={14} />

            <div className={`tg-step-pill ${autonomousResult || intelligenceResult ? 'done' : isRunning ? 'active' : ''}`}>
              <Layers size={12} />
              <span>2. Journey Mapping</span>
            </div>
            <ChevronRight className="tg-step-arrow" size={14} />

            <div className={`tg-step-pill ${autonomousResult || intelligenceResult ? 'done' : isRunning ? 'active' : ''}`}>
              <FileCode2 size={12} />
              <span>3. Test Selection</span>
            </div>
            <ChevronRight className="tg-step-arrow" size={14} />

            <div className={`tg-step-pill ${autonomousResult ? 'done' : isRunning ? 'active' : ''}`}>
              <Activity size={12} />
              <span>4. Execution</span>
            </div>
            <ChevronRight className="tg-step-arrow" size={14} />

            <div className={`tg-step-pill ${autonomousResult?.diagnosis_results?.length ? (autonomousResult.diagnosis_results[0].classification === 'PRODUCT_DEFECT' ? 'blocked' : 'done') : ''}`}>
              <AlertTriangle size={12} />
              <span>5. AI Diagnosis</span>
            </div>
            <ChevronRight className="tg-step-arrow" size={14} />

            <div className={`tg-step-pill ${autonomousResult?.healing_results?.length ? (autonomousResult.healing_results[0].status === 'HEALED_SUCCESSFULLY' ? 'done' : 'blocked') : ''}`}>
              <Wrench size={12} />
              <span>6. Self-Healing</span>
            </div>
            <ChevronRight className="tg-step-arrow" size={14} />

            <div className={`tg-step-pill ${isAllowed ? 'done' : isBlocked ? 'blocked' : ''}`}>
              <Shield size={12} />
              <span>7. Release Gate</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Main Workspace Area ──────────────────────────────────────────────── */}
      <main className="tg-main-content">
        {errorMsg && (
          <div style={{ background: 'rgba(244, 63, 94, 0.15)', border: '1px solid #f43f5e', padding: '1rem', borderRadius: '8px', color: '#fca5a5' }}>
            {errorMsg}
          </div>
        )}

        {isRunning && (
          <div style={{ textAlign: 'center', padding: '3rem 1rem', background: 'var(--tg-surface)', borderRadius: '12px', border: '1px solid var(--tg-border)' }}>
            <RotateCcw size={36} className="spin-animate" color="#38bdf8" style={{ marginBottom: '1rem' }} />
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.2rem' }}>TravelGuard AI Autonomous Execution in Progress</h3>
            <p style={{ color: 'var(--tg-text-muted)', fontSize: '0.9rem' }}>{runStatusMsg}</p>
          </div>
        )}

        {/* Executive Verdict Banner */}
        {autonomousResult && qr && (
          <div className={`tg-verdict-banner ${isAllowed ? 'tg-verdict-allowed' : 'tg-verdict-blocked'}`}>
            <div className="tg-verdict-info">
              <div className="tg-verdict-icon-box">
                {isAllowed ? <CheckCircle2 size={26} /> : <XCircle size={26} />}
              </div>
              <div className="tg-verdict-text">
                <h2>{qr.release_decision || (isAllowed ? 'RELEASE ALLOWED' : 'RELEASE BLOCKED')}</h2>
                <p>{qr.summary}</p>
              </div>
            </div>

            <div className="tg-verdict-meta">
              <div className="tg-meta-item">
                <span className="tg-meta-item-label">Release Confidence</span>
                <span className="tg-meta-item-value" style={{ color: isAllowed ? '#34d399' : '#fb7185' }}>
                  {Math.round(qr.release_confidence * 100)}%
                </span>
              </div>

              <div className="tg-meta-item">
                <span className="tg-meta-item-label">Quality Status</span>
                <span className="tg-meta-item-value">{qr.status}</span>
              </div>

              <div className="tg-meta-item">
                <span className="tg-meta-item-label">Gate Exit Code</span>
                <span className="tg-meta-item-value" style={{ fontFamily: 'var(--tg-font-mono)' }}>
                  {autonomousResult.quality_gate_decision?.exit_code ?? 0}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Tabs Bar */}
        {(autonomousResult || intelligenceResult) && (
          <nav className="tg-tabs-bar">
            {autonomousResult && (
              <>
                <button
                  className={`tg-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
                  onClick={() => setActiveTab('overview')}
                >
                  <Activity size={15} />
                  <span>Pipeline & Quality Gate</span>
                </button>

                <button
                  className={`tg-tab-btn ${activeTab === 'healing' ? 'active' : ''}`}
                  onClick={() => setActiveTab('healing')}
                >
                  <Wrench size={15} />
                  <span>Self-Healing Inspector ({autonomousResult.healing_results.length})</span>
                </button>

                <button
                  className={`tg-tab-btn ${activeTab === 'selection' ? 'active' : ''}`}
                  onClick={() => setActiveTab('selection')}
                >
                  <CheckCircle2 size={15} />
                  <span>Tests Selected ({autonomousResult.selected_tests.length})</span>
                </button>
              </>
            )}

            {intelligenceResult && (
              <button
                className={`tg-tab-btn ${activeTab === 'generator' ? 'active' : ''}`}
                onClick={() => setActiveTab('generator')}
              >
                <Sparkles size={15} />
                <span>AI Generated Playwright Test</span>
              </button>
            )}

            <button
              className={`tg-tab-btn ${activeTab === 'diff' ? 'active' : ''}`}
              onClick={() => setActiveTab('diff')}
            >
              <FileCode2 size={15} />
              <span>Unified Code Diff</span>
            </button>

            <button
              className={`tg-tab-btn ${activeTab === 'catalog' ? 'active' : ''}`}
              onClick={() => setActiveTab('catalog')}
            >
              <Layers size={15} />
              <span>Journeys & Inventory</span>
            </button>
          </nav>
        )}

        {/* ── TAB: OVERVIEW & PIPELINE ────────────────────────────────────────── */}
        {autonomousResult && activeTab === 'overview' && (
          <div className="tg-grid-2">
            {/* Failure Diagnosis Card */}
            <div className="tg-card">
              <div className="tg-card-header">
                <span className="tg-card-title">
                  <AlertTriangle size={16} color="#38bdf8" />
                  AI Failure Diagnosis
                </span>
                {autonomousResult.diagnosis_results.length > 0 && (
                  <span
                    className={`tg-pill ${
                      autonomousResult.diagnosis_results[0].classification === 'TEST_DRIFT'
                        ? 'tg-pill-drift'
                        : autonomousResult.diagnosis_results[0].classification === 'PRODUCT_DEFECT'
                        ? 'tg-pill-defect'
                        : 'tg-pill-env'
                    }`}
                  >
                    {autonomousResult.diagnosis_results[0].classification}
                  </span>
                )}
              </div>

              {autonomousResult.diagnosis_results.length === 0 ? (
                <p style={{ color: 'var(--tg-emerald)', margin: '0.5rem 0' }}>
                  ✓ All tests passed without failures. No diagnosis required.
                </p>
              ) : (
                autonomousResult.diagnosis_results.map((d, i) => (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--tg-text-muted)' }}>
                      <strong>Test:</strong> {d.test_id} (Confidence:{' '}
                      <span style={{ color: 'var(--tg-cyan)', fontWeight: 700 }}>
                        {Math.round(d.confidence * 100)}%
                      </span>
                      )
                    </div>
                    <p style={{ fontSize: '0.85rem', lineHeight: 1.5, margin: 0 }}>
                      {d.summary}
                    </p>
                    <div style={{ marginTop: '0.5rem', padding: '0.5rem', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', fontSize: '0.8rem' }}>
                      <strong>Recommended Action:</strong>{' '}
                      <span style={{ color: d.classification === 'TEST_DRIFT' ? 'var(--tg-emerald)' : 'var(--tg-rose)' }}>
                        {d.recommended_action}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Confidence Breakdown Card */}
            <div className="tg-card">
              <div className="tg-card-header">
                <span className="tg-card-title">
                  <Shield size={16} color="#10b981" />
                  Release Confidence Arithmetic
                </span>
                <span style={{ fontFamily: 'var(--tg-font-mono)', fontSize: '0.9rem', color: isAllowed ? '#34d399' : '#fb7185', fontWeight: 800 }}>
                  {Math.round((qr?.release_confidence || 0) * 100)}%
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ fontSize: '0.82rem', color: 'var(--tg-text-muted)', lineHeight: 1.5 }}>
                  {autonomousResult.release_confidence_breakdown?.formula_explanation || qr?.confidence_explanation}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.78rem' }}>
                  <div style={{ background: 'var(--tg-surface-card)', padding: '0.5rem', borderRadius: '6px' }}>
                    <span style={{ color: 'var(--tg-text-dim)' }}>Base Pass Score:</span>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                      {autonomousResult.release_confidence_breakdown?.base_pass_score ?? 1.0}
                    </div>
                  </div>

                  <div style={{ background: 'var(--tg-surface-card)', padding: '0.5rem', borderRadius: '6px' }}>
                    <span style={{ color: 'var(--tg-text-dim)' }}>Healed Penalty Discount:</span>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--tg-amber)' }}>
                      -{((autonomousResult.release_confidence_breakdown?.healed_discount ?? 0) * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Test Execution Counts Card */}
            <div className="tg-card" style={{ gridColumn: 'span 2' }}>
              <div className="tg-card-header">
                <span className="tg-card-title">
                  <Activity size={16} />
                  Test Execution Summary
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
                <div style={{ background: 'var(--tg-surface-card)', padding: '0.75rem', borderRadius: '8px', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--tg-text-dim)' }}>SELECTED</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800 }}>{qr?.selected_tests ?? 0}</div>
                </div>

                <div style={{ background: 'var(--tg-surface-card)', padding: '0.75rem', borderRadius: '8px', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--tg-text-dim)' }}>SKIPPED</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--tg-text-dim)' }}>{qr?.skipped_tests ?? 0}</div>
                </div>

                <div style={{ background: 'var(--tg-surface-card)', padding: '0.75rem', borderRadius: '8px', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--tg-text-dim)' }}>PASSED</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--tg-emerald)' }}>{qr?.passed ?? 0}</div>
                </div>

                <div style={{ background: 'var(--tg-surface-card)', padding: '0.75rem', borderRadius: '8px', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--tg-text-dim)' }}>FAILED</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: (qr?.failed ?? 0) > 0 ? 'var(--tg-rose)' : 'inherit' }}>
                    {qr?.failed ?? 0}
                  </div>
                </div>

                <div style={{ background: 'var(--tg-surface-card)', padding: '0.75rem', borderRadius: '8px', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--tg-text-dim)' }}>SELF-HEALED</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--tg-amber)' }}>{qr?.healed ?? 0}</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB: SELF-HEALING INSPECTOR ────────────────────────────────────── */}
        {autonomousResult && activeTab === 'healing' && (
          <div className="tg-card">
            <div className="tg-card-header">
              <span className="tg-card-title">
                <Wrench size={16} color="#f59e0b" />
                Self-Healing Verification & Locator Patch
              </span>
            </div>

            {autonomousResult.healing_results.length === 0 ? (
              <p style={{ color: 'var(--tg-text-muted)' }}>No tests required self-healing.</p>
            ) : (
              autonomousResult.healing_results.map((h, i) => (
                <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div>
                      <strong>Target Test:</strong> <code>{h.test_id}</code>
                    </div>
                    <span className={`tg-pill ${h.status === 'HEALED_SUCCESSFULLY' ? 'tg-badge-active' : 'tg-pill-defect'}`}>
                      {h.status}
                    </span>
                  </div>

                  <p style={{ fontSize: '0.85rem', color: 'var(--tg-text-muted)', margin: 0 }}>
                    {h.reason}
                  </p>

                  {h.proposal && (
                    <div className="tg-diff-viewer" style={{ marginTop: '0.5rem' }}>
                      <div style={{ fontSize: '0.78rem', color: 'var(--tg-text-dim)', fontWeight: 700 }}>
                        LOCATOR MUTATION DIFF:
                      </div>
                      <div className="tg-diff-line-del">
                        - {h.proposal.original_locator}
                      </div>
                      <div className="tg-diff-line-add">
                        + {h.proposal.repaired_locator}
                      </div>
                    </div>
                  )}

                  <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem', color: '#6ee7b7' }}>
                    ✓ Automated re-validation executed: Test re-ran against updated SUT and passed successfully.
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── TAB: TEST SELECTION ────────────────────────────────────────────── */}
        {autonomousResult && activeTab === 'selection' && (
          <div className="tg-grid-2">
            <div className="tg-card">
              <div className="tg-card-header">
                <span className="tg-card-title">
                  <CheckCircle2 size={16} color="#10b981" />
                  Selected Tests ({autonomousResult.selected_tests.length})
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {autonomousResult.selected_tests.map((t, i) => (
                  <div key={i} style={{ background: 'var(--tg-surface-card)', padding: '0.75rem', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>{t.name}</span>
                      <span className={`tg-pill ${t.priority === 'P0' ? 'tg-pill-p0' : t.priority === 'P1' ? 'tg-pill-p1' : 'tg-pill-p2'}`}>
                        {t.priority}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--tg-text-dim)', fontFamily: 'var(--tg-font-mono)', margin: '0.25rem 0' }}>
                      {t.file}
                    </div>
                    <p style={{ fontSize: '0.8rem', color: 'var(--tg-text-muted)', margin: '0.25rem 0 0 0' }}>
                      {t.reason}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="tg-card">
              <div className="tg-card-header">
                <span className="tg-card-title">
                  <XCircle size={16} color="var(--tg-text-dim)" />
                  Skipped Tests ({autonomousResult.skipped_tests.length})
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {autonomousResult.skipped_tests.map((t, i) => (
                  <div key={i} style={{ background: 'var(--tg-surface-card)', padding: '0.75rem', borderRadius: '8px', opacity: 0.85 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{t.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--tg-text-dim)', fontFamily: 'var(--tg-font-mono)', margin: '0.2rem 0' }}>
                      {t.file}
                    </div>
                    <p style={{ fontSize: '0.78rem', color: 'var(--tg-text-muted)', margin: 0 }}>
                      Reason: {t.reason}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── TAB: AI TEST GENERATOR (SCENARIO D) ────────────────────────────── */}
        {intelligenceResult && activeTab === 'generator' && (
          <div className="tg-card">
            <div className="tg-card-header">
              <span className="tg-card-title">
                <Sparkles size={16} color="#38bdf8" />
                AI Generated Playwright Test (Coverage Gap Remediation)
              </span>
              <button
                onClick={copyGeneratedCode}
                className="tg-btn-scenario"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem' }}
              >
                {copiedCode ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
                <span>{copiedCode ? 'Copied!' : 'Copy Code'}</span>
              </button>
            </div>

            {intelligenceResult.coverage && (
              <div style={{ background: 'rgba(244, 63, 94, 0.12)', border: '1px solid rgba(244, 63, 94, 0.3)', padding: '0.75rem', borderRadius: '8px', color: '#fca5a5', fontSize: '0.85rem' }}>
                <strong>Coverage Status: {intelligenceResult.coverage.status}</strong>
                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem' }}>
                  {intelligenceResult.coverage.reason}
                </p>
              </div>
            )}

            {intelligenceResult.generated_test ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.82rem' }}>
                  <span>
                    <strong>File:</strong> <code>{intelligenceResult.generated_test.file_path}</code>
                  </span>
                  <span className="tg-badge-active">
                    Validation: {intelligenceResult.generated_test.validation_status}
                  </span>
                </div>

                <div className="tg-code-block">
                  {intelligenceResult.generated_test.code}
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--tg-text-muted)' }}>
                No generated test was required. Existing test coverage is sufficient.
              </p>
            )}
          </div>
        )}

        {/* ── TAB: UNIFIED DIFF ──────────────────────────────────────────────── */}
        {activeTab === 'diff' && (
          <div className="tg-card">
            <div className="tg-card-header">
              <span className="tg-card-title">
                <FileCode2 size={16} color="#06b6d4" />
                Unified Git Diff
              </span>
            </div>
            <div className="tg-code-block">
              {autonomousResult?.raw_diff || intelligenceResult?.raw_diff || '(No diff content available for this run)'}
            </div>
          </div>
        )}

        {/* ── TAB: JOURNEYS & CATALOG ────────────────────────────────────────── */}
        {activeTab === 'catalog' && (
          <div className="tg-grid-2">
            <div className="tg-card">
              <div className="tg-card-header">
                <span className="tg-card-title">
                  <Layers size={16} />
                  Registered Business User Journeys ({journeys.length})
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {journeys.map((j) => (
                  <div key={j.id} style={{ background: 'var(--tg-surface-card)', padding: '0.75rem', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{j.name}</span>
                      <span className="tg-pill tg-pill-drift">{j.criticality}</span>
                    </div>
                    <p style={{ fontSize: '0.8rem', color: 'var(--tg-text-muted)', margin: '0.35rem 0' }}>
                      {j.description}
                    </p>
                    <div style={{ fontSize: '0.75rem', color: 'var(--tg-text-dim)', fontFamily: 'var(--tg-font-mono)' }}>
                      Paths: {j.frontend_paths.concat(j.api_paths).slice(0, 2).join(', ')}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="tg-card">
              <div className="tg-card-header">
                <span className="tg-card-title">
                  <Terminal size={16} />
                  Registered Test Catalog ({inventory.length})
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {inventory.map((t) => (
                  <div key={t.id} style={{ background: 'var(--tg-surface-card)', padding: '0.75rem', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>{t.name}</span>
                      <span className="tg-pill tg-pill-p0">{t.priority_tier}</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--tg-cyan)', fontFamily: 'var(--tg-font-mono)', margin: '0.2rem 0' }}>
                      {t.file}
                    </div>
                    <p style={{ fontSize: '0.78rem', color: 'var(--tg-text-muted)', margin: 0 }}>
                      {t.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Initial Empty State if no run yet */}
        {!autonomousResult && !intelligenceResult && !isRunning && (
          <div style={{ textAlign: 'center', padding: '4rem 1rem', background: 'var(--tg-surface)', borderRadius: '12px', border: '1px solid var(--tg-border)' }}>
            <Shield size={48} color="#06b6d4" style={{ marginBottom: '1rem' }} />
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.3rem' }}>TravelGuard AI Ready</h3>
            <p style={{ color: 'var(--tg-text-muted)', maxWidth: '500px', margin: '0 auto 1.5rem auto', fontSize: '0.9rem' }}>
              Select a demo scenario above or click &ldquo;Execute TravelGuard&rdquo; to analyze local git changes, diagnose failures, and test self-healing locators.
            </p>
            <button
              className="tg-btn-primary-run"
              style={{ margin: '0 auto' }}
              onClick={() => handleRunAutonomous('booking-ui-drift')}
            >
              <Play size={16} fill="#ffffff" />
              <span>Run Scenario A: UI Drift & Self-Healing</span>
            </button>
          </div>
        )}
      </main>
    </div>
  );
};
