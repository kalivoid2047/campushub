import 'dart:convert';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/features/search/data/search_repository_impl.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('search sends q as a query parameter and parses typed hits', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/search');
        expect(request.url.queryParameters['q'], 'genome');
        return http.Response(
          jsonEncode({
            'query': 'genome',
            'hits': [
              {
                'kind': 'resource',
                'id': 'r-1',
                'title': 'Genome slides',
                'snippet': 'Genome slides',
                'context_id': 'm-1',
                'created_at': '2026-07-16T00:00:00Z',
              },
              {
                'kind': 'message',
                'id': 'msg-1',
                'title': 'Message',
                'snippet': 'anyone understand genome imprinting?',
                'context_id': 'ch-1',
                'created_at': '2026-07-15T00:00:00Z',
              },
            ],
          }),
          200,
        );
      }),
    );
    final repository = SearchRepositoryImpl(api);

    final hits = await repository.search('genome');
    expect(hits, hasLength(2));
    expect(hits[0].kind, 'resource');
    expect(hits[0].contextId, 'm-1');
    expect(hits[1].kind, 'message');
    expect(hits[1].contextId, 'ch-1');
  });

  test('empty hits returns an empty list', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        return http.Response(jsonEncode({'query': 'x', 'hits': []}), 200);
      }),
    );
    final repository = SearchRepositoryImpl(api);

    expect(await repository.search('x'), isEmpty);
  });
}
