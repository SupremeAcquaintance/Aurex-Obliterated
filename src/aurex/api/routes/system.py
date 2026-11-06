import json
from hashlib import sha256
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from aurex.api.dependencies import get_db
from aurex.backtest_engine.periodic_flow_daily_cross_source import (
    Q1_DAILY_CROSS_PASS_AUTHORIZATION,
    Q1_DAILY_CROSS_PASS_DECISION,
    PeriodicFlowDailyCrossSourceAudit,
    PeriodicFlowDailyCrossSourceProtocol,
    PeriodicFlowDailyCrossSourceResult,
    audit_daily_cross_audit,
    audit_daily_cross_protocol,
    audit_daily_cross_result,
)
from aurex.backtest_engine.periodic_flow_full_development_acquisition import (
    FULL_DEVELOPMENT_AUTHORIZATION,
    PeriodicFlowFullDevelopmentProtocol,
    PeriodicFlowFullDevelopmentProtocolAudit,
    audit_full_development_protocol,
    audit_full_development_protocol_audit,
)
from aurex.backtest_engine.periodic_flow_full_development_preflight import (
    PREFLIGHT_BLOCK_DECISION,
    PeriodicFlowAcquisitionPreflightAudit,
    PeriodicFlowAcquisitionPreflightResult,
    audit_preflight_audit,
    audit_preflight_result,
)
from aurex.backtest_engine.periodic_flow_full_development_runner import (
    PeriodicFlowExecutionContract,
    PeriodicFlowExecutionContractAudit,
    audit_execution_contract,
    audit_execution_contract_audit,
)
from aurex.backtest_engine.periodic_flow_metadata_census import (
    Q1_CENSUS_PASS_AUTHORIZATION,
    Q1_CENSUS_PASS_DECISION,
    PeriodicFlowMetadataCensusAudit,
    PeriodicFlowMetadataCensusContract,
    PeriodicFlowMetadataCensusResult,
    audit_metadata_census_audit,
    audit_metadata_census_contract,
    audit_metadata_census_result,
)
from aurex.backtest_engine.periodic_flow_overlap_census import (
    Q1_OVERLAP_PASS_AUTHORIZATION,
    Q1_OVERLAP_PASS_DECISION,
    PeriodicFlowOverlapCensusAudit,
    PeriodicFlowOverlapCensusProtocol,
    PeriodicFlowOverlapCensusResult,
    audit_overlap_census_audit,
    audit_overlap_census_protocol,
    audit_overlap_census_result,
)
from aurex.backtest_engine.periodic_flow_payload_gap_remediation import (
    Q1_GAP_FAIL_AUTHORIZATION,
    Q1_GAP_FAIL_DECISION,
    PeriodicFlowGapRemediationAudit,
    PeriodicFlowGapRemediationProtocol,
    PeriodicFlowGapRemediationResult,
    audit_gap_remediation_audit,
    audit_gap_remediation_protocol,
    audit_gap_remediation_result,
)
from aurex.backtest_engine.periodic_flow_payload_pilot import (
    Q1_PAYLOAD_FAIL_AUTHORIZATION,
    Q1_PAYLOAD_FAIL_DECISION,
    PeriodicFlowPayloadPilotAudit,
    PeriodicFlowPayloadPilotProtocol,
    PeriodicFlowPayloadPilotResult,
    audit_periodic_flow_payload_audit,
    audit_periodic_flow_payload_protocol,
    audit_periodic_flow_payload_result,
)
from aurex.backtest_engine.periodic_flow_payload_transport_amendment import (
    PeriodicFlowPayloadTransportAmendment,
    audit_periodic_flow_transport_amendment,
)
from aurex.backtest_engine.periodic_flow_raw_trades_metadata_census import (
    RAW_TRADES_PASS_AUTHORIZATION,
    RAW_TRADES_PASS_DECISION,
    RawTradesMetadataCensusAudit,
    RawTradesMetadataCensusProtocol,
    RawTradesMetadataCensusResult,
    RawTradesMetadataProtocolAudit,
    audit_raw_trades_audit,
    audit_raw_trades_protocol,
    audit_raw_trades_protocol_audit,
    audit_raw_trades_result,
)
from aurex.backtest_engine.periodic_flow_raw_trades_payload_evidence_v2 import (
    RawTradesPayloadPilotAuditV2,
    RawTradesPayloadPilotResultV2,
    audit_raw_payload_audit_v2,
    audit_raw_payload_result_v2,
)
from aurex.backtest_engine.periodic_flow_raw_trades_payload_pilot import (
    RAW_PAYLOAD_PASS_AUTHORIZATION,
    RAW_PAYLOAD_PASS_DECISION,
    RawTradesPayloadPilotProtocol,
    RawTradesPayloadProtocolAudit,
    audit_raw_payload_protocol,
    audit_raw_payload_protocol_audit,
)
from aurex.backtest_engine.periodic_flow_spot_charter import (
    PERIODIC_FLOW_NEXT_AUTHORIZATION,
    PeriodicFlowSpotCharter,
    PeriodicFlowSpotCharterAudit,
    audit_periodic_flow_spot_charter,
    audit_periodic_flow_spot_charter_audit,
)
from aurex.backtest_engine.s1_btc_source_acquisition import (
    S1_BTC_SOURCE_NEXT,
    S1BtcSourceAcquisitionProtocol,
    S1BtcSourceAcquisitionProtocolAudit,
)
from aurex.backtest_engine.s1_development_outcome_audit import (
    S11DevelopmentOutcomeAudit,
)
from aurex.backtest_engine.s1_development_outcome_execution import (
    S11DevelopmentOutcomeResult,
)
from aurex.backtest_engine.s1_post_failure_analysis import (
    S1PostFailureAnalysisAudit,
    S1PostFailureAnalysisResult,
)
from aurex.backtest_engine.s2_bigquery_feasibility import (
    S2_FEASIBILITY_BLOCK_METADATA,
    S2_FEASIBILITY_RETRY,
    S2BigQueryFeasibilityAudit,
    S2BigQueryFeasibilityProtocol,
    S2BigQueryFeasibilityProtocolAudit,
    S2BigQueryFeasibilityResult,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v2 import (
    S2_FEASIBILITY_V2_BLOCK_DRY_RUN,
    S2_FEASIBILITY_V2_RETRY,
    S2BigQueryFeasibilityAuditV2,
    S2BigQueryFeasibilityProtocolAuditV2,
    S2BigQueryFeasibilityProtocolV2,
    S2BigQueryFeasibilityResultV2,
)
from aurex.backtest_engine.s2_bigquery_feasibility_v3 import (
    S2_FEASIBILITY_V3_NEXT,
    S2_FEASIBILITY_V3_PASS,
    S2BigQueryFeasibilityAuditV3,
    S2BigQueryFeasibilityProtocolAuditV3,
    S2BigQueryFeasibilityProtocolV3,
    S2BigQueryFeasibilityResultV3,
)
from aurex.backtest_engine.s2_bigquery_payload import (
    S2_PAYLOAD_BLOCK_VALIDATION,
    S2_PAYLOAD_NEXT,
    S2_PAYLOAD_PASS,
    S2BigQueryPayloadProtocol,
    S2BigQueryPayloadProtocolAudit,
    S2BigQueryPayloadResult,
    S2DevelopmentWeeklyPayload,
)
from aurex.backtest_engine.s2_bigquery_payload_v2 import (
    S2BigQueryPayloadAuditV2,
    S2BigQueryPayloadFailureAuditV1,
    S2BigQueryPayloadProtocolAuditV2,
    S2BigQueryPayloadProtocolV2,
    S2BigQueryPayloadResultV2,
)
from aurex.backtest_engine.s2_btc_source_acquisition import (
    S2BtcSourceAcquisitionProtocol,
    S2BtcSourceAcquisitionProtocolAudit,
)
from aurex.backtest_engine.s2_btc_source_execution import (
    S2_BTC_ACQUISITION_NEXT,
    S2_BTC_ACQUISITION_PASS,
    S2BtcAcquisitionCheckpoint,
    S2BtcSourceAcquisitionAudit,
    S2BtcSourceAcquisitionResult,
    S2BtcSourceExecutionAudit,
    S2BtcSourceExecutionContract,
)
from aurex.backtest_engine.s2_development_backtest import (
    S2_BACKTEST_STOP,
    S2DevelopmentBacktestExecutionAudit,
    S2DevelopmentBacktestExecutionContract,
    S2DevelopmentBacktestProtocol,
    S2DevelopmentBacktestProtocolAudit,
    S2DevelopmentBacktestResult,
    S2DevelopmentBacktestResultAudit,
)
from aurex.backtest_engine.s2_development_measurement_execution import (
    S2_MEASUREMENT_PASS,
    S2_MEASUREMENT_PREREG_NEXT,
    S2DevelopmentMeasurementExecutionAddendum,
    S2DevelopmentMeasurementExecutionAudit,
    S2DevelopmentMeasurementResult,
    S2DevelopmentMeasurementResultAudit,
)
from aurex.backtest_engine.s2_development_measurement_protocol import (
    S2_MEASUREMENT_AUDIT_DECISION,
    S2_MEASUREMENT_DECISION,
    S2_MEASUREMENT_NEXT,
    S2DevelopmentMeasurementProtocol,
    S2DevelopmentMeasurementProtocolAudit,
)
from aurex.backtest_engine.s2_onchain_settlement_charter import (
    S2_CHARTER_DECISION,
    S2_NEXT_AUTHORIZATION,
    S2OnchainSettlementCharter,
    S2OnchainSettlementCharterAudit,
)
from aurex.backtest_engine.s2_strategy_preregistration import (
    S2_STRATEGY_PREREG_NEXT,
    S2StrategyPreregistration,
    S2StrategyPreregistrationAudit,
)
from aurex.backtest_engine.s3_cftc_positioning_charter import (
    S3_NEXT_AUTHORIZATION,
    S3CftcPositioningCharter,
    S3CftcPositioningCharterAudit,
    audit_s3_charter,
    audit_s3_charter_audit,
)
from aurex.backtest_engine.s3_cftc_source_feasibility import (
    S3CftcSourceFeasibilityProtocol,
    S3CftcSourceFeasibilityProtocolAudit,
    S3CftcSourceFeasibilityResult,
    audit_s3_feasibility_protocol,
    audit_s3_feasibility_protocol_audit,
    audit_s3_feasibility_result,
)
from aurex.backtest_engine.s3_cftc_source_feasibility_transport import (
    S3CftcMetadataTransportAmendmentAuditV2,
    S3CftcMetadataTransportAmendmentV2,
    S3CftcSourceTransportFailureAudit,
    audit_transport_amendment,
    audit_transport_amendment_audit,
    audit_transport_failure,
)
from aurex.backtest_engine.s3_cftc_source_transport_outcome import (
    S3_DISTINCT_SUCCESSOR_AUTHORIZATION,
    S3_TRANSPORT_V2_RETIREMENT,
    S3CftcMetadataTransportExecutionReceiptAuditV2,
    S3CftcMetadataTransportExecutionReceiptV2,
    audit_transport_execution_receipt,
    audit_transport_execution_receipt_audit,
)
from aurex.backtest_engine.s4_etp_source_feasibility_viability import (
    S4_VIABILITY_NEXT,
    S4_VIABILITY_STOP,
    S4EtpSourceFeasibilityViabilityReview,
    S4EtpSourceFeasibilityViabilityReviewAudit,
    audit_s4_viability_review,
    audit_s4_viability_review_audit,
)
from aurex.backtest_engine.s4_spot_bitcoin_etp_charter import (
    S4_CHARTER_DECISION,
    S4_NEXT_AUTHORIZATION,
    S4SpotBitcoinEtpCharter,
    S4SpotBitcoinEtpCharterAudit,
    audit_s4_charter,
    audit_s4_charter_audit,
)
from aurex.backtest_engine.s4_spot_bitcoin_etp_source_feasibility import (
    S4_FEASIBILITY_RUN_AUTHORIZATION,
    S4EtpSourceFeasibilityProtocol,
    S4EtpSourceFeasibilityProtocolAudit,
    audit_s4_feasibility_protocol,
    audit_s4_feasibility_protocol_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_development_charter import (
    S5BitcoinCoreDevelopmentCharter,
    S5BitcoinCoreDevelopmentCharterAudit,
    audit_s5_charter,
    audit_s5_charter_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk import (
    S5_GITHUB_BULK_NEXT,
    S5_GITHUB_BULK_PASS,
    S5_GITHUB_BULK_STOP,
    S5GitHubBulkAcquisitionProtocol,
    S5GitHubBulkProtocolAudit,
    S5GitHubBulkResult,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_correction import (
    S5GitHubBulkFailureAudit,
    S5GitHubBulkResponseHandlingAmendmentAuditV2,
    S5GitHubBulkResponseHandlingAmendmentV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_pagination import (
    S5GitHubBulkFinalResultAuditV4,
    S5GitHubBulkMonotonicTerminalAmendmentAuditV4,
    S5GitHubBulkMonotonicTerminalAmendmentV4,
    S5GitHubBulkTerminalDriftFailureAuditV3,
)
from aurex.backtest_engine.s5_bitcoin_core_github_bulk_resume import (
    S5GitHubBulkContiguousResumeAmendmentAuditV3,
    S5GitHubBulkContiguousResumeAmendmentV3,
    S5GitHubBulkSuspensionFailureAuditV2,
)
from aurex.backtest_engine.s5_bitcoin_core_github_preflight import (
    S5_GITHUB_PREFLIGHT_NEXT,
    S5_GITHUB_PREFLIGHT_STOP,
    S5GitHubPreflightProtocol,
    S5GitHubPreflightProtocolAudit,
    S5GitHubPreflightResult,
    S5GitHubPreflightResultAudit,
    audit_s5_github_preflight_protocol,
    audit_s5_github_preflight_protocol_audit,
    audit_s5_github_preflight_result,
    audit_s5_github_preflight_result_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_github_preflight_correction import (
    S5_GITHUB_PREFLIGHT_CORRECTED_PASS,
    S5GitHubPreflightCorrectedResultAuditV2,
    S5GitHubPreflightCorrectedResultV2,
    S5GitHubPreflightFailureAudit,
    S5GitHubPreflightInterpreterAmendmentAuditV2,
    S5GitHubPreflightInterpreterAmendmentV2,
    evidence_hash_valid,
)
from aurex.backtest_engine.s5_bitcoin_core_github_transport import (
    S5_GITHUB_TRANSPORT_DECISION,
    S5_GITHUB_TRANSPORT_NEXT,
    S5GitHubTransportDecision,
    S5GitHubTransportDecisionAudit,
    audit_s5_github_transport_decision,
    audit_s5_github_transport_decision_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_census import (
    S5_CENSUS_NEXT,
    S5_CENSUS_PASS,
    S5BitcoinCoreHistoryCensusProtocol,
    S5BitcoinCoreHistoryCensusProtocolAudit,
    S5BitcoinCoreHistoryCensusResult,
    S5BitcoinCoreHistoryCensusResultAudit,
    audit_s5_census_protocol,
    audit_s5_census_protocol_audit,
    audit_s5_census_result,
    audit_s5_census_result_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload import (
    S5_HISTORY_NEXT,
    S5_HISTORY_PASS,
    S5_HISTORY_STOP,
    S5BitcoinCoreHistoryPayloadProtocol,
    S5BitcoinCoreHistoryPayloadProtocolAudit,
    S5BitcoinCoreHistoryPayloadResult,
    S5BitcoinCoreHistoryPayloadResultAudit,
    audit_s5_history_protocol,
    audit_s5_history_protocol_audit,
    audit_s5_history_result,
    audit_s5_history_result_audit,
)
from aurex.backtest_engine.s5_bitcoin_core_history_payload_transport import (
    S5_VERIFIER_FAILURE_ADJUDICATION,
    S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2,
    S5BitcoinCoreHistoryLocalVerifierAmendmentV2,
    S5BitcoinCoreHistoryPayloadResultAuditV2,
    S5BitcoinCoreHistoryPayloadResultV2,
    S5BitcoinCoreHistoryVerifierFailureAudit,
    audit_s5_history_result_audit_v2,
    audit_s5_history_result_v2,
    audit_verifier_amendment,
    audit_verifier_amendment_audit,
    audit_verifier_failure,
)
from aurex.backtest_engine.s5_bitcoin_core_source_feasibility import (
    S5_SOURCE_NEXT,
    S5_SOURCE_PASS,
    S5BitcoinCoreSourceFeasibilityProtocol,
    S5BitcoinCoreSourceFeasibilityProtocolAudit,
    S5BitcoinCoreSourceFeasibilityResult,
    S5BitcoinCoreSourceFeasibilityResultAudit,
    audit_s5_source_protocol,
    audit_s5_source_protocol_audit,
    audit_s5_source_result,
    audit_s5_source_result_audit,
)
from aurex.backtest_engine.s5_measurement_readiness import (
    S5_MEASUREMENT_CHECKPOINT,
    S5_MEASUREMENT_NEXT,
    verify_measurement_checkpoint,
)
from aurex.backtest_engine.strategy_factory_contract import StrategyFactoryContract
from aurex.backtest_engine.strategy_factory_readiness import (
    StrategyFactoryReadinessAudit,
    StrategyFactoryReadinessResult,
    audit_readiness_audit,
    audit_readiness_result,
)
from aurex.backtest_engine.universe import universe_evidence_hash
from aurex.db.models import SystemEvent
from aurex.observability.schemas import SystemEventResponse
from aurex.strategy_engine.registry import (
    REGISTERED_STRATEGIES,
    strategy_lifecycle_allows_enable,
)

router = APIRouter(prefix="/system", tags=["system"])
DbSession = Annotated[Session, Depends(get_db)]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
READINESS_BASELINE_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_baseline_result_v1.json"
)
READINESS_CURRENT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v64.json"
)
FACTORY_CONTRACT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_contract_v1.json"
)
Q1_CHARTER_PATH = PROJECT_ROOT / "data" / "evidence" / "periodic_flow_spot_charter_v1.json"
Q1_CHARTER_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "periodic_flow_spot_charter_audit_v1.json"
)
Q1_CENSUS_CONTRACT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_metadata_census_contract_v1.json"
)
Q1_CENSUS_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_metadata_census_result_v1.json"
)
Q1_CENSUS_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_metadata_census_audit_v1.json"
)
Q1_PAYLOAD_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_payload_pilot_protocol_v1.json"
)
Q1_PAYLOAD_TRANSPORT_AMENDMENT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_payload_transport_amendment_v1.json"
)
Q1_PAYLOAD_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_payload_pilot_result_v1.json"
)
Q1_PAYLOAD_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_payload_pilot_audit_v1.json"
)
Q1_GAP_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_payload_gap_remediation_protocol_v1.json"
)
Q1_GAP_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_payload_gap_remediation_result_v1.json"
)
Q1_GAP_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_payload_gap_remediation_audit_v1.json"
)
Q1_OVERLAP_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_overlap_census_protocol_v1.json"
)
Q1_OVERLAP_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_overlap_census_result_v1.json"
)
Q1_OVERLAP_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_overlap_census_audit_v1.json"
)
Q1_DAILY_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_daily_cross_source_protocol_v1.json"
)
Q1_DAILY_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_daily_cross_source_result_v1.json"
)
Q1_DAILY_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_daily_cross_source_audit_v1.json"
)
Q1_RAW_TRADES_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_usdm_raw_trades_metadata_census_protocol_v1.json"
)
Q1_RAW_TRADES_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_usdm_raw_trades_metadata_census_protocol_audit_v1.json"
)
Q1_RAW_TRADES_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_usdm_raw_trades_metadata_census_result_v1.json"
)
Q1_RAW_TRADES_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_usdm_raw_trades_metadata_census_audit_v1.json"
)
Q1_RAW_PAYLOAD_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_usdm_raw_trades_payload_pilot_protocol_v1.json"
)
Q1_RAW_PAYLOAD_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_usdm_raw_trades_payload_pilot_protocol_audit_v1.json"
)
Q1_RAW_PAYLOAD_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_usdm_raw_trades_payload_pilot_result_v2.json"
)
Q1_RAW_PAYLOAD_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_usdm_raw_trades_payload_pilot_audit_v2.json"
)
Q1_FULL_DEVELOPMENT_PROTOCOL_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "q1_periodic_flow_full_development_acquisition_protocol_v1.json"
)
Q1_FULL_DEVELOPMENT_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "q1_periodic_flow_full_development_acquisition_protocol_audit_v1.json"
)
Q1_FULL_DEVELOPMENT_EXECUTION_CONTRACT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "q1_periodic_flow_full_development_execution_contract_v1.json"
)
Q1_FULL_DEVELOPMENT_EXECUTION_CONTRACT_AUDIT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "q1_periodic_flow_full_development_execution_contract_audit_v1.json"
)
Q1_FULL_DEVELOPMENT_PREFLIGHT_RESULT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "q1_periodic_flow_full_development_preflight_result_v1.json"
)
Q1_FULL_DEVELOPMENT_PREFLIGHT_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "q1_periodic_flow_full_development_preflight_audit_v1.json"
)
Q1_FULL_READINESS_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v8.json"
)
Q1_FULL_READINESS_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_audit_v8.json"
)
JAM_FULL_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "jam_archive_full_acquisition_result_v1.json"
)
JAM_FULL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "jam_archive_full_acquisition_audit_v1.json"
)
JAM_REMEDIATION_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "jam_archive_quality_remediation_result_v1.json"
)
JAM_REMEDIATION_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "jam_archive_quality_remediation_audit_v1.json"
)
S1_BTC_SOURCE_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s1_btc_source_acquisition_protocol_v1.json"
)
S1_BTC_SOURCE_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s1_btc_source_acquisition_protocol_audit_v1.json"
)
S1_1_OUTCOME_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s1_1_development_outcome_result_v1.json"
)
S1_1_OUTCOME_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s1_1_development_outcome_audit_v1.json"
)
S1_FAILURE_ANALYSIS_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s1_post_failure_analysis_result_v1.json"
)
S1_FAILURE_ANALYSIS_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s1_post_failure_analysis_audit_v1.json"
)
S2_ONCHAIN_CHARTER_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_onchain_settlement_charter_v1.json"
)
S2_ONCHAIN_CHARTER_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_onchain_settlement_charter_audit_v1.json"
)
S2_BIGQUERY_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_protocol_v1.json"
)
S2_BIGQUERY_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_protocol_audit_v1.json"
)
S2_BIGQUERY_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_result_v1.json"
)
S2_BIGQUERY_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_audit_v1.json"
)
S2_BIGQUERY_PROTOCOL_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_protocol_v2.json"
)
S2_BIGQUERY_PROTOCOL_AUDIT_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_protocol_audit_v2.json"
)
S2_BIGQUERY_RESULT_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_result_v2.json"
)
S2_BIGQUERY_AUDIT_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_audit_v2.json"
)
S2_BIGQUERY_PROTOCOL_V3_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_protocol_v3.json"
)
S2_BIGQUERY_PROTOCOL_AUDIT_V3_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_protocol_audit_v3.json"
)
S2_BIGQUERY_RESULT_V3_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_result_v3.json"
)
S2_BIGQUERY_AUDIT_V3_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_feasibility_audit_v3.json"
)
S2_PAYLOAD_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_payload_protocol_v1.json"
)
S2_PAYLOAD_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_payload_protocol_audit_v1.json"
)
S2_PAYLOAD_RESULT_PATH = PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_payload_result_v1.json"
S2_PAYLOAD_FAILURE_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_payload_failure_audit_v1.json"
)
S2_PAYLOAD_PROTOCOL_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_payload_protocol_v2.json"
)
S2_PAYLOAD_PROTOCOL_AUDIT_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_payload_protocol_audit_v2.json"
)
S2_PAYLOAD_RESULT_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_payload_result_v2.json"
)
S2_PAYLOAD_AUDIT_V2_PATH = PROJECT_ROOT / "data" / "evidence" / "s2_bigquery_payload_audit_v2.json"
S2_DEVELOPMENT_PAYLOAD_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_weekly_payload_v1.json"
)
S2_MEASUREMENT_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_measurement_protocol_v1.json"
)
S2_MEASUREMENT_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_measurement_protocol_audit_v1.json"
)
S2_MEASUREMENT_EXECUTION_ADDENDUM_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_measurement_execution_addendum_v1.json"
)
S2_MEASUREMENT_EXECUTION_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_measurement_execution_audit_v1.json"
)
S2_MEASUREMENT_DATASET_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_measurements_v1.jsonl"
)
S2_MEASUREMENT_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_measurement_result_v1.json"
)
S2_MEASUREMENT_RESULT_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_measurement_result_audit_v1.json"
)
S2_STRATEGY_PREREGISTRATION_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_strategy_preregistration_v1.json"
)
S2_STRATEGY_PREREGISTRATION_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_strategy_preregistration_audit_v1.json"
)
S2_BTC_SOURCE_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_btc_source_acquisition_protocol_v1.json"
)
S2_BTC_SOURCE_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_btc_source_acquisition_protocol_audit_v1.json"
)
S2_BTC_SOURCE_EXECUTION_CONTRACT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_btc_source_execution_contract_v1.json"
)
S2_BTC_SOURCE_EXECUTION_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_btc_source_execution_audit_v1.json"
)
S2_BTC_SOURCE_CHECKPOINT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_btc_source_acquisition_checkpoint_v1.json"
)
S2_BTC_SOURCE_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_btc_source_acquisition_result_v1.json"
)
S2_BTC_SOURCE_RESULT_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_btc_source_acquisition_audit_v1.json"
)
S2_BTC_PRICE_DATASET_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "datasets" / "s2_btcusdt_monday_00h_opens_v1.jsonl"
)
S2_BACKTEST_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_backtest_protocol_v1.json"
)
S2_BACKTEST_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_backtest_protocol_audit_v1.json"
)
S2_BACKTEST_EXECUTION_CONTRACT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_backtest_execution_contract_v1.json"
)
S2_BACKTEST_EXECUTION_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_backtest_execution_audit_v1.json"
)
S2_BACKTEST_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_backtest_result_v1.json"
)
S2_BACKTEST_RESULT_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s2_development_backtest_result_audit_v1.json"
)
S2_BACKTEST_LEDGER_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "datasets" / "s2_development_backtest_ledger_v1.jsonl"
)
S2_TERMINAL_NEXT_ACTION = (
    "FREEZE_AND_AUDIT_A_DISTINCT_S3_MECHANISM_CHARTER_WITHOUT_TUNING_OR_REUSING_S2"
)
SANDBOX_PROFILE_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "binance_spot_testnet_sandbox_profile_v1.json"
)
S1_SUCCESSOR_LINEAGE_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s1_successor_lineage_ledger_v1.json"
)
S1_SUCCESSOR_LINEAGE_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s1_successor_lineage_audit_v1.json"
)
READINESS_V23_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v23.json"
)
READINESS_V23_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_audit_v23.json"
)
READINESS_V24_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v24.json"
)
READINESS_V24_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_audit_v24.json"
)
READINESS_V25_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v25.json"
)
READINESS_V25_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_audit_v25.json"
)
READINESS_V26_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v26.json"
)
READINESS_V26_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_audit_v26.json"
)
READINESS_V27_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v27.json"
)
READINESS_V27_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_audit_v27.json"
)
READINESS_V28_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v28.json"
)
READINESS_V28_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_audit_v28.json"
)
READINESS_V29_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v29.json"
)
READINESS_V29_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_audit_v29.json"
)
READINESS_V30_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v30.json"
)
READINESS_V30_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_audit_v30.json"
)
READINESS_V31_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_result_v31.json"
)
READINESS_V31_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "aurex_strategy_factory_readiness_current_audit_v31.json"
)
S3_CFTC_CHARTER_PATH = PROJECT_ROOT / "data" / "evidence" / "s3_cftc_positioning_charter_v1.json"
S3_CFTC_CHARTER_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s3_cftc_positioning_charter_audit_v1.json"
)
S3_CFTC_FEASIBILITY_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s3_cftc_source_feasibility_protocol_v1.json"
)
S3_CFTC_FEASIBILITY_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s3_cftc_source_feasibility_protocol_audit_v1.json"
)
S3_CFTC_FEASIBILITY_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s3_cftc_source_feasibility_result_v1.json"
)
S3_CFTC_TRANSPORT_FAILURE_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s3_cftc_source_transport_failure_audit_v1.json"
)
S3_CFTC_TRANSPORT_AMENDMENT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s3_cftc_metadata_transport_amendment_v2.json"
)
S3_CFTC_TRANSPORT_AMENDMENT_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s3_cftc_metadata_transport_amendment_audit_v2.json"
)
S3_CFTC_TRANSPORT_RECEIPT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s3_cftc_metadata_transport_execution_receipt_v2.json"
)
S3_CFTC_TRANSPORT_RECEIPT_AUDIT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s3_cftc_metadata_transport_execution_receipt_audit_v2.json"
)
S4_ETP_CHARTER_PATH = PROJECT_ROOT / "data" / "evidence" / "s4_spot_bitcoin_etp_charter_v1.json"
S4_ETP_CHARTER_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s4_spot_bitcoin_etp_charter_audit_v1.json"
)
S4_ETP_FEASIBILITY_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s4_etp_source_feasibility_protocol_v1.json"
)
S4_ETP_FEASIBILITY_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s4_etp_source_feasibility_protocol_audit_v1.json"
)
S4_ETP_FEASIBILITY_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s4_etp_source_feasibility_result_v1.json"
)
S4_ETP_FEASIBILITY_VIABILITY_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s4_etp_source_feasibility_viability_review_v1.json"
)
S4_ETP_FEASIBILITY_VIABILITY_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s4_etp_source_feasibility_viability_review_audit_v1.json"
)
S5_CHARTER_PATH = PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_development_charter_v1.json"
S5_CHARTER_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_development_charter_audit_v1.json"
)
S5_SOURCE_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_source_feasibility_protocol_v1.json"
)
S5_SOURCE_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_source_feasibility_protocol_audit_v1.json"
)
S5_SOURCE_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_source_feasibility_result_v1.json"
)
S5_SOURCE_RESULT_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_source_feasibility_result_audit_v1.json"
)
S5_HISTORY_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_payload_protocol_v1.json"
)
S5_HISTORY_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_payload_protocol_audit_v1.json"
)
S5_HISTORY_RESULT_V1_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_payload_result_v1.json"
)
S5_HISTORY_RESULT_AUDIT_V1_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_payload_result_audit_v1.json"
)
S5_HISTORY_FAILURE_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_verifier_failure_audit_v1.json"
)
S5_HISTORY_AMENDMENT_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_local_verifier_amendment_v2.json"
)
S5_HISTORY_AMENDMENT_AUDIT_V2_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_history_local_verifier_amendment_audit_v2.json"
)
S5_HISTORY_RESULT_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_payload_result_v2.json"
)
S5_HISTORY_RESULT_AUDIT_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_payload_result_audit_v2.json"
)
S5_HISTORY_DATASET_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_payload_v1.git"
)
S5_CENSUS_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_census_protocol_v1.json"
)
S5_CENSUS_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_census_protocol_audit_v1.json"
)
S5_CENSUS_RESULT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_census_result_v1.json"
)
S5_CENSUS_RESULT_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_history_census_result_audit_v1.json"
)
S5_GITHUB_TRANSPORT_DECISION_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_transport_decision_v1.json"
)
S5_GITHUB_TRANSPORT_DECISION_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_transport_decision_audit_v1.json"
)
S5_GITHUB_PREFLIGHT_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_preflight_protocol_v1.json"
)
S5_GITHUB_PREFLIGHT_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_preflight_protocol_audit_v1.json"
)
S5_GITHUB_PREFLIGHT_RESULT_V1_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_preflight_result_v1.json"
)
S5_GITHUB_PREFLIGHT_RESULT_AUDIT_V1_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_preflight_result_audit_v1.json"
)
S5_GITHUB_PREFLIGHT_TRANSCRIPT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_github_pull_metadata_preflight_transcript_v1.json"
)
S5_GITHUB_PREFLIGHT_FAILURE_AUDIT_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_preflight_failure_audit_v1.json"
)
S5_GITHUB_PREFLIGHT_AMENDMENT_V2_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_preflight_interpreter_amendment_v2.json"
)
S5_GITHUB_PREFLIGHT_AMENDMENT_AUDIT_V2_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_preflight_interpreter_amendment_audit_v2.json"
)
S5_GITHUB_PREFLIGHT_CORRECTED_RESULT_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_preflight_corrected_result_v2.json"
)
S5_GITHUB_PREFLIGHT_CORRECTED_RESULT_AUDIT_V2_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_preflight_corrected_result_audit_v2.json"
)
S5_GITHUB_REPOSITORY_METADATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_source_feasibility_responses_v1"
    / "01_github_repository_metadata.json"
)
S5_GITHUB_BULK_PROTOCOL_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_bulk_acquisition_protocol_v1.json"
)
S5_GITHUB_BULK_PROTOCOL_AUDIT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_bulk_acquisition_protocol_audit_v1.json"
)
S5_GITHUB_BULK_RESULT_V1_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_bulk_result_v1.json"
)
S5_GITHUB_BULK_FAILURE_AUDIT_V1_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_bulk_failure_audit_v1.json"
)
S5_GITHUB_BULK_RESPONSE_AMENDMENT_V2_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_bulk_response_handling_amendment_v2.json"
)
S5_GITHUB_BULK_RESPONSE_AMENDMENT_AUDIT_V2_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_bulk_response_handling_amendment_audit_v2.json"
)
S5_GITHUB_BULK_RESULT_V2_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_bulk_result_v2.json"
)
S5_GITHUB_BULK_SUSPENSION_AUDIT_V2_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_bulk_suspension_failure_audit_v2.json"
)
S5_GITHUB_BULK_RESUME_AMENDMENT_V3_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_bulk_contiguous_resume_amendment_v3.json"
)
S5_GITHUB_BULK_RESUME_AMENDMENT_AUDIT_V3_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_bulk_contiguous_resume_amendment_audit_v3.json"
)
S5_GITHUB_BULK_RESULT_V3_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_bulk_result_v3.json"
)
S5_GITHUB_BULK_DRIFT_AUDIT_V3_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_bulk_terminal_drift_failure_audit_v3.json"
)
S5_GITHUB_BULK_MONOTONIC_AMENDMENT_V4_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4.json"
)
S5_GITHUB_BULK_MONOTONIC_AMENDMENT_AUDIT_V4_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_audit_v4.json"
)
S5_GITHUB_BULK_RESULT_V4_PATH = (
    PROJECT_ROOT / "data" / "evidence" / "s5_bitcoin_core_github_bulk_result_v4.json"
)
S5_GITHUB_BULK_FINAL_AUDIT_V4_PATH = (
    PROJECT_ROOT
    / "data"
    / "evidence"
    / "s5_bitcoin_core_github_bulk_final_result_audit_v4.json"
)
S5_GITHUB_BULK_PAGE_DIRECTORY = (
    PROJECT_ROOT / "data" / "evidence" / "s5_github_pull_metadata_bulk_v1"
)
S5_GITHUB_BULK_FAILURE_PATHS = (
    S5_GITHUB_BULK_PAGE_DIRECTORY / "failure_page_0001.json",
    S5_GITHUB_BULK_PAGE_DIRECTORY / "failure_v2_page_0118.json",
    S5_GITHUB_BULK_PAGE_DIRECTORY / "failure_v3_page_0118.json",
)
S5_GITHUB_BULK_V4_RUNNER_SOURCES = (
    "src/aurex/backtest_engine/s5_bitcoin_core_github_bulk.py",
    "scripts/run_s5_bitcoin_core_github_bulk_acquisition.py",
    "src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_correction.py",
    "scripts/run_s5_bitcoin_core_github_bulk_acquisition_v2.py",
    "src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_resume.py",
    "scripts/run_s5_bitcoin_core_github_bulk_acquisition_v3.py",
    "src/aurex/backtest_engine/s5_bitcoin_core_github_bulk_pagination.py",
    "scripts/audit_s5_bitcoin_core_github_bulk_terminal_drift_failure_v3.py",
    "scripts/freeze_s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4.py",
    "scripts/audit_s5_bitcoin_core_github_bulk_monotonic_terminal_amendment_v4.py",
    "scripts/run_s5_bitcoin_core_github_bulk_acquisition_v4.py",
)
S5_GITHUB_BULK_FINAL_AUDITOR_SOURCE = (
    "scripts/audit_s5_bitcoin_core_github_bulk_final_result_v4.py"
)


class StrategyFactoryReadinessResponse(BaseModel):
    status: str
    decision: str
    strategy_research_ready: bool
    paper_operation_ready: bool
    sandbox_strategy_use_ready: bool
    production_ready: bool
    live_ready: bool
    source_integrity_verified: bool
    active_research_checkpoint: str
    research_checkpoint_verified: bool
    acquisition_preflight_ready: bool
    acquisition_preflight_decision: str
    acquisition_free_disk_bytes_observed: int
    acquisition_required_free_disk_bytes: int
    acquisition_additional_free_disk_bytes_required: int
    passed_gate_count: int
    partial_gate_count: int
    failed_gate_count: int
    research_blocking_gate_ids: list[str]
    downstream_partial_gate_ids: list[str]
    qualified_strategy_count: int
    enable_eligible_strategy_count: int
    real_net_profit_usd: str
    next_action: str
    current_result_evidence_hash: str
    baseline_result_evidence_hash: str
    contract_evidence_hash: str
    evaluated_at: str
    gate_results: list[dict]
    strategy_lifecycle: list[dict]
    limitations: list[str]


@router.get("/events", response_model=list[SystemEventResponse])
def list_system_events(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SystemEvent]:
    return list(
        db.execute(
            select(SystemEvent).order_by(SystemEvent.occurred_at.desc()).limit(limit)
        ).scalars()
    )


@router.get("/readiness", response_model=StrategyFactoryReadinessResponse)
def strategy_factory_readiness() -> StrategyFactoryReadinessResponse:
    try:
        baseline = StrategyFactoryReadinessResult.model_validate(read_json(READINESS_BASELINE_PATH))
        current = StrategyFactoryReadinessResult.model_validate(read_json(READINESS_CURRENT_PATH))
        contract = StrategyFactoryContract.model_validate(read_json(FACTORY_CONTRACT_PATH))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Canonical strategy-factory readiness evidence is unavailable: {exc}",
        ) from exc

    source_integrity = source_evidence_integrity(current) and source_evidence_integrity(contract)
    measurement_verified = verify_measurement_checkpoint(PROJECT_ROOT)
    research_ready = current.strategy_research_ready and source_integrity and measurement_verified
    downstream_partial = [
        gate.gate_id
        for gate in current.gate_results
        if gate.status != "PASS" and gate.gate_id not in current.research_blocking_gate_ids
    ]
    strategy_lifecycle = [
        {
            "strategy": definition.strategy,
            "version": definition.version,
            "lifecycle_status": definition.lifecycle_status.value,
            "lifecycle_reason": definition.lifecycle_reason,
            "enable_eligible": strategy_lifecycle_allows_enable(definition.strategy),
        }
        for definition in sorted(
            REGISTERED_STRATEGIES.values(),
            key=lambda item: item.strategy,
        )
    ]
    enable_eligible_count = sum(bool(item["enable_eligible"]) for item in strategy_lifecycle)
    s2_checkpoint_verified = verify_s2_development_backtest_terminal_checkpoint()
    s3_checkpoint_verified = verify_s3_cftc_positioning_charter_checkpoint()
    s3_terminal_verified = verify_s3_cftc_source_feasibility_terminal_checkpoint()
    s4_checkpoint_verified = verify_s4_spot_bitcoin_etp_charter_checkpoint()
    s4_terminal_verified = verify_s4_etp_source_feasibility_terminal_checkpoint()
    s5_source_verified = verify_s5_bitcoin_core_source_feasibility_checkpoint()
    s5_history_verified = verify_s5_bitcoin_core_history_payload_checkpoint()
    s5_census_verified = verify_s5_bitcoin_core_history_census_checkpoint(
        history_verified=s5_history_verified
    )
    s5_transport_selected = verify_s5_github_transport_decision_checkpoint(
        census_verified=s5_census_verified
    )
    s5_github_preflight_verified = verify_s5_github_preflight_corrected_checkpoint(
        transport_selected=s5_transport_selected
    )
    s5_github_bulk_verified = verify_s5_github_bulk_acquisition_checkpoint(
        preflight_verified=s5_github_preflight_verified
    )
    try:
        acquisition_preflight = PeriodicFlowAcquisitionPreflightResult.model_validate(
            read_json(Q1_FULL_DEVELOPMENT_PREFLIGHT_RESULT_PATH)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        acquisition_preflight = None
    if not research_ready:
        next_action = "Restore canonical readiness source integrity and close every research gate."
    elif s5_github_bulk_verified:
        next_action = S5_GITHUB_BULK_NEXT
    elif s5_github_preflight_verified:
        next_action = S5_GITHUB_PREFLIGHT_NEXT
    elif s5_transport_selected:
        next_action = S5_GITHUB_TRANSPORT_NEXT
    elif s5_census_verified:
        next_action = S5_CENSUS_NEXT
    elif s5_history_verified:
        next_action = S5_HISTORY_NEXT
    elif s5_source_verified:
        next_action = S5_SOURCE_NEXT
    elif s4_terminal_verified:
        next_action = S4_VIABILITY_NEXT
    elif s4_checkpoint_verified:
        next_action = S4_NEXT_AUTHORIZATION
    elif s3_terminal_verified:
        next_action = S3_DISTINCT_SUCCESSOR_AUTHORIZATION
    elif s3_checkpoint_verified:
        next_action = S3_NEXT_AUTHORIZATION
    elif s2_checkpoint_verified:
        next_action = S2_TERMINAL_NEXT_ACTION
    else:
        next_action = (
            "Restore and independently verify the terminal S2 development evidence "
            "before any successor research action."
        )
    response = StrategyFactoryReadinessResponse(
        status=(
            "STRATEGY_FACTORY_BLOCKED"
            if not research_ready
            else (
                "S5_GITHUB_METADATA_NORMALIZATION_AND_COMPLETENESS_PROTOCOL_REQUIRED"
                if s5_github_bulk_verified
                else (
                    "S5_GITHUB_METADATA_BULK_ACQUISITION_PROTOCOL_REQUIRED"
                    if s5_github_preflight_verified
                    else (
                        "S5_GITHUB_PULL_REQUEST_METADATA_PREFLIGHT_PROTOCOL_REQUIRED"
                        if s5_transport_selected
                        else (
                            "S5_GITHUB_PULL_REQUEST_METADATA_TRANSPORT_DECISION_REQUIRED"
                            if s5_census_verified
                            else (
                                "S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_PROTOCOL_REQUIRED"
                                if s5_history_verified
                                else (
                                    "S5_BITCOIN_CORE_HISTORY_PAYLOAD_PROTOCOL_REQUIRED"
                                    if s5_source_verified
                                    else (
                                        "S4_PROTOCOL_DESIGN_INFEASIBLE_RETIRED"
                                        if s4_terminal_verified
                                        else (
                                            "S4_ETP_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL_REQUIRED"
                                            if s4_checkpoint_verified
                                            else (
                                                "S3_CFTC_SOURCE_FEASIBILITY_NOT_ESTABLISHED_RETIRED"
                                                if s3_terminal_verified
                                                else (
                                                    "S3_CFTC_POINT_IN_TIME_SOURCE_FEASIBILITY_PROTOCOL_REQUIRED"
                                                    if s3_checkpoint_verified
                                                    else (
                                                        "S2_DEVELOPMENT_BACKTEST_FAILED_RETIRED"
                                                        if s2_checkpoint_verified
                                                        else "S2_TERMINAL_EVIDENCE_UNVERIFIED"
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        ),
        decision=current.decision,
        strategy_research_ready=research_ready,
        paper_operation_ready=False,
        sandbox_strategy_use_ready=False,
        production_ready=False,
        live_ready=False,
        source_integrity_verified=source_integrity,
        active_research_checkpoint=(
            "S5_GITHUB_METADATA_BULK_ACQUISITION_PASSED"
            if s5_github_bulk_verified
            else (
                "S5_GITHUB_METADATA_PREFLIGHT_PASSED_AFTER_LOCAL_CORRECTION"
                if s5_github_preflight_verified
                else (
                    "S5_GITHUB_PULL_REQUEST_METADATA_TRANSPORT_SELECTED"
                    if s5_transport_selected
                    else (
                        "S5_BITCOIN_CORE_HISTORY_COMPLETENESS_CENSUS_PASSED"
                        if s5_census_verified
                        else (
                            "S5_BITCOIN_CORE_HISTORY_PAYLOAD_PASSED"
                            if s5_history_verified
                            else (
                                "S5_BITCOIN_CORE_SOURCE_METADATA_FEASIBILITY_PASSED"
                                if s5_source_verified
                                else (
                                    "S4_PROTOCOL_DESIGN_INFEASIBLE_RETIRED"
                                    if s4_terminal_verified
                                    else (
                                        "S4_SPOT_BITCOIN_ETP_CHARTER_PASSED"
                                        if s4_checkpoint_verified
                                        else (
                                            "S3_CFTC_SOURCE_FEASIBILITY_NOT_ESTABLISHED_RETIRED"
                                            if s3_terminal_verified
                                            else (
                                                "S3_CFTC_POSITIONING_CHARTER_PASSED"
                                                if s3_checkpoint_verified
                                                else (
                                                    "S2_DEVELOPMENT_BACKTEST_FAILED_RETIRED"
                                                    if s2_checkpoint_verified
                                                    else (
                                                        "S2_DEVELOPMENT_BACKTEST_TERMINAL_EVIDENCE_REQUIRED"
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        ),
        research_checkpoint_verified=(
            s5_github_preflight_verified
            or s5_transport_selected
            or s5_census_verified
            or s5_history_verified
            or s5_source_verified
            or s4_terminal_verified
            or s4_checkpoint_verified
            or s3_terminal_verified
            or s3_checkpoint_verified
        ),
        acquisition_preflight_ready=(
            acquisition_preflight is not None
            and acquisition_preflight.additional_free_disk_bytes_required == 0
        ),
        acquisition_preflight_decision=(
            "UNAVAILABLE" if acquisition_preflight is None else acquisition_preflight.decision
        ),
        acquisition_free_disk_bytes_observed=(
            0 if acquisition_preflight is None else acquisition_preflight.free_disk_bytes
        ),
        acquisition_required_free_disk_bytes=(
            0 if acquisition_preflight is None else acquisition_preflight.required_free_disk_bytes
        ),
        acquisition_additional_free_disk_bytes_required=(
            0
            if acquisition_preflight is None
            else acquisition_preflight.additional_free_disk_bytes_required
        ),
        passed_gate_count=current.passed_gate_count,
        partial_gate_count=current.partial_gate_count,
        failed_gate_count=current.failed_gate_count,
        research_blocking_gate_ids=([] if research_ready else current.research_blocking_gate_ids),
        downstream_partial_gate_ids=downstream_partial,
        qualified_strategy_count=0,
        enable_eligible_strategy_count=enable_eligible_count,
        real_net_profit_usd="0",
        next_action=next_action,
        current_result_evidence_hash=current.result_evidence_hash,
        baseline_result_evidence_hash=baseline.result_evidence_hash,
        contract_evidence_hash=contract.contract_evidence_hash,
        evaluated_at=current.evaluated_at.isoformat(),
        gate_results=[gate.model_dump(mode="json") for gate in current.gate_results],
        strategy_lifecycle=strategy_lifecycle,
        limitations=list(current.limitations),
    )
    response.active_research_checkpoint = (
        S5_MEASUREMENT_CHECKPOINT if measurement_verified else "S5_MEASUREMENT_EVIDENCE_UNVERIFIED"
    )
    response.research_checkpoint_verified = measurement_verified
    if research_ready:
        response.status = S5_MEASUREMENT_CHECKPOINT
        response.next_action = S5_MEASUREMENT_NEXT
    elif not measurement_verified:
        response.next_action = (
            "Restore and independently verify the S5 amended measurement evidence."
        )
    return response


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def source_evidence_integrity(
    evidence: StrategyFactoryReadinessResult | StrategyFactoryContract,
) -> bool:
    sources = (
        evidence.source_evidence
        if isinstance(evidence, StrategyFactoryContract)
        else [source for gate in evidence.gate_results for source in gate.source_evidence]
    )
    for source in sources:
        path = PROJECT_ROOT / source.path
        if not path.is_file() or path.stat().st_size != source.byte_count:
            return False
        if sha256(path.read_bytes()).hexdigest() != source.file_sha256:
            return False
    return True


def verify_s1_btc_source_checkpoint() -> bool:
    try:
        protocol = S1BtcSourceAcquisitionProtocol.model_validate(
            read_json(S1_BTC_SOURCE_PROTOCOL_PATH)
        )
        audit = S1BtcSourceAcquisitionProtocolAudit.model_validate(
            read_json(S1_BTC_SOURCE_PROTOCOL_AUDIT_PATH)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    return (
        sha256(S1_BTC_SOURCE_PROTOCOL_PATH.read_bytes()).hexdigest() == audit.protocol_file_sha256
        and protocol.protocol_evidence_hash == audit.protocol_evidence_hash
        and protocol.builder_contract_hash == audit.builder_contract_hash
        and protocol.preregistration_evidence_hash == audit.preregistration_evidence_hash
        and protocol.preregistration_audit_evidence_hash
        == audit.preregistration_audit_evidence_hash
        and protocol.next_authorization == S1_BTC_SOURCE_NEXT
        and audit.next_authorization == S1_BTC_SOURCE_NEXT
        and protocol.authorizes_runner_implementation is True
        and protocol.authorizes_network_acquisition_now is False
        and audit.network_requests_observed == 0
        and audit.payload_bytes_observed == 0
        and audit.btc_market_values_read == 0
        and audit.returns_calculated == 0
    )


def verify_s1_1_terminal_checkpoint() -> bool:
    try:
        result = S11DevelopmentOutcomeResult.model_validate(read_json(S1_1_OUTCOME_RESULT_PATH))
        audit = S11DevelopmentOutcomeAudit.model_validate(read_json(S1_1_OUTCOME_AUDIT_PATH))
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    ledger_path = PROJECT_ROOT / result.outcome_ledger_path
    return (
        sha256(S1_1_OUTCOME_RESULT_PATH.read_bytes()).hexdigest() == audit.result_file_sha256
        and result.result_evidence_hash == audit.result_evidence_hash
        and result.protocol_evidence_hash == audit.protocol_evidence_hash
        and result.execution_contract_evidence_hash == audit.execution_contract_evidence_hash
        and result.runner_contract_hash == audit.runner_contract_hash
        and ledger_path.is_file()
        and sha256(ledger_path.read_bytes()).hexdigest() == audit.outcome_ledger_file_sha256
        and result.decision == "STOP_S1_1_DEVELOPMENT_OUTCOME_FAILED"
        and result.next_authorization == "NONE_S1_1_DEVELOPMENT_OUTCOME_FAILED"
        and audit.decision == "CONFIRM_S1_1_DEVELOPMENT_OUTCOME_FAILED"
        and result.failed_primary_gate_count == 5
        and result.diagnostic_promotion_count == 0
        and result.validation_values_read == 0
        and result.holdout_values_read == 0
        and result.orders_submitted == 0
    )


def verify_s1_post_failure_checkpoint() -> bool:
    if not verify_s1_1_terminal_checkpoint():
        return False
    try:
        outcome = S11DevelopmentOutcomeResult.model_validate(read_json(S1_1_OUTCOME_RESULT_PATH))
        result = S1PostFailureAnalysisResult.model_validate(
            read_json(S1_FAILURE_ANALYSIS_RESULT_PATH)
        )
        audit = S1PostFailureAnalysisAudit.model_validate(read_json(S1_FAILURE_ANALYSIS_AUDIT_PATH))
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    return (
        sha256(S1_FAILURE_ANALYSIS_RESULT_PATH.read_bytes()).hexdigest() == audit.result_file_sha256
        and result.result_evidence_hash == audit.result_evidence_hash
        and result.protocol_evidence_hash == audit.protocol_evidence_hash
        and result.execution_contract_evidence_hash == audit.execution_contract_evidence_hash
        and result.runner_contract_hash == audit.runner_contract_hash
        and result.outcome_result_file_sha256
        == sha256(S1_1_OUTCOME_RESULT_PATH.read_bytes()).hexdigest()
        and result.outcome_result_evidence_hash == outcome.result_evidence_hash
        and result.outcome_ledger_file_sha256 == outcome.outcome_ledger_file_sha256
        and result.decision == "RETIRE_S1_MACRO_FINANCIAL_CONDITIONS_NO_RESCUE"
        and result.next_authorization == "AUTHORIZE_S2_DISTINCT_MECHANISM_CHARTER_ONLY"
        and audit.decision == "CONFIRM_S1_RETIRED_NO_RESCUE"
        and len(result.analysis_ids) == 7
        and len(result.primary_failed_gate_ids) == 5
        and result.new_market_data_values_read == 0
        and result.new_candidate_definitions_created == 0
        and result.parameter_variants_evaluated == 0
        and result.validation_values_read == 0
        and result.holdout_values_read == 0
        and result.diagnostic_promotion_count == 0
        and result.orders_submitted == 0
    )


def verify_s2_onchain_settlement_checkpoint() -> bool:
    if not verify_s1_post_failure_checkpoint():
        return False
    try:
        charter = S2OnchainSettlementCharter.model_validate(read_json(S2_ONCHAIN_CHARTER_PATH))
        audit = S2OnchainSettlementCharterAudit.model_validate(
            read_json(S2_ONCHAIN_CHARTER_AUDIT_PATH)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    predecessor_integrity = all(
        (PROJECT_ROOT / binding.path).is_file()
        and sha256((PROJECT_ROOT / binding.path).read_bytes()).hexdigest() == binding.file_sha256
        for binding in charter.predecessor_bindings
    )
    return (
        predecessor_integrity
        and sha256(S2_ONCHAIN_CHARTER_PATH.read_bytes()).hexdigest() == audit.charter_file_sha256
        and charter.charter_evidence_hash == audit.charter_evidence_hash
        and charter.builder_contract_hash == audit.builder_contract_hash
        and charter.decision == S2_CHARTER_DECISION
        and charter.next_authorization == S2_NEXT_AUTHORIZATION
        and audit.next_authorization == S2_NEXT_AUTHORIZATION
        and audit.reconstructed_exactly is True
        and len(charter.research_sources) == 6
        and len(charter.partitions) == 5
        and charter.market_numeric_fields_inspected == ()
        and charter.blockchain_numeric_fields_inspected == ()
        and charter.exact_parameters_defined == ()
        and charter.return_metrics_calculated == ()
        and charter.strategy_candidates_created == 0
        and charter.strategy_executions == 0
        and charter.orders_submitted == 0
        and charter.authorizes_bigquery_numeric_queries is False
        and charter.authorizes_market_value_access is False
        and charter.authorizes_payload_acquisition is False
        and charter.authorizes_return_testing is False
        and charter.authorizes_paper is False
        and charter.authorizes_testnet_strategy_orders is False
        and charter.authorizes_production is False
        and charter.authorizes_live is False
    )


def verify_s2_bigquery_feasibility_checkpoint() -> bool:
    if not verify_s2_onchain_settlement_checkpoint():
        return False
    try:
        protocol = S2BigQueryFeasibilityProtocol.model_validate(
            read_json(S2_BIGQUERY_PROTOCOL_PATH)
        )
        protocol_audit = S2BigQueryFeasibilityProtocolAudit.model_validate(
            read_json(S2_BIGQUERY_PROTOCOL_AUDIT_PATH)
        )
        result = S2BigQueryFeasibilityResult.model_validate(read_json(S2_BIGQUERY_RESULT_PATH))
        audit = S2BigQueryFeasibilityAudit.model_validate(read_json(S2_BIGQUERY_AUDIT_PATH))
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    source_integrity = all(
        (PROJECT_ROOT / binding.path).is_file()
        and sha256((PROJECT_ROOT / binding.path).read_bytes()).hexdigest() == binding.file_sha256
        for binding in protocol.source_bindings
    )
    return (
        source_integrity
        and sha256(S2_BIGQUERY_PROTOCOL_PATH.read_bytes()).hexdigest()
        == protocol_audit.protocol_file_sha256
        and protocol.protocol_evidence_hash == protocol_audit.protocol_evidence_hash
        and sha256(S2_BIGQUERY_RESULT_PATH.read_bytes()).hexdigest() == audit.result_file_sha256
        and result.result_evidence_hash == audit.result_evidence_hash
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.protocol_audit_evidence_hash == protocol_audit.audit_evidence_hash
        and result.runner_contract_hash == audit.runner_contract_hash
        and result.decision == S2_FEASIBILITY_BLOCK_METADATA
        and audit.decision == S2_FEASIBILITY_BLOCK_METADATA
        and result.next_authorization == S2_FEASIBILITY_RETRY
        and audit.next_authorization == S2_FEASIBILITY_RETRY
        and result.metadata_request_count == 3
        and all(item.http_status == 401 for item in result.metadata_attempts)
        and result.gcloud_available is False
        and result.bq_available is False
        and result.active_project_configured is False
        and result.sandbox_without_billing_verified is False
        and result.dry_run_request_count == 0
        and result.query_execution_count == 0
        and result.query_result_rows_returned == 0
        and result.blockchain_row_values_read == 0
        and result.market_values_read == 0
        and result.payload_bytes_acquired == 0
        and result.returns_calculated == 0
        and result.orders_submitted == 0
        and audit.response_artifact_count == 0
    )


def verify_s2_bigquery_feasibility_amendment_v2() -> bool:
    if not verify_s2_bigquery_feasibility_checkpoint():
        return False
    try:
        protocol = S2BigQueryFeasibilityProtocolV2.model_validate(
            read_json(S2_BIGQUERY_PROTOCOL_V2_PATH)
        )
        protocol_audit = S2BigQueryFeasibilityProtocolAuditV2.model_validate(
            read_json(S2_BIGQUERY_PROTOCOL_AUDIT_V2_PATH)
        )
        prior_result = S2BigQueryFeasibilityResult.model_validate(
            read_json(S2_BIGQUERY_RESULT_PATH)
        )
        prior_audit = S2BigQueryFeasibilityAudit.model_validate(read_json(S2_BIGQUERY_AUDIT_PATH))
        result = S2BigQueryFeasibilityResultV2.model_validate(read_json(S2_BIGQUERY_RESULT_V2_PATH))
        audit = S2BigQueryFeasibilityAuditV2.model_validate(read_json(S2_BIGQUERY_AUDIT_V2_PATH))
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    source_integrity = all(
        (PROJECT_ROOT / binding.path).is_file()
        and sha256((PROJECT_ROOT / binding.path).read_bytes()).hexdigest() == binding.file_sha256
        for binding in protocol.source_bindings
    )
    response_integrity = all(
        attempt.response_path is not None
        and (PROJECT_ROOT / attempt.response_path).is_file()
        and (PROJECT_ROOT / attempt.response_path).stat().st_size == attempt.response_bytes
        and sha256((PROJECT_ROOT / attempt.response_path).read_bytes()).hexdigest()
        == attempt.response_sha256
        for attempt in result.metadata_attempts
    )
    return (
        source_integrity
        and response_integrity
        and sha256(S2_BIGQUERY_PROTOCOL_V2_PATH.read_bytes()).hexdigest()
        == protocol_audit.protocol_file_sha256
        and protocol.protocol_evidence_hash == protocol_audit.protocol_evidence_hash
        and protocol.charter_evidence_hash == protocol_audit.charter_evidence_hash
        and protocol.prior_result_evidence_hash == prior_result.result_evidence_hash
        and protocol.prior_result_evidence_hash == protocol_audit.prior_result_evidence_hash
        and protocol.prior_result_audit_evidence_hash == prior_audit.audit_evidence_hash
        and protocol_audit.builder_contract_hash == protocol.builder_contract_hash
        and protocol_audit.reconstructed_exactly is True
        and protocol_audit.network_requests_observed == 0
        and sha256(S2_BIGQUERY_RESULT_V2_PATH.read_bytes()).hexdigest() == audit.result_file_sha256
        and result.result_evidence_hash == audit.result_evidence_hash
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.protocol_audit_evidence_hash == protocol_audit.audit_evidence_hash
        and result.prior_result_evidence_hash == prior_result.result_evidence_hash
        and result.prior_result_audit_evidence_hash == prior_audit.audit_evidence_hash
        and result.runner_contract_hash == audit.runner_contract_hash
        and result.decision == S2_FEASIBILITY_V2_BLOCK_DRY_RUN
        and audit.decision == S2_FEASIBILITY_V2_BLOCK_DRY_RUN
        and result.next_authorization == S2_FEASIBILITY_V2_RETRY
        and audit.next_authorization == S2_FEASIBILITY_V2_RETRY
        and result.active_auth_configured is True
        and result.active_project_configured is True
        and result.sandbox_without_billing_verified is True
        and result.billing_boundary_request_count == 1
        and result.access_token_request_count == 1
        and result.metadata_request_count == 3
        and all(item.error_class == "NONE" for item in result.metadata_attempts)
        and result.dry_run_request_count == 1
        and result.dry_run_attempts[0].error_class == "API_ERROR"
        and audit.response_artifact_count == 3
        and audit.response_artifacts_verified is True
        and audit.result_reconstructed_exactly is True
        and protocol.account_identifier_persistence_permitted is False
        and protocol.project_identifier_persistence_permitted is False
        and protocol.credential_or_token_persistence_permitted is False
        and protocol.query_result_rows_permitted == 0
        and protocol.blockchain_row_values_permitted is False
        and protocol.market_values_permitted is False
        and protocol.payload_acquisition_permitted is False
        and protocol.returns_permitted is False
        and protocol.orders_permitted is False
        and protocol.production_permitted is False
        and protocol.live_permitted is False
        and result.query_execution_count == 0
        and result.query_result_rows_returned == 0
        and result.blockchain_row_values_read == 0
        and result.market_values_read == 0
        and result.payload_bytes_acquired == 0
        and result.returns_calculated == 0
        and result.orders_submitted == 0
    )


def verify_s2_bigquery_feasibility_amendment_v3() -> bool:
    if not verify_s2_bigquery_feasibility_amendment_v2():
        return False
    try:
        protocol = S2BigQueryFeasibilityProtocolV3.model_validate(
            read_json(S2_BIGQUERY_PROTOCOL_V3_PATH)
        )
        protocol_audit = S2BigQueryFeasibilityProtocolAuditV3.model_validate(
            read_json(S2_BIGQUERY_PROTOCOL_AUDIT_V3_PATH)
        )
        prior_result = S2BigQueryFeasibilityResultV2.model_validate(
            read_json(S2_BIGQUERY_RESULT_V2_PATH)
        )
        prior_audit = S2BigQueryFeasibilityAuditV2.model_validate(
            read_json(S2_BIGQUERY_AUDIT_V2_PATH)
        )
        result = S2BigQueryFeasibilityResultV3.model_validate(read_json(S2_BIGQUERY_RESULT_V3_PATH))
        audit = S2BigQueryFeasibilityAuditV3.model_validate(read_json(S2_BIGQUERY_AUDIT_V3_PATH))
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    source_integrity = all(
        (PROJECT_ROOT / binding.path).is_file()
        and sha256((PROJECT_ROOT / binding.path).read_bytes()).hexdigest() == binding.file_sha256
        for binding in protocol.source_bindings
    )
    return (
        source_integrity
        and sha256(S2_BIGQUERY_PROTOCOL_V3_PATH.read_bytes()).hexdigest()
        == protocol_audit.protocol_file_sha256
        and protocol.protocol_evidence_hash == protocol_audit.protocol_evidence_hash
        and protocol.prior_result_evidence_hash == prior_result.result_evidence_hash
        and protocol.prior_result_audit_evidence_hash == prior_audit.audit_evidence_hash
        and protocol.prior_result_evidence_hash == protocol_audit.prior_result_evidence_hash
        and protocol.prior_result_audit_evidence_hash
        == protocol_audit.prior_result_audit_evidence_hash
        and protocol.builder_contract_hash == protocol_audit.builder_contract_hash
        and protocol_audit.reconstructed_exactly is True
        and protocol_audit.network_requests_observed == 0
        and sha256(S2_BIGQUERY_RESULT_V3_PATH.read_bytes()).hexdigest() == audit.result_file_sha256
        and result.result_evidence_hash == audit.result_evidence_hash
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.protocol_audit_evidence_hash == protocol_audit.audit_evidence_hash
        and result.prior_result_evidence_hash == prior_result.result_evidence_hash
        and result.prior_result_audit_evidence_hash == prior_audit.audit_evidence_hash
        and result.runner_contract_hash == audit.runner_contract_hash
        and result.decision == S2_FEASIBILITY_V3_PASS
        and audit.decision == S2_FEASIBILITY_V3_PASS
        and result.next_authorization == S2_FEASIBILITY_V3_NEXT
        and audit.next_authorization == S2_FEASIBILITY_V3_NEXT
        and result.active_auth_configured is True
        and result.active_project_configured is True
        and result.sandbox_without_billing_verified is True
        and result.billing_boundary_request_count == 1
        and result.access_token_request_count == 1
        and result.access_token_available is True
        and result.reused_metadata_artifact_count == 3
        and result.rest_dry_run_request_count == 2
        and all(item.succeeded for item in result.rest_dry_run_attempts)
        and all(item.error_class == "NONE" for item in result.rest_dry_run_attempts)
        and result.response_bodies_persisted == 0
        and result.query_execution_count == 0
        and result.query_result_rows_returned == 0
        and result.blockchain_row_values_read == 0
        and result.market_values_read == 0
        and result.payload_bytes_acquired == 0
        and result.parameters_defined == 0
        and result.returns_calculated == 0
        and result.candidates_created == 0
        and result.orders_submitted == 0
        and audit.source_artifact_count == 8
        and audit.source_artifacts_verified is True
        and audit.result_reconstructed_exactly is True
        and audit.identifiers_observed_in_artifacts == 0
        and audit.credentials_or_tokens_observed_in_artifacts == 0
        and audit.response_bodies_persisted == 0
        and audit.query_result_rows_returned == 0
        and audit.blockchain_row_values_read == 0
        and audit.market_values_read == 0
        and audit.orders_submitted == 0
        and result.authorizes_numeric_query is False
        and result.authorizes_payload_acquisition is False
        and result.authorizes_returns is False
        and result.authorizes_paper is False
        and result.authorizes_testnet_strategy_orders is False
        and result.authorizes_production is False
        and result.authorizes_live is False
    )


def verify_s2_development_payload_checkpoint() -> bool:
    if not verify_s2_bigquery_feasibility_amendment_v3():
        return False
    try:
        protocol_v1 = S2BigQueryPayloadProtocol.model_validate(read_json(S2_PAYLOAD_PROTOCOL_PATH))
        protocol_audit_v1 = S2BigQueryPayloadProtocolAudit.model_validate(
            read_json(S2_PAYLOAD_PROTOCOL_AUDIT_PATH)
        )
        result_v1 = S2BigQueryPayloadResult.model_validate(read_json(S2_PAYLOAD_RESULT_PATH))
        failure_audit_v1 = S2BigQueryPayloadFailureAuditV1.model_validate(
            read_json(S2_PAYLOAD_FAILURE_AUDIT_PATH)
        )
        protocol_v2 = S2BigQueryPayloadProtocolV2.model_validate(
            read_json(S2_PAYLOAD_PROTOCOL_V2_PATH)
        )
        protocol_audit_v2 = S2BigQueryPayloadProtocolAuditV2.model_validate(
            read_json(S2_PAYLOAD_PROTOCOL_AUDIT_V2_PATH)
        )
        result_v2 = S2BigQueryPayloadResultV2.model_validate(read_json(S2_PAYLOAD_RESULT_V2_PATH))
        audit_v2 = S2BigQueryPayloadAuditV2.model_validate(read_json(S2_PAYLOAD_AUDIT_V2_PATH))
        payload = S2DevelopmentWeeklyPayload.model_validate(read_json(S2_DEVELOPMENT_PAYLOAD_PATH))
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    source_integrity = all(
        (PROJECT_ROOT / binding.path).is_file()
        and sha256((PROJECT_ROOT / binding.path).read_bytes()).hexdigest() == binding.file_sha256
        for protocol in (protocol_v1, protocol_v2)
        for binding in protocol.source_bindings
    )
    payload_file_sha256 = sha256(S2_DEVELOPMENT_PAYLOAD_PATH.read_bytes()).hexdigest()
    return (
        source_integrity
        and sha256(S2_PAYLOAD_PROTOCOL_PATH.read_bytes()).hexdigest()
        == protocol_audit_v1.protocol_file_sha256
        and protocol_v1.protocol_evidence_hash == protocol_audit_v1.protocol_evidence_hash
        and protocol_v1.feasibility_result_evidence_hash
        == protocol_audit_v1.feasibility_result_evidence_hash
        and protocol_audit_v1.reconstructed_exactly is True
        and protocol_audit_v1.network_requests_observed == 0
        and sha256(S2_PAYLOAD_RESULT_PATH.read_bytes()).hexdigest()
        == failure_audit_v1.result_file_sha256
        and result_v1.result_evidence_hash == failure_audit_v1.result_evidence_hash
        and result_v1.protocol_evidence_hash == protocol_v1.protocol_evidence_hash
        and result_v1.protocol_audit_evidence_hash == protocol_audit_v1.audit_evidence_hash
        and result_v1.decision == S2_PAYLOAD_BLOCK_VALIDATION
        and result_v1.blockers == ("payload_schema_mismatch",)
        and result_v1.query_submission_count == 1
        and result_v1.query_completed is True
        and result_v1.query_result_rows_returned == 0
        and result_v1.blockchain_row_values_read == 0
        and result_v1.payload_path is None
        and result_v1.payload_byte_count == 0
        and failure_audit_v1.result_reconstructed_exactly is True
        and failure_audit_v1.query_result_rows_accepted == 0
        and failure_audit_v1.payload_bytes_persisted == 0
        and failure_audit_v1.blocker == "payload_schema_mismatch"
        and sha256(S2_PAYLOAD_PROTOCOL_V2_PATH.read_bytes()).hexdigest()
        == protocol_audit_v2.protocol_file_sha256
        and protocol_v2.protocol_evidence_hash == protocol_audit_v2.protocol_evidence_hash
        and protocol_v2.prior_payload_protocol_evidence_hash == protocol_v1.protocol_evidence_hash
        and protocol_v2.prior_payload_protocol_audit_evidence_hash
        == protocol_audit_v1.audit_evidence_hash
        and protocol_v2.prior_payload_result_evidence_hash == result_v1.result_evidence_hash
        and protocol_v2.prior_payload_failure_audit_evidence_hash
        == failure_audit_v1.audit_evidence_hash
        and protocol_audit_v2.prior_payload_result_evidence_hash == result_v1.result_evidence_hash
        and protocol_audit_v2.prior_payload_failure_audit_evidence_hash
        == failure_audit_v1.audit_evidence_hash
        and protocol_audit_v2.reconstructed_exactly is True
        and protocol_audit_v2.network_requests_observed == 0
        and sha256(S2_PAYLOAD_RESULT_V2_PATH.read_bytes()).hexdigest()
        == audit_v2.result_file_sha256
        and result_v2.result_evidence_hash == audit_v2.result_evidence_hash
        and result_v2.protocol_evidence_hash == protocol_v2.protocol_evidence_hash
        and result_v2.protocol_audit_evidence_hash == protocol_audit_v2.audit_evidence_hash
        and result_v2.prior_payload_result_evidence_hash == result_v1.result_evidence_hash
        and result_v2.prior_payload_failure_audit_evidence_hash
        == failure_audit_v1.audit_evidence_hash
        and result_v2.decision == S2_PAYLOAD_PASS
        and audit_v2.decision == S2_PAYLOAD_PASS
        and result_v2.next_authorization == S2_PAYLOAD_NEXT
        and audit_v2.next_authorization == S2_PAYLOAD_NEXT
        and result_v2.query_submission_count == 1
        and result_v2.query_result_poll_count == 0
        and result_v2.query_result_page_count == 1
        and result_v2.query_completed is True
        and result_v2.total_bytes_processed == 46_852_212_436
        and result_v2.query_result_rows_returned == 280
        and result_v2.blockchain_row_values_read == 280
        and result_v2.payload_path == "data/evidence/s2_development_weekly_payload_v1.json"
        and result_v2.payload_file_sha256 == payload_file_sha256
        and result_v2.payload_evidence_hash == payload.payload_evidence_hash
        and result_v2.payload_byte_count == S2_DEVELOPMENT_PAYLOAD_PATH.stat().st_size
        and result_v2.payload_byte_count == 94_662
        and payload.protocol_evidence_hash == protocol_v2.protocol_evidence_hash
        and payload.query_sha256 == protocol_v2.query_spec.query_sha256
        and payload.row_count == len(payload.rows) == 280
        and audit_v2.payload_file_sha256 == payload_file_sha256
        and audit_v2.payload_evidence_hash == payload.payload_evidence_hash
        and audit_v2.payload_byte_count == result_v2.payload_byte_count
        and audit_v2.payload_row_count == payload.row_count
        and audit_v2.source_artifacts_verified is True
        and audit_v2.payload_reconstructed_exactly is True
        and audit_v2.result_reconstructed_exactly is True
        and result_v2.authorizes_measurement_protocol is True
        and result_v2.authorizes_parameters is False
        and result_v2.authorizes_returns is False
        and result_v2.authorizes_paper is False
        and result_v2.authorizes_testnet_strategy_orders is False
        and result_v2.authorizes_production is False
        and result_v2.authorizes_live is False
        and result_v2.market_values_read == 0
        and result_v2.parameters_defined == 0
        and result_v2.returns_calculated == 0
        and result_v2.candidates_created == 0
        and result_v2.signals_generated == 0
        and result_v2.orders_submitted == 0
        and result_v2.real_net_profit_usd == "0"
    )


def verify_s2_development_measurement_protocol_checkpoint() -> bool:
    if not verify_s2_development_payload_checkpoint():
        return False
    try:
        protocol = S2DevelopmentMeasurementProtocol.model_validate(
            read_json(S2_MEASUREMENT_PROTOCOL_PATH)
        )
        audit = S2DevelopmentMeasurementProtocolAudit.model_validate(
            read_json(S2_MEASUREMENT_PROTOCOL_AUDIT_PATH)
        )
        payload_result = S2BigQueryPayloadResultV2.model_validate(
            read_json(S2_PAYLOAD_RESULT_V2_PATH)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    source_integrity = all(
        (PROJECT_ROOT / binding.path).is_file()
        and sha256((PROJECT_ROOT / binding.path).read_bytes()).hexdigest() == binding.file_sha256
        for binding in protocol.source_bindings
    )
    payload_file_sha256 = sha256(S2_DEVELOPMENT_PAYLOAD_PATH.read_bytes()).hexdigest()
    return (
        source_integrity
        and sha256(S2_MEASUREMENT_PROTOCOL_PATH.read_bytes()).hexdigest()
        == audit.protocol_file_sha256
        and protocol.protocol_evidence_hash == audit.protocol_evidence_hash
        and protocol.builder_contract_hash == audit.builder_contract_hash
        and protocol.payload_result_evidence_hash == payload_result.result_evidence_hash
        and protocol.payload_file_sha256 == payload_result.payload_file_sha256
        and protocol.payload_file_sha256 == payload_file_sha256
        and protocol.payload_evidence_hash == payload_result.payload_evidence_hash
        and protocol.payload_bytes_hashed_during_freeze
        == S2_DEVELOPMENT_PAYLOAD_PATH.stat().st_size
        and protocol.payload_bytes_hashed_during_freeze == 94_662
        and protocol.payload_value_rows_parsed_during_freeze == 0
        and protocol.input_row_count == 280
        and protocol.warmup_input_rows == 7
        and protocol.expected_measurement_row_count == 273
        and protocol.measurement_count == len(protocol.measurement_definitions) == 7
        and protocol.future_strategy_family_budget == 1
        and protocol.future_candidate_budget == 1
        and protocol.future_parameter_combination_budget == 1
        and protocol.strategy_parameters_defined == ()
        and protocol.strategy_rules_defined == ()
        and protocol.decision == S2_MEASUREMENT_DECISION
        and protocol.next_authorization == S2_MEASUREMENT_NEXT
        and protocol.authorizes_measurement_runner_implementation is True
        and protocol.authorizes_payload_value_read_now is False
        and protocol.authorizes_measurement_calculation_now is False
        and protocol.authorizes_strategy_parameter_definition is False
        and protocol.authorizes_market_value_access is False
        and protocol.authorizes_return_testing is False
        and protocol.authorizes_validation_access is False
        and protocol.authorizes_holdout_access is False
        and protocol.authorizes_strategy_candidate is False
        and protocol.authorizes_pine is False
        and protocol.authorizes_paper is False
        and protocol.authorizes_testnet_strategy_orders is False
        and protocol.authorizes_production is False
        and protocol.authorizes_live is False
        and audit.payload_file_sha256 == payload_file_sha256
        and audit.payload_evidence_hash == protocol.payload_evidence_hash
        and audit.source_binding_count == len(protocol.source_bindings) == 15
        and audit.payload_bytes_hashed == protocol.payload_bytes_hashed_during_freeze
        and audit.payload_value_rows_parsed == 0
        and audit.measurement_definition_count == protocol.measurement_count
        and audit.expected_measurement_row_count == protocol.expected_measurement_row_count
        and audit.reconstructed_exactly is True
        and audit.network_requests_observed == 0
        and audit.market_values_read == 0
        and audit.returns_calculated == 0
        and audit.strategy_candidates_created == 0
        and audit.orders_submitted == 0
        and audit.decision == S2_MEASUREMENT_AUDIT_DECISION
        and audit.next_authorization == S2_MEASUREMENT_NEXT
    )


def verify_s2_development_measurement_result_checkpoint() -> bool:
    if not verify_s2_development_measurement_protocol_checkpoint():
        return False
    try:
        protocol = S2DevelopmentMeasurementProtocol.model_validate(
            read_json(S2_MEASUREMENT_PROTOCOL_PATH)
        )
        protocol_audit = S2DevelopmentMeasurementProtocolAudit.model_validate(
            read_json(S2_MEASUREMENT_PROTOCOL_AUDIT_PATH)
        )
        addendum = S2DevelopmentMeasurementExecutionAddendum.model_validate(
            read_json(S2_MEASUREMENT_EXECUTION_ADDENDUM_PATH)
        )
        execution_audit = S2DevelopmentMeasurementExecutionAudit.model_validate(
            read_json(S2_MEASUREMENT_EXECUTION_AUDIT_PATH)
        )
        result = S2DevelopmentMeasurementResult.model_validate(
            read_json(S2_MEASUREMENT_RESULT_PATH)
        )
        audit = S2DevelopmentMeasurementResultAudit.model_validate(
            read_json(S2_MEASUREMENT_RESULT_AUDIT_PATH)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    runner_path = PROJECT_ROOT / "scripts" / "run_s2_development_measurements.py"
    dataset_file_sha256 = sha256(S2_MEASUREMENT_DATASET_PATH.read_bytes()).hexdigest()
    return (
        sha256(S2_MEASUREMENT_EXECUTION_ADDENDUM_PATH.read_bytes()).hexdigest()
        == execution_audit.addendum_file_sha256
        and addendum.addendum_evidence_hash == execution_audit.addendum_evidence_hash
        and addendum.protocol_evidence_hash == protocol.protocol_evidence_hash
        and addendum.protocol_audit_evidence_hash == protocol_audit.audit_evidence_hash
        and addendum.runner_contract_hash == execution_audit.runner_contract_hash
        and runner_path.is_file()
        and sha256(runner_path.read_bytes()).hexdigest() == addendum.runner_contract_hash
        and addendum.output_was_absent is True
        and addendum.result_was_absent is True
        and addendum.authorizes_single_measurement_run is True
        and addendum.authorizes_payload_value_read is True
        and addendum.authorizes_measurement_calculation is True
        and addendum.authorizes_strategy_parameter_definition is False
        and addendum.authorizes_market_value_access is False
        and addendum.authorizes_return_testing is False
        and addendum.authorizes_validation_access is False
        and addendum.authorizes_holdout_access is False
        and addendum.authorizes_strategy_candidate is False
        and addendum.authorizes_pine is False
        and addendum.authorizes_paper is False
        and addendum.authorizes_testnet_strategy_orders is False
        and addendum.authorizes_production is False
        and addendum.authorizes_live is False
        and execution_audit.payload_value_rows_parsed == 0
        and execution_audit.measurement_rows_calculated == 0
        and execution_audit.reconstructed_exactly is True
        and sha256(S2_MEASUREMENT_RESULT_PATH.read_bytes()).hexdigest() == audit.result_file_sha256
        and result.result_evidence_hash == audit.result_evidence_hash
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.protocol_audit_evidence_hash == protocol_audit.audit_evidence_hash
        and result.execution_addendum_evidence_hash == addendum.addendum_evidence_hash
        and result.execution_audit_evidence_hash == execution_audit.audit_evidence_hash
        and result.runner_contract_hash == addendum.runner_contract_hash
        and S2_MEASUREMENT_DATASET_PATH.is_file()
        and dataset_file_sha256 == result.measurement_dataset_file_sha256
        and S2_MEASUREMENT_DATASET_PATH.stat().st_size == result.measurement_dataset_bytes
        and result.measurement_dataset_bytes == 130_754
        and result.input_row_count == 280
        and result.measurement_row_count == 273
        and result.first_measurement_sequence == 8
        and result.last_measurement_sequence == 280
        and len(result.row_evidence_hashes) == result.measurement_row_count
        and all(gate.status == "PASS" for gate in result.gates)
        and result.decision == S2_MEASUREMENT_PASS
        and result.market_values_read == 0
        and result.strategy_parameters_defined == 0
        and result.returns_calculated == 0
        and result.strategy_candidates_created == 0
        and result.signals_generated == 0
        and result.orders_submitted == 0
        and result.authorizes_strategy_parameter_definition is False
        and result.authorizes_market_value_access is False
        and result.authorizes_return_testing is False
        and result.authorizes_validation_access is False
        and result.authorizes_holdout_access is False
        and result.authorizes_strategy_candidate is False
        and result.authorizes_pine is False
        and result.authorizes_paper is False
        and result.authorizes_testnet_strategy_orders is False
        and result.authorizes_production is False
        and result.authorizes_live is False
        and result.real_net_profit_usd == "0"
        and audit.measurement_dataset_file_sha256 == dataset_file_sha256
        and audit.runner_contract_hash == result.runner_contract_hash
        and audit.input_row_count == result.input_row_count
        and audit.measurement_row_count == result.measurement_row_count
        and audit.reconstructed_exactly is True
        and audit.market_values_read == 0
        and audit.returns_calculated == 0
        and audit.orders_submitted == 0
        and audit.next_authorization == S2_MEASUREMENT_PREREG_NEXT
    )


def verify_s2_strategy_preregistration_checkpoint() -> bool:
    if not verify_s2_development_measurement_result_checkpoint():
        return False
    try:
        protocol = S2StrategyPreregistration.model_validate(
            read_json(S2_STRATEGY_PREREGISTRATION_PATH)
        )
        audit = S2StrategyPreregistrationAudit.model_validate(
            read_json(S2_STRATEGY_PREREGISTRATION_AUDIT_PATH)
        )
        measurement_result = S2DevelopmentMeasurementResult.model_validate(
            read_json(S2_MEASUREMENT_RESULT_PATH)
        )
        measurement_audit = S2DevelopmentMeasurementResultAudit.model_validate(
            read_json(S2_MEASUREMENT_RESULT_AUDIT_PATH)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    source_integrity = all(
        (PROJECT_ROOT / binding.path).is_file()
        and sha256((PROJECT_ROOT / binding.path).read_bytes()).hexdigest() == binding.file_sha256
        for binding in protocol.source_bindings
    )
    return (
        source_integrity
        and sha256(S2_STRATEGY_PREREGISTRATION_PATH.read_bytes()).hexdigest()
        == audit.protocol_file_sha256
        and protocol.protocol_evidence_hash == audit.protocol_evidence_hash
        and protocol.builder_contract_hash == audit.builder_contract_hash
        and protocol.measurement_result_evidence_hash == measurement_result.result_evidence_hash
        and protocol.measurement_audit_evidence_hash == measurement_audit.audit_evidence_hash
        and protocol.measurement_dataset_file_sha256
        == measurement_result.measurement_dataset_file_sha256
        and protocol.measurement_dataset_bytes_hashed_during_freeze == 130_754
        and protocol.measurement_value_rows_parsed_during_freeze == 0
        and protocol.measurement_row_count == 273
        and protocol.candidate_count == 1
        and protocol.candidate.parameter_count == 0
        and protocol.candidate.parameter_combinations == 1
        and protocol.candidate.long_rule == "SETTLEMENT_DEMAND_AGREEMENT_EQ_BOTH_BROADENING"
        and protocol.required_price_date_count == 273
        and protocol.first_required_price_date == "2017-10-16"
        and protocol.last_required_price_date == "2023-01-02"
        and protocol.expected_weekly_interval_count == 272
        and protocol.base_total_cost_bps_per_fill == "15"
        and protocol.stress_total_cost_bps_per_fill == "22.5"
        and len(protocol.development_gates) == 15
        and protocol.diagnostic_candidates_permitted is False
        and protocol.outcome_driven_parameter_search_permitted is False
        and protocol.authorizes_btc_source_acquisition_now is False
        and protocol.authorizes_btc_market_value_access is False
        and protocol.authorizes_return_testing is False
        and protocol.authorizes_historical_screen_access is False
        and protocol.authorizes_validation_access is False
        and protocol.authorizes_holdout_access is False
        and protocol.authorizes_candidate_outcome is False
        and protocol.authorizes_pine is False
        and protocol.authorizes_paper is False
        and protocol.authorizes_testnet_strategy_orders is False
        and protocol.authorizes_production is False
        and protocol.authorizes_live is False
        and protocol.next_authorization == S2_STRATEGY_PREREG_NEXT
        and audit.source_binding_count == len(protocol.source_bindings) == 7
        and audit.measurement_dataset_bytes_hashed == 130_754
        and audit.measurement_value_rows_parsed == 0
        and audit.btc_market_values_read == 0
        and audit.candidate_count == 1
        and audit.parameter_combination_count == 1
        and audit.development_gate_count == 15
        and audit.reconstructed_exactly is True
        and audit.next_authorization == S2_STRATEGY_PREREG_NEXT
    )


def verify_s2_btc_source_acquisition_checkpoint() -> bool:
    if not verify_s2_strategy_preregistration_checkpoint():
        return False
    try:
        protocol = S2BtcSourceAcquisitionProtocol.model_validate(
            read_json(S2_BTC_SOURCE_PROTOCOL_PATH)
        )
        protocol_audit = S2BtcSourceAcquisitionProtocolAudit.model_validate(
            read_json(S2_BTC_SOURCE_PROTOCOL_AUDIT_PATH)
        )
        contract = S2BtcSourceExecutionContract.model_validate(
            read_json(S2_BTC_SOURCE_EXECUTION_CONTRACT_PATH)
        )
        execution_audit = S2BtcSourceExecutionAudit.model_validate(
            read_json(S2_BTC_SOURCE_EXECUTION_AUDIT_PATH)
        )
        checkpoint = S2BtcAcquisitionCheckpoint.model_validate(
            read_json(S2_BTC_SOURCE_CHECKPOINT_PATH)
        )
        result = S2BtcSourceAcquisitionResult.model_validate(read_json(S2_BTC_SOURCE_RESULT_PATH))
        result_audit = S2BtcSourceAcquisitionAudit.model_validate(
            read_json(S2_BTC_SOURCE_RESULT_AUDIT_PATH)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    protocol_file_sha256 = sha256(S2_BTC_SOURCE_PROTOCOL_PATH.read_bytes()).hexdigest()
    contract_file_sha256 = sha256(S2_BTC_SOURCE_EXECUTION_CONTRACT_PATH.read_bytes()).hexdigest()
    checkpoint_file_sha256 = sha256(S2_BTC_SOURCE_CHECKPOINT_PATH.read_bytes()).hexdigest()
    result_file_sha256 = sha256(S2_BTC_SOURCE_RESULT_PATH.read_bytes()).hexdigest()
    dataset_file_sha256 = sha256(S2_BTC_PRICE_DATASET_PATH.read_bytes()).hexdigest()
    return (
        protocol_file_sha256 == protocol_audit.protocol_file_sha256
        and contract_file_sha256 == execution_audit.contract_file_sha256
        and contract_file_sha256 == result_audit.execution_contract_file_sha256
        and checkpoint_file_sha256 == result.checkpoint_file_sha256
        and checkpoint_file_sha256 == result_audit.checkpoint_file_sha256
        and result_file_sha256 == result_audit.result_file_sha256
        and dataset_file_sha256 == result.dataset_file_sha256
        and dataset_file_sha256 == result_audit.dataset_file_sha256
        and S2_BTC_PRICE_DATASET_PATH.stat().st_size == result.dataset_bytes == 173_031
        and protocol.protocol_evidence_hash == protocol_audit.protocol_evidence_hash
        and contract.protocol_file_sha256 == protocol_file_sha256
        and contract.protocol_evidence_hash == protocol.protocol_evidence_hash
        and contract.protocol_audit_evidence_hash == protocol_audit.audit_evidence_hash
        and execution_audit.contract_evidence_hash == contract.contract_evidence_hash
        and execution_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and execution_audit.runner_contract_hash == contract.runner_contract_hash
        and checkpoint.protocol_file_sha256 == protocol_file_sha256
        and checkpoint.protocol_evidence_hash == protocol.protocol_evidence_hash
        and checkpoint.execution_contract_file_sha256 == contract_file_sha256
        and checkpoint.execution_contract_evidence_hash == contract.contract_evidence_hash
        and checkpoint.runner_contract_hash == contract.runner_contract_hash
        and result.checkpoint_evidence_hash == checkpoint.checkpoint_evidence_hash
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.execution_contract_evidence_hash == contract.contract_evidence_hash
        and result.runner_contract_hash == contract.runner_contract_hash
        and result_audit.protocol_file_sha256 == protocol_file_sha256
        and result_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result_audit.execution_contract_evidence_hash == contract.contract_evidence_hash
        and result_audit.checkpoint_evidence_hash == checkpoint.checkpoint_evidence_hash
        and result_audit.result_evidence_hash == result.result_evidence_hash
        and result_audit.runner_contract_hash == contract.runner_contract_hash
        and checkpoint.terminal is True
        and checkpoint.next_sequence is None
        and checkpoint.classified_target_count == 273
        and checkpoint.complete_target_count == 273
        and checkpoint.failed_target_count == 0
        and result.classified_target_count == 273
        and result.complete_target_count == 273
        and result.failed_target_count == 0
        and len(result.price_rows) == 273
        and len(result.gates) == 10
        and all(gate.status == "PASS" for gate in result.gates)
        and result.decision == S2_BTC_ACQUISITION_PASS
        and result.next_authorization == S2_BTC_ACQUISITION_NEXT
        and result.return_metrics_calculated == ()
        and result.historical_screen_values_read == 0
        and result.validation_values_read == 0
        and result.holdout_values_read == 0
        and result.orders_submitted == 0
        and result_audit.reconstructed_exactly is True
        and result_audit.price_rows_reconstructed == 273
        and result_audit.returns_calculated == 0
        and result_audit.strategy_outcomes_calculated == 0
        and result_audit.orders_submitted == 0
        and result_audit.lineage_next_authorization == S2_BTC_ACQUISITION_NEXT
    )


def verify_s2_development_backtest_terminal_checkpoint() -> bool:
    if not verify_s2_btc_source_acquisition_checkpoint():
        return False
    try:
        protocol = S2DevelopmentBacktestProtocol.model_validate(
            read_json(S2_BACKTEST_PROTOCOL_PATH)
        )
        protocol_audit = S2DevelopmentBacktestProtocolAudit.model_validate(
            read_json(S2_BACKTEST_PROTOCOL_AUDIT_PATH)
        )
        contract = S2DevelopmentBacktestExecutionContract.model_validate(
            read_json(S2_BACKTEST_EXECUTION_CONTRACT_PATH)
        )
        execution_audit = S2DevelopmentBacktestExecutionAudit.model_validate(
            read_json(S2_BACKTEST_EXECUTION_AUDIT_PATH)
        )
        result = S2DevelopmentBacktestResult.model_validate(read_json(S2_BACKTEST_RESULT_PATH))
        result_audit = S2DevelopmentBacktestResultAudit.model_validate(
            read_json(S2_BACKTEST_RESULT_AUDIT_PATH)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    protocol_file_sha256 = sha256(S2_BACKTEST_PROTOCOL_PATH.read_bytes()).hexdigest()
    contract_file_sha256 = sha256(S2_BACKTEST_EXECUTION_CONTRACT_PATH.read_bytes()).hexdigest()
    result_file_sha256 = sha256(S2_BACKTEST_RESULT_PATH.read_bytes()).hexdigest()
    measurement_dataset_file_sha256 = sha256(S2_MEASUREMENT_DATASET_PATH.read_bytes()).hexdigest()
    price_dataset_file_sha256 = sha256(S2_BTC_PRICE_DATASET_PATH.read_bytes()).hexdigest()
    ledger_file_sha256 = sha256(S2_BACKTEST_LEDGER_PATH.read_bytes()).hexdigest()
    failed_gate_ids = {gate.gate_id for gate in result.gate_results if gate.status == "FAIL"}
    return (
        protocol_file_sha256 == protocol_audit.protocol_file_sha256
        and contract_file_sha256 == execution_audit.contract_file_sha256
        and result_file_sha256 == result_audit.result_file_sha256
        and protocol.protocol_evidence_hash == protocol_audit.protocol_evidence_hash
        and protocol.measurement_dataset_file_sha256 == measurement_dataset_file_sha256
        and protocol.price_dataset_file_sha256 == price_dataset_file_sha256
        and protocol.source_result_file_sha256
        == sha256(S2_BTC_SOURCE_RESULT_PATH.read_bytes()).hexdigest()
        and protocol.source_audit_file_sha256
        == sha256(S2_BTC_SOURCE_RESULT_AUDIT_PATH.read_bytes()).hexdigest()
        and contract.protocol_file_sha256 == protocol_file_sha256
        and contract.protocol_evidence_hash == protocol.protocol_evidence_hash
        and contract.protocol_audit_evidence_hash == protocol_audit.audit_evidence_hash
        and contract.measurement_dataset_file_sha256 == measurement_dataset_file_sha256
        and contract.price_dataset_file_sha256 == price_dataset_file_sha256
        and execution_audit.contract_evidence_hash == contract.contract_evidence_hash
        and execution_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and execution_audit.runner_contract_hash == contract.runner_contract_hash
        and result.protocol_file_sha256 == protocol_file_sha256
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.execution_contract_file_sha256 == contract_file_sha256
        and result.execution_contract_evidence_hash == contract.contract_evidence_hash
        and result.runner_contract_hash == contract.runner_contract_hash
        and result.measurement_dataset_file_sha256 == measurement_dataset_file_sha256
        and result.price_dataset_file_sha256 == price_dataset_file_sha256
        and result.outcome_ledger_file_sha256 == ledger_file_sha256
        and S2_BACKTEST_LEDGER_PATH.stat().st_size == result.outcome_ledger_bytes == 411_217
        and result.outcome_ledger_row_count == 272
        and result_audit.protocol_file_sha256 == protocol_file_sha256
        and result_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result_audit.execution_contract_file_sha256 == contract_file_sha256
        and result_audit.execution_contract_evidence_hash == contract.contract_evidence_hash
        and result_audit.result_evidence_hash == result.result_evidence_hash
        and result_audit.outcome_ledger_file_sha256 == ledger_file_sha256
        and result_audit.runner_contract_hash == contract.runner_contract_hash
        and result_audit.interval_manifest_evidence_hash
        == result.candidate_outcome.interval_manifest_evidence_hash
        and result.candidate_count == 1
        and result.parameter_combination_count == 1
        and result.rescue_candidate_count == 0
        and result.passed_gate_count == 9
        and result.failed_gate_count == 6
        and failed_gate_ids
        == {
            "BASE_PROFIT_FACTOR",
            "BASE_MAXIMUM_DRAWDOWN",
            "STRESS_MAXIMUM_DRAWDOWN",
            "POSITIVE_FULL_CALENDAR_YEARS",
            "STRESS_BOOTSTRAP_95PCT_LOWER_MEAN_WEEKLY_RETURN",
            "BASE_CALMAR_RATIO",
        }
        and result.candidate_outcome.interval_count == 272
        and result.candidate_outcome.base_net_total_return
        == "0.12063472602313097390395411111125681031398202678511415629486"
        and result.candidate_outcome.base_profit_factor
        == "1.02748199373037372669293691431666728509008944612872613358741"
        and result.candidate_outcome.base_maximum_drawdown
        == "0.707740049956904089285893208176271142584762183384968050755893"
        and result.candidate_outcome.stress_bootstrap_lower_mean_weekly_return
        == "-0.00454300194938842239445260680287457919341326241980245048258930"
        and result.historical_screen_values_read == 0
        and result.validation_values_read == 0
        and result.holdout_values_read == 0
        and result.orders_submitted == 0
        and result.decision == S2_BACKTEST_STOP
        and result.next_authorization == "NONE_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
        and result_audit.measurement_rows_reparsed == 273
        and result_audit.price_rows_reparsed == 273
        and result_audit.interval_rows_reconstructed == 272
        and result_audit.returns_recalculated == 272
        and result_audit.orders_submitted == 0
        and result_audit.reconstructed_exactly is True
        and result_audit.decision == "CONFIRM_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
        and result_audit.lineage_next_authorization
        == "NONE_S2_DEVELOPMENT_BACKTEST_FAILED_RETIRE_S2"
    )


def verify_s3_cftc_positioning_charter_checkpoint() -> bool:
    if not verify_s2_development_backtest_terminal_checkpoint():
        return False
    try:
        charter = S3CftcPositioningCharter.model_validate(read_json(S3_CFTC_CHARTER_PATH))
        audit = S3CftcPositioningCharterAudit.model_validate(read_json(S3_CFTC_CHARTER_AUDIT_PATH))
        expected_bindings = {
            path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(): sha256(
                path.read_bytes()
            ).hexdigest()
            for path in (
                FACTORY_CONTRACT_PATH,
                SANDBOX_PROFILE_PATH,
                S1_SUCCESSOR_LINEAGE_PATH,
                S1_SUCCESSOR_LINEAGE_AUDIT_PATH,
                S2_ONCHAIN_CHARTER_PATH,
                S2_ONCHAIN_CHARTER_AUDIT_PATH,
                S2_BTC_SOURCE_RESULT_PATH,
                S2_BTC_SOURCE_RESULT_AUDIT_PATH,
                S2_BACKTEST_RESULT_PATH,
                S2_BACKTEST_RESULT_AUDIT_PATH,
                READINESS_V23_RESULT_PATH,
                READINESS_V23_AUDIT_PATH,
            )
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    actual_bindings = {item.path: item.file_sha256 for item in charter.predecessor_bindings}
    charter_file_sha256 = sha256(S3_CFTC_CHARTER_PATH.read_bytes()).hexdigest()
    return (
        audit_s3_charter(charter)
        and audit_s3_charter_audit(audit)
        and actual_bindings == expected_bindings
        and len(charter.research_sources) == 8
        and all(source.does_not_prove_edge is True for source in charter.research_sources)
        and len(charter.partitions) == 6
        and all(partition.outcome_access_permitted is False for partition in charter.partitions)
        and charter.familywise_predecessor_count == 10
        and charter.published_rule_outcome_awareness_declared is True
        and charter.published_study_results_cannot_qualify_s3 is True
        and charter.cftc_position_values_inspected == ()
        and charter.btc_market_numeric_fields_inspected == ()
        and charter.exact_parameters_defined == ()
        and charter.return_metrics_calculated == ()
        and charter.strategy_candidates_created == 0
        and charter.strategy_executions == 0
        and charter.orders_submitted == 0
        and charter.authorizes_source_metadata_requests is True
        and charter.authorizes_release_calendar_metadata_requests is True
        and charter.authorizes_cftc_position_value_access is False
        and charter.authorizes_market_value_access is False
        and charter.authorizes_payload_acquisition is False
        and charter.authorizes_parameter_definition is False
        and charter.authorizes_return_testing is False
        and charter.authorizes_paper is False
        and charter.authorizes_testnet_strategy_orders is False
        and charter.authorizes_production is False
        and charter.authorizes_live is False
        and charter.real_net_profit_usd == "0"
        and charter.next_authorization == S3_NEXT_AUTHORIZATION
        and audit.charter_file_sha256 == charter_file_sha256
        and audit.charter_evidence_hash == charter.charter_evidence_hash
        and audit.builder_contract_hash == charter.builder_contract_hash
        and audit.reconstructed_exactly is True
        and audit.cftc_position_values_inspected == ()
        and audit.btc_market_numeric_fields_inspected == ()
        and audit.return_metrics_calculated == ()
        and audit.next_authorization == S3_NEXT_AUTHORIZATION
    )


def verify_s3_cftc_source_feasibility_terminal_checkpoint() -> bool:
    if not verify_s3_cftc_positioning_charter_checkpoint():
        return False
    try:
        protocol = S3CftcSourceFeasibilityProtocol.model_validate(
            read_json(S3_CFTC_FEASIBILITY_PROTOCOL_PATH)
        )
        protocol_audit = S3CftcSourceFeasibilityProtocolAudit.model_validate(
            read_json(S3_CFTC_FEASIBILITY_PROTOCOL_AUDIT_PATH)
        )
        result = S3CftcSourceFeasibilityResult.model_validate(
            read_json(S3_CFTC_FEASIBILITY_RESULT_PATH)
        )
        failure = S3CftcSourceTransportFailureAudit.model_validate(
            read_json(S3_CFTC_TRANSPORT_FAILURE_AUDIT_PATH)
        )
        amendment = S3CftcMetadataTransportAmendmentV2.model_validate(
            read_json(S3_CFTC_TRANSPORT_AMENDMENT_PATH)
        )
        amendment_audit = S3CftcMetadataTransportAmendmentAuditV2.model_validate(
            read_json(S3_CFTC_TRANSPORT_AMENDMENT_AUDIT_PATH)
        )
        receipt = S3CftcMetadataTransportExecutionReceiptV2.model_validate(
            read_json(S3_CFTC_TRANSPORT_RECEIPT_PATH)
        )
        receipt_audit = S3CftcMetadataTransportExecutionReceiptAuditV2.model_validate(
            read_json(S3_CFTC_TRANSPORT_RECEIPT_AUDIT_PATH)
        )

        def relative_hashes(paths: tuple[Path, ...]) -> dict[str, str]:
            return {
                path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(): sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }

        protocol_bindings = relative_hashes(
            (
                S3_CFTC_CHARTER_PATH,
                S3_CFTC_CHARTER_AUDIT_PATH,
                READINESS_V24_RESULT_PATH,
                READINESS_V24_AUDIT_PATH,
            )
        )
        amendment_bindings = relative_hashes(
            (
                S3_CFTC_FEASIBILITY_PROTOCOL_PATH,
                S3_CFTC_FEASIBILITY_PROTOCOL_AUDIT_PATH,
                S3_CFTC_FEASIBILITY_RESULT_PATH,
                S3_CFTC_TRANSPORT_FAILURE_AUDIT_PATH,
            )
        )
        receipt_bindings = relative_hashes(
            (
                S3_CFTC_FEASIBILITY_PROTOCOL_PATH,
                S3_CFTC_FEASIBILITY_PROTOCOL_AUDIT_PATH,
                S3_CFTC_FEASIBILITY_RESULT_PATH,
                S3_CFTC_TRANSPORT_FAILURE_AUDIT_PATH,
                S3_CFTC_TRANSPORT_AMENDMENT_PATH,
                S3_CFTC_TRANSPORT_AMENDMENT_AUDIT_PATH,
            )
        )
        result_v2_path = PROJECT_ROOT / receipt.result_artifact_path
        response_paths = tuple(PROJECT_ROOT / path for path in receipt.expected_response_paths)
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    return (
        audit_s3_feasibility_protocol(protocol)
        and audit_s3_feasibility_protocol_audit(protocol_audit)
        and audit_s3_feasibility_result(result)
        and audit_transport_failure(failure)
        and audit_transport_amendment(amendment)
        and audit_transport_amendment_audit(amendment_audit)
        and audit_transport_execution_receipt(receipt)
        and audit_transport_execution_receipt_audit(receipt_audit)
        and {item.path: item.file_sha256 for item in protocol.source_bindings} == protocol_bindings
        and protocol_audit.protocol_file_sha256
        == sha256(S3_CFTC_FEASIBILITY_PROTOCOL_PATH.read_bytes()).hexdigest()
        and protocol_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and protocol.target_position_values_permitted is False
        and protocol.btc_market_values_permitted is False
        and protocol.returns_permitted is False
        and protocol.paper_permitted is False
        and protocol.testnet_strategy_orders_permitted is False
        and protocol.production_permitted is False
        and protocol.live_permitted is False
        and len(result.metadata_attempts) == 3
        and all(
            attempt.error_class == "NETWORK_ERROR"
            and attempt.http_status == 0
            and attempt.response_path is None
            and attempt.response_sha256 is None
            and attempt.target_position_values_read == 0
            for attempt in result.metadata_attempts
        )
        and result.cftc_target_position_values_read == 0
        and result.btc_market_values_read == 0
        and result.returns_calculated == 0
        and result.orders_submitted == 0
        and failure.result_file_sha256
        == sha256(S3_CFTC_FEASIBILITY_RESULT_PATH.read_bytes()).hexdigest()
        and failure.result_evidence_hash == result.result_evidence_hash
        and failure.successful_response_count == 0
        and failure.response_artifact_count == 0
        and failure.next_authorization == "AUTHORIZE_S3_CFTC_METADATA_TRANSPORT_AMENDMENT_V2_ONLY"
        and {item.path: item.file_sha256 for item in amendment.source_bindings}
        == amendment_bindings
        and amendment.failure_audit_evidence_hash == failure.audit_evidence_hash
        and amendment.maximum_rerun_count == 1
        and amendment.maximum_metadata_requests == 3
        and amendment.target_position_values_permitted is False
        and amendment.btc_market_values_permitted is False
        and amendment.returns_permitted is False
        and amendment.testnet_strategy_orders_permitted is False
        and amendment.live_permitted is False
        and amendment_audit.amendment_file_sha256
        == sha256(S3_CFTC_TRANSPORT_AMENDMENT_PATH.read_bytes()).hexdigest()
        and amendment_audit.amendment_evidence_hash == amendment.amendment_evidence_hash
        and {item.path: item.file_sha256 for item in receipt.source_bindings} == receipt_bindings
        and receipt.transport_amendment_evidence_hash == amendment.amendment_evidence_hash
        and receipt.transport_amendment_audit_evidence_hash == amendment_audit.audit_evidence_hash
        and receipt.process_exit_code == 1
        and receipt.result_artifact_created is False
        and receipt.persisted_response_artifact_count == 0
        and receipt.successful_response_count_observed == "UNKNOWN_NOT_PERSISTED"
        and receipt.rerun_authority_exhausted is True
        and receipt.cftc_target_position_values_read == 0
        and receipt.btc_market_values_read == 0
        and receipt.returns_calculated == 0
        and receipt.orders_submitted == 0
        and receipt.production_authority is False
        and receipt.live_authority is False
        and receipt.decision == S3_TRANSPORT_V2_RETIREMENT
        and receipt.next_authorization == S3_DISTINCT_SUCCESSOR_AUTHORIZATION
        and not result_v2_path.exists()
        and all(not path.exists() for path in response_paths)
        and receipt_audit.receipt_file_sha256
        == sha256(S3_CFTC_TRANSPORT_RECEIPT_PATH.read_bytes()).hexdigest()
        and receipt_audit.receipt_evidence_hash == receipt.receipt_evidence_hash
        and receipt_audit.result_artifact_absence_verified is True
        and receipt_audit.persisted_response_artifact_count == 0
        and receipt_audit.rerun_authority_exhaustion_verified is True
        and receipt_audit.orders_submitted == 0
        and receipt_audit.next_authorization == S3_DISTINCT_SUCCESSOR_AUTHORIZATION
    )


def verify_s4_spot_bitcoin_etp_charter_checkpoint() -> bool:
    if not verify_s3_cftc_source_feasibility_terminal_checkpoint():
        return False
    try:
        charter = S4SpotBitcoinEtpCharter.model_validate(read_json(S4_ETP_CHARTER_PATH))
        audit = S4SpotBitcoinEtpCharterAudit.model_validate(read_json(S4_ETP_CHARTER_AUDIT_PATH))
        expected_bindings = {
            path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(): sha256(
                path.read_bytes()
            ).hexdigest()
            for path in (
                FACTORY_CONTRACT_PATH,
                SANDBOX_PROFILE_PATH,
                S1_SUCCESSOR_LINEAGE_PATH,
                S1_SUCCESSOR_LINEAGE_AUDIT_PATH,
                S2_ONCHAIN_CHARTER_PATH,
                S2_ONCHAIN_CHARTER_AUDIT_PATH,
                S2_BACKTEST_RESULT_PATH,
                S2_BACKTEST_RESULT_AUDIT_PATH,
                S3_CFTC_CHARTER_PATH,
                S3_CFTC_CHARTER_AUDIT_PATH,
                S3_CFTC_FEASIBILITY_PROTOCOL_PATH,
                S3_CFTC_FEASIBILITY_PROTOCOL_AUDIT_PATH,
                S3_CFTC_FEASIBILITY_RESULT_PATH,
                S3_CFTC_TRANSPORT_FAILURE_AUDIT_PATH,
                S3_CFTC_TRANSPORT_AMENDMENT_PATH,
                S3_CFTC_TRANSPORT_AMENDMENT_AUDIT_PATH,
                S3_CFTC_TRANSPORT_RECEIPT_PATH,
                S3_CFTC_TRANSPORT_RECEIPT_AUDIT_PATH,
                READINESS_V25_RESULT_PATH,
                READINESS_V25_AUDIT_PATH,
            )
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    disclosed_fields = (
        "BITCOIN_QUANTITY_HELD",
        "NET_ASSET_VALUE",
        "SHARES_CREATED_OR_REDEEMED_ANNUAL_TOTAL",
        "SHARES_OUTSTANDING",
    )
    charter_file_sha256 = sha256(S4_ETP_CHARTER_PATH.read_bytes()).hexdigest()
    return (
        audit_s4_charter(charter)
        and audit_s4_charter_audit(audit)
        and {item.path: item.file_sha256 for item in charter.predecessor_bindings}
        == expected_bindings
        and len(charter.research_sources) == 8
        and all(source.does_not_prove_edge is True for source in charter.research_sources)
        and len(charter.partitions) == 6
        and all(partition.outcome_access_permitted is False for partition in charter.partitions)
        and charter.familywise_predecessor_count == 11
        and charter.all_historical_etp_outcomes_declared_outcome_aware is True
        and charter.historical_etp_results_cannot_qualify_s4 is True
        and charter.known_regulatory_regime_change_declared is True
        and charter.per_fund_in_kind_effective_date_required is True
        and charter.incidental_source_numeric_fields_observed == disclosed_fields
        and charter.etp_time_series_rows_parsed == 0
        and charter.etp_numeric_payloads_acquired == 0
        and charter.btc_market_numeric_fields_inspected == ()
        and charter.exact_parameters_defined == ()
        and charter.return_metrics_calculated == ()
        and charter.strategy_candidates_created == 0
        and charter.strategy_executions == 0
        and charter.orders_submitted == 0
        and charter.authorizes_source_metadata_requests is True
        and charter.authorizes_sec_filing_metadata_requests is True
        and charter.authorizes_etp_numeric_value_access is False
        and charter.authorizes_market_value_access is False
        and charter.authorizes_payload_acquisition is False
        and charter.authorizes_parameter_definition is False
        and charter.authorizes_return_testing is False
        and charter.authorizes_historical_screen_access is False
        and charter.authorizes_validation_access is False
        and charter.authorizes_holdout_access is False
        and charter.authorizes_pine_deployment is False
        and charter.authorizes_paper is False
        and charter.authorizes_testnet_strategy_orders is False
        and charter.authorizes_production is False
        and charter.authorizes_live is False
        and charter.real_net_profit_usd == "0"
        and charter.decision == S4_CHARTER_DECISION
        and charter.next_authorization == S4_NEXT_AUTHORIZATION
        and audit.charter_file_sha256 == charter_file_sha256
        and audit.charter_evidence_hash == charter.charter_evidence_hash
        and audit.builder_contract_hash == charter.builder_contract_hash
        and audit.reconstructed_exactly is True
        and audit.predecessor_binding_count == 20
        and audit.research_source_count == 8
        and audit.partition_count == 6
        and audit.incidental_source_numeric_fields_observed == disclosed_fields
        and audit.etp_time_series_rows_parsed == 0
        and audit.etp_numeric_payloads_acquired == 0
        and audit.btc_market_numeric_fields_inspected == ()
        and audit.return_metrics_calculated == ()
        and audit.orders_submitted == 0
        and audit.next_authorization == S4_NEXT_AUTHORIZATION
    )


def verify_s4_etp_source_feasibility_terminal_checkpoint() -> bool:
    if not verify_s4_spot_bitcoin_etp_charter_checkpoint():
        return False
    try:
        charter = S4SpotBitcoinEtpCharter.model_validate(read_json(S4_ETP_CHARTER_PATH))
        protocol = S4EtpSourceFeasibilityProtocol.model_validate(
            read_json(S4_ETP_FEASIBILITY_PROTOCOL_PATH)
        )
        protocol_audit = S4EtpSourceFeasibilityProtocolAudit.model_validate(
            read_json(S4_ETP_FEASIBILITY_PROTOCOL_AUDIT_PATH)
        )
        review = S4EtpSourceFeasibilityViabilityReview.model_validate(
            read_json(S4_ETP_FEASIBILITY_VIABILITY_PATH)
        )
        review_audit = S4EtpSourceFeasibilityViabilityReviewAudit.model_validate(
            read_json(S4_ETP_FEASIBILITY_VIABILITY_AUDIT_PATH)
        )

        def relative_hashes(paths: tuple[Path, ...]) -> dict[str, str]:
            return {
                path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(): sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }

        protocol_bindings = relative_hashes(
            (
                S4_ETP_CHARTER_PATH,
                S4_ETP_CHARTER_AUDIT_PATH,
                READINESS_V26_RESULT_PATH,
                READINESS_V26_AUDIT_PATH,
            )
        )
        review_bindings = relative_hashes(
            (
                S4_ETP_FEASIBILITY_PROTOCOL_PATH,
                S4_ETP_FEASIBILITY_PROTOCOL_AUDIT_PATH,
            )
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    return (
        audit_s4_feasibility_protocol(protocol)
        and audit_s4_feasibility_protocol_audit(protocol_audit)
        and audit_s4_viability_review(review)
        and audit_s4_viability_review_audit(review_audit)
        and {item.path: item.file_sha256 for item in protocol.source_bindings} == protocol_bindings
        and protocol.charter_evidence_hash == charter.charter_evidence_hash
        and len(protocol.static_metadata_endpoints) == 5
        and protocol.maximum_run_count == 1
        and protocol.result_artifact_required_on_every_exit is True
        and protocol.attempt_record_required_for_every_planned_request is True
        and protocol.partial_response_artifacts_must_be_preserved is True
        and protocol.all_or_nothing_response_persistence_forbidden is True
        and protocol.unknown_attempt_or_success_counts_forbidden is True
        and protocol.issuer_page_response_bodies_permitted is False
        and protocol.sec_filing_document_bodies_permitted is False
        and protocol.xbrl_fact_endpoints_permitted is False
        and protocol.etp_numeric_values_permitted is False
        and protocol.btc_market_values_permitted is False
        and protocol.returns_permitted is False
        and protocol.paper_permitted is False
        and protocol.testnet_strategy_orders_permitted is False
        and protocol.production_permitted is False
        and protocol.live_permitted is False
        and protocol.next_authorization == S4_FEASIBILITY_RUN_AUTHORIZATION
        and protocol_audit.protocol_file_sha256
        == sha256(S4_ETP_FEASIBILITY_PROTOCOL_PATH.read_bytes()).hexdigest()
        and protocol_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and protocol_audit.reconstructed_exactly is True
        and protocol_audit.network_requests_observed == 0
        and protocol_audit.etp_numeric_values_observed_by_protocol == 0
        and protocol_audit.orders_observed == 0
        and {item.path: item.file_sha256 for item in review.source_bindings} == review_bindings
        and review.protocol_evidence_hash == protocol.protocol_evidence_hash
        and review.protocol_audit_evidence_hash == protocol_audit.audit_evidence_hash
        and review.protocol_reconstructed_before_review is True
        and review.unreachable_gate_count == 6
        and review.protocol_pass_condition_reachable is False
        and review.protocol_run_permitted_after_review is False
        and review.network_requests_executed == 0
        and review.run_authority_consumed is False
        and review.etp_time_series_rows_parsed == 0
        and review.etp_numeric_values_read == 0
        and review.btc_market_values_read == 0
        and review.parameters_defined == 0
        and review.returns_calculated == 0
        and review.candidates_created == 0
        and review.strategy_executions == 0
        and review.orders_submitted == 0
        and review.source_feasibility_conclusion == "NOT_EVALUATED_PROTOCOL_STOPPED_BEFORE_NETWORK"
        and review.predictive_edge_conclusion == "NOT_EVALUATED"
        and review.decision == S4_VIABILITY_STOP
        and review.next_authorization == S4_VIABILITY_NEXT
        and review.authorizes_protocol_run is False
        and review.authorizes_protocol_amendment is False
        and review.authorizes_etp_numeric_payload is False
        and review.authorizes_market_values is False
        and review.authorizes_returns is False
        and review.authorizes_testnet_strategy_orders is False
        and review.authorizes_production is False
        and review.authorizes_live is False
        and review.real_net_profit_usd == "0"
        and review_audit.review_file_sha256
        == sha256(S4_ETP_FEASIBILITY_VIABILITY_PATH.read_bytes()).hexdigest()
        and review_audit.review_evidence_hash == review.review_evidence_hash
        and review_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and review_audit.reconstructed_exactly is True
        and review_audit.unreachable_gate_count == 6
        and review_audit.network_requests_observed == 0
        and review_audit.run_authority_consumed is False
        and review_audit.source_feasibility_not_inferred is True
        and review_audit.predictive_edge_not_inferred is True
        and review_audit.orders_observed == 0
        and review_audit.next_authorization == S4_VIABILITY_NEXT
        and not S4_ETP_FEASIBILITY_RESULT_PATH.exists()
    )


def verify_s5_bitcoin_core_source_feasibility_checkpoint() -> bool:
    if not verify_s4_etp_source_feasibility_terminal_checkpoint():
        return False
    try:
        charter = S5BitcoinCoreDevelopmentCharter.model_validate(read_json(S5_CHARTER_PATH))
        charter_audit = S5BitcoinCoreDevelopmentCharterAudit.model_validate(
            read_json(S5_CHARTER_AUDIT_PATH)
        )
        protocol = S5BitcoinCoreSourceFeasibilityProtocol.model_validate(
            read_json(S5_SOURCE_PROTOCOL_PATH)
        )
        protocol_audit = S5BitcoinCoreSourceFeasibilityProtocolAudit.model_validate(
            read_json(S5_SOURCE_PROTOCOL_AUDIT_PATH)
        )
        result = S5BitcoinCoreSourceFeasibilityResult.model_validate(
            read_json(S5_SOURCE_RESULT_PATH)
        )
        result_audit = S5BitcoinCoreSourceFeasibilityResultAudit.model_validate(
            read_json(S5_SOURCE_RESULT_AUDIT_PATH)
        )

        def relative_hashes(paths: tuple[Path, ...]) -> dict[str, str]:
            return {
                path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(): sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }

        protocol_bindings = relative_hashes(
            (
                S5_CHARTER_PATH,
                S5_CHARTER_AUDIT_PATH,
                READINESS_V27_RESULT_PATH,
                READINESS_V27_AUDIT_PATH,
            )
        )
        charter_bindings_valid = all(
            (PROJECT_ROOT / item.path).is_file()
            and sha256((PROJECT_ROOT / item.path).read_bytes()).hexdigest() == item.file_sha256
            for item in charter.predecessor_bindings
        )
        attempts = {item.attempt_id: item for item in result.attempts}
        raw_artifacts_valid = all(
            (PROJECT_ROOT / item.path).is_file()
            and (PROJECT_ROOT / item.path).stat().st_size == item.byte_count
            and sha256((PROJECT_ROOT / item.path).read_bytes()).hexdigest() == item.file_sha256
            and attempts[item.attempt_id].raw_artifact_path == item.path
            and attempts[item.attempt_id].raw_artifact_sha256 == item.file_sha256
            for item in result.raw_artifacts
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return False

    return (
        audit_s5_charter(charter)
        and audit_s5_charter_audit(charter_audit)
        and charter_bindings_valid
        and len(charter.predecessor_bindings) == 28
        and len(charter.research_sources) == 10
        and len(charter.partitions) == 6
        and charter.mechanism_id == "S5-BITCOIN-CORE-ACCEPTED-DEVELOPMENT-BREADTH"
        and charter.metadata_protocol_pass_condition_reachable_by_allowed_sources is True
        and charter.pre_freeze_public_git_probe_request_count == 1
        and len(charter.pre_freeze_git_ref_records) == 3
        and charter.repository_commit_history_records_parsed == 0
        and charter.github_historical_api_records_parsed == 0
        and charter.repository_history_payload_bytes_acquired == 0
        and charter.btc_market_numeric_fields_inspected == ()
        and charter.exact_parameters_defined == ()
        and charter.return_metrics_calculated == ()
        and charter.strategy_candidates_created == 0
        and charter.strategy_executions == 0
        and charter.orders_submitted == 0
        and charter.authorizes_repository_clone is False
        and charter.authorizes_repository_history_access is False
        and charter.authorizes_market_value_access is False
        and charter.authorizes_return_testing is False
        and charter.authorizes_paper is False
        and charter.authorizes_testnet_strategy_orders is False
        and charter.authorizes_production is False
        and charter.authorizes_live is False
        and charter.real_net_profit_usd == "0"
        and charter_audit.charter_file_sha256 == sha256(S5_CHARTER_PATH.read_bytes()).hexdigest()
        and charter_audit.charter_evidence_hash == charter.charter_evidence_hash
        and charter_audit.builder_contract_hash == charter.builder_contract_hash
        and charter_audit.reconstructed_exactly is True
        and charter_audit.predecessor_binding_count == 28
        and charter_audit.research_source_count == 10
        and charter_audit.partition_count == 6
        and charter_audit.repository_commit_history_records_parsed == 0
        and charter_audit.github_historical_api_records_parsed == 0
        and charter_audit.repository_history_payload_bytes_acquired == 0
        and charter_audit.orders_submitted == 0
        and audit_s5_source_protocol(protocol)
        and audit_s5_source_protocol_audit(protocol_audit)
        and {item.path: item.file_sha256 for item in protocol.source_bindings} == protocol_bindings
        and protocol.charter_evidence_hash == charter.charter_evidence_hash
        and protocol.maximum_total_attempts == 2
        and protocol.maximum_run_count == 1
        and protocol.result_artifact_required_on_every_exit is True
        and protocol.attempt_record_required_for_every_planned_attempt is True
        and protocol.raw_response_artifact_required_for_every_completed_attempt is True
        and protocol.partial_response_artifacts_must_be_preserved is True
        and protocol.authentication_permitted is False
        and protocol.repository_clone_permitted is False
        and protocol.repository_history_permitted is False
        and protocol.github_commit_history_permitted is False
        and protocol.github_pull_request_history_permitted is False
        and protocol.market_values_permitted is False
        and protocol.returns_permitted is False
        and protocol.testnet_strategy_orders_permitted is False
        and protocol.production_permitted is False
        and protocol.live_permitted is False
        and protocol.network_requests_executed == 0
        and protocol.repository_history_records_parsed == 0
        and protocol.orders_submitted == 0
        and protocol_audit.protocol_file_sha256
        == sha256(S5_SOURCE_PROTOCOL_PATH.read_bytes()).hexdigest()
        and protocol_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and protocol_audit.reconstructed_exactly is True
        and protocol_audit.planned_attempt_count == 2
        and protocol_audit.network_requests_observed == 0
        and protocol_audit.repository_history_records_parsed == 0
        and protocol_audit.orders_submitted == 0
        and audit_s5_source_result(result)
        and raw_artifacts_valid
        and len(result.raw_artifacts) == 2
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.attempted_count == 2
        and result.succeeded_count == 2
        and result.passed_gate_count == 14
        and result.failed_gate_count == 0
        and result.repository_full_name == "bitcoin/bitcoin"
        and result.repository_private is False
        and result.repository_archived is False
        and result.repository_disabled is False
        and result.repository_default_branch == "master"
        and result.repository_license_spdx_id == "MIT"
        and len(result.git_ref_records) == 3
        and result.head_matches_master is True
        and result.credentials_used is False
        and result.repository_history_records_parsed == 0
        and result.github_commit_history_records_parsed == 0
        and result.github_pull_request_history_records_parsed == 0
        and result.btc_market_values_read == 0
        and result.parameters_defined == 0
        and result.returns_calculated == 0
        and result.candidates_created == 0
        and result.strategy_executions == 0
        and result.orders_submitted == 0
        and result.predictive_edge_conclusion == "NOT_EVALUATED"
        and result.decision == S5_SOURCE_PASS
        and result.next_authorization == S5_SOURCE_NEXT
        and result.authorizes_history_payload_protocol is True
        and result.authorizes_repository_history_access is False
        and result.authorizes_market_values is False
        and result.authorizes_returns is False
        and result.authorizes_testnet_strategy_orders is False
        and result.authorizes_production is False
        and result.authorizes_live is False
        and result.real_net_profit_usd == "0"
        and audit_s5_source_result_audit(result_audit)
        and result_audit.result_file_sha256
        == sha256(S5_SOURCE_RESULT_PATH.read_bytes()).hexdigest()
        and result_audit.result_evidence_hash == result.result_evidence_hash
        and result_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result_audit.runner_contract_hash == result.runner_contract_hash
        and result_audit.reconstructed_exactly is True
        and result_audit.raw_artifacts_verified is True
        and result_audit.attempted_count == 2
        and result_audit.succeeded_count == 2
        and result_audit.passed_gate_count == 14
        and result_audit.failed_gate_count == 0
        and result_audit.repository_history_records_parsed == 0
        and result_audit.market_values_read == 0
        and result_audit.returns_calculated == 0
        and result_audit.orders_submitted == 0
        and result_audit.next_authorization == S5_SOURCE_NEXT
    )


def verify_s5_bitcoin_core_history_payload_checkpoint() -> bool:
    if not verify_s5_bitcoin_core_source_feasibility_checkpoint():
        return False
    try:
        protocol = S5BitcoinCoreHistoryPayloadProtocol.model_validate(
            read_json(S5_HISTORY_PROTOCOL_PATH)
        )
        protocol_audit = S5BitcoinCoreHistoryPayloadProtocolAudit.model_validate(
            read_json(S5_HISTORY_PROTOCOL_AUDIT_PATH)
        )
        result_v1 = S5BitcoinCoreHistoryPayloadResult.model_validate(
            read_json(S5_HISTORY_RESULT_V1_PATH)
        )
        result_audit_v1 = S5BitcoinCoreHistoryPayloadResultAudit.model_validate(
            read_json(S5_HISTORY_RESULT_AUDIT_V1_PATH)
        )
        failure_audit = S5BitcoinCoreHistoryVerifierFailureAudit.model_validate(
            read_json(S5_HISTORY_FAILURE_AUDIT_PATH)
        )
        amendment = S5BitcoinCoreHistoryLocalVerifierAmendmentV2.model_validate(
            read_json(S5_HISTORY_AMENDMENT_V2_PATH)
        )
        amendment_audit = S5BitcoinCoreHistoryLocalVerifierAmendmentAuditV2.model_validate(
            read_json(S5_HISTORY_AMENDMENT_AUDIT_V2_PATH)
        )
        result_v2 = S5BitcoinCoreHistoryPayloadResultV2.model_validate(
            read_json(S5_HISTORY_RESULT_V2_PATH)
        )
        result_audit_v2 = S5BitcoinCoreHistoryPayloadResultAuditV2.model_validate(
            read_json(S5_HISTORY_RESULT_AUDIT_V2_PATH)
        )

        def expected_bindings(paths: tuple[Path, ...]) -> dict[str, str]:
            return {
                path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(): sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in paths
            }

        protocol_bindings = expected_bindings(
            (
                S5_CHARTER_PATH,
                S5_CHARTER_AUDIT_PATH,
                S5_SOURCE_PROTOCOL_PATH,
                S5_SOURCE_PROTOCOL_AUDIT_PATH,
                S5_SOURCE_RESULT_PATH,
                S5_SOURCE_RESULT_AUDIT_PATH,
                READINESS_V28_RESULT_PATH,
                READINESS_V28_AUDIT_PATH,
            )
        )
        failure_binding_paths = tuple(
            sorted(PROJECT_ROOT / item.path for item in failure_audit.source_bindings)
        )
        amendment_binding_paths = tuple(
            sorted(PROJECT_ROOT / item.path for item in amendment.source_bindings)
        )
        failure_bindings = expected_bindings(failure_binding_paths)
        amendment_bindings = expected_bindings(amendment_binding_paths)

        if not S5_HISTORY_DATASET_PATH.is_dir():
            return False
        actual_files = tuple(
            sorted(
                (
                    path
                    for path in S5_HISTORY_DATASET_PATH.rglob("*")
                    if path.is_file() and not path.is_symlink()
                ),
                key=lambda path: path.as_posix(),
            )
        )
        manifest = result_v2.dataset_file_manifest
        manifest_by_path = {item.relative_path: item for item in manifest}
        dataset_manifest_valid = (
            len(actual_files) == result_v2.dataset_file_count == len(manifest)
            and len(manifest_by_path) == len(manifest)
            and all(
                (relative := path.relative_to(S5_HISTORY_DATASET_PATH).as_posix())
                in manifest_by_path
                and path.stat().st_size == manifest_by_path[relative].byte_count
                and sha256(path.read_bytes()).hexdigest() == manifest_by_path[relative].file_sha256
                for path in actual_files
            )
            and sum(item.byte_count for item in manifest) == result_v2.dataset_byte_count
            and universe_evidence_hash([item.model_dump(mode="json") for item in manifest])
            == result_v2.dataset_directory_sha256
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return False

    return (
        audit_s5_history_protocol(protocol)
        and audit_s5_history_protocol_audit(protocol_audit)
        and {item.path: item.file_sha256 for item in protocol.source_bindings} == protocol_bindings
        and len(protocol.source_bindings) == 8
        and protocol.source_feasibility_result_evidence_hash
        == S5BitcoinCoreSourceFeasibilityResult.model_validate(
            read_json(S5_SOURCE_RESULT_PATH)
        ).result_evidence_hash
        and protocol.readiness_v28_result_evidence_hash
        == StrategyFactoryReadinessResult.model_validate(
            read_json(READINESS_V28_RESULT_PATH)
        ).result_evidence_hash
        and protocol.clone_spec.remote_url == "https://github.com/bitcoin/bitcoin.git"
        and protocol.clone_spec.branch == "master"
        and protocol.clone_spec.credentials_permitted is False
        and protocol.maximum_run_count == 1
        and protocol.history_semantic_parsing_permitted is False
        and protocol.github_api_requests_permitted is False
        and protocol.market_values_permitted is False
        and protocol.parameters_permitted is False
        and protocol.returns_permitted is False
        and protocol.paper_permitted is False
        and protocol.testnet_strategy_orders_permitted is False
        and protocol.production_permitted is False
        and protocol.live_permitted is False
        and protocol_audit.protocol_file_sha256
        == sha256(S5_HISTORY_PROTOCOL_PATH.read_bytes()).hexdigest()
        and protocol_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and protocol_audit.reconstructed_exactly is True
        and protocol_audit.history_access_observed == 0
        and protocol_audit.orders_submitted == 0
        and audit_s5_history_result(result_v1)
        and result_v1.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result_v1.attempt.attempted is True
        and result_v1.attempt.succeeded is True
        and result_v1.attempt.exit_code == 0
        and result_v1.attempt.error_type == "ValueError"
        and result_v1.failed_gate_count == 8
        and result_v1.decision == S5_HISTORY_STOP
        and result_v1.authorizes_history_completeness_census_protocol is False
        and result_v1.btc_market_values_read == 0
        and result_v1.returns_calculated == 0
        and result_v1.orders_submitted == 0
        and audit_s5_history_result_audit(result_audit_v1)
        and result_audit_v1.result_file_sha256
        == sha256(S5_HISTORY_RESULT_V1_PATH.read_bytes()).hexdigest()
        and result_audit_v1.result_evidence_hash == result_v1.result_evidence_hash
        and result_audit_v1.failed_gate_count == 8
        and audit_verifier_failure(failure_audit)
        and {item.path: item.file_sha256 for item in failure_audit.source_bindings}
        == failure_bindings
        and failure_audit.result_evidence_hash == result_v1.result_evidence_hash
        and failure_audit.result_audit_evidence_hash == result_audit_v1.audit_evidence_hash
        and failure_audit.successful_clone_process_count == 1
        and failure_audit.additional_network_process_count == 0
        and failure_audit.clone_exit_code == 0
        and failure_audit.verifier_rejected_promised_missing_blob is True
        and failure_audit.repository_is_bare is True
        and failure_audit.repository_is_shallow is False
        and failure_audit.remote_origin_url == protocol.clone_spec.remote_url
        and failure_audit.remote_promisor is True
        and failure_audit.remote_partial_clone_filter == "blob:none"
        and failure_audit.source_cutoff_commit == protocol.source_cutoff_commit
        and failure_audit.cutoff_commit_present is True
        and failure_audit.cutoff_commit_count == 50_395
        and failure_audit.adjudication == S5_VERIFIER_FAILURE_ADJUDICATION
        and failure_audit.commit_messages_read == 0
        and failure_audit.author_identities_read == 0
        and failure_audit.pull_request_ids_parsed == 0
        and failure_audit.market_values_read == 0
        and failure_audit.returns_calculated == 0
        and failure_audit.orders_submitted == 0
        and audit_verifier_amendment(amendment)
        and {item.path: item.file_sha256 for item in amendment.source_bindings}
        == amendment_bindings
        and amendment.protocol_evidence_hash == protocol.protocol_evidence_hash
        and amendment.prior_result_evidence_hash == result_v1.result_evidence_hash
        and amendment.failure_audit_evidence_hash == failure_audit.audit_evidence_hash
        and amendment.additional_network_process_count == 0
        and amendment.network_access_permitted is False
        and amendment.credential_access_permitted is False
        and amendment.corrected_object_enumeration.endswith("--missing=print <cutoff>")
        and amendment.protocol_source_cutoff_unchanged is True
        and amendment.protocol_gate_ids_unchanged is True
        and amendment.history_semantic_parsing_permitted is False
        and amendment.github_api_requests_permitted is False
        and amendment.market_values_permitted is False
        and amendment.parameters_permitted is False
        and amendment.returns_permitted is False
        and amendment.paper_permitted is False
        and amendment.testnet_strategy_orders_permitted is False
        and amendment.production_permitted is False
        and amendment.live_permitted is False
        and audit_verifier_amendment_audit(amendment_audit)
        and amendment_audit.amendment_file_sha256
        == sha256(S5_HISTORY_AMENDMENT_V2_PATH.read_bytes()).hexdigest()
        and amendment_audit.amendment_evidence_hash == amendment.amendment_evidence_hash
        and amendment_audit.failure_audit_evidence_hash == failure_audit.audit_evidence_hash
        and amendment_audit.additional_network_processes_observed == 0
        and amendment_audit.orders_submitted == 0
        and audit_s5_history_result_v2(result_v2)
        and dataset_manifest_valid
        and result_v2.dataset_path == S5_HISTORY_DATASET_PATH.relative_to(PROJECT_ROOT).as_posix()
        and result_v2.partial_dataset_path is None
        and result_v2.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result_v2.prior_result_evidence_hash == result_v1.result_evidence_hash
        and result_v2.failure_audit_evidence_hash == failure_audit.audit_evidence_hash
        and result_v2.verifier_amendment_evidence_hash == amendment.amendment_evidence_hash
        and result_v2.verifier_amendment_audit_evidence_hash == amendment_audit.audit_evidence_hash
        and result_v2.passed_gate_count == 14
        and result_v2.failed_gate_count == 0
        and result_v2.network_process_count == 1
        and result_v2.additional_network_process_count == 0
        and result_v2.repository_is_bare is True
        and result_v2.repository_is_shallow is False
        and result_v2.remote_origin_url == protocol.clone_spec.remote_url
        and result_v2.remote_promisor is True
        and result_v2.remote_partial_clone_filter == "blob:none"
        and result_v2.local_branch_refs == ("refs/heads/master",)
        and result_v2.local_tag_ref_count == 0
        and result_v2.source_cutoff_commit == protocol.source_cutoff_commit
        and result_v2.cutoff_commit_present is True
        and result_v2.cutoff_is_ancestor_of_fetched_master is True
        and result_v2.cutoff_commit_count == 50_395
        and result_v2.repository_history_records_acquired == 50_395
        and result_v2.reachable_object_id_count == 320_247
        and result_v2.missing_promised_object_count == 116_360
        and result_v2.repository_history_records_semantically_parsed == 0
        and result_v2.commit_messages_read == 0
        and result_v2.author_identities_read == 0
        and result_v2.author_timestamps_read == 0
        and result_v2.pull_request_ids_parsed == 0
        and result_v2.github_api_requests_executed == 0
        and result_v2.btc_market_values_read == 0
        and result_v2.parameters_defined == 0
        and result_v2.returns_calculated == 0
        and result_v2.candidates_created == 0
        and result_v2.strategy_executions == 0
        and result_v2.orders_submitted == 0
        and result_v2.predictive_edge_conclusion == "NOT_EVALUATED"
        and result_v2.decision == S5_HISTORY_PASS
        and result_v2.next_authorization == S5_HISTORY_NEXT
        and result_v2.authorizes_history_completeness_census_protocol is True
        and result_v2.authorizes_history_semantic_parsing is False
        and result_v2.authorizes_github_api_requests is False
        and result_v2.authorizes_market_values is False
        and result_v2.authorizes_parameters is False
        and result_v2.authorizes_returns is False
        and result_v2.authorizes_paper is False
        and result_v2.authorizes_testnet_strategy_orders is False
        and result_v2.authorizes_production is False
        and result_v2.authorizes_live is False
        and result_v2.real_net_profit_usd == "0"
        and audit_s5_history_result_audit_v2(result_audit_v2)
        and result_audit_v2.result_file_sha256
        == sha256(S5_HISTORY_RESULT_V2_PATH.read_bytes()).hexdigest()
        and result_audit_v2.result_evidence_hash == result_v2.result_evidence_hash
        and result_audit_v2.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result_audit_v2.runner_contract_hash == result_v2.runner_contract_hash
        and result_audit_v2.transcript_reverified is True
        and result_audit_v2.dataset_manifest_reverified is True
        and result_audit_v2.local_git_integrity_reverified is True
        and result_audit_v2.passed_gate_count == 14
        and result_audit_v2.failed_gate_count == 0
        and result_audit_v2.dataset_file_count == 23
        and result_audit_v2.dataset_byte_count == 77_762_990
        and result_audit_v2.cutoff_commit_count == 50_395
        and result_audit_v2.additional_network_process_count == 0
        and result_audit_v2.missing_promised_object_count == 116_360
        and result_audit_v2.market_values_read == 0
        and result_audit_v2.returns_calculated == 0
        and result_audit_v2.orders_submitted == 0
        and result_audit_v2.next_authorization == S5_HISTORY_NEXT
    )


def verify_s5_bitcoin_core_history_census_checkpoint(
    *, history_verified: bool | None = None
) -> bool:
    if history_verified is None:
        history_verified = verify_s5_bitcoin_core_history_payload_checkpoint()
    if not history_verified:
        return False
    try:
        protocol = S5BitcoinCoreHistoryCensusProtocol.model_validate(
            read_json(S5_CENSUS_PROTOCOL_PATH)
        )
        protocol_audit = S5BitcoinCoreHistoryCensusProtocolAudit.model_validate(
            read_json(S5_CENSUS_PROTOCOL_AUDIT_PATH)
        )
        result = S5BitcoinCoreHistoryCensusResult.model_validate(read_json(S5_CENSUS_RESULT_PATH))
        result_audit = S5BitcoinCoreHistoryCensusResultAudit.model_validate(
            read_json(S5_CENSUS_RESULT_AUDIT_PATH)
        )
        expected_binding_paths = (
            S5_HISTORY_PROTOCOL_PATH,
            S5_HISTORY_PROTOCOL_AUDIT_PATH,
            S5_HISTORY_RESULT_V1_PATH,
            S5_HISTORY_RESULT_AUDIT_V1_PATH,
            S5_HISTORY_FAILURE_AUDIT_PATH,
            S5_HISTORY_AMENDMENT_V2_PATH,
            S5_HISTORY_AMENDMENT_AUDIT_V2_PATH,
            S5_HISTORY_RESULT_V2_PATH,
            S5_HISTORY_RESULT_AUDIT_V2_PATH,
            READINESS_V29_RESULT_PATH,
            READINESS_V29_AUDIT_PATH,
        )
        expected_bindings = {
            path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(): sha256(
                path.read_bytes()
            ).hexdigest()
            for path in expected_binding_paths
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    return (
        audit_s5_census_protocol(protocol)
        and {item.path: item.file_sha256 for item in protocol.source_bindings} == expected_bindings
        and len(protocol.source_bindings) == 11
        and protocol.dataset_path == S5_HISTORY_DATASET_PATH.relative_to(PROJECT_ROOT).as_posix()
        and protocol.dataset_directory_sha256 == result.dataset_directory_sha256
        and protocol.source_cutoff_commit == result.source_cutoff_commit
        and protocol.maximum_reachable_commit_count == 50_395
        and tuple((item.pattern_id, item.regular_expression) for item in protocol.message_patterns)
        == (
            (
                "BITCOIN_CORE_MAINTAINER_MERGE",
                r"^Merge bitcoin/bitcoin#([1-9][0-9]*):(?: |$)",
            ),
            (
                "GITHUB_DEFAULT_PULL_MERGE",
                r"^Merge pull request #([1-9][0-9]*) from .+$",
            ),
        )
        and protocol.maximum_local_git_process_count == 2
        and protocol.maximum_run_count == 1
        and protocol.network_access_permitted is False
        and protocol.repository_fetch_permitted is False
        and protocol.author_header_parsing_permitted is False
        and protocol.committer_header_parsing_permitted is False
        and protocol.timestamp_parsing_permitted is False
        and protocol.github_api_requests_permitted is False
        and protocol.btc_market_values_permitted is False
        and protocol.parameters_permitted is False
        and protocol.returns_permitted is False
        and protocol.strategy_candidate_permitted is False
        and protocol.paper_permitted is False
        and protocol.testnet_strategy_orders_permitted is False
        and protocol.production_permitted is False
        and protocol.live_permitted is False
        and audit_s5_census_protocol_audit(protocol_audit)
        and protocol_audit.protocol_file_sha256
        == sha256(S5_CENSUS_PROTOCOL_PATH.read_bytes()).hexdigest()
        and protocol_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and protocol_audit.reconstructed_exactly is True
        and protocol_audit.local_git_processes_observed == 0
        and protocol_audit.github_api_requests_observed == 0
        and protocol_audit.market_values_read == 0
        and protocol_audit.orders_submitted == 0
        and audit_s5_census_result(result)
        and result.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result.local_git_process_count == 2
        and result.first_parent_commit_count == 17_543
        and result.commit_object_count == 17_543
        and result.root_commit_count == 1
        and result.single_parent_commit_count == 821
        and result.merge_commit_count == 16_721
        and result.octopus_merge_commit_count == 0
        and result.recognized_pull_merge_count == 7_961
        and result.unrecognized_merge_count == 8_760
        and result.recognized_pattern_counts
        == {
            "BITCOIN_CORE_MAINTAINER_MERGE": 6_570,
            "GITHUB_DEFAULT_PULL_MERGE": 1_391,
        }
        and result.distinct_pull_request_count == 7_961
        and result.duplicate_pull_request_reference_count == 0
        and result.single_parent_pattern_match_count == 0
        and result.exact_direct_pull_request_count == 7_961
        and result.unauthenticated_direct_request_hours_lower_bound == 133
        and result.authenticated_direct_request_hours_lower_bound == 2
        and result.minimum_list_endpoint_pages_at_100_records == 80
        and result.github_token_environment_present is False
        and result.passed_gate_count == 13
        and result.failed_gate_count == 0
        and result.commit_message_bodies_received == 17_543
        and result.commit_message_first_lines_parsed == 17_543
        and result.commit_message_bodies_persisted == 0
        and result.author_headers_parsed == 0
        and result.committer_headers_parsed == 0
        and result.timestamps_parsed == 0
        and result.github_api_requests_executed == 0
        and result.btc_market_values_read == 0
        and result.parameters_defined == 0
        and result.returns_calculated == 0
        and result.candidates_created == 0
        and result.strategy_executions == 0
        and result.orders_submitted == 0
        and result.source_completeness_conclusion == "NOT_YET_ADJUDICATED"
        and result.predictive_edge_conclusion == "NOT_EVALUATED"
        and result.decision == S5_CENSUS_PASS
        and result.next_authorization == S5_CENSUS_NEXT
        and result.authorizes_metadata_transport_decision is True
        and result.authorizes_github_api_requests is False
        and result.authorizes_market_values is False
        and result.authorizes_parameters is False
        and result.authorizes_returns is False
        and result.authorizes_paper is False
        and result.authorizes_testnet_strategy_orders is False
        and result.authorizes_production is False
        and result.authorizes_live is False
        and result.real_net_profit_usd == "0"
        and audit_s5_census_result_audit(result_audit)
        and result_audit.result_file_sha256
        == sha256(S5_CENSUS_RESULT_PATH.read_bytes()).hexdigest()
        and result_audit.result_evidence_hash == result.result_evidence_hash
        and result_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and result_audit.runner_contract_hash == result.runner_contract_hash
        and result_audit.reconstructed_exactly is True
        and result_audit.dataset_hash_reverified is True
        and result_audit.first_parent_stream_reverified is True
        and result_audit.commit_object_count == 17_543
        and result_audit.recognized_pull_merge_count == 7_961
        and result_audit.distinct_pull_request_count == 7_961
        and result_audit.exact_direct_pull_request_count == 7_961
        and result_audit.passed_gate_count == 13
        and result_audit.failed_gate_count == 0
        and result_audit.github_api_requests_executed == 0
        and result_audit.market_values_read == 0
        and result_audit.returns_calculated == 0
        and result_audit.orders_submitted == 0
        and result_audit.next_authorization == S5_CENSUS_NEXT
    )


def verify_s5_github_transport_decision_checkpoint(*, census_verified: bool | None = None) -> bool:
    if census_verified is None:
        census_verified = verify_s5_bitcoin_core_history_census_checkpoint()
    if not census_verified:
        return False
    try:
        decision = S5GitHubTransportDecision.model_validate(
            read_json(S5_GITHUB_TRANSPORT_DECISION_PATH)
        )
        audit = S5GitHubTransportDecisionAudit.model_validate(
            read_json(S5_GITHUB_TRANSPORT_DECISION_AUDIT_PATH)
        )
        expected_binding_paths = (
            S5_CENSUS_PROTOCOL_PATH,
            S5_CENSUS_PROTOCOL_AUDIT_PATH,
            S5_CENSUS_RESULT_PATH,
            S5_CENSUS_RESULT_AUDIT_PATH,
            READINESS_V30_RESULT_PATH,
            READINESS_V30_AUDIT_PATH,
        )
        expected_bindings = {
            path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(): sha256(
                path.read_bytes()
            ).hexdigest()
            for path in expected_binding_paths
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    return (
        audit_s5_github_transport_decision(decision)
        and {item.path: item.file_sha256 for item in decision.source_bindings} == expected_bindings
        and len(decision.source_bindings) == 6
        and decision.endpoint == "https://api.github.com/repos/bitcoin/bitcoin/pulls"
        and decision.method == "GET"
        and decision.accept_header == "application/vnd.github+json"
        and decision.api_version_header == "2026-03-10"
        and decision.selected_query_state == "closed"
        and decision.selected_query_base == "master"
        and decision.selected_query_sort == "created"
        and decision.selected_query_direction == "asc"
        and decision.preflight_query_per_page == 1
        and decision.preflight_query_page == 1
        and decision.maximum_records_per_list_page == 100
        and decision.unauthenticated_requests_per_hour == 60
        and decision.authenticated_requests_per_hour == 5_000
        and decision.census_recognized_pull_request_count == 7_961
        and decision.census_unrecognized_merge_count == 8_760
        and decision.direct_request_count == 7_961
        and decision.direct_unauthenticated_hours_lower_bound == 133
        and decision.direct_authenticated_hours_lower_bound == 2
        and decision.census_list_page_lower_bound == 80
        and decision.selected_transport == "REST_LIST_CLOSED_MASTER_PULLS"
        and decision.selected_transport_requires_authentication is False
        and decision.token_value_access_permitted is False
        and decision.preflight_request_count == 1
        and decision.preflight_maximum_response_bytes == 1_048_576
        and decision.preflight_maximum_elapsed_seconds == 60
        and decision.preflight_maximum_redirects == 0
        and decision.preflight_must_parse_terminal_link_page is True
        and decision.preflight_must_validate_rate_limit_headers is True
        and decision.preflight_must_validate_pull_schema is True
        and decision.acquisition_page_count_known is False
        and decision.acquisition_request_budget_authorized is False
        and decision.passed_gate_count == 12
        and decision.failed_gate_count == 0
        and decision.github_api_requests_executed == 0
        and decision.github_metadata_records_parsed == 0
        and decision.network_response_bytes_received == 0
        and decision.btc_market_values_read == 0
        and decision.parameters_defined == 0
        and decision.returns_calculated == 0
        and decision.candidates_created == 0
        and decision.strategy_executions == 0
        and decision.orders_submitted == 0
        and decision.decision == S5_GITHUB_TRANSPORT_DECISION
        and decision.next_authorization == S5_GITHUB_TRANSPORT_NEXT
        and decision.authorizes_preflight_protocol_design is True
        and decision.authorizes_preflight_request_now is False
        and decision.authorizes_bulk_metadata_acquisition is False
        and decision.authorizes_market_values is False
        and decision.authorizes_parameters is False
        and decision.authorizes_returns is False
        and decision.authorizes_paper is False
        and decision.authorizes_testnet_strategy_orders is False
        and decision.authorizes_production is False
        and decision.authorizes_live is False
        and decision.real_net_profit_usd == "0"
        and audit_s5_github_transport_decision_audit(audit)
        and audit.decision_file_sha256
        == sha256(S5_GITHUB_TRANSPORT_DECISION_PATH.read_bytes()).hexdigest()
        and audit.decision_evidence_hash == decision.decision_evidence_hash
        and audit.builder_contract_hash == decision.builder_contract_hash
        and audit.reconstructed_exactly is True
        and audit.source_binding_count == 6
        and audit.option_count == 5
        and audit.passed_gate_count == 12
        and audit.failed_gate_count == 0
        and audit.selected_transport == decision.selected_transport
        and audit.preflight_request_count == 1
        and audit.github_api_requests_observed == 0
        and audit.github_metadata_records_parsed == 0
        and audit.market_values_read == 0
        and audit.returns_calculated == 0
        and audit.orders_submitted == 0
        and audit.next_authorization == S5_GITHUB_TRANSPORT_NEXT
    )


def verify_s5_github_preflight_corrected_checkpoint(
    *, transport_selected: bool | None = None
) -> bool:
    if transport_selected is None:
        transport_selected = verify_s5_github_transport_decision_checkpoint()
    if not transport_selected:
        return False

    def expected_bindings(paths: tuple[Path, ...]) -> dict[str, str]:
        return {
            path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(): sha256(
                path.read_bytes()
            ).hexdigest()
            for path in paths
        }

    try:
        protocol = S5GitHubPreflightProtocol.model_validate(
            read_json(S5_GITHUB_PREFLIGHT_PROTOCOL_PATH)
        )
        protocol_audit = S5GitHubPreflightProtocolAudit.model_validate(
            read_json(S5_GITHUB_PREFLIGHT_PROTOCOL_AUDIT_PATH)
        )
        prior_result = S5GitHubPreflightResult.model_validate(
            read_json(S5_GITHUB_PREFLIGHT_RESULT_V1_PATH)
        )
        prior_result_audit = S5GitHubPreflightResultAudit.model_validate(
            read_json(S5_GITHUB_PREFLIGHT_RESULT_AUDIT_V1_PATH)
        )
        failure_audit = S5GitHubPreflightFailureAudit.model_validate(
            read_json(S5_GITHUB_PREFLIGHT_FAILURE_AUDIT_PATH)
        )
        amendment = S5GitHubPreflightInterpreterAmendmentV2.model_validate(
            read_json(S5_GITHUB_PREFLIGHT_AMENDMENT_V2_PATH)
        )
        amendment_audit = S5GitHubPreflightInterpreterAmendmentAuditV2.model_validate(
            read_json(S5_GITHUB_PREFLIGHT_AMENDMENT_AUDIT_V2_PATH)
        )
        corrected = S5GitHubPreflightCorrectedResultV2.model_validate(
            read_json(S5_GITHUB_PREFLIGHT_CORRECTED_RESULT_V2_PATH)
        )
        corrected_audit = S5GitHubPreflightCorrectedResultAuditV2.model_validate(
            read_json(S5_GITHUB_PREFLIGHT_CORRECTED_RESULT_AUDIT_V2_PATH)
        )
        protocol_bindings = expected_bindings(
            (
                READINESS_V31_AUDIT_PATH,
                READINESS_V31_RESULT_PATH,
                S5_GITHUB_TRANSPORT_DECISION_AUDIT_PATH,
                S5_GITHUB_TRANSPORT_DECISION_PATH,
            )
        )
        failure_bindings = expected_bindings(
            (
                S5_GITHUB_PREFLIGHT_PROTOCOL_AUDIT_PATH,
                S5_GITHUB_PREFLIGHT_PROTOCOL_PATH,
                S5_GITHUB_PREFLIGHT_RESULT_AUDIT_V1_PATH,
                S5_GITHUB_PREFLIGHT_RESULT_V1_PATH,
                S5_GITHUB_REPOSITORY_METADATA_PATH,
                S5_SOURCE_RESULT_PATH,
                S5_GITHUB_PREFLIGHT_TRANSCRIPT_PATH,
            )
        )
        amendment_bindings = expected_bindings(
            (
                S5_GITHUB_PREFLIGHT_FAILURE_AUDIT_PATH,
                S5_GITHUB_PREFLIGHT_RESULT_AUDIT_V1_PATH,
                S5_GITHUB_PREFLIGHT_RESULT_V1_PATH,
            )
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    transcript_sha256 = sha256(S5_GITHUB_PREFLIGHT_TRANSCRIPT_PATH.read_bytes()).hexdigest()
    return (
        audit_s5_github_preflight_protocol(protocol)
        and {item.path: item.file_sha256 for item in protocol.source_bindings} == protocol_bindings
        and protocol.status == "FROZEN_PROTOCOL_ONLY_ZERO_REQUESTS"
        and protocol.maximum_request_attempt_count == 1
        and protocol.authorization_header_permitted is False
        and protocol.authorizes_bulk_metadata_acquisition is False
        and audit_s5_github_preflight_protocol_audit(protocol_audit)
        and protocol_audit.protocol_file_sha256
        == sha256(S5_GITHUB_PREFLIGHT_PROTOCOL_PATH.read_bytes()).hexdigest()
        and protocol_audit.protocol_evidence_hash == protocol.protocol_evidence_hash
        and audit_s5_github_preflight_result(prior_result)
        and prior_result.transcript_file_sha256 == transcript_sha256
        and prior_result.request_attempt_count == 1
        and prior_result.http_status == 200
        and prior_result.decision == S5_GITHUB_PREFLIGHT_STOP
        and prior_result.authorizes_bulk_acquisition_protocol_design is False
        and prior_result.authorizes_bulk_metadata_acquisition_now is False
        and audit_s5_github_preflight_result_audit(prior_result_audit)
        and prior_result_audit.result_file_sha256
        == sha256(S5_GITHUB_PREFLIGHT_RESULT_V1_PATH.read_bytes()).hexdigest()
        and prior_result_audit.result_evidence_hash == prior_result.result_evidence_hash
        and prior_result_audit.reconstructed_exactly is True
        and evidence_hash_valid(failure_audit, "audit_evidence_hash")
        and {item.path: item.file_sha256 for item in failure_audit.source_bindings}
        == failure_bindings
        and failure_audit.prior_result_evidence_hash == prior_result.result_evidence_hash
        and failure_audit.transport_succeeded is True
        and failure_audit.original_stop_preserved is True
        and failure_audit.additional_request_count == 0
        and evidence_hash_valid(amendment, "amendment_evidence_hash")
        and {item.path: item.file_sha256 for item in amendment.source_bindings}
        == amendment_bindings
        and amendment.failure_audit_evidence_hash == failure_audit.audit_evidence_hash
        and amendment.corrected_required_identity_field == "head.sha"
        and amendment.additional_network_requests_permitted == 0
        and evidence_hash_valid(amendment_audit, "audit_evidence_hash")
        and amendment_audit.amendment_file_sha256
        == sha256(S5_GITHUB_PREFLIGHT_AMENDMENT_V2_PATH.read_bytes()).hexdigest()
        and amendment_audit.amendment_evidence_hash == amendment.amendment_evidence_hash
        and amendment_audit.reconstructed_exactly is True
        and evidence_hash_valid(corrected, "result_evidence_hash")
        and corrected.protocol_evidence_hash == protocol.protocol_evidence_hash
        and corrected.prior_result_evidence_hash == prior_result.result_evidence_hash
        and corrected.failure_audit_evidence_hash == failure_audit.audit_evidence_hash
        and corrected.amendment_evidence_hash == amendment.amendment_evidence_hash
        and corrected.amendment_audit_evidence_hash == amendment_audit.audit_evidence_hash
        and corrected.transcript_file_sha256 == transcript_sha256
        and corrected.local_revalidation_count == 1
        and corrected.original_request_attempt_count == 1
        and corrected.additional_network_request_count == 0
        and corrected.terminal_record_count == 24_012
        and corrected.bulk_request_page_count_at_100 == 241
        and corrected.passed_gate_count == 14
        and corrected.failed_gate_count == 0
        and corrected.decision == S5_GITHUB_PREFLIGHT_CORRECTED_PASS
        and corrected.next_authorization == S5_GITHUB_PREFLIGHT_NEXT
        and corrected.authorizes_bulk_acquisition_protocol_design is True
        and corrected.authorizes_bulk_metadata_acquisition_now is False
        and corrected.authorizes_market_values is False
        and corrected.authorizes_parameters is False
        and corrected.authorizes_returns is False
        and corrected.authorizes_paper is False
        and corrected.authorizes_testnet_strategy_orders is False
        and corrected.authorizes_production is False
        and corrected.authorizes_live is False
        and corrected.real_net_profit_usd == "0"
        and evidence_hash_valid(corrected_audit, "audit_evidence_hash")
        and corrected_audit.result_file_sha256
        == sha256(S5_GITHUB_PREFLIGHT_CORRECTED_RESULT_V2_PATH.read_bytes()).hexdigest()
        and corrected_audit.result_evidence_hash == corrected.result_evidence_hash
        and corrected_audit.reconstructed_exactly is True
        and corrected_audit.transcript_hash_reverified is True
        and corrected_audit.response_body_hash_reverified is True
        and corrected_audit.additional_network_request_count == 0
        and corrected_audit.passed_gate_count == 14
        and corrected_audit.failed_gate_count == 0
        and corrected_audit.next_authorization == S5_GITHUB_PREFLIGHT_NEXT
    )


def verify_s5_github_bulk_acquisition_checkpoint(*, preflight_verified: bool) -> bool:
    if not preflight_verified:
        return False

    def relative(path: Path) -> str:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()

    def bound_sources_valid(model: BaseModel) -> bool:
        try:
            for binding in model.source_bindings:
                path = (PROJECT_ROOT / binding.path).resolve()
                path.relative_to(PROJECT_ROOT.resolve())
                if (
                    not path.is_file()
                    or sha256(path.read_bytes()).hexdigest() != binding.file_sha256
                ):
                    return False
        except (AttributeError, OSError, ValueError):
            return False
        return True

    try:
        protocol = S5GitHubBulkAcquisitionProtocol.model_validate(
            read_json(S5_GITHUB_BULK_PROTOCOL_PATH)
        )
        protocol_audit = S5GitHubBulkProtocolAudit.model_validate(
            read_json(S5_GITHUB_BULK_PROTOCOL_AUDIT_PATH)
        )
        result_v1 = S5GitHubBulkResult.model_validate(
            read_json(S5_GITHUB_BULK_RESULT_V1_PATH)
        )
        failure_audit = S5GitHubBulkFailureAudit.model_validate(
            read_json(S5_GITHUB_BULK_FAILURE_AUDIT_V1_PATH)
        )
        response_amendment = S5GitHubBulkResponseHandlingAmendmentV2.model_validate(
            read_json(S5_GITHUB_BULK_RESPONSE_AMENDMENT_V2_PATH)
        )
        response_amendment_audit = (
            S5GitHubBulkResponseHandlingAmendmentAuditV2.model_validate(
                read_json(S5_GITHUB_BULK_RESPONSE_AMENDMENT_AUDIT_V2_PATH)
            )
        )
        result_v2 = S5GitHubBulkResult.model_validate(
            read_json(S5_GITHUB_BULK_RESULT_V2_PATH)
        )
        suspension_audit = S5GitHubBulkSuspensionFailureAuditV2.model_validate(
            read_json(S5_GITHUB_BULK_SUSPENSION_AUDIT_V2_PATH)
        )
        resume_amendment = S5GitHubBulkContiguousResumeAmendmentV3.model_validate(
            read_json(S5_GITHUB_BULK_RESUME_AMENDMENT_V3_PATH)
        )
        resume_amendment_audit = (
            S5GitHubBulkContiguousResumeAmendmentAuditV3.model_validate(
                read_json(S5_GITHUB_BULK_RESUME_AMENDMENT_AUDIT_V3_PATH)
            )
        )
        result_v3 = S5GitHubBulkResult.model_validate(
            read_json(S5_GITHUB_BULK_RESULT_V3_PATH)
        )
        drift_audit = S5GitHubBulkTerminalDriftFailureAuditV3.model_validate(
            read_json(S5_GITHUB_BULK_DRIFT_AUDIT_V3_PATH)
        )
        monotonic_amendment = S5GitHubBulkMonotonicTerminalAmendmentV4.model_validate(
            read_json(S5_GITHUB_BULK_MONOTONIC_AMENDMENT_V4_PATH)
        )
        monotonic_amendment_audit = (
            S5GitHubBulkMonotonicTerminalAmendmentAuditV4.model_validate(
                read_json(S5_GITHUB_BULK_MONOTONIC_AMENDMENT_AUDIT_V4_PATH)
            )
        )
        result_v4 = S5GitHubBulkResult.model_validate(
            read_json(S5_GITHUB_BULK_RESULT_V4_PATH)
        )
        final_audit = S5GitHubBulkFinalResultAuditV4.model_validate(
            read_json(S5_GITHUB_BULK_FINAL_AUDIT_V4_PATH)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    bound_models = (
        protocol,
        failure_audit,
        response_amendment,
        suspension_audit,
        resume_amendment,
        drift_audit,
        monotonic_amendment,
    )
    if not all(bound_sources_valid(model) for model in bound_models):
        return False

    historical_results = (result_v1, result_v2, result_v3)
    if not all(
        evidence_hash_valid(result, "result_evidence_hash")
        for result in historical_results
    ):
        return False
    for result, failure_path in zip(
        historical_results, S5_GITHUB_BULK_FAILURE_PATHS, strict=True
    ):
        if not (
            result.decision == S5_GITHUB_BULK_STOP
            and result.protocol_evidence_hash == protocol.protocol_evidence_hash
            and result.failure_artifact_path == relative(failure_path)
            and result.failure_artifact_sha256 == sha256(failure_path.read_bytes()).hexdigest()
            and result.authorizes_normalization_protocol_design is False
            and result.authorizes_market_values is False
            and result.authorizes_returns is False
            and result.authorizes_testnet_strategy_orders is False
            and result.authorizes_live is False
        ):
            return False

    expected_runner_contract = universe_evidence_hash(
        {
            "sources": tuple(
                {
                    "path": path,
                    "file_sha256": sha256((PROJECT_ROOT / path).read_bytes()).hexdigest(),
                }
                for path in S5_GITHUB_BULK_V4_RUNNER_SOURCES
            )
        }
    )
    runner_path = S5_GITHUB_BULK_V4_RUNNER_SOURCES[-1]
    expected_final_auditor_contract = universe_evidence_hash(
        {
            "runner_path": runner_path,
            "runner_sha256": sha256((PROJECT_ROOT / runner_path).read_bytes()).hexdigest(),
            "script_path": S5_GITHUB_BULK_FINAL_AUDITOR_SOURCE,
            "script_sha256": sha256(
                (PROJECT_ROOT / S5_GITHUB_BULK_FINAL_AUDITOR_SOURCE).read_bytes()
            ).hexdigest(),
        }
    )

    page_files = sorted(S5_GITHUB_BULK_PAGE_DIRECTORY.glob("page_*.json"))
    expected_page_names = [f"page_{page:04d}.json" for page in range(1, 246)]
    observed_failure_files = sorted(S5_GITHUB_BULK_PAGE_DIRECTORY.glob("failure*.json"))
    if (
        [path.name for path in page_files] != expected_page_names
        or observed_failure_files != sorted(S5_GITHUB_BULK_FAILURE_PATHS)
        or list(S5_GITHUB_BULK_PAGE_DIRECTORY.glob("*.part"))
        or len(result_v4.page_bindings) != 245
    ):
        return False
    for page, (path, binding) in enumerate(
        zip(page_files, result_v4.page_bindings, strict=True), start=1
    ):
        if not (
            binding.page == page
            and binding.path == relative(path)
            and binding.file_byte_count == path.stat().st_size
            and binding.file_sha256 == sha256(path.read_bytes()).hexdigest()
            and binding.record_count == (7 if page == 245 else 100)
        ):
            return False

    return all(
        (
            evidence_hash_valid(protocol, "protocol_evidence_hash"),
            evidence_hash_valid(protocol_audit, "audit_evidence_hash"),
            protocol_audit.protocol_file_sha256
            == sha256(S5_GITHUB_BULK_PROTOCOL_PATH.read_bytes()).hexdigest(),
            protocol_audit.protocol_evidence_hash == protocol.protocol_evidence_hash,
            evidence_hash_valid(failure_audit, "audit_evidence_hash"),
            failure_audit.prior_result_evidence_hash == result_v1.result_evidence_hash,
            failure_audit.original_stop_preserved is True,
            response_amendment.failure_audit_evidence_hash == failure_audit.audit_evidence_hash,
            response_amendment.prior_result_evidence_hash == result_v1.result_evidence_hash,
            response_amendment.maximum_total_request_attempts_including_prior_failure == 300,
            evidence_hash_valid(response_amendment_audit, "audit_evidence_hash"),
            response_amendment_audit.amendment_file_sha256
            == sha256(S5_GITHUB_BULK_RESPONSE_AMENDMENT_V2_PATH.read_bytes()).hexdigest(),
            response_amendment_audit.amendment_evidence_hash
            == response_amendment.amendment_evidence_hash,
            result_v2.successful_request_count == 117,
            result_v2.raw_record_count == 11_700,
            suspension_audit.prior_result_evidence_hash == result_v2.result_evidence_hash,
            suspension_audit.total_request_attempt_count == 118,
            suspension_audit.page_118_request_attempted is False,
            resume_amendment.suspension_failure_audit_evidence_hash
            == suspension_audit.audit_evidence_hash,
            resume_amendment.prior_result_evidence_hash == result_v2.result_evidence_hash,
            evidence_hash_valid(resume_amendment_audit, "audit_evidence_hash"),
            resume_amendment_audit.amendment_file_sha256
            == sha256(S5_GITHUB_BULK_RESUME_AMENDMENT_V3_PATH.read_bytes()).hexdigest(),
            result_v3.successful_request_count == 117,
            result_v3.raw_record_count == 11_700,
            drift_audit.prior_result_evidence_hash == result_v3.result_evidence_hash,
            drift_audit.total_request_attempt_count == 119,
            drift_audit.candidate_page == 118,
            drift_audit.observed_terminal_page == 245,
            drift_audit.candidate_page_reusable_without_request is True,
            monotonic_amendment.terminal_drift_audit_evidence_hash
            == drift_audit.audit_evidence_hash,
            monotonic_amendment.prior_result_evidence_hash == result_v3.result_evidence_hash,
            monotonic_amendment.maximum_completable_terminal_page == 299,
            monotonic_amendment.promoted_page_additional_request_count == 0,
            evidence_hash_valid(monotonic_amendment_audit, "audit_evidence_hash"),
            monotonic_amendment_audit.amendment_file_sha256
            == sha256(S5_GITHUB_BULK_MONOTONIC_AMENDMENT_V4_PATH.read_bytes()).hexdigest(),
            monotonic_amendment_audit.amendment_evidence_hash
            == monotonic_amendment.amendment_evidence_hash,
            evidence_hash_valid(result_v4, "result_evidence_hash"),
            result_v4.runner_contract_hash == expected_runner_contract,
            result_v4.decision == S5_GITHUB_BULK_PASS,
            result_v4.next_authorization == S5_GITHUB_BULK_NEXT,
            result_v4.successful_request_count == 245,
            result_v4.terminal_page_count == 245,
            result_v4.raw_record_count == 24_407,
            result_v4.cohort_record_count == 24_398,
            result_v4.post_cutoff_record_count == 9,
            result_v4.duplicate_pull_number_count == 0,
            result_v4.passed_gate_count == 16,
            result_v4.failed_gate_count == 0,
            result_v4.total_response_bytes
            == sum(binding.response_byte_count for binding in result_v4.page_bindings),
            result_v4.authorizes_normalization_protocol_design is True,
            result_v4.authorizes_market_values is False,
            result_v4.authorizes_returns is False,
            result_v4.authorizes_paper is False,
            result_v4.authorizes_testnet_strategy_orders is False,
            result_v4.authorizes_production is False,
            result_v4.authorizes_live is False,
            result_v4.real_net_profit_usd == "0",
            evidence_hash_valid(final_audit, "audit_evidence_hash"),
            final_audit.result_file_sha256
            == sha256(S5_GITHUB_BULK_RESULT_V4_PATH.read_bytes()).hexdigest(),
            final_audit.result_evidence_hash == result_v4.result_evidence_hash,
            final_audit.amendment_evidence_hash
            == monotonic_amendment.amendment_evidence_hash,
            final_audit.amendment_audit_evidence_hash
            == monotonic_amendment_audit.audit_evidence_hash,
            final_audit.runner_contract_hash == expected_runner_contract,
            final_audit.auditor_contract_hash == expected_final_auditor_contract,
            final_audit.reconstructed_exactly is True,
            final_audit.every_page_file_hash_reverified is True,
            final_audit.every_response_body_hash_reverified is True,
            final_audit.total_request_attempt_count == 246,
            final_audit.page_count == 245,
            final_audit.raw_record_count == 24_407,
            final_audit.cohort_record_count == 24_398,
            final_audit.post_cutoff_record_count == 9,
            final_audit.failed_gate_count == 0,
            final_audit.next_authorization == S5_GITHUB_BULK_NEXT,
        )
    )


def verify_q1_research_checkpoint() -> bool:
    try:
        charter = PeriodicFlowSpotCharter.model_validate(read_json(Q1_CHARTER_PATH))
        audit = PeriodicFlowSpotCharterAudit.model_validate(read_json(Q1_CHARTER_AUDIT_PATH))
        census_contract = PeriodicFlowMetadataCensusContract.model_validate(
            read_json(Q1_CENSUS_CONTRACT_PATH)
        )
        census_result = PeriodicFlowMetadataCensusResult.model_validate(
            read_json(Q1_CENSUS_RESULT_PATH)
        )
        census_audit = PeriodicFlowMetadataCensusAudit.model_validate(
            read_json(Q1_CENSUS_AUDIT_PATH)
        )
        payload_protocol = PeriodicFlowPayloadPilotProtocol.model_validate(
            read_json(Q1_PAYLOAD_PROTOCOL_PATH)
        )
        transport_amendment = PeriodicFlowPayloadTransportAmendment.model_validate(
            read_json(Q1_PAYLOAD_TRANSPORT_AMENDMENT_PATH)
        )
        payload_result = PeriodicFlowPayloadPilotResult.model_validate(
            read_json(Q1_PAYLOAD_RESULT_PATH)
        )
        payload_audit = PeriodicFlowPayloadPilotAudit.model_validate(
            read_json(Q1_PAYLOAD_AUDIT_PATH)
        )
        gap_protocol = PeriodicFlowGapRemediationProtocol.model_validate(
            read_json(Q1_GAP_PROTOCOL_PATH)
        )
        gap_result = PeriodicFlowGapRemediationResult.model_validate(read_json(Q1_GAP_RESULT_PATH))
        gap_audit = PeriodicFlowGapRemediationAudit.model_validate(read_json(Q1_GAP_AUDIT_PATH))
        overlap_protocol = PeriodicFlowOverlapCensusProtocol.model_validate(
            read_json(Q1_OVERLAP_PROTOCOL_PATH)
        )
        overlap_result = PeriodicFlowOverlapCensusResult.model_validate(
            read_json(Q1_OVERLAP_RESULT_PATH)
        )
        overlap_audit = PeriodicFlowOverlapCensusAudit.model_validate(
            read_json(Q1_OVERLAP_AUDIT_PATH)
        )
        daily_protocol = PeriodicFlowDailyCrossSourceProtocol.model_validate(
            read_json(Q1_DAILY_PROTOCOL_PATH)
        )
        daily_result = PeriodicFlowDailyCrossSourceResult.model_validate(
            read_json(Q1_DAILY_RESULT_PATH)
        )
        daily_audit = PeriodicFlowDailyCrossSourceAudit.model_validate(
            read_json(Q1_DAILY_AUDIT_PATH)
        )
        raw_protocol = RawTradesMetadataCensusProtocol.model_validate(
            read_json(Q1_RAW_TRADES_PROTOCOL_PATH)
        )
        raw_protocol_audit = RawTradesMetadataProtocolAudit.model_validate(
            read_json(Q1_RAW_TRADES_PROTOCOL_AUDIT_PATH)
        )
        raw_result = RawTradesMetadataCensusResult.model_validate(
            read_json(Q1_RAW_TRADES_RESULT_PATH)
        )
        raw_audit = RawTradesMetadataCensusAudit.model_validate(read_json(Q1_RAW_TRADES_AUDIT_PATH))
        raw_payload_protocol = RawTradesPayloadPilotProtocol.model_validate(
            read_json(Q1_RAW_PAYLOAD_PROTOCOL_PATH)
        )
        raw_payload_protocol_audit = RawTradesPayloadProtocolAudit.model_validate(
            read_json(Q1_RAW_PAYLOAD_PROTOCOL_AUDIT_PATH)
        )
        raw_payload_result = RawTradesPayloadPilotResultV2.model_validate(
            read_json(Q1_RAW_PAYLOAD_RESULT_PATH)
        )
        raw_payload_audit = RawTradesPayloadPilotAuditV2.model_validate(
            read_json(Q1_RAW_PAYLOAD_AUDIT_PATH)
        )
        full_protocol = PeriodicFlowFullDevelopmentProtocol.model_validate(
            read_json(Q1_FULL_DEVELOPMENT_PROTOCOL_PATH)
        )
        full_protocol_audit = PeriodicFlowFullDevelopmentProtocolAudit.model_validate(
            read_json(Q1_FULL_DEVELOPMENT_PROTOCOL_AUDIT_PATH)
        )
        execution_contract = PeriodicFlowExecutionContract.model_validate(
            read_json(Q1_FULL_DEVELOPMENT_EXECUTION_CONTRACT_PATH)
        )
        execution_contract_audit = PeriodicFlowExecutionContractAudit.model_validate(
            read_json(Q1_FULL_DEVELOPMENT_EXECUTION_CONTRACT_AUDIT_PATH)
        )
        acquisition_preflight = PeriodicFlowAcquisitionPreflightResult.model_validate(
            read_json(Q1_FULL_DEVELOPMENT_PREFLIGHT_RESULT_PATH)
        )
        acquisition_preflight_audit = PeriodicFlowAcquisitionPreflightAudit.model_validate(
            read_json(Q1_FULL_DEVELOPMENT_PREFLIGHT_AUDIT_PATH)
        )
        full_readiness = StrategyFactoryReadinessResult.model_validate(
            read_json(Q1_FULL_READINESS_RESULT_PATH)
        )
        full_readiness_audit = StrategyFactoryReadinessAudit.model_validate(
            read_json(Q1_FULL_READINESS_AUDIT_PATH)
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    charter_file_hash = sha256(Q1_CHARTER_PATH.read_bytes()).hexdigest()
    census_contract_file_hash = sha256(Q1_CENSUS_CONTRACT_PATH.read_bytes()).hexdigest()
    census_result_file_hash = sha256(Q1_CENSUS_RESULT_PATH.read_bytes()).hexdigest()
    payload_protocol_file_hash = sha256(Q1_PAYLOAD_PROTOCOL_PATH.read_bytes()).hexdigest()
    payload_result_file_hash = sha256(Q1_PAYLOAD_RESULT_PATH.read_bytes()).hexdigest()
    gap_result_file_hash = sha256(Q1_GAP_RESULT_PATH.read_bytes()).hexdigest()
    overlap_result_file_hash = sha256(Q1_OVERLAP_RESULT_PATH.read_bytes()).hexdigest()
    daily_result_file_hash = sha256(Q1_DAILY_RESULT_PATH.read_bytes()).hexdigest()
    raw_protocol_file_hash = sha256(Q1_RAW_TRADES_PROTOCOL_PATH.read_bytes()).hexdigest()
    raw_protocol_audit_file_hash = sha256(
        Q1_RAW_TRADES_PROTOCOL_AUDIT_PATH.read_bytes()
    ).hexdigest()
    raw_result_file_hash = sha256(Q1_RAW_TRADES_RESULT_PATH.read_bytes()).hexdigest()
    raw_audit_file_hash = sha256(Q1_RAW_TRADES_AUDIT_PATH.read_bytes()).hexdigest()
    raw_payload_protocol_file_hash = sha256(Q1_RAW_PAYLOAD_PROTOCOL_PATH.read_bytes()).hexdigest()
    raw_payload_protocol_audit_file_hash = sha256(
        Q1_RAW_PAYLOAD_PROTOCOL_AUDIT_PATH.read_bytes()
    ).hexdigest()
    raw_payload_result_file_hash = sha256(Q1_RAW_PAYLOAD_RESULT_PATH.read_bytes()).hexdigest()
    raw_payload_audit_file_hash = sha256(Q1_RAW_PAYLOAD_AUDIT_PATH.read_bytes()).hexdigest()
    full_protocol_file_hash = sha256(Q1_FULL_DEVELOPMENT_PROTOCOL_PATH.read_bytes()).hexdigest()
    execution_contract_file_hash = sha256(
        Q1_FULL_DEVELOPMENT_EXECUTION_CONTRACT_PATH.read_bytes()
    ).hexdigest()
    acquisition_preflight_result_file_hash = sha256(
        Q1_FULL_DEVELOPMENT_PREFLIGHT_RESULT_PATH.read_bytes()
    ).hexdigest()
    full_readiness_result_file_hash = sha256(Q1_FULL_READINESS_RESULT_PATH.read_bytes()).hexdigest()
    return (
        audit_periodic_flow_spot_charter(charter)
        and audit_periodic_flow_spot_charter_audit(audit)
        and audit.charter_file_sha256 == charter_file_hash
        and audit.charter_evidence_hash == charter.charter_evidence_hash
        and audit.builder_contract_hash == charter.builder_contract_hash
        and charter.next_authorization == PERIODIC_FLOW_NEXT_AUTHORIZATION
        and audit_metadata_census_contract(census_contract)
        and audit_metadata_census_result(census_result)
        and audit_metadata_census_audit(census_audit)
        and census_contract.charter_file_sha256 == charter_file_hash
        and census_contract.charter_evidence_hash == charter.charter_evidence_hash
        and census_result.contract_file_sha256 == census_contract_file_hash
        and census_result.contract_evidence_hash == census_contract.contract_evidence_hash
        and census_audit.result_file_sha256 == census_result_file_hash
        and census_audit.result_evidence_hash == census_result.result_evidence_hash
        and census_result.decision == Q1_CENSUS_PASS_DECISION
        and census_result.next_authorization == Q1_CENSUS_PASS_AUTHORIZATION
        and census_result.archive_payload_requests_made == 0
        and census_result.market_numeric_fields_inspected == ()
        and census_result.return_metrics_calculated == ()
        and audit_periodic_flow_payload_protocol(payload_protocol)
        and audit_periodic_flow_transport_amendment(transport_amendment)
        and transport_amendment.parent_protocol_file_sha256 == payload_protocol_file_hash
        and transport_amendment.parent_protocol_evidence_hash
        == payload_protocol.protocol_evidence_hash
        and audit_periodic_flow_payload_result(payload_result)
        and audit_periodic_flow_payload_audit(payload_audit)
        and payload_result.protocol_evidence_hash == payload_protocol.protocol_evidence_hash
        and payload_audit.result_file_sha256 == payload_result_file_hash
        and payload_audit.result_evidence_hash == payload_result.result_evidence_hash
        and payload_result.decision == Q1_PAYLOAD_FAIL_DECISION
        and payload_result.next_authorization == Q1_PAYLOAD_FAIL_AUTHORIZATION
        and payload_result.price_or_quantity_values_parsed == ()
        and payload_result.return_metrics_calculated == ()
        and audit_gap_remediation_protocol(gap_protocol)
        and audit_gap_remediation_result(gap_result)
        and audit_gap_remediation_audit(gap_audit)
        and gap_protocol.parent_result_file_sha256 == payload_result_file_hash
        and gap_protocol.parent_result_evidence_hash == payload_result.result_evidence_hash
        and gap_audit.result_file_sha256 == gap_result_file_hash
        and gap_audit.result_evidence_hash == gap_result.result_evidence_hash
        and gap_result.decision == Q1_GAP_FAIL_DECISION
        and gap_result.next_authorization == Q1_GAP_FAIL_AUTHORIZATION
        and gap_result.raw_trade_range_overlap_count == 1
        and gap_result.price_or_quantity_values_parsed == ()
        and gap_result.return_metrics_calculated == ()
        and audit_overlap_census_protocol(overlap_protocol)
        and audit_overlap_census_result(overlap_result)
        and audit_overlap_census_audit(overlap_audit)
        and overlap_protocol.parent_result_file_sha256 == gap_result_file_hash
        and overlap_protocol.parent_result_evidence_hash == gap_result.result_evidence_hash
        and overlap_audit.result_file_sha256 == overlap_result_file_hash
        and overlap_audit.result_evidence_hash == overlap_result.result_evidence_hash
        and overlap_result.decision == Q1_OVERLAP_PASS_DECISION
        and overlap_result.next_authorization == Q1_OVERLAP_PASS_AUTHORIZATION
        and overlap_result.archive_payload_requests_made == 0
        and overlap_result.price_or_quantity_values_parsed == ()
        and audit_daily_cross_protocol(daily_protocol)
        and audit_daily_cross_result(daily_result)
        and audit_daily_cross_audit(daily_audit)
        and daily_protocol.census_result_file_sha256 == overlap_result_file_hash
        and daily_protocol.census_result_evidence_hash == overlap_result.result_evidence_hash
        and daily_audit.result_file_sha256 == daily_result_file_hash
        and daily_audit.result_evidence_hash == daily_result.result_evidence_hash
        and daily_result.decision == Q1_DAILY_CROSS_PASS_DECISION
        and daily_result.next_authorization == Q1_DAILY_CROSS_PASS_AUTHORIZATION
        and daily_result.authorizes_usdm_raw_trades_metadata_census_protocol
        and daily_result.price_or_quantity_values_parsed == ()
        and daily_result.return_metrics_calculated == ()
        and not daily_result.authorizes_paper_operation
        and not daily_result.authorizes_testnet_strategy_orders
        and not daily_result.authorizes_production
        and not daily_result.authorizes_live
        and audit_raw_trades_protocol(raw_protocol)
        and audit_raw_trades_protocol_audit(raw_protocol_audit)
        and audit_raw_trades_result(raw_result)
        and audit_raw_trades_audit(raw_audit)
        and raw_protocol.parent_result_file_sha256 == daily_result_file_hash
        and raw_protocol.parent_result_evidence_hash == daily_result.result_evidence_hash
        and raw_protocol_audit.protocol_file_sha256 == raw_protocol_file_hash
        and raw_protocol_audit.protocol_evidence_hash == raw_protocol.protocol_evidence_hash
        and raw_result.protocol_file_sha256 == raw_protocol_file_hash
        and raw_result.protocol_evidence_hash == raw_protocol.protocol_evidence_hash
        and raw_result.protocol_audit_file_sha256 == raw_protocol_audit_file_hash
        and raw_result.protocol_audit_evidence_hash == raw_protocol_audit.audit_evidence_hash
        and raw_audit.result_file_sha256 == raw_result_file_hash
        and raw_audit.result_evidence_hash == raw_result.result_evidence_hash
        and raw_result.decision == RAW_TRADES_PASS_DECISION
        and raw_result.next_authorization == RAW_TRADES_PASS_AUTHORIZATION
        and raw_result.authorizes_one_month_payload_protocol
        and raw_result.summary.present_count == 72
        and raw_result.summary.missing_count == 0
        and raw_result.checksum_get_requests_made == 72
        and raw_result.archive_head_requests_made == 0
        and raw_result.archive_payload_requests_made == 0
        and raw_result.market_numeric_fields_inspected == ()
        and raw_result.return_metrics_calculated == ()
        and not raw_result.authorizes_paper_operation
        and not raw_result.authorizes_testnet_strategy_orders
        and not raw_result.authorizes_production
        and not raw_result.authorizes_live
        and audit_raw_payload_protocol(raw_payload_protocol)
        and audit_raw_payload_protocol_audit(raw_payload_protocol_audit)
        and audit_raw_payload_result_v2(raw_payload_result)
        and audit_raw_payload_audit_v2(raw_payload_audit)
        and raw_payload_protocol.raw_census_result_file_sha256 == raw_result_file_hash
        and raw_payload_protocol.raw_census_result_evidence_hash == raw_result.result_evidence_hash
        and raw_payload_protocol.raw_census_audit_file_sha256 == raw_audit_file_hash
        and raw_payload_protocol.raw_census_audit_evidence_hash == raw_audit.audit_evidence_hash
        and raw_payload_protocol.source_adjudication_result_file_sha256 == daily_result_file_hash
        and raw_payload_protocol.source_adjudication_result_evidence_hash
        == daily_result.result_evidence_hash
        and raw_payload_protocol.qualified_spot_reference.source_result_file_sha256
        == payload_result_file_hash
        and raw_payload_protocol.qualified_spot_reference.source_result_evidence_hash
        == payload_result.result_evidence_hash
        and raw_payload_protocol_audit.protocol_file_sha256 == raw_payload_protocol_file_hash
        and raw_payload_protocol_audit.protocol_evidence_hash
        == raw_payload_protocol.protocol_evidence_hash
        and raw_payload_protocol_audit.payload_requests_made == 0
        and not raw_payload_protocol_audit.authorizes_full_acquisition
        and not raw_payload_protocol_audit.authorizes_outcomes
        and not raw_payload_protocol_audit.authorizes_trading
        and raw_payload_result.protocol_file_sha256 == raw_payload_protocol_file_hash
        and raw_payload_result.protocol_evidence_hash == raw_payload_protocol.protocol_evidence_hash
        and raw_payload_result.protocol_audit_file_sha256 == raw_payload_protocol_audit_file_hash
        and raw_payload_result.protocol_audit_evidence_hash
        == raw_payload_protocol_audit.audit_evidence_hash
        and raw_payload_audit.result_file_sha256 == raw_payload_result_file_hash
        and raw_payload_audit.result_evidence_hash == raw_payload_result.result_evidence_hash
        and raw_payload_audit.protocol_evidence_hash == raw_payload_protocol.protocol_evidence_hash
        and raw_payload_audit.raw_archive_file_sha256
        == raw_payload_result.raw_archive_evidence.archive_sha256
        and raw_payload_audit.spot_archive_file_sha256
        == raw_payload_result.qualified_spot_archive_sha256
        and raw_payload_audit.request_marker_manifest_hash
        == raw_payload_result.request_marker_manifest_hash
        and raw_payload_audit.request_marker_count == 1
        and raw_payload_result.request_marker_count == 1
        and raw_payload_result.payload_get_attempt_count == 1
        and raw_payload_result.decision == RAW_PAYLOAD_PASS_DECISION
        and raw_payload_result.next_authorization == RAW_PAYLOAD_PASS_AUTHORIZATION
        and raw_payload_result.authorizes_paired_full_development_acquisition_protocol
        and raw_payload_result.raw_archive_evidence.archive_pass
        and raw_payload_result.raw_archive_evidence.row_count == 10_281_248
        and raw_payload_result.raw_archive_evidence.unique_minute_count == 44_640
        and raw_payload_result.raw_archive_evidence.trade_id_duplicate_count == 0
        and raw_payload_result.raw_archive_evidence.trade_id_non_increasing_count == 0
        and raw_payload_result.raw_archive_evidence.maximum_single_skipped_trade_id_count == 35
        and raw_payload_result.raw_archive_evidence.timestamp_regression_count == 0
        and raw_payload_result.paired_clock_evidence.paired_minute_count == 44_640
        and raw_payload_result.paired_clock_evidence.paired_clock_pass
        and raw_payload_result.price_or_quantity_values_parsed == ()
        and raw_payload_result.features_calculated == ()
        and raw_payload_result.parameters_defined == ()
        and raw_payload_result.return_metrics_calculated == ()
        and raw_payload_result.strategy_candidates_created == 0
        and raw_payload_result.strategy_executions == 0
        and raw_payload_result.orders_submitted == 0
        and not raw_payload_result.authorizes_pine_deployment
        and not raw_payload_result.authorizes_paper_operation
        and not raw_payload_result.authorizes_testnet_strategy_orders
        and not raw_payload_result.authorizes_production
        and not raw_payload_result.authorizes_live
        and audit_full_development_protocol(full_protocol)
        and audit_full_development_protocol_audit(full_protocol_audit)
        and full_protocol_audit.protocol_file_sha256 == full_protocol_file_hash
        and full_protocol_audit.protocol_evidence_hash == full_protocol.protocol_evidence_hash
        and full_protocol.parent_result_file_sha256 == raw_payload_result_file_hash
        and full_protocol.parent_result_evidence_hash == raw_payload_result.result_evidence_hash
        and full_protocol.parent_audit_file_sha256 == raw_payload_audit_file_hash
        and full_protocol.parent_audit_evidence_hash == raw_payload_audit.audit_evidence_hash
        and full_protocol.spot_census_result_file_sha256 == census_result_file_hash
        and full_protocol.spot_census_result_evidence_hash == census_result.result_evidence_hash
        and full_protocol.spot_census_audit_file_sha256
        == sha256(Q1_CENSUS_AUDIT_PATH.read_bytes()).hexdigest()
        and full_protocol.spot_census_audit_evidence_hash == census_audit.audit_evidence_hash
        and full_protocol.raw_census_result_file_sha256 == raw_result_file_hash
        and full_protocol.raw_census_result_evidence_hash == raw_result.result_evidence_hash
        and full_protocol.raw_census_audit_file_sha256 == raw_audit_file_hash
        and full_protocol.raw_census_audit_evidence_hash == raw_audit.audit_evidence_hash
        and full_protocol.jam_acquisition_result_file_sha256
        == sha256(JAM_FULL_RESULT_PATH.read_bytes()).hexdigest()
        and full_protocol.jam_acquisition_audit_file_sha256
        == sha256(JAM_FULL_AUDIT_PATH.read_bytes()).hexdigest()
        and full_protocol.jam_remediation_result_file_sha256
        == sha256(JAM_REMEDIATION_RESULT_PATH.read_bytes()).hexdigest()
        and full_protocol.jam_remediation_audit_file_sha256
        == sha256(JAM_REMEDIATION_AUDIT_PATH.read_bytes()).hexdigest()
        and audit_readiness_result(full_readiness)
        and audit_readiness_audit(full_readiness_audit)
        and full_readiness_audit.result_file_sha256 == full_readiness_result_file_hash
        and full_readiness_audit.result_evidence_hash == full_readiness.result_evidence_hash
        and full_protocol.readiness_result_evidence_hash == full_readiness.result_evidence_hash
        and full_protocol.readiness_audit_evidence_hash == full_readiness_audit.audit_evidence_hash
        and full_protocol.next_authorization == FULL_DEVELOPMENT_AUTHORIZATION
        and len(full_protocol.targets) == 96
        and full_protocol.month_count == 48
        and full_protocol.reuse_candidate_count == 37
        and full_protocol.network_target_count == 59
        and full_protocol.maximum_payload_get_attempts == 177
        and full_protocol_audit.network_requests_made == 0
        and full_protocol_audit.archive_payload_requests_made == 0
        and full_protocol_audit.authorizes_full_development_archive_acquisition
        and not full_protocol_audit.authorizes_features_or_outcomes
        and not full_protocol_audit.authorizes_trading
        and not full_protocol.price_or_quantity_parsing_permitted
        and not full_protocol.feature_calculation_permitted
        and not full_protocol.parameter_definition_permitted
        and not full_protocol.return_calculation_permitted
        and not full_protocol.validation_access_permitted
        and not full_protocol.holdout_access_permitted
        and not full_protocol.candidate_creation_permitted
        and not full_protocol.pine_deployment_permitted
        and not full_protocol.paper_operation_permitted
        and not full_protocol.testnet_strategy_orders_permitted
        and not full_protocol.production_permitted
        and not full_protocol.live_permitted
        and audit_execution_contract(execution_contract)
        and audit_execution_contract_audit(execution_contract_audit)
        and execution_contract.parent_protocol_file_sha256 == full_protocol_file_hash
        and execution_contract.parent_protocol_evidence_hash == full_protocol.protocol_evidence_hash
        and execution_contract.parent_protocol_audit_file_sha256
        == sha256(Q1_FULL_DEVELOPMENT_PROTOCOL_AUDIT_PATH.read_bytes()).hexdigest()
        and execution_contract.parent_protocol_audit_evidence_hash
        == full_protocol_audit.audit_evidence_hash
        and execution_contract_audit.contract_file_sha256 == execution_contract_file_hash
        and execution_contract_audit.contract_evidence_hash
        == execution_contract.contract_evidence_hash
        and execution_contract_audit.network_requests_made == 0
        and execution_contract_audit.payload_bytes_received == 0
        and execution_contract_audit.outcomes_accessed == 0
        and execution_contract_audit.orders_submitted == 0
        and audit_preflight_result(acquisition_preflight)
        and audit_preflight_audit(acquisition_preflight_audit)
        and acquisition_preflight.protocol_file_sha256 == full_protocol_file_hash
        and acquisition_preflight.protocol_evidence_hash == full_protocol.protocol_evidence_hash
        and acquisition_preflight.execution_contract_file_sha256 == execution_contract_file_hash
        and acquisition_preflight.execution_contract_evidence_hash
        == execution_contract.contract_evidence_hash
        and acquisition_preflight.runner_source_hash == execution_contract.runner_source_hash
        and acquisition_preflight.reuse_candidate_count == 37
        and acquisition_preflight.network_target_count == 59
        and acquisition_preflight.network_requests_made == 0
        and acquisition_preflight.payload_bytes_received == 0
        and acquisition_preflight.decision == PREFLIGHT_BLOCK_DECISION
        and acquisition_preflight.free_disk_bytes == 48_036_913_152
        and acquisition_preflight.required_free_disk_bytes == 120_000_000_000
        and acquisition_preflight.additional_free_disk_bytes_required == 71_963_086_848
        and acquisition_preflight.outcomes_accessed == 0
        and acquisition_preflight.orders_submitted == 0
        and acquisition_preflight_audit.result_file_sha256 == acquisition_preflight_result_file_hash
        and acquisition_preflight_audit.result_evidence_hash
        == acquisition_preflight.result_evidence_hash
        and acquisition_preflight_audit.reuse_manifest_hash
        == acquisition_preflight.reuse_manifest_hash
        and acquisition_preflight_audit.decision == PREFLIGHT_BLOCK_DECISION
        and acquisition_preflight_audit.network_requests_made == 0
        and acquisition_preflight_audit.outcomes_accessed == 0
        and acquisition_preflight_audit.orders_submitted == 0
    )
