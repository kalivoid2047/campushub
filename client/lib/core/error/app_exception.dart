import 'dart:convert';

/// Base exception type for the app (docs/06-api-design.md sections 3-4).
class AppException implements Exception {
  AppException(this.code, this.message);

  final String code;
  final String message;

  @override
  String toString() => '$code: $message';
}

/// The device is offline or the server is unreachable. Callers treat this as
/// "serve from local store and queue mutations" (docs/09-offline-sync.md).
class NetworkUnavailableException extends AppException {
  NetworkUnavailableException(String message)
      : super('NETWORK_UNAVAILABLE', message);
}

/// A non-2xx API response, carrying the HTTP status and server detail.
class ApiException extends AppException {
  ApiException(this.statusCode, String code, String message)
      : super(code, message);

  final int statusCode;

  factory ApiException.fromResponse(int statusCode, String body) {
    var detail = 'Request failed';
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map<String, dynamic>) {
        final rawDetail = decoded['detail'];
        if (rawDetail is String) detail = rawDetail;
      }
    } catch (_) {
      // Non-JSON error body; keep the generic message.
    }
    final code = switch (statusCode) {
      401 => 'UNAUTHENTICATED',
      403 => 'FORBIDDEN',
      404 => 'NOT_FOUND',
      409 => 'CONFLICT',
      413 => 'PAYLOAD_TOO_LARGE',
      422 => 'INVALID',
      429 => 'RATE_LIMITED',
      _ => 'API_ERROR',
    };
    return ApiException(statusCode, code, detail);
  }
}
