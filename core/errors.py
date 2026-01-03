

from fastapi import status
from core.exceptions import AppException

class ErrorCode:
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_UNAUTHORIZED = "AUTH_UNAUTHORIZED"

    USER_NOT_FOUND = "USER_NOT_FOUND"

    GAME_NOT_FOUND = "GAME_NOT_FOUND"
    GAME_NOT_YOUR_TURN = "GAME_NOT_YOUR_TURN"
    GAME_ALREADY_COMPLETED = "GAME_ALREADY_COMPLETED"
    INVALID_MOVE = "INVALID_MOVE"

    CHALLENGE_NOT_FOUND = "CHALLENGE_NOT_FOUND"
    CHALLENGE_ALREADY_ACCEPTED = "CHALLENGE_ALREADY_ACCEPTED"

    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"


class ErrorMessage:
    INVALID_CREDENTIALS = "Invalid email or password"
    UNAUTHORIZED = "You are not authorized to perform this action"

    USER_NOT_FOUND = "User not found"

    GAME_NOT_FOUND = "Game not found"
    GAME_NOT_YOUR_TURN = "It is not your turn"
    GAME_ALREADY_COMPLETED = "Game is already completed"
    INVALID_MOVE = "Invalid chess move"

    CHALLENGE_NOT_FOUND = "Challenge not found"
    CHALLENGE_ALREADY_ACCEPTED = "Challenge has already been accepted"

    INSUFFICIENT_BALANCE = "Insufficient wallet balance"



def bad_request(code: str, message: str, details: dict | None = None):
    return AppException(
        status_code=status.HTTP_400_BAD_REQUEST,
        code=code,
        message=message,
        details=details
    )


def unauthorized(message: str = ErrorMessage.UNAUTHORIZED):
    return AppException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=ErrorCode.AUTH_UNAUTHORIZED,
        message=message
    )


def forbidden(code: str, message: str):
    return AppException(
        status_code=status.HTTP_403_FORBIDDEN,
        code=code,
        message=message
    )


def not_found(code: str, message: str):
    return AppException(
        status_code=status.HTTP_404_NOT_FOUND,
        code=code,
        message=message
    )
