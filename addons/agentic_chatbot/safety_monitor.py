"""
Safety Monitor - Requires user confirmation for dangerous operations

This component handles:
- Detection of potentially dangerous operations
- User confirmation dialogs for risky actions
- Safety policy enforcement and logging
"""

import logging
import re
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox, QWidget


class RiskLevel(Enum):
    """Risk level enumeration."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SafetyRule:
    """Represents a safety rule for operation validation."""
    rule_id: str
    name: str
    description: str
    risk_level: RiskLevel
    pattern: str  # Regex pattern to match against
    requires_confirmation: bool
    block_operation: bool
    metadata: Dict[str, Any]


@dataclass
class SafetyViolation:
    """Represents a safety rule violation."""
    violation_id: str
    rule_id: str
    operation_type: str
    operation_details: str
    risk_level: RiskLevel
    timestamp: datetime
    user_confirmed: bool
    blocked: bool
    metadata: Dict[str, Any]


class SafetyMonitor(QObject):
    """
    Monitors operations for safety violations and requires user confirmation.
    
    This component:
    - Detects potentially dangerous operations
    - Requires user confirmation for risky actions
    - Enforces safety policies and logs violations
    - Provides configurable safety rules and risk levels
    """
    
    # Signals
    safety_violation_detected = Signal(dict)    # violation_info
    user_confirmation_required = Signal(dict)   # confirmation_request
    operation_blocked = Signal(dict)            # blocked_operation
    safety_rule_triggered = Signal(dict)        # rule_info
    
    def __init__(self, config: Dict[str, Any], parent_widget: Optional[QWidget] = None):
        """
        Initialize the safety monitor.
        
        Args:
            config: Configuration dictionary for safety monitoring
            parent_widget: Parent widget for confirmation dialogs
        """
        super().__init__()
        
        self.config = config
        self.parent_widget = parent_widget
        self._logger = logging.getLogger(__name__)
        
        # Safety settings
        self.enable_safety_monitoring = config.get("enable_safety_monitoring", True)
        self.require_confirmation_for_high_risk = config.get("require_confirmation_for_high_risk", True)
        self.block_critical_operations = config.get("block_critical_operations", True)
        self.log_all_violations = config.get("log_all_violations", True)
        
        # Safety rules
        self._safety_rules: Dict[str, SafetyRule] = {}
        self._violations_log: List[SafetyViolation] = []
        self._user_confirmations: Dict[str, bool] = {}  # operation_hash -> confirmed
        
        # Initialize default safety rules
        self._init_default_rules()
        
        # Load custom rules from config
        self._load_custom_rules()
    
    def _init_default_rules(self):
        """Initialize default safety rules."""
        default_rules = [
            SafetyRule(
                rule_id="file_deletion",
                name="File Deletion",
                description="Detects file deletion operations",
                risk_level=RiskLevel.MEDIUM,
                pattern=r"delete|remove|rm\s+|unlink",
                requires_confirmation=True,
                block_operation=False,
                metadata={"category": "file_operations"}
            ),
            SafetyRule(
                rule_id="directory_deletion",
                name="Directory Deletion",
                description="Detects directory deletion operations",
                risk_level=RiskLevel.HIGH,
                pattern=r"rmdir|rm\s+-r|remove.*directory",
                requires_confirmation=True,
                block_operation=False,
                metadata={"category": "file_operations"}
            ),
            SafetyRule(
                rule_id="system_commands",
                name="System Commands",
                description="Detects potentially dangerous system commands",
                risk_level=RiskLevel.CRITICAL,
                pattern=r"sudo|su\s|chmod\s+777|chown|mkfs|dd\s+if=|format|fdisk",
                requires_confirmation=True,
                block_operation=True,
                metadata={"category": "system_operations"}
            ),
            SafetyRule(
                rule_id="network_operations",
                name="Network Operations",
                description="Detects network-related operations",
                risk_level=RiskLevel.MEDIUM,
                pattern=r"curl|wget|ssh|scp|rsync.*:|ftp|telnet",
                requires_confirmation=True,
                block_operation=False,
                metadata={"category": "network_operations"}
            ),
            SafetyRule(
                rule_id="process_termination",
                name="Process Termination",
                description="Detects process termination commands",
                risk_level=RiskLevel.HIGH,
                pattern=r"kill\s+-9|killall|pkill|taskkill",
                requires_confirmation=True,
                block_operation=False,
                metadata={"category": "process_operations"}
            ),
            SafetyRule(
                rule_id="file_overwrite",
                name="File Overwrite",
                description="Detects operations that might overwrite important files",
                risk_level=RiskLevel.MEDIUM,
                pattern=r">\s*[^>]|tee\s+(?!.*>>)",
                requires_confirmation=True,
                block_operation=False,
                metadata={"category": "file_operations"}
            )
        ]
        
        for rule in default_rules:
            self._safety_rules[rule.rule_id] = rule
        
        self._logger.info(f"Initialized {len(default_rules)} default safety rules")
    
    def _load_custom_rules(self):
        """Load custom safety rules from configuration."""
        try:
            custom_rules = self.config.get("custom_safety_rules", [])
            
            for rule_data in custom_rules:
                rule = SafetyRule(
                    rule_id=rule_data["rule_id"],
                    name=rule_data["name"],
                    description=rule_data["description"],
                    risk_level=RiskLevel(rule_data["risk_level"]),
                    pattern=rule_data["pattern"],
                    requires_confirmation=rule_data.get("requires_confirmation", True),
                    block_operation=rule_data.get("block_operation", False),
                    metadata=rule_data.get("metadata", {})
                )
                
                self._safety_rules[rule.rule_id] = rule
            
            if custom_rules:
                self._logger.info(f"Loaded {len(custom_rules)} custom safety rules")
                
        except Exception as e:
            self._logger.error(f"Error loading custom safety rules: {e}")
    
    def validate_operation(self, operation_type: str, operation_details: str,
                         metadata: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[SafetyViolation]]:
        """
        Validate an operation against safety rules.
        
        Args:
            operation_type: Type of operation (e.g., 'command_execution', 'file_operation')
            operation_details: Details of the operation (e.g., command text, file path)
            metadata: Optional metadata about the operation
            
        Returns:
            Tuple of (is_allowed, violation_info)
        """
        try:
            if not self.enable_safety_monitoring:
                return True, None
            
            # Check operation against all safety rules
            for rule in self._safety_rules.values():
                if self._check_rule_match(rule, operation_type, operation_details):
                    # Rule violation detected
                    violation = self._create_violation(rule, operation_type, operation_details, metadata)
                    
                    # Log violation
                    if self.log_all_violations:
                        self._log_violation(violation)
                    
                    # Emit signal
                    self.safety_violation_detected.emit({
                        "violation_id": violation.violation_id,
                        "rule_id": rule.rule_id,
                        "rule_name": rule.name,
                        "risk_level": rule.risk_level.value,
                        "operation_type": operation_type,
                        "operation_details": operation_details,
                        "requires_confirmation": rule.requires_confirmation,
                        "block_operation": rule.block_operation
                    })
                    
                    # Handle based on rule configuration
                    if rule.block_operation and self.block_critical_operations:
                        # Block the operation
                        violation.blocked = True
                        self.operation_blocked.emit({
                            "violation_id": violation.violation_id,
                            "rule_name": rule.name,
                            "reason": "Operation blocked by safety rule"
                        })
                        return False, violation
                    
                    elif rule.requires_confirmation and self.require_confirmation_for_high_risk:
                        # Require user confirmation
                        if self._require_user_confirmation(violation):
                            violation.user_confirmed = True
                            return True, violation
                        else:
                            violation.user_confirmed = False
                            violation.blocked = True
                            return False, violation
                    
                    # Rule triggered but operation allowed
                    return True, violation
            
            # No rules violated
            return True, None
            
        except Exception as e:
            self._logger.error(f"Error validating operation: {e}")
            # Fail safe - block operation on error
            return False, None
    
    def _check_rule_match(self, rule: SafetyRule, operation_type: str, operation_details: str) -> bool:
        """
        Check if an operation matches a safety rule.
        
        Args:
            rule: Safety rule to check
            operation_type: Type of operation
            operation_details: Details of the operation
            
        Returns:
            bool: True if rule matches, False otherwise
        """
        try:
            # Check pattern match in operation details
            if re.search(rule.pattern, operation_details, re.IGNORECASE):
                return True
            
            # Check pattern match in operation type
            if re.search(rule.pattern, operation_type, re.IGNORECASE):
                return True
            
            return False
            
        except Exception as e:
            self._logger.warning(f"Error checking rule match for {rule.rule_id}: {e}")
            return False
    
    def _create_violation(self, rule: SafetyRule, operation_type: str, 
                         operation_details: str, metadata: Optional[Dict[str, Any]]) -> SafetyViolation:
        """
        Create a safety violation record.
        
        Args:
            rule: Safety rule that was violated
            operation_type: Type of operation
            operation_details: Details of the operation
            metadata: Optional metadata
            
        Returns:
            SafetyViolation: Created violation record
        """
        violation_id = f"violation_{int(datetime.now().timestamp())}_{rule.rule_id}"
        
        return SafetyViolation(
            violation_id=violation_id,
            rule_id=rule.rule_id,
            operation_type=operation_type,
            operation_details=operation_details,
            risk_level=rule.risk_level,
            timestamp=datetime.now(),
            user_confirmed=False,
            blocked=False,
            metadata=metadata or {}
        )
    
    def _require_user_confirmation(self, violation: SafetyViolation) -> bool:
        """
        Require user confirmation for a safety violation.
        
        Args:
            violation: Safety violation requiring confirmation
            
        Returns:
            bool: True if user confirmed, False otherwise
        """
        try:
            # Check if we already have confirmation for this operation
            operation_hash = self._hash_operation(violation.operation_type, violation.operation_details)
            if operation_hash in self._user_confirmations:
                return self._user_confirmations[operation_hash]
            
            # Emit signal for UI to handle
            confirmation_request = {
                "violation_id": violation.violation_id,
                "rule_name": self._safety_rules[violation.rule_id].name,
                "risk_level": violation.risk_level.value,
                "operation_type": violation.operation_type,
                "operation_details": violation.operation_details,
                "description": self._safety_rules[violation.rule_id].description
            }
            
            self.user_confirmation_required.emit(confirmation_request)
            
            # Show confirmation dialog if parent widget is available
            if self.parent_widget:
                confirmed = self._show_confirmation_dialog(violation)
                self._user_confirmations[operation_hash] = confirmed
                return confirmed
            
            # Default to not confirmed if no UI available
            self._logger.warning(f"User confirmation required but no UI available for {violation.violation_id}")
            return False
            
        except Exception as e:
            self._logger.error(f"Error requiring user confirmation: {e}")
            return False
    
    def _show_confirmation_dialog(self, violation: SafetyViolation) -> bool:
        """
        Show confirmation dialog to user.
        
        Args:
            violation: Safety violation requiring confirmation
            
        Returns:
            bool: True if user confirmed, False otherwise
        """
        try:
            rule = self._safety_rules[violation.rule_id]
            
            # Create message box
            msg_box = QMessageBox(self.parent_widget)
            msg_box.setWindowTitle("Safety Confirmation Required")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            
            # Set message text
            message = f"""
