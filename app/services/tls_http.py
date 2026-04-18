import os
import ssl
from urllib import request as urllib_request
from urllib.error import URLError


def get_ca_bundle_path() -> str | None:
    env_path = str(os.getenv("SSL_CERT_FILE", "")).strip()
    if env_path:
        return env_path

    try:
        import certifi

        return certifi.where()
    except Exception:
        return None


def build_ssl_context() -> ssl.SSLContext:
    ca_bundle = get_ca_bundle_path()
    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)
    return ssl.create_default_context()


def urlopen_with_tls(req: urllib_request.Request, timeout: float):
    context = build_ssl_context()
    return urllib_request.urlopen(req, timeout=timeout, context=context)


def format_tls_error(exc: Exception) -> str:
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            ca_path = get_ca_bundle_path() or "system-default"
            return f"TLS certificate verification failed ({reason}); ca_bundle={ca_path}"
        if reason is not None:
            return f"Network error: {reason}"

    return str(exc)
