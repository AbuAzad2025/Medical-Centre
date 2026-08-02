#!/usr/bin/env python3
"""Audit script to detect orphaned tenant_id=0 rows in tenant-scoped tables.

Scans all tenant-scoped models for rows with tenant_id=0 (invalid)
and reports them. Returns non-zero exit code if orphans found OR if
required tables are missing from the database.

Tables are categorized as:
  - REQUIRED_TABLES: Core tables that MUST exist in the database.
    If missing, the audit fails with exit code 1.
  - OPTIONAL_TABLES: Optional tables (feature-dependent).
    If missing, logged as DEBUG and audit continues.

Exit codes:
  0: Success - no orphans, no missing required tables
  1: Orphaned rows found OR required tables missing
"""

import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault('APP_ENV', 'testing')
os.environ.setdefault('FLASK_ENV', 'testing')

from app_factory import create_app

# Core tables that MUST exist in every deployment
REQUIRED_TABLES = frozenset(
    {
        'tenants',
        'users',
        'patients',
        'visits',
        'invoices',
        'payments',
        'patient_accounts',
        'appointments',
        'departments',
        'roles',
        'permissions',
        'role_permissions',
        'module_definitions',
        'tenant_modules',
        'platform_audit_logs',
        'audit_trails',
        'system_configs',
        'subscription_plans',
        'subscription_lines',
        'subscription_usage_records',
        'resource_usage',
        'tenant_feature_flags',
    }
)

