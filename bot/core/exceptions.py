class BotException(Exception):
    pass


class APIException(BotException):
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationException(APIException):
    pass


class NotFoundException(APIException):
    pass


class ValidationException(APIException):
    pass


class SubscriptionExpiredException(BotException):
    pass


class UserNotRegisteredException(BotException):
    pass
