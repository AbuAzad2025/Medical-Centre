"""
Shared Enums and Constants
"""
from enum import Enum

class SubscriptionType(str, Enum):
    PERPETUAL = "perpetual"
    MONTHLY = "monthly"
    YEARLY = "yearly"

class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    EXPIRED = "expired"
    DELETED = "deleted"

class StorageMode(str, Enum):
    CLOUD = "cloud"
    LOCAL = "local"
    HYBRID = "hybrid"

class ModuleName(str, Enum):
    RECEPTION = "reception"
    DOCTOR = "doctor"
    LAB = "lab"
    RADIOLOGY = "radiology"
    PHARMACY = "pharmacy"
    EMERGENCY = "emergency"
    NURSING = "nursing"
    BILLING = "billing"
    INVENTORY = "inventory"
    REPORTING = "reporting"
    APPOINTMENTS = "appointments"
    OWNER = "owner"
