import '../../../core/network/api_client.dart';
import '../../../core/storage/secure_storage.dart';
import '../domain/auth_repository.dart';

/// Auth repository + TokenProvider (docs/06 section 2).
///
/// Access tokens live only in memory; refresh tokens go to platform secure
/// storage (docs/08 section 5). Attach to the ApiClient after construction:
///   apiClient.tokenProvider = authRepository;
class AuthRepositoryImpl implements AuthRepository, TokenProvider {
  AuthRepositoryImpl(this._api, this._secureStore);

  final ApiClient _api;
  final SecureStore _secureStore;

  String? _accessToken;

  @override
  String? get accessToken => _accessToken;

  @override
  Future<bool> refresh() async {
    final refreshToken = await _secureStore.read(SecureKeys.refreshToken);
    if (refreshToken == null) return false;
    try {
      final body = await _api.postJson(
        '/api/v1/auth/refresh',
        {'refresh_token': refreshToken},
        authenticated: false,
      );
      await _storeSession(body);
      return true;
    } catch (_) {
      // Refresh rejected (rotated elsewhere, expired, revoked): drop the
      // dead token so the app falls back to the login screen.
      _accessToken = null;
      await _secureStore.deleteKey(SecureKeys.refreshToken);
      return false;
    }
  }

  @override
  Future<bool> hasSession() async {
    if (_accessToken != null) return true;
    return await _secureStore.read(SecureKeys.refreshToken) != null;
  }

  @override
  Future<UserProfile> login({
    required String tenantSlug,
    required String email,
    required String password,
  }) async {
    final body = await _api.postJson(
      '/api/v1/auth/login',
      {'tenant_slug': tenantSlug, 'email': email, 'password': password},
      authenticated: false,
    );
    await _storeSession(body);
    await _secureStore.write(SecureKeys.tenantSlug, tenantSlug);
    return currentUser();
  }

  @override
  Future<UserProfile> currentUser() async {
    final body = await _api.getJson('/api/v1/auth/me');
    return UserProfile.fromJson(body);
  }

  @override
  Future<void> logout() async {
    final refreshToken = await _secureStore.read(SecureKeys.refreshToken);
    if (refreshToken != null) {
      try {
        await _api.postJson(
          '/api/v1/auth/logout',
          {'refresh_token': refreshToken},
          authenticated: false,
        );
      } catch (_) {
        // Offline logout still clears local state; the refresh token dies
        // server-side at its natural expiry (docs/08 section 2).
      }
    }
    _accessToken = null;
    await _secureStore.deleteKey(SecureKeys.refreshToken);
  }

  Future<void> _storeSession(Map<String, dynamic> tokenPair) async {
    _accessToken = tokenPair['access_token'] as String;
    await _secureStore.write(
      SecureKeys.refreshToken,
      tokenPair['refresh_token'] as String,
    );
  }
}
