"""Custom exception hierarchy and Result type pattern."""

from typing import Generic, TypeVar, Optional, Any

T = TypeVar('T')
E = TypeVar('E', bound=Exception)


class YtdlAppError(Exception):
    """Base application exception for YouTube Downloader."""
    
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class DownloadCancelled(YtdlAppError):
    """Raised when a download is cancelled by the user."""
    
    def __init__(self, message: str = "Descarga cancelada por el usuario", details: Optional[dict] = None):
        super().__init__(message, code="CANCELLED", status_code=200, details=details)


class DependencyError(YtdlAppError):
    """Raised when external system dependencies (FFmpeg, Node.js) are missing."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="DEPENDENCY_ERROR", status_code=503, details=details)


class ExtractionError(YtdlAppError):
    """Base exception for errors during metadata or playlist extraction."""
    
    def __init__(self, message: str, code: str = "EXTRACTION_ERROR", status_code: int = 400, details: Optional[dict] = None):
        super().__init__(message, code=code, status_code=status_code, details=details)


class PrivateVideoError(ExtractionError):
    """Raised when a video is private or region-blocked."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="PRIVATE_VIDEO", status_code=403, details=details)


class AgeRestrictedError(ExtractionError):
    """Raised when a video is age-restricted and requires authentication."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="AGE_RESTRICTED", status_code=403, details=details)


class BotChallengeError(ExtractionError):
    """Raised when YouTube blocks requests requiring a sign-in or cookie file."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="BOT_CHALLENGE", status_code=401, details=details)


class DownloadError(YtdlAppError):
    """Base exception for download execution errors."""
    
    def __init__(self, message: str, code: str = "DOWNLOAD_ERROR", status_code: int = 500, details: Optional[dict] = None):
        super().__init__(message, code=code, status_code=status_code, details=details)


class NetworkTimeoutError(DownloadError):
    """Raised when network requests timeout during download."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="NETWORK_TIMEOUT", status_code=503, details=details)


class DiskSpaceError(DownloadError):
    """Raised when there is insufficient space on the target drive."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="DISK_SPACE", status_code=507, details=details)


class PermissionDeniedError(DownloadError):
    """Raised when the application lacks write permissions in the target folder."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="PERMISSION_DENIED", status_code=403, details=details)


class ConfigError(YtdlAppError):
    """Raised when persistent configurations cannot be loaded or saved."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="CONFIG_ERROR", status_code=500, details=details)


class Result(Generic[T, E]):
    """Container representing either a successful computation or an error exception."""
    
    def __init__(self, success: bool, value: Optional[T] = None, error: Optional[E] = None):
        self.success = success
        self.value = value
        self.error = error

    @property
    def is_ok(self) -> bool:
        return self.success

    @property
    def is_fail(self) -> bool:
        return not self.success

    @classmethod
    def ok(cls, value: T) -> 'Result[T, E]':
        return cls(success=True, value=value)

    @classmethod
    def fail(cls, error: E) -> 'Result[T, E]':
        return cls(success=False, error=error)

    def unwrap(self) -> T:
        if not self.success:
            raise self.error
        return self.value

    def value_or(self, default: Any) -> Any:
        if not self.success:
            return default
        return self.value


def map_ytdlp_error(exc: Exception, context_msg: str = "Error de procesamiento") -> YtdlAppError:
    """Map standard yt-dlp and network exceptions to our custom hierarchy."""
    msg = str(exc)
    lower_msg = msg.lower()
    
    # Check for bot challenge / captcha
    if "confirm you’re not a bot" in lower_msg or "confirm you're not a bot" in lower_msg or "sign in to confirm" in lower_msg:
        return BotChallengeError(f"Límite o reto de bot en YouTube: {msg}")
    
    # Check for private or restricted video
    if "private video" in lower_msg or "is private" in lower_msg or "login to view" in lower_msg:
        return PrivateVideoError(f"El contenido es privado o requiere inicio de sesión: {msg}")
        
    # Check for age restriction
    if "age-restricted" in lower_msg or "confirm your age" in lower_msg or "confirm you are of age" in lower_msg:
        return AgeRestrictedError(f"El contenido tiene restricción de edad: {msg}")
        
    # Check for network timeout/connectivity issues
    if "timeout" in lower_msg or "connection refused" in lower_msg or "timed out" in lower_msg or "unable to download webpage" in lower_msg:
        return NetworkTimeoutError(f"Fallo de conexión o tiempo de espera agotado: {msg}")
        
    # Check for space issues
    if "no space left" in lower_msg or "disk full" in lower_msg or "enospc" in lower_msg:
        return DiskSpaceError(f"Espacio insuficiente en disco: {msg}")
        
    # Check for permission denied
    if "permission denied" in lower_msg or "eacces" in lower_msg:
        return PermissionDeniedError(f"Permiso denegado en la ruta de destino: {msg}")
        
    # Fallback to generic extraction or download error depending on context
    if "extract" in context_msg.lower() or "informacion" in context_msg.lower():
        return ExtractionError(f"{context_msg}: {msg}")
    return DownloadError(f"{context_msg}: {msg}")

