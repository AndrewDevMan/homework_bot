class BadStatusCodeResponse(Exception):
    """Ответ от сервера не 200."""


class InvalidData(Exception):
    """Некорректные данные словоря."""
