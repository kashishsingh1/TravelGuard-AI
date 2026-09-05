export interface DemoScenario {
  key: string;
  name: string;
  description: string;
  fixture_file: string;
  type: string;
}

export interface BusinessJourney {
  id: string;
  name: string;
  description: string;
  criticality: string;
  workflow_stage: number;
  components: string[];
  frontend_paths: string[];
  api_paths: string[];
  tests: string[];
}

export interface TestInventoryItem {
  id: string;
  name: string;
  file: string;
  priority_tier: string;
  criticality: string;
  business_journeys: string[];
  description: string;
  expected_duration_ms: number;
}

export interface SelectedTest {
  test_id: string;
  file: string;
  name: string;
  priority: string;
  reason: string;
  confidence: number;
}

export interface SkippedTest {
  test_id: string;
  file: string;
  name: string;
  reason: string;
}

export interface DiagnosisResult {
  test_id: string;
  classification: 'TEST_DRIFT' | 'PRODUCT_DEFECT' | 'ENVIRONMENT_FAILURE' | 'UNKNOWN';
  confidence: number;
  summary: string;
  root_cause: string;
  recommended_action: string;
}

export interface RepairProposal {
  test_id: string;
  test_file: string;
  original_locator: string;
  repaired_locator: string;
  confidence: number;
  explanation: string;
}

export interface HealingResult {
  test_id: string;
  status: string;
  reason: string;
  proposal?: RepairProposal;
  validation_run?: any;
}

export interface QualityGateDecision {
  action: string;
  exit_code: number;
  verdict: string;
  passed_gate: boolean;
  reasons: string[];
}

export interface QualityReport {
  run_id: string;
  timestamp: string;
  status: string;
  changed_files: number;
  selected_tests: number;
  skipped_tests: number;
  passed: number;
  failed: number;
  healed: number;
  real_defects: number;
  environment_failures: number;
  unknown_failures: number;
  release_confidence: number;
  release_decision: string;
  quality_gate_passed: boolean;
  confidence_explanation: string;
  summary: string;
}

export interface AutonomousRunResult {
  run_id: string;
  impact?: any;
  selected_tests: SelectedTest[];
  skipped_tests: SkippedTest[];
  execution_results: any[];
  diagnosis_results: DiagnosisResult[];
  healing_results: HealingResult[];
  quality_report: QualityReport;
  release_confidence_breakdown?: {
    raw_score: number;
    base_pass_score: number;
    healed_discount: number;
    risk_level: string;
    formula_explanation: string;
  };
  quality_gate_decision?: QualityGateDecision;
  raw_diff?: string;
}

export interface GeneratedTest {
  file_path: string;
  scenario_name: string;
  code: string;
  validation_status: string;
  validation_details?: string;
}

export interface CoverageResult {
  status: string;
  reason: string;
  missing_scenarios: string[];
}

export interface IntelligenceResult {
  impact: any;
  selected_tests: SelectedTest[];
  skipped_tests: SkippedTest[];
  coverage: CoverageResult;
  generated_test?: GeneratedTest;
  raw_diff?: string;
  change_set?: any;
}
