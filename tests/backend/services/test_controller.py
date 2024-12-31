from decision_data.backend.services.controller import (
    get_current_hour,
)


def test_get_current_time():
    # Arrange
    offset = 0

    # Act
    current_time = get_current_hour(offset)

    # Assert
    assert isinstance(current_time, int)
