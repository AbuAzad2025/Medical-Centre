"""Tests for phase 13 — motion system + workflow macros (§22)."""

from pathlib import Path


class TestMotionAssets:
    def test_motion_js_respects_reduced_motion(self):
        js = (Path(__file__).parent.parent / 'static' / 'js' / 'motion.js').read_text(encoding='utf-8')
        assert 'motionEnabled' in js
        assert 'prefers-reduced-motion' in js
        assert '.animate-in' in js

    def test_motion_css_exists(self):
        css = (Path(__file__).parent.parent / 'static' / 'css' / 'motion.css').read_text(encoding='utf-8')
        assert '.animate-in' in css
        assert 'prefers-reduced-motion' in css

    def test_base_html_includes_motion(self, auth_client):
        resp = auth_client.get('/medication/dashboard')
        text = resp.get_data(as_text=True)
        assert 'motion.css' in text
        assert 'motion.js' in text


class TestWorkflowMacros:
    def _macro_used_in(self, path: str, macro_file: str) -> bool:
        text = (Path(__file__).parent.parent / path).read_text(encoding='utf-8')
        return macro_file in text

    def test_patient_context_panel_in_three_templates(self):
        templates = [
            'templates/doctor/patient_details.html',
            'templates/reception/visits.html',
            'templates/lab/process.html',
        ]
        assert all(self._macro_used_in(t, '_patient_context_panel.html') for t in templates)

    def test_workflow_next_actions_in_three_templates(self):
        templates = [
            'templates/doctor/patient_details.html',
            'templates/reception/visits.html',
            'templates/lab/process.html',
        ]
        assert all(self._macro_used_in(t, '_workflow_next_actions.html') for t in templates)

    def test_visit_next_actions_helper_registered(self, app):
        with app.app_context():
            from flask import render_template_string
            from services.workflow_orchestrator import WorkflowOrchestrator
            assert WorkflowOrchestrator.next_actions is not None
            out = render_template_string('{{ visit_next_actions is defined }}')
            assert 'True' in out
