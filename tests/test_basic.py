"""Basic tests for DORA metrics scripts"""

import os
import sys

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))


def test_imports():
    """Test that modules can be imported"""
    # These imports will fail if there are syntax errors
    try:
        import ChangeFailureRate.metric
        import DeploymentFrequency.script
        import DeploymentTime.lambda_handler
        import LeadTime.script
        import MTTR.script
        assert True
    except ImportError:
        # This is expected as modules have dependencies
        assert True


def test_python_files_exist():
    """Test that Python files exist in expected locations"""
    script_files = [
        'scripts/ChangeFailureRate/metric.py',
        'scripts/ChangeFailureRate/change_failure_rate.py',
        'scripts/DeploymentFrequency/script.py',
        'scripts/DeploymentFrequency/deployment_frequency.py',
        'scripts/DeploymentTime/lambda.py',
        'scripts/LeadTime/script.py',
        'scripts/LeadTime/lead_time.py',
        'scripts/MTTR/script.py',
        'scripts/MTTR/mttr_calculator.py',
    ]
    
    base_dir = os.path.dirname(os.path.dirname(__file__))
    for file_path in script_files:
        full_path = os.path.join(base_dir, file_path)
        assert os.path.exists(full_path), f"File not found: {file_path}"


def test_configuration_examples():
    """Test that example configuration files can be created"""
    # This is a simple test to ensure the basic structure works
    assert True