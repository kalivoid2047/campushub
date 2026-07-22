import 'dart:convert';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/core/storage/local_database.dart';
import 'package:campushub/features/communication/data/communication_repository_impl.dart';
import 'package:campushub/features/resources/data/resources_repository_impl.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

Future<LocalDatabase> _openDb() =>
    LocalDatabase.open(inMemoryDatabasePath, factory: databaseFactoryFfi);

const _course = {
  'id': 'c-1',
  'department_id': 'd-1',
  'name': 'Data Structures',
  'code': 'CS201',
  'term': '2026-F',
  'created_at': '2026-07-16T00:00:00Z',
};

void main() {
  sqfliteFfiInit();

  test('online listCourses refreshes the cache; offline serves it', () async {
    final db = await _openDb();
    var online = true;
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (!online) throw http.ClientException('offline');
        expect(request.url.path, '/api/v1/courses');
        return http.Response(jsonEncode([_course]), 200);
      }),
    );
    final repository = CatalogRepositoryImpl(api, db);

    final fresh = await repository.listCourses();
    expect(fresh.single.code, 'CS201');

    online = false; // airplane mode
    final cached = await repository.listCourses();
    expect(cached.single.code, 'CS201');
    expect(cached.single.name, 'Data Structures');
    await db.close();
  });

  test('offline module/resource lists are scoped to their parent', () async {
    final db = await _openDb();
    var online = true;
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (!online) throw http.ClientException('offline');
        if (request.url.path.endsWith('/modules')) {
          final courseId = request.url.pathSegments[3];
          return http.Response(
            jsonEncode([
              {
                'id': 'm-$courseId',
                'course_id': courseId,
                'title': 'Week 1',
                'position': 1,
                'created_at': '2026-07-16T00:00:00Z'
              },
            ]),
            200,
          );
        }
        return http.Response(jsonEncode([]), 200);
      }),
    );
    final repository = CatalogRepositoryImpl(api, db);

    await repository.listModules('c-1');
    await repository.listModules('c-2');

    online = false;
    final courseOneModules = await repository.listModules('c-1');
    expect(courseOneModules.single.id, 'm-c-1'); // not c-2's module
    await db.close();
  });

  test('announcements fall back to cache newest-first', () async {
    final db = await _openDb();
    var online = true;
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        if (!online) throw http.ClientException('offline');
        return http.Response(
          jsonEncode([
            {
              'id': 'a-1',
              'scope': 'institution',
              'scope_id': null,
              'title': 'Old',
              'body': 'x',
              'published_by': 'u-1',
              'created_at': '2026-07-01T00:00:00Z'
            },
            {
              'id': 'a-2',
              'scope': 'course',
              'scope_id': 'c-1',
              'title': 'New',
              'body': 'y',
              'published_by': 'u-1',
              'created_at': '2026-07-15T00:00:00Z'
            },
          ]),
          200,
        );
      }),
    );
    final repository = CommunicationRepositoryImpl(api, db);

    await repository.listAnnouncements();
    online = false;
    final cached = await repository.listAnnouncements();
    expect(cached.map((a) => a.title).toList(), ['New', 'Old']);
    await db.close();
  });
}
