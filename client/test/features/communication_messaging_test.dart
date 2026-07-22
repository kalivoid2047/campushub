import 'dart:convert';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/core/storage/local_database.dart';
import 'package:campushub/core/sync/sync_engine.dart';
import 'package:campushub/features/communication/data/communication_repository_impl.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

Future<LocalDatabase> _openDb() =>
    LocalDatabase.open(inMemoryDatabasePath, factory: databaseFactoryFfi);

void main() {
  sqfliteFfiInit();

  test('getCourseChannel hits the lazy-create endpoint', () async {
    final db = await _openDb();
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/courses/c-1/channel');
        return http.Response(
          jsonEncode({
            'id': 'ch-1',
            'type': 'course',
            'course_id': 'c-1',
            'name': 'CS101 discussion',
            'created_at': '2026-07-16T00:00:00Z',
          }),
          200,
        );
      }),
    );
    final repository = CommunicationRepositoryImpl(api, db);

    final channel = await repository.getCourseChannel('c-1');
    expect(channel.id, 'ch-1');
    expect(channel.type, 'course');
    await db.close();
  });

  test('getOrCreateDm posts the recipient id', () async {
    final db = await _openDb();
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/channels/dm');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['recipient_id'], 'u-2');
        return http.Response(
          jsonEncode({
            'id': 'dm-1',
            'type': 'dm',
            'course_id': null,
            'name': null,
            'created_at': '2026-07-16T00:00:00Z',
          }),
          200,
        );
      }),
    );
    final repository = CommunicationRepositoryImpl(api, db);

    final channel = await repository.getOrCreateDm('u-2');
    expect(channel.id, 'dm-1');
    expect(channel.type, 'dm');
    await db.close();
  });

  test('sendMessage includes a client_id and parses the response', () async {
    final db = await _openDb();
    String? seenClientId;
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/channels/ch-1/messages');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        seenClientId = body['client_id'] as String?;
        expect(body['body'], 'hello class');
        return http.Response(
          jsonEncode({
            'id': 'm-1',
            'channel_id': 'ch-1',
            'sender_id': 'u-1',
            'body': body['body'],
            'attachments': [],
            'created_at': '2026-07-16T00:00:00Z',
            'edited_at': null,
          }),
          201,
        );
      }),
    );
    final repository = CommunicationRepositoryImpl(api, db);

    final message = await repository.sendMessage(
      'ch-1',
      'hello class',
      currentUserId: 'u-1',
    );
    expect(message.body, 'hello class');
    expect(message.pending, isFalse);
    expect(seenClientId, isNotNull);
    expect(await db.countQueue('pending'), 0); // nothing queued when online
    await db.close();
  });

  test('offline sendMessage queues and returns a pending optimistic item',
      () async {
    final db = await _openDb();
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        throw http.ClientException('offline');
      }),
    );
    final repository = CommunicationRepositoryImpl(api, db);

    final message = await repository.sendMessage(
      'ch-1',
      'written offline',
      currentUserId: 'u-1',
    );
    expect(message.pending, isTrue);
    expect(message.senderId, 'u-1');
    expect(message.body, 'written offline');
    expect(await db.countQueue('pending'), 1);
    await db.close();
  });

  test('the queued payload matches the backend messages sync-handler contract',
      () async {
    final db = await _openDb();
    var online = false;
    final batchBodies = <Map<String, dynamic>>[];
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (!online) throw http.ClientException('offline');
        if (request.url.path == '/api/v1/sync/batch') {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          batchBodies.add(body);
          final item = (body['items'] as List).single as Map<String, dynamic>;
          return http.Response(
            jsonEncode({
              'results': [
                {
                  'client_id': item['client_id'],
                  'status': 'applied',
                  'entity_id': item['entity_id'],
                  'new_version': 1,
                },
              ],
            }),
            200,
          );
        }
        return http.Response(
          jsonEncode({'changes': [], 'next_cursor': 0, 'has_more': false}),
          200,
        );
      }),
    );
    final repository = CommunicationRepositoryImpl(api, db);

    final queued = await repository.sendMessage(
      'ch-1',
      'from the sync queue',
      currentUserId: 'u-1',
    );
    expect(queued.pending, isTrue);

    online = true;
    final result = await SyncEngine(api, db).runSyncCycle();
    expect(result.pushed, 1);
    expect(await db.countQueue('pending'), 0);

    final item =
        (batchBodies.single['items'] as List).single as Map<String, dynamic>;
    expect(item['entity_table'], 'messages');
    expect(item['operation'], 'create');
    final payload = item['payload'] as Map<String, dynamic>;
    expect(payload['channel_id'], 'ch-1');
    expect(payload['body'], 'from the sync queue');
    await db.close();
  });

  test('listMessages paginates via the before cursor', () async {
    final db = await _openDb();
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/channels/ch-1/messages');
        if (request.url.queryParameters.containsKey('before')) {
          expect(request.url.queryParameters['before'], '2026-07-15T00:00:00Z');
          return http.Response(
            jsonEncode({
              'messages': [
                {
                  'id': 'm-0',
                  'channel_id': 'ch-1',
                  'sender_id': 'u-1',
                  'body': 'older',
                  'attachments': [],
                  'created_at': '2026-07-14T00:00:00Z',
                  'edited_at': null,
                },
              ],
              'next_cursor': null,
              'has_more': false,
            }),
            200,
          );
        }
        return http.Response(
          jsonEncode({
            'messages': [
              {
                'id': 'm-1',
                'channel_id': 'ch-1',
                'sender_id': 'u-1',
                'body': 'newest',
                'attachments': [],
                'created_at': '2026-07-15T00:00:00Z',
                'edited_at': null,
              },
            ],
            'next_cursor': '2026-07-15T00:00:00Z',
            'has_more': true,
          }),
          200,
        );
      }),
    );
    final repository = CommunicationRepositoryImpl(api, db);

    final page1 = await repository.listMessages('ch-1');
    expect(page1.messages.single.body, 'newest');
    expect(page1.hasMore, isTrue);

    final page2 =
        await repository.listMessages('ch-1', before: page1.nextCursor);
    expect(page2.messages.single.body, 'older');
    expect(page2.hasMore, isFalse);
    await db.close();
  });
}
