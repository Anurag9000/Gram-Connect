import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import api_server


@pytest.fixture(autouse=True)
def isolated_runtime_state():
    api_server.reset_runtime_state()
    yield
    api_server.reset_runtime_state()
