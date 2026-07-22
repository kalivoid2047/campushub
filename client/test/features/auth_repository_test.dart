import 'dart:convert';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/core/storage/secure_storage.dart';
import 'package:campushub/features/auth/data/auth_repository_impl.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('login stores refresh token securely and exposes profile', () async {
    final store = InMemorySecureStore();
    final client = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        switch (request.url.path) {
          case '/api/v1/auth/login':
            final body = jsonDecode(request.body) as Map<String, dynamic>;
            expect(body['tenant_slug'], 'demo-college');
            return http.Response(
              jsonEncode({
                'access_token': 'access-1',
                'refresh_token': 'refresh-1',
                'token_type': 'bearer',
                'expires_in': 900,
              }),
              200,
            );
          case '/api/v1/auth/me':
            expect(request.headers['Authorization'], 'Bearer access-1');
            return http.Response(
              jsonEncode({
                'id': 'u-1',
                'tenant_id': 't-1',
                'email': 'student@demo.edu',
                'full_name': 'Demo Student',
                'status': 'active',
                'roles': ['student'],
              }),
              200,
            );
        }
        return http.Response('not found', 404);
      }),
    );
    final auth = AuthRepositoryImpl(client, store);
    client.tokenProvider = auth;

    final profile = await auth.login(
      tenantSlug: 'demo-college',
      email: 'student@demo.edu',
      password: 'demo-stud-pass',
    );

    expect(profile.roles, ['student']);
    expect(await store.read(SecureKeys.refreshToken), 'refresh-1');
    expect(await auth.hasSession(), isTrue);
  });

  test('refresh rotates tokens; rejected refresh clears the session', () async {
    final store = InMemorySecureStore();
    await store.write(SecureKeys.refreshToken, 'refresh-old');
    var rejectRefresh = false;
    final client = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (request.url.path == '/api/v1/auth/refresh') {
          if (rejectRefresh) {
            return http.Response(
                jsonEncode({'detail': 'Invalid credentials'}), 401);
          }
          expect(
            (jsonDecode(request.body) as Map)['refresh_token'],
            'refresh-old',
          );
          return http.Response(
            jsonEncode({
              'access_token': 'access-2',
              'refresh_token': 'refresh-new',
              'token_type': 'bearer',
              'expires_in': 900,
            }),
            200,
          );
        }
        return http.Response('not found', 404);
      }),
    );
    final auth = AuthRepositoryImpl(client, store);
    client.tokenProvider = auth;

    expect(await auth.refresh(), isTrue);
    expect(auth.accessToken, 'access-2');
    expect(await store.read(SecureKeys.refreshToken), 'refresh-new');

    // Server rejects (rotation theft-signal): local session is torn down.
    rejectRefresh = true;
    expect(await auth.refresh(), isFalse);
    expect(auth.accessToken, isNull);
    expect(await store.read(SecureKeys.refreshToken), isNull);
    expect(await auth.hasSession(), isFalse);
  });

  test('logout revokes server-side and clears local state even offline',
      () async {
    final store = InMemorySecureStore();
    await store.write(SecureKeys.refreshToken, 'refresh-1');
    final client = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        throw http.ClientException('offline');
      }),
    );
    final auth = AuthRepositoryImpl(client, store);
    client.tokenProvider = auth;

    await auth.logout(); // must not throw despite being offline
    expect(await store.read(SecureKeys.refreshToken), isNull);
    expect(await auth.hasSession(), isFalse);
  });
}
