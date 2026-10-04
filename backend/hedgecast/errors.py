class ServiceError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def not_found(message):
    return ServiceError(404, message)


def conflict(message):
    return ServiceError(409, message)


def bad_request(message):
    return ServiceError(400, message)


def unavailable(message):
    return ServiceError(503, message)
