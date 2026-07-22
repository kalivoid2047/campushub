import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Abstraction over platform secure storage (docs/08-security-design.md
/// section 5). Holds refresh tokens and the offline session artifact —
/// never raw credentials. The interface exists so tests can substitute an
/// in-memory fake without a platform channel.
abstract class SecureStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> deleteKey(String key);
}

/// Well-known keys.
abstract final class SecureKeys {
  static const refreshToken = 'campushub.refresh_token';
  static const offlineSession = 'campushub.offline_session';
  static const tenantSlug = 'campushub.tenant_slug';
}

/// Production implementation backed by Keychain/Keystore/DPAPI/Secret
/// Service depending on platform.
class PlatformSecureStore implements SecureStore {
  PlatformSecureStore() : _storage = const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);

  @override
  Future<void> deleteKey(String key) => _storage.delete(key: key);
}

/// In-memory fake for widget/unit tests.
class InMemorySecureStore implements SecureStore {
  final Map<String, String> _values = {};

  @override
  Future<String?> read(String key) async => _values[key];

  @override
  Future<void> write(String key, String value) async => _values[key] = value;

  @override
  Future<void> deleteKey(String key) async => _values.remove(key);
}
