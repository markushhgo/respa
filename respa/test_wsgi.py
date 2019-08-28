import pytest

import os


@pytest.mark.wsgi
def test_file_exist():
    assert os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
