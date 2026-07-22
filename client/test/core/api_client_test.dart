import 'dart:convert';

import 'package:campushub/core/error/app_exception.dart';
import 'package:campushub/core/network/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenProvider implements TokenProvider {
  _FakeTokenProvider(this._token);

  String? _token;
  int refreshCalls = 0;
  bool refreshSucceeds = true;

  @override
  String? get accessToken => _token;

  @override
  Future<bool> refresh() async {
    refreshCalls++;
    if (!refreshSucceeds) return false;
    _token = 'fresh-token';
    return true;
  }
}

void main() {
  test('attaches bearer token and decodes JSON', () async {
    late http.Request captured;
    final client = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        captured = request;
        return http.Response(jsonEncode({'ok': true}), 200);
      }),
      tokenProvider: _FakeTokenProvider('token-1'),
    );

    final body = await client.getJson('/api/v1/auth/me');
    expect(body['ok'], isTrue);
    expect(captured.headers['Authorization'], 'Bearer token-1');
  });

  test('retries once through refresh on 401 and succeeds', () async {
    final provider = _FakeTokenProvider('stale-token');
    var calls = 0;
    final client = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        calls++;
        if (request.headers['Authorization'] == 'Bearer fresh-token') {
          return http.Response(jsonEncode({'me': 'you'}), 200);
        }
        return http.Response(jsonEncode({'detail': 'expired'}), 401);
      }),
      tokenProvider: provider,
    );

    final body = await client.getJson('/api/v1/auth/me');
    expect(body['me'], 'you');
    expect(provider.refreshCalls, 1);
    expect(calls, 2); // original + one retry, never more
  });

  test('failed refresh surfaces the 401 without retry loop', () async {
    final provider = _FakeTokenProvider('stale-token')..refreshSucceeds = false;
    var calls = 0;
    final client = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        calls++;
        return http.Response(jsonEncode({'detail': 'nope'}), 401);
      }),
      tokenProvider: provider,
    );

    await expectLater(
      client.getJson('/api/v1/auth/me'),
      throwsA(
        isA<ApiException>().having((e) => e.statusCode, 'statusCode', 401),
      ),
    );
    expect(calls, 1);
  });

  test('connection failure maps to NetworkUnavailableException', () async {
    final client = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        throw http.ClientException('connection refused');
      }),
    );
    await expectLater(
      client.getJson('/api/v1/sync/changes'),
      throwsA(isA<NetworkUnavailableException>()),
    );
  });

  test('maps error statuses to stable codes with server detail', () async {
    final client = ApiClient(
      'http://api.test',
      httpClient: MockClient(
        (request) async => http.Response(
            jsonEncode({'detail': 'Not enrolled in course'}), 403),
      ),
      tokenProvider: _FakeTokenProvider('t'),
    );
    await expectLater(
      client.getJson('/api/v1/courses/x/modules'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.code, 'code', 'FORBIDDEN')
            .having((e) => e.message, 'message', 'Not enrolled in course'),
      ),
    );
  });
}
