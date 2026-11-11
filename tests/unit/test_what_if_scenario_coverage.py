"""Coverage tests for models.what_if_scenario.py"""

from __future__ import annotations

from decimal import Decimal

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestWhatIfScenario:
    def test_add_doctor_projection(self, app, db, test_tenant):
        from models.what_if_scenario import WhatIfScenario

        scenario = WhatIfScenario(
            tenant_id=test_tenant.id,
            name='Add 2 Doctors',
            scenario_type='add_doctor',
            baseline_visits_per_day=100,
            baseline_avg_wait_minutes=Decimal('30.0'),
            baseline_revenue_per_day=Decimal('5000.0'),
            param_new_staff_count=2,
        )
        db.session.add(scenario)
        db.session.flush()
        scenario.calculate_projections()

        assert scenario.projected_visits_per_day == 116  # 100 + 2*8
        assert scenario.projected_capacity_increase == 16.0  # (116-100)/100 * 100

    def test_add_doctor_no_baseline(self, app, db, test_tenant):
        from models.what_if_scenario import WhatIfScenario

        scenario = WhatIfScenario(
            tenant_id=test_tenant.id,
            name='No Baseline',
            scenario_type='add_doctor',
            param_new_staff_count=2,
        )
        db.session.add(scenario)
        db.session.flush()
        scenario.calculate_projections()

        assert scenario.projected_visits_per_day is None

    def test_add_beds_projection(self, app, db, test_tenant):
        from models.what_if_scenario import WhatIfScenario

        scenario = WhatIfScenario(
            tenant_id=test_tenant.id,
            name='Add 10 Beds',
            scenario_type='add_beds',
            baseline_visits_per_day=100,
            baseline_revenue_per_day=Decimal('5000.0'),
            param_new_bed_count=10,
        )
        db.session.add(scenario)
        db.session.flush()
        scenario.calculate_projections()

        assert scenario.projected_visits_per_day == 105  # 100 + 10*0.5

    def test_extend_hours_projection(self, app, db, test_tenant):
        from models.what_if_scenario import WhatIfScenario

        scenario = WhatIfScenario(
            tenant_id=test_tenant.id,
            name='Extend Hours 20%',
            scenario_type='extend_hours',
            baseline_visits_per_day=100,
            baseline_revenue_per_day=Decimal('5000.0'),
            param_change_percent=Decimal('20.0'),
        )
        db.session.add(scenario)
        db.session.flush()
        scenario.calculate_projections()

        assert scenario.projected_visits_per_day == 120  # 100 * 1.2

    def test_price_change_projection(self, app, db, test_tenant):
        from models.what_if_scenario import WhatIfScenario

        scenario = WhatIfScenario(
            tenant_id=test_tenant.id,
            name='Price +10%',
            scenario_type='price_change',
            baseline_visits_per_day=100,
            baseline_revenue_per_day=Decimal('5000.0'),
            param_change_percent=Decimal('10.0'),
        )
        db.session.add(scenario)
        db.session.flush()
        scenario.calculate_projections()

        # factor = 1.1, demand_factor = 1 + 0.1 * (-0.5) = 0.95
        # projected_revenue = 5000 * 1.1 * 0.95 = 5225
        # projected_visits = 100 * 0.95 = 95
        assert scenario.projected_visits_per_day == pytest.approx(95)
        assert scenario.projected_revenue_per_day == pytest.approx(5225, rel=1e-6)

    def test_unknown_scenario_type(self, app, db, test_tenant):
        from models.what_if_scenario import WhatIfScenario

        scenario = WhatIfScenario(
            tenant_id=test_tenant.id,
            name='Unknown Type',
            scenario_type='unknown_type',
            baseline_visits_per_day=100,
        )
        db.session.add(scenario)
        db.session.flush()
        scenario.calculate_projections()

        assert scenario.projected_visits_per_day is None
        assert scenario.projected_capacity_increase is None

    def test_repr(self, app, db, test_tenant):
        from models.what_if_scenario import WhatIfScenario

        scenario = WhatIfScenario(
            tenant_id=test_tenant.id,
            name='Test Scenario',
            scenario_type='add_doctor',
        )
        assert 'Test Scenario' in repr(scenario)
