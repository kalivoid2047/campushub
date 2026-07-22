import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../error/app_exception.dart';

/// Supplies the current access token and performs a refresh when the API
/// rejects it. Implemented by the auth layer; injected so ApiClient stays
/// free of auth-domain knowledge.
abstract class TokenProvider {
  String? get accessToken;

  /// Attempt a refresh; returns true when a new access token is available.
  Future<bool> refresh();
}

/// HTTP client per docs/06-api-design.md: attaches `Authorization: Bearer`,
/// retries exactly once through the refresh flow on 401, and maps error
/// responses to [ApiException].
class ApiClient {
  ApiClient(this.baseUrl,
      {http.Client? httpClient, TokenProvider? tokenProvider})
      : _http = httpClient ?? http.Client(),
        _tokenProvider = tokenProvider;

  final String baseUrl;
  final http.Client _http;
  TokenProvider? _tokenProvider;

  /// Late binding: the auth repository needs an ApiClient to log in, and the
  /// client needs the auth layer for tokens — resolved by attaching after
  /// construction.
  set tokenProvider(TokenProvider provider) => _tokenProvider = provider;

  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, String>? query,
  }) async {
    final response = await _send('GET', path, query: query);
    return _decodeObject(response);
  }

  Future<List<dynamic>> getJsonList(
    String path, {
    Map<String, String>? query,
  }) async {
    final response = await _send('GET', path, query: query);
    return jsonDecode(utf8.decode(response.bodyBytes)) as List<dynamic>;
  }

  Future<Map<String, dynamic>> postJson(
    String path,
    Map<String, dynamic> body, {
    bool authenticated = true,
  }) async {
    final response =
        await _send('POST', path, body: body, authenticated: authenticated);
    return _decodeObject(response);
  }

  Future<Map<String, dynamic>> patchJson(
    String path,
    Map<String, dynamic> body,
  ) async {
    final response = await _send('PATCH', path, body: body);
    return _decodeObject(response);
  }

  Future<void> delete(String path) async {
    await _send('DELETE', path);
  }

  /// Raw bytes from an authenticated API route (e.g. the local-storage
  /// content-stream endpoint, docs/06 section 6 `/resources/{id}/content`).
  Future<http.Response> getBytes(String path) => _send('GET', path);

  /// Fetches a presigned URL (S3-compatible download link) directly — no
  /// Authorization header, since the URL itself carries a signed, scoped,
  /// time-limited credential (docs/08 section 6). Never send bearer tokens
  /// to third-party/absolute URLs supplied by the server.
  Future<Uint8List> fetchExternal(String absoluteUrl) async {
    try {
      final response = await _http.get(Uri.parse(absoluteUrl));
      if (response.statusCode >= 400) {
        throw ApiException.fromResponse(response.statusCode, response.body);
      }
      return response.bodyBytes;
    } on http.ClientException catch (error) {
      throw NetworkUnavailableException(error.message);
    }
  }

  Future<http.Response> _send(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? query,
    bool authenticated = true,
    bool isRetry = false,
  }) async {
    final uri = Uri.parse('$baseUrl$path').replace(
      queryParameters: query == null || query.isEmpty ? null : query,
    );
    final request = http.Request(method, uri);
    request.headers['Accept'] = 'application/json';
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }
    final token = _tokenProvider?.accessToken;
    if (authenticated && token != null) {
      request.headers['Authorization'] = 'Bearer $token';
    }

    final http.Response response;
    try {
      response = await http.Response.fromStream(await _http.send(request));
    } on http.ClientException catch (error) {
      throw NetworkUnavailableException(error.message);
    }

    if (response.statusCode == 401 && authenticated && !isRetry) {
      final refreshed = await _tokenProvider?.refresh() ?? false;
      if (refreshed) {
        return _send(method, path, body: body, query: query, isRetry: true);
      }
    }
    if (response.statusCode >= 400) {
      throw ApiException.fromResponse(response.statusCode, response.body);
    }
    return response;
  }

  Map<String, dynamic> _decodeObject(http.Response response) {
    if (response.bodyBytes.isEmpty) return const {};
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }
}
