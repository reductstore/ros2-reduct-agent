import pytest
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import String

from ros2_reduct_agent.recorder import Recorder


def generate_string(size_kb: int) -> str:
    """Generate a string of size_kb kilobytes."""
    return "X" * (size_kb * 1024)


@pytest.fixture
def publisher_node():
    node = Node("test_publisher")
    yield node
    node.destroy_node()


@pytest.fixture
def publisher(publisher_node: Node):
    pub = publisher_node.create_publisher(String, "/test/topic", 10)
    return pub


@pytest.mark.parametrize("size_kb", [1, 10, 100])
def test_recorder_state_size(publisher_node, publisher, low_chunk_recorder, size_kb):
    """Test that the Recorder node can handle large messages."""

    msg = String()
    msg.data = generate_string(size_kb)

    for i in range(5):
        publisher.publish(msg)

    for _ in range(5):
        rclpy.spin_once(low_chunk_recorder, timeout_sec=0.1)
        rclpy.spin_once(publisher_node, timeout_sec=0.1)

    # 5 messages of size_kb KB each plus 203 bytes for MCAP overhead (Schema, Channel, etc.)
    assert low_chunk_recorder.pipeline_states["timer_test_topic"].current_size == 5 * (
        size_kb * 1024 + 203
    ), "Recorder did not receive the expected size of data"


def test_recorder_timer_trigger(monkeypatch, basic_recorder):
    """Test that the Recorder triggers segment reset on timer expiration."""
    uploads = []

    def mock_upload_pipeline(
        _,
        pipeline_name,
        state,
    ):
        uploads.append((pipeline_name, state))

    monkeypatch.setattr(Recorder, "upload_pipeline", mock_upload_pipeline)

    # Wait for the timer to trigger
    rclpy.spin_once(basic_recorder, timeout_sec=1.1)

    assert len(uploads) == 1, "Timer did not trigger upload as expected"
    assert (
        uploads[0][0] == "timer_test_topic"
    ), "Pipeline name in upload does not match expected"
    assert (
        basic_recorder.pipeline_states["timer_test_topic"].increment == 0
    ), "An empty segement was uploaded, but it should not have been"