A potentially dangerous operation has been detected:

Rule: {rule.name}
Risk Level: {violation.risk_level.value.upper()}
Operation: {violation.operation_type}
Details: {violation.operation_details}

Description: {rule.description}

Do you want to proceed with this operation?
            """.strip()
            
            msg_box.setText(message)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            
            # Show dialog and get result
            result = msg_box.exec()
            confirmed = result == QMessageBox.StandardButton.Yes
            
            self._logger.info(f"User {'confirmed' if confirmed else 'denied'} operation: {violation.violation_id}")
            return confirmed
            
        except Exception as e:
            self._logger.error(f"Error showing confirmation dialog: {e}")
            return False
    
    def _hash_operation(self, operation_type: str, operation_details: str) -> str:
        """
        Create a hash for an operation to track confirmations.
        
        Args:
            operation_type: Type of operation
            operation_details: Details of the operation
            
        Returns:
            str: Operation hash
        """
        import hashlib
        operation_str = f"{operation_type}:{operation_details}"
        return hashlib.sha256(operation_str.encode()).hexdigest()[:16]
    
    def _log_violation(self, violation: SafetyViolation):
        """
        Log a safety violation.
        
        Args:
            violation: Safety violation to log
        """
        self._violations_log.append(violation)
        
        # Keep only recent violations (last 1000)
        if len(self._violations_log) > 1000:
            self._violations_log = self._violations_log[-1000:]
        
        self._logger.warning(f"Safety violation: {violation.rule_id} - {violation.operation_details}")
    
    def add_safety_rule(self, rule: SafetyRule) -> bool:
        """
        Add a custom safety rule.
        
        Args:
            rule: Safety rule to add
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        try:
            self._safety_rules[rule.rule_id] = rule
            self._logger.info(f"Added safety rule: {rule.rule_id}")
            return True
            
        except Exception as e:
            self._logger.error(f"Error adding safety rule: {e}")
            return False
    
    def remove_safety_rule(self, rule_id: str) -> bool:
        """
        Remove a safety rule.
        
        Args:
            rule_id: ID of the rule to remove
            
        Returns:
            bool: True if removed successfully, False otherwise
        """
        try:
            if rule_id in self._safety_rules:
                del self._safety_rules[rule_id]
                self._logger.info(f"Removed safety rule: {rule_id}")
                return True
            else:
                self._logger.warning(f"Safety rule not found: {rule_id}")
                return False
                
        except Exception as e:
            self._logger.error(f"Error removing safety rule: {e}")
            return False
    
    def get_safety_rules(self) -> List[SafetyRule]:
        """
        Get list of all safety rules.
        
        Returns:
            List[SafetyRule]: List of safety rules
        """
        return list(self._safety_rules.values())
    
    def get_violations_log(self, hours: Optional[int] = None) -> List[SafetyViolation]:
        """
        Get safety violations log.
        
        Args:
            hours: Optional hours to look back (all if None)
            
        Returns:
            List[SafetyViolation]: List of violations
        """
        if hours is None:
            return self._violations_log.copy()
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [v for v in self._violations_log if v.timestamp >= cutoff_time]
    
    def clear_confirmations(self):
        """Clear stored user confirmations."""
        self._user_confirmations.clear()
        self._logger.info("Cleared user confirmations")
    
    def set_safety_enabled(self, enabled: bool):
        """
        Enable or disable safety monitoring.
        
        Args:
            enabled: Whether to enable safety monitoring
        """
        self.enable_safety_monitoring = enabled
        self._logger.info(f"Safety monitoring {'enabled' if enabled else 'disabled'}")
    
    def get_safety_stats(self) -> Dict[str, Any]:
        """
        Get safety monitoring statistics.
        
        Returns:
            Dict containing safety statistics
        """
        total_violations = len(self._violations_log)
        violations_by_risk = {}
        violations_by_rule = {}
        
        for violation in self._violations_log:
            risk_level = violation.risk_level.value
            violations_by_risk[risk_level] = violations_by_risk.get(risk_level, 0) + 1
            
            rule_id = violation.rule_id
            violations_by_rule[rule_id] = violations_by_rule.get(rule_id, 0) + 1
        
        return {
            "enabled": self.enable_safety_monitoring,
            "total_rules": len(self._safety_rules),
            "total_violations": total_violations,
            "violations_by_risk": violations_by_risk,
            "violations_by_rule": violations_by_rule,
            "stored_confirmations": len(self._user_confirmations),
            "require_confirmation_for_high_risk": self.require_confirmation_for_high_risk,
            "block_critical_operations": self.block_critical_operations
        }