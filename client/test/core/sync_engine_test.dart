import 'dart:convert';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/core/storage/local_database.dart';
import 'package:campushub/core/sync/sync_engine.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

Future<LocalDatabase> _openDb() =>
    LocalDatabase.open(inMemoryDatabasePath, factory: databaseFactoryFfi);

void main() {
  sqfliteFfiInit();

  test('queue drains through /sync/batch and marks per-item outcomes',
      () async {
    final db = await _openDb();
    await db.enqueue(
      clientId: 'c-1',
      entityTable: 'submissions',
      entityId: 'e-1',
      operation: 'create',
      payloadJson: jsonEncode({'assignment_id': 'a-1', 'content': {}}),
    );
    await db.enqueue(
      clientId: 'c-2',
      entityTable: 'submissions',
      entityId: 'e-2',
      operation: 'update',
      payloadJson: jsonEncode({'assignment_id': 'a-1'}),
      baseVersion: 1,
    );

    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (request.url.path == '/api/v1/sync/batch') {
          final items = (jsonDecode(request.body) as Map)['items'] as List;
          expect(items, hasLength(2));
          return http.Response(
            jsonEncode({
              'results': [
                {
                  'client_id': 'c-1',
                  'status': 'applied',
                  'entity_id': 'e-1',
                  'new_version': 1
                },
                {
                  'client_id': 'c-2',
                  'status': 'conflict',
                  'entity_id': 'e-2',
                  'server_version': 3,
                  'server_payload': {
                    'content': {'x': 1}
                  }
                },
              ],
            }),
            200,
          );
        }
        // Pull: empty page.
        return http.Response(
          jsonEncode({'changes': [], 'next_cursor': 0, 'has_more': false}),
          200,
        );
      }),
    );

    final result = await SyncEngine(api, db).runSyncCycle();
    expect(result.pushed, 1);
    expect(result.conflicts, 1);
    expect(result.offline, isFalse);
    expect(await db.countQueue('pending'), 0);
    expect(await db.countQueue('applied'), 1);
    expect(await db.countQueue('conflict'), 1);
    await db.close();
  });

  test('pull applies deltas to entity cache and advances the cursor', () async {
    final db = await _openDb();
    var pullCalls = 0;
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (request.url.path == '/api/v1/sync/batch') {
          return http.Response(jsonEncode({'results': []}), 200);
        }
        pullCalls++;
        if (pullCalls == 1) {
          expect(request.url.queryParameters['since'], '0');
          return http.Response(
            jsonEncode({
              'changes': [
                {
                  'cursor': 7,
                  'entity_table': 'resources',
                  'entity_id': 'r-1',
                  'operation': 'create',
                  'payload': {'title': 'Notes'},
                  'version': 1,
                  'changed_at': '2026-07-16T00:00:00Z'
                },
                {
                  'cursor': 9,
                  'entity_table': 'resources',
                  'entity_id': 'r-1',
                  'operation': 'delete',
                  'payload': {},
                  'version': 1,
                  'changed_at': '2026-07-16T00:01:00Z'
                },
              ],
              'next_cursor': 9,
              'has_more': true,
            }),
            200,
          );
        }
        expect(request.url.queryParameters['since'], '9');
        return http.Response(
          jsonEncode({
            'changes': [
              {
                'cursor': 12,
                'entity_table': 'announcements',
                'entity_id': 'a-1',
                'operation': 'create',
                'payload': {'title': 'Hello'},
                'version': 1,
                'changed_at': '2026-07-16T00:02:00Z'
              },
            ],
            'next_cursor': 12,
            'has_more': false,
          }),
          200,
        );
      }),
    );

    final result = await SyncEngine(api, db).runSyncCycle();
    expect(result.pulled, 3);
    // Deleted entity is hidden from reads.
    expect(await db.getEntity('resources', 'r-1'), isNull);
    final announcements = await db.listEntities('announcements');
    expect(announcements, hasLength(1));
    // Cursor persisted for the next incremental cycle.
    expect(await db.getState('pull_cursor'), '12');
    await db.close();
  });

  test('offline cycle keeps queue intact and reports offline', () async {
    final db = await _openDb();
    await db.enqueue(
      clientId: 'c-1',
      entityTable: 'submissions',
      entityId: 'e-1',
      operation: 'create',
      payloadJson: '{}',
    );
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        throw http.ClientException('no route to host');
      }),
    );

    final result = await SyncEngine(api, db).runSyncCycle();
    expect(result.offline, isTrue);
    expect(await db.countQueue('pending'), 1); // nothing lost
    await db.close();
  });
}
