import 'dart:convert';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/core/storage/local_database.dart';
import 'package:campushub/core/sync/sync_engine.dart';
import 'package:campushub/features/assignments/data/assignments_repository_impl.dart';
import 'package:campushub/features/assignments/domain/assignments_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

Future<LocalDatabase> _openDb() =>
    LocalDatabase.open(inMemoryDatabasePath, factory: databaseFactoryFfi);

void main() {
  sqfliteFfiInit();

  test('online submit posts with client_id and reports server status',
      () async {
    final db = await _openDb();
    String? seenClientId;
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/assignments/a-1/submissions');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        seenClientId = body['client_id'] as String?;
        expect(body['finalize'], isTrue);
        return http.Response(
          jsonEncode({
            'id': 's-1',
            'assignment_id': 'a-1',
            'student_id': 'u-1',
            'content': body['content'],
            'status': 'late',
            'version': 1,
            'submitted_at': '2026-07-16T00:00:00Z',
            'created_at': '2026-07-16T00:00:00Z',
            'updated_at': '2026-07-16T00:00:00Z',
          }),
          201,
        );
      }),
    );
    final repository = AssignmentsRepositoryImpl(api, db);

    final outcome = await repository.submit(
      assignmentId: 'a-1',
      content: {'text': 'answer'},
    );
    expect(outcome.delivery, SubmissionDelivery.submitted);
    expect(outcome.status, 'late');
    expect(seenClientId, isNotNull);
    expect(await db.countQueue('pending'), 0); // nothing queued when online
    await db.close();
  });

  test('offline submit queues, then the sync engine delivers it', () async {
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
    final repository = AssignmentsRepositoryImpl(api, db);

    // Airplane mode: the submission is queued, not lost.
    final outcome = await repository.submit(
      assignmentId: 'a-1',
      content: {'text': 'written on a bus'},
    );
    expect(outcome.delivery, SubmissionDelivery.queuedOffline);
    expect(await db.countQueue('pending'), 1);

    // Connectivity returns: the sync cycle drains the queue.
    online = true;
    final result = await SyncEngine(api, db).runSyncCycle();
    expect(result.pushed, 1);
    expect(await db.countQueue('pending'), 0);

    // The queued payload matches the backend sync-handler contract.
    final item =
        (batchBodies.single['items'] as List).single as Map<String, dynamic>;
    expect(item['entity_table'], 'submissions');
    expect(item['operation'], 'create');
    final payload = item['payload'] as Map<String, dynamic>;
    expect(payload['assignment_id'], 'a-1');
    expect(payload['finalize'], isTrue);
    expect(payload['content'], {'text': 'written on a bus'});
    await db.close();
  });

  test('assignments list falls back to cache per course', () async {
    final db = await _openDb();
    var online = true;
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (!online) throw http.ClientException('offline');
        final courseId = request.url.pathSegments[3];
        return http.Response(
          jsonEncode([
            {
              'id': 'a-$courseId',
              'course_id': courseId,
              'title': 'PS1',
              'instructions': 'Solve.',
              'due_at': null,
              'allow_late': true,
              'max_score': 100,
              'rubric': null,
              'created_by': 'u-1',
              'created_at': '2026-07-16T00:00:00Z',
            },
          ]),
          200,
        );
      }),
    );
    final repository = AssignmentsRepositoryImpl(api, db);

    await repository.listAssignments('c-1');
    await repository.listAssignments('c-2');
    online = false;
    final cached = await repository.listAssignments('c-1');
    expect(cached.single.id, 'a-c-1');
    await db.close();
  });
}
