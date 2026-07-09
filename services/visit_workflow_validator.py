"""
Workflow Status Utility - Patient Visit State Machine
Validates and tracks patient journey through clinical workflow stages.
"""
from enum import Enum
from typing import Optional, List, Dict
from flask import flash


class VisitStage(str, Enum):
    """Clinical workflow stages in order"""
    REGISTERED = "registered"           # Patient registered at reception
    TRIAGED = "triaged"                 # Triage/nursing assessment done
    AWAITING_DOCTOR = "awaiting_doctor"  # In queue waiting for doctor
    WITH_DOCTOR = "with_doctor"         # Currently with doctor
    LAB_ORDERED = "lab_ordered"         # Lab tests requested
    LAB_COMPLETED = "lab_completed"     # Lab results received
    RADIOLOGY_ORDERED = "radiology_ordered"
    RADIOLOGY_COMPLETED = "radiology_completed"
    PHARMACY = "pharmacy"              # Prescription to be dispensed
    DISCHARGED = "discharged"           # Patient discharged
    ADMITTED = "admitted"              # Patient admitted to ward
    TRANSFERRED = "transferred"        # Transferred to another department
    CANCELLED = "cancelled"            # Visit cancelled

    @classmethod
    def stage_order(cls) -> Dict["VisitStage", int]:
        return {
            cls.REGISTERED: 1,
            cls.TRIAGED: 2,
            cls.AWAITING_DOCTOR: 3,
            cls.WITH_DOCTOR: 4,
            cls.LAB_ORDERED: 5,
            cls.RADIOLOGY_ORDERED: 5,
            cls.LAB_COMPLETED: 6,
            cls.RADIOLOGY_COMPLETED: 6,
            cls.PHARMACY: 7,
            cls.DISCHARGED: 8,
            cls.ADMITTED: 8,
            cls.TRANSFERRED: 8,
            cls.CANCELLED: 0,
        }

    @classmethod
    def stage_label_ar(cls, stage: "VisitStage") -> str:
        labels = {
            cls.REGISTERED: "مسجل",
            cls.TRIAGED: "مفرز",
            cls.AWAITING_DOCTOR: "بانتظار الطبيب",
            cls.WITH_DOCTOR: "مع الطبيب",
            cls.LAB_ORDERED: "فحوصات مطلوبة",
            cls.LAB_COMPLETED: "فحوصات مكتملة",
            cls.RADIOLOGY_ORDERED: "أشعة مطلوبة",
            cls.RADIOLOGY_COMPLETED: "أشعة مكتملة",
            cls.PHARMACY: "الصيدلية",
            cls.DISCHARGED: "خرج",
            cls.ADMITTED: "منوم",
            cls.TRANSFERRED: "محول",
            cls.CANCELLED: "ملغي",
        }
        return labels.get(stage, stage.value)

    @classmethod
    def stage_icon(cls, stage: "VisitStage") -> str:
        icons = {
            cls.REGISTERED: "fa-user-plus",
            cls.TRIAGED: "fa-heart-pulse",
            cls.AWAITING_DOCTOR: "fa-clock",
            cls.WITH_DOCTOR: "fa-stethoscope",
            cls.LAB_ORDERED: "fa-flask",
            cls.LAB_COMPLETED: "fa-vial-circle-check",
            cls.RADIOLOGY_ORDERED: "fa-x-ray",
            cls.RADIOLOGY_COMPLETED: "fa-check-circle",
            cls.PHARMACY: "fa-pills",
            cls.DISCHARGED: "fa-circle-check",
            cls.ADMITTED: "fa-bed",
            cls.TRANSFERRED: "fa-arrows-left-right",
            cls.CANCELLED: "fa-circle-xmark",
        }
        return icons.get(stage, "fa-circle")


