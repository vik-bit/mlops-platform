import pytest

from app.routes.gateway import ADMIN_ONLY_DEPLOYMENT_PATH


@pytest.mark.parametrize("path", [
    "deployments/3/rollouts", "rollouts/7/rollback", "rollouts/7/promote",
    "deployments/3/promote", "deployments/3/policy", "deployments/3/events",
])
def test_lifecycle_changes_need_admin(path):
    assert ADMIN_ONLY_DEPLOYMENT_PATH.search(path)


@pytest.mark.parametrize("path", [
    "deployments/3/predict", "deployments/3/feedback", "predict/5/named", "deploy/5",
])
def test_predictions_and_feedback_stay_open_to_users(path):
    assert not ADMIN_ONLY_DEPLOYMENT_PATH.search(path)