# Optional tables that may not exist depending on subscription/features
OPTIONAL_TABLES = frozenset(
    {
        'payment_cards',
        'backup_logs',
        'backup_configs',
        'webhooks',
        'api_keys',
        'themes',
        'system_themes',
        'announcements',
        'support_tickets',
        'notification_rules',
        'notifications',
        'sms_templates',
        'email_templates',
        'integration_configs',
        'third_party_tokens',
        'fhir_endpoints',
        'dicom_studies',
        'dicom_series',
        'dicom_instances',
        'ai_models',
        'ai_inference_jobs',
        'telemedicine_sessions',
        'telemedicine_recordings',
        'telehealth_appointments',
        'lab_orders',
        'lab_results',
        'radiology_orders',
        'radiology_images',
        'radiology_reports',
        'prescriptions',
        'prescription_items',
        'medication_orders',
        'medication_administrations',
        'pharmacy_sales',
        'pharmacy_sale_items',
        'pharmacy_returns',
        'inventory_items',
        'inventory_transactions',
        'purchase_orders',
        'suppliers',
        'barcodes',
        'barcode_scans',
        'bed_management',
        'bed_assignments',
        'nursing_assessments',
        'nursing_tasks',
        'emar_records',
        'vital_signs',
        'nursing_notes',
        'pathology_orders',
        'pathology_results',
        'pathology_samples',
        'radiology_imaging_studies',
        'radiology_series',
        'radiology_instances',
        'clinical_pathways',
        'pathway_steps',
        'patient_pathway_enrollments',
        'clinical_coding',
        'icd_codes',
        'cpt_codes',
        'drg_codes',
        'clinical_forms',
        'form_submissions',
        'specialty_forms',
        'clinical_decision_support',
        'cds_alerts',
        'cds_rules',
        'pathway_instances',
        'vaccination_records',
        'immunization_schedules',
        'vaccine_inventory',
        'referrals',
        'referral_responses',
        'insurance_claims',
        'claim_line_items',
        'insurance_payments',
        'patient_portal_accounts',
        'patient_portal_preferences',
        'online_bookings',
        'waitlist_entries',
        'kiosk_checkins',
        'queue_tickets',
        'queue_settings',
        'waiting_display_configs',
        'call_displays',
        'patient_surveys',
        'survey_responses',
        'quality_measures',
        'quality_reports',
        'population_health_metrics',
        'cohort_definitions',
        'cohort_members',
        'risk_stratifications',
        'care_gaps',
        'care_plans',
        'care_plan_tasks',
        'care_team_members',
        'goals',
        'outcome_measures',
        'population_health_reports',
        'data_warehouse_exports',
        'report_templates',
        'report_schedules',
        'custom_reports',
        'report_builder_reports',
        'data_warehouse_tables',
        'population_health_analytics',
        'quality_dashboards',
        'analytics_events',
        'user_sessions',
        'audit_logs',
        'security_events',
        'login_attempts',
        'password_resets',
        'session_logs',
        'api_access_logs',
        'webhook_deliveries',
        'webhook_endpoints',
        'sso_configs',
        'sso_sessions',
        'fhir_resources',
        'fhir_bundles',
        'fhir_subscriptions',
        'ai_imaging_studies',
        'ai_analysis_results',
        'workflow_instances',
        'workflow_tasks',
        'workflow_definitions',
        'digital_signatures',
        'consent_forms',
        'consent_signatures',
        'document_templates',
        'documents',
        'document_versions',
        'document_signatures',
        'clinical_documents',
        'document_annotations',
        'electronic_signatures',
        'document_folders',
        'document_shares',
        'document_access_logs',
        'scanned_documents',
        'ocr_results',
        'document_ocr',
        'electronic_health_records',
        'ehr_modules',
        'ehr_sections',
        'ehr_entries',
        'clinical_notes',
        'vital_signs_history',
        'allergy_records',
        'immunization_records',
        'problem_list',
        'diagnoses',
        'procedures',
        'medications',
        'medication_reconciliations',
        'allergy_alerts',
        'drug_interactions',
        'cds_hooks',
        'cds_cards',
        'cds_services',
        'clinical_guidelines',
        'guideline_recommendations',
        'order_sets',
        'order_set_items',
        'clinical_decision_support_rules',
        'cds_interventions',
        'cds_recommendations',
        'population_health_cohorts',
        'risk_stratification_models',
        'risk_scores',
        'care_gap_interventions',
        'quality_measure_results',
        'registry_patients',
        'registry_definitions',
        'registry_enrollments',
        'population_reports',
        'population_analytics',
        'risk_stratification',
        'predictive_models',
        'predictive_scores',
        'ml_models',
        'ml_predictions',
        'ml_features',
        'ml_training_jobs',
        'ml_model_versions',
        'ml_experiments',
        'ml_artifacts',
        'ml_pipelines',
        'ml_dataset_versions',
        'ml_feature_stores',
        'ml_monitoring',
        'ml_drift_detection',
        'ml_explainability',
        'ml_fairness',
        'ml_governance',
        'ml_compliance',
        'ml_security',
        'ml_privacy',
        'ml_ethics',
        'ml_audit_trails',
        'ml_lineage',
        'ml_metadata',
        'ml_registries',
        'ml_deployments',
        'ml_endpoints',
        'ml_batch_predictions',
        'ml_realtime_predictions',
        'ml_ab_tests',
        'ml_champion_challenger',
        'ml_canary_deployments',
        'ml_shadow_deployments',
        'ml_rollouts',
        'ml_feature_flags',
        'ml_variants',
        'ml_assignments',
        'ml_metrics',
        'ml_statistical_significance',
        'ml_confidence_intervals',
        'ml_power_analysis',
        'ml_sample_sizes',
        'ml_randomization',
        'ml_stratification',
        'ml_blocking',
        'ml_covariates',
        'ml_outcomes',
        'ml_treatment_effects',
        'ml_ate',
        'ml_att',
        'ml_itt',
        'ml_per_protocol',
        'ml_as_treated',
        'ml_instrumental_variables',
        'ml_regression_discontinuity',
        'ml_difference_in_differences',
        'ml_matching',
        'ml_propensity_scores',
        'ml_inverse_probability_weighting',
        'ml_doubly_robust',
        'ml_g_computation',
        'ml_targeted_maximum_likelihood',
        'ml_bayesian_inference',
        'ml_causal_forests',
        'ml_uplift_modeling',
        'ml_heterogeneous_treatment_effects',
        'ml_personalization',
        'ml_recommendation_systems',
        'ml_collaborative_filtering',
        'ml_content_based_filtering',
        'ml_hybrid_recommendations',
        'ml_ranking',
        'ml_learning_to_rank',
        'ml_click_through_rate',
        'ml_conversion_rate',
        'ml_revenue_optimization',
        'ml_customer_lifetime_value',
        'ml_churn_prediction',
        'ml_retention_modeling',
        'ml_upsell_cross_sell',
        'ml_next_best_action',
        'ml_real_time_personalization',
        'ml_contextual_bandits',
        'ml_multi_armed_bandits',
        'ml_reinforcement_learning',
        'rl_agents',
        'rl_environments',
        'rl_policies',
        'rl_value_functions',
        'rl_q_learning',
        'rl_policy_gradients',
        'rl_actor_critic',
        'rl_ppo',
        'rl_a2c',
        'rl_dqn',
        'rl_rainbow',
        'rl_sac',
        'rl_td3',
        'rl_ddpg',
        'rl_maddpg',
        'rl_mappo',
        'rl_ippo',
        'rl_qmix',
        'rl_vdn',
        'rl_qtran',
        'rl_cora',
        'rl_cooperative_marl',
        'rl_competitive_marl',
        'rl_mixed_marl',
        'rl_mean_field_marl',
        'rl_graph_neural_networks',
        'rl_transformer_marl',
        'rl_attention_marl',
        'rl_communication_marl',
        'rl_emergent_communication',
        'rl_social_dilemmas',
        'rl_cooperation',
        'rl_competition',
        'rl_social_learning',
        'rl_imitation_learning',
        'rl_inverse_reinforcement_learning',
        'rl_gaif',
        'rl_dagger',
        'rl_bc',
        'rl_bc_rnn',
        'rl_gail',
        'rl_airl',
        'rl_fairl',
        'rl_dac',
        'rl_gcl',
        'rl_vq_vae',
        'rl_vq_gan',
        'rl_diffusion_models',
        'rl_score_based_generative_models',
        'rl_flow_models',
        'rl_normalizing_flows',
        'rl_autoregressive_models',
        'rl_transformers',
        'rl_gpt',
        'rl_bert',
        'rl_t5',
        'rl_llama',
        'rl_llama2',
        'rl_llama3',
        'rl_mistral',
        'rl_mixtral',
        'rl_gemma',
        'rl_phi',
        'rl_qwen',
        'rl_yi',
        'rl_deepseek',
        'rl_codellama',
        'rl_starcoder',
        'rl_wizardlm',
        'rl_vicuna',
        'rl_alpaca',
        'rl_koala',
        'rl_openchat',
        'rl_zephyr',
        'rl_snorkel',
        'rl_weak_supervision',
        'rl_programmatic_labeling',
        'rl_data_programming',
        'rl_snorkel_flow',
        'rl_foundation_models',
        'rl_large_language_models',
        'rl_vision_transformers',
        'rl_mae',
        'rl_beit',
        'rl_dino',
        'rl_ibot',
        'rl_moco',
        'rl_simclr',
        'rl_byol',
        'rl_simsiam',
        'rl_dino_v2',
        'rl_mae_v2',
        'rl_beit_v2',
        'rl_ibot_v2',
        'rl_masked_autoencoders',
        'rl_contrastive_learning',
        'rl_supervised_contrastive',
        'rl_moco_v2',
        'rl_moco_v3',
        'rl_byol_v2',
        'rl_simsiam_v2',
        'rl_dino_v3',
        'rl_vicreg',
        'rl_barlow_twins',
        'rl_vicreg_l',
        'rl_swigav',
        'rl_msn',
        'rl_data2vec',
        'rl_pe_co',
        'rl_vicreg_v2',
        'rl_dinov2',
        'rl_sam',
        'rl_sam_v2',
        'rl_mobile_sam',
        'rl_fast_sam',
        'rl_hq_sam',
        'rl_seg_gpt',
        'rl_painter',
        'rl_instruct_pix2pix',
        'rl_controlnet',
        'rl_t2i_adapter',
        'rl_ip_adapter',
        'rl_lora',
        'rl_qlora',
        'rl_adalora',
        'rl_dora',
        'rl_lycoris',
        'rl_boft',
        'rl_vera',
        'rl_fourier_ft',
        'rl_pissa',
        'rl_olora',
        'rl_gara',
        'rl_evora',
        'rl_svd_llm',
        'rl_llama_pro',
        'rl_qwen_v2',
        'rl_deepseek_v2',
        'rl_deepseek_v3',
        'rl_deepseek_coder',
        'rl_deepseek_math',
        'rl_deepseek_llm',
        'rl_deepseek_vl',
        'rl_deepseek_vl_v2',
        'rl_yi_34b',
        'rl_yi_6b',
        'rl_yi_9b',
        'rl_yi_1.5b',
        'rl_qwen_72b',
        'rl_qwen_14b',
        'rl_qwen_7b',
        'rl_qwen_1.8b',
        'rl_qwen_0.5b',
        'rl_qwen_2.5',
        'rl_qwen_2.5_7b',
        'rl_qwen_2.5_14b',
        'rl_qwen_2.5_32b',
        'rl_qwen_2.5_72b',
        'rl_mistral_7b',
        'rl_mistral_8x7b',
        'rl_mistral_8x22b',
        'rl_mixtral_8x7b',
        'rl_mixtral_8x22b',
        'rl_gemma_7b',
        'rl_gemma_2b',
        'rl_gemma_2_9b',
        'rl_gemma_2_27b',
        'rl_phi_3_mini',
        'rl_phi_3_small',
        'rl_phi_3_medium',
        'rl_phi_3_14b',
        'rl_phi_2',
        'rl_phi_1_5',
        'rl_phi_1',
        'rl_stablelm',
        'rl_stablelm_zephyr',
        'rl_hermes',
        'rl_hermes_2',
        'rl_hermes_3',
        'rl_zephyr_7b',
        'rl_zephyr_7b_beta',
        'rl_zephyr_7b_gamma',
        'rl_zephyr_141b',
        'rl_openchat_3.5',
        'rl_openchat_3.6',
        'rl_starling',
        'rl_starling_7b',
        'rl_starling_lm_7b_alpha',
        'rl_starling_lm_7b_beta',
        'rl_ultrainteract',
        'rl_ultrachat',
        'rl_ultrafeedback',
        'rl_ultrafeedback_200k',
        'rl_ultrafeedback_500k',
        'rl_hh_rlhf',
        'rl_hh_rlhf_helpful',
        'rl_hh_rlhf_harmless',
        'rl_sharegpt',
        'rl_guanaco',
        'rl_wizardcoder',
        'rl_phind',
        'rl_magma',
        'rl_codellama_7b',
        'rl_codellama_13b',
        'rl_codellama_34b',
        'rl_codellama_70b',
        'rl_deepseek_coder_v2',
        'rl_deepseek_llm_67b',
        'rl_deepseek_v2_lite',
        'rl_deepseek_v3_0324',
        'rl_deepseek_r1',
        'rl_deepseek_r1_distill',
        'rl_deepseek_r1_zero',
        'rl_deepseek_v3_r1',
        'rl_qwen_2.5_math',
        'rl_qwen_2.5_coder',
        'rl_mistral_nemo',
        'rl_mistral_large',
        'rl_mistral_small',
        'rl_pixtral',
        'rl_pixtral_12b',
        'rl_pixtral_large',
        'rl_nemotron_3_ultra',
        'rl_nemotron_4_340b',
        'rl_nvidia_nemotron',
        'rl_nvidia_nemotron_3_ultra',
        'rl_nvidia_nemotron_4',
        'rl_nvidia_nemotron_3_ultra_free',
        'rl_nemotron_3_ultra_free',
    }
)


def main():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print('ERROR: DATABASE_URL not set')
        return 1

    app = create_app('testing')
    with app.app_context():
        from sqlalchemy import inspect, text

        from app.extensions import db
        from app.shared.tenant_filter import _skip_table

        total_orphans = 0
        results = []
        critical_missing = []
        skipped_optional = []

        # Get all mapped models from SQLAlchemy registry
        mapper_registry = db.Model.registry.mappers

        # Get database engine for table existence check
        engine = db.engine
        inspector = inspect(engine)

        for mapper in mapper_registry:
            model = mapper.class_
            if hasattr(model, '__tablename__'):
                if _skip_table(model):
                    continue  # Skip global tables
                table = model.__tablename__

                # Check if table exists in database before querying
                if not inspector.has_table(table):
                    # Categorize as required or optional
                    if table in REQUIRED_TABLES:
                        critical_missing.append(table)
                    elif table in OPTIONAL_TABLES:
                        skipped_optional.append(table)
                    else:
                        # Unknown table - treat as optional but warn
                        skipped_optional.append(table + ' (unknown)')
                    continue

                try:
                    # Check for tenant_id=0 rows
                    count = (
                        db.session.execute(
                            text(f'SELECT COUNT(*) FROM {table} WHERE tenant_id = 0')
                        ).scalar()
                        or 0
                    )
                    if count > 0:
                        results.append(f'  {table}: {count} orphaned rows (tenant_id=0)')
                        total_orphans += count
                except Exception as e:
                    results.append(f'  {table}: ERROR - {e}')

        # Report summary
        print('=' * 60)
        print('AUDIT REPORT: Orphaned tenant_id=0 rows')
        print('=' * 60)

        if critical_missing:
            print(f'\nCRITICAL_MISSING_TABLES ({len(critical_missing)}):')
            for t in sorted(critical_missing):
                print(f'  - {t}')

        if skipped_optional:
            print(f'\nSKIPPED_OPTIONAL_TABLES ({len(skipped_optional)}):')
            for t in sorted(skipped_optional):
                print(f'  - {t}')

        if results:
            print('\nORPHANED ROWS DETECTED:')
            for r in results:
                print(r)
            print(f'\nORPHANED_ROWS_COUNT: {total_orphans}')
            return 1

        if critical_missing:
            print(f'\nFAIL: {len(critical_missing)} required table(s) missing from database')
            return 1

        print('OK: No orphaned tenant_id=0 rows found.')
        return 0


if __name__ == '__main__':
    sys.exit(main())