class VisitWorkflowValidator:
    """Validates stage transitions in the patient visit workflow"""

    VALID_TRANSITIONS = {
        VisitStage.REGISTERED: [VisitStage.TRIAGED, VisitStage.AWAITING_DOCTOR, VisitStage.CANCELLED],
        VisitStage.TRIAGED: [VisitStage.AWAITING_DOCTOR, VisitStage.CANCELLED],
        VisitStage.AWAITING_DOCTOR: [VisitStage.WITH_DOCTOR, VisitStage.CANCELLED],
        VisitStage.WITH_DOCTOR: [
            VisitStage.LAB_ORDERED,
            VisitStage.RADIOLOGY_ORDERED,
            VisitStage.PHARMACY,
            VisitStage.DISCHARGED,
            VisitStage.ADMITTED,
            VisitStage.CANCELLED
        ],
        VisitStage.LAB_ORDERED: [VisitStage.LAB_COMPLETED, VisitStage.CANCELLED],
        VisitStage.LAB_COMPLETED: [VisitStage.WITH_DOCTOR, VisitStage.PHARMACY, VisitStage.DISCHARGED],
        VisitStage.RADIOLOGY_ORDERED: [VisitStage.RADIOLOGY_COMPLETED, VisitStage.CANCELLED],
        VisitStage.RADIOLOGY_COMPLETED: [VisitStage.WITH_DOCTOR, VisitStage.PHARMACY, VisitStage.DISCHARGED],
        VisitStage.PHARMACY: [VisitStage.DISCHARGED],
        VisitStage.DISCHARGED: [],  # Terminal state
        VisitStage.ADMITTED: [VisitStage.DISCHARGED, VisitStage.TRANSFERRED],
        VisitStage.TRANSFERRED: [VisitStage.DISCHARGED, VisitStage.ADMITTED],
        VisitStage.CANCELLED: [],  # Terminal state
    }

    @classmethod
    def can_transition(cls, from_stage: VisitStage, to_stage: VisitStage) -> bool:
        """Check if a transition is valid"""
        allowed = cls.VALID_TRANSITIONS.get(from_stage, [])
        return to_stage in allowed

    @classmethod
    def get_available_transitions(cls, current_stage: VisitStage) -> List[VisitStage]:
        """Get list of valid next stages"""
        return cls.VALID_TRANSITIONS.get(current_stage, [])

    @classmethod
    def get_journey_stage_number(cls, stage: VisitStage) -> int:
        """Get the stage's position in the journey (1-8)"""
        stages = [
            VisitStage.REGISTERED, VisitStage.TRIAGED, VisitStage.AWAITING_DOCTOR,
            VisitStage.WITH_DOCTOR, VisitStage.LAB_ORDERED, VisitStage.LAB_COMPLETED,
            VisitStage.RADIOLOGY_ORDERED, VisitStage.RADIOLOGY_COMPLETED,
            VisitStage.PHARMACY, VisitStage.DISCHARGED
        ]
        try:
            return stages.index(stage) + 1
        except ValueError:
            return 0

    @classmethod
    def validate_and_transition(cls, visit, new_stage: VisitStage, commit: bool = True) -> bool:
        """Validate and apply a stage transition with optional flash message"""
        from app_factory import db
        
        current = VisitStage(visit.status) if visit.status else VisitStage.REGISTERED
        
        if not cls.can_transition(current, new_stage):
            flash(
                f"لا يمكن الانتقال من '{VisitStage.stage_label_ar(current)}' "
                f"إلى '{VisitStage.stage_label_ar(new_stage)}'",
                "error"
            )
            return False
        
        visit.status = new_stage.value
        if commit:
            from utils.db_safety import safe_commit
            safe_commit(db.session, error_message="Failed to save stage transition", reraise=True)
        
        flash(
            f"تم تحديث حالة المريض إلى '{VisitStage.stage_label_ar(new_stage)}'",
            "success"
        )
        return True


def resolve_visit_status_badge_class(status: str) -> str:
    """Return Bootstrap badge color class for a visit status"""
    badge_map = {
        "registered": "info",
        "triaged": "warning",
        "awaiting_doctor": "secondary",
        "with_doctor": "primary",
        "lab_ordered": "warning",
        "lab_completed": "success",
        "radiology_ordered": "warning",
        "radiology_completed": "success",
        "pharmacy": "danger",
        "discharged": "success",
        "admitted": "dark",
        "transferred": "info",
        "cancelled": "danger",
    }
    return badge_map.get(status, "secondary")
