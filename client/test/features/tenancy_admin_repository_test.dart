import 'dart:convert';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/features/tenancy_admin/data/tenancy_admin_repository_impl.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('createDepartment posts name/code and parses the response', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.url.path, '/api/v1/admin/departments');
        expect(jsonDecode(request.body), {'name': 'Computer Science', 'code': 'CS'});
        return http.Response(
          jsonEncode({
            'id': 'd-1',
            'name': 'Computer Science',
            'code': 'CS',
            'created_at': '2026-07-22T00:00:00Z',
          }),
          201,
        );
      }),
    );
    final repository = TenancyAdminRepositoryImpl(api);

    final department = await repository.createDepartment(name: 'Computer Science', code: 'CS');
    expect(department.id, 'd-1');
    expect(department.code, 'CS');
  });

  test('createCourse posts department_id/name/code/term', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/admin/courses');
        expect(jsonDecode(request.body), {
          'department_id': 'd-1',
          'name': 'Algorithms',
          'code': 'CS201',
          'term': '2026-fall',
        });
        return http.Response(
          jsonEncode({
            'id': 'c-1',
            'department_id': 'd-1',
            'name': 'Algorithms',
            'code': 'CS201',
            'term': '2026-fall',
            'created_at': '2026-07-22T00:00:00Z',
          }),
          201,
        );
      }),
    );
    final repository = TenancyAdminRepositoryImpl(api);

    final course = await repository.createCourse(
      departmentId: 'd-1',
      name: 'Algorithms',
      code: 'CS201',
      term: '2026-fall',
    );
    expect(course.id, 'c-1');
    expect(course.departmentId, 'd-1');
  });

  test('enrollUser posts user_id/role to the course enrollments endpoint', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/admin/courses/c-1/enrollments');
        expect(jsonDecode(request.body), {'user_id': 'u-1', 'role': 'student'});
        return http.Response(
          jsonEncode({
            'id': 'e-1',
            'course_id': 'c-1',
            'user_id': 'u-1',
            'role': 'student',
            'enrolled_at': '2026-07-22T00:00:00Z',
          }),
          201,
        );
      }),
    );
    final repository = TenancyAdminRepositoryImpl(api);

    await repository.enrollUser(courseId: 'c-1', userId: 'u-1', role: 'student');
  });

  test('storageUsage parses the quota response', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/admin/storage/usage');
        return http.Response(
          jsonEncode({'used_bytes': 512, 'quota_bytes': 1024, 'percent_used': 50.0}),
          200,
        );
      }),
    );
    final repository = TenancyAdminRepositoryImpl(api);

    final usage = await repository.storageUsage();
    expect(usage.usedBytes, 512);
    expect(usage.percentUsed, 50.0);
  });

  test('listUsers sends limit/offset and parses the directory', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/admin/users');
        expect(request.url.queryParameters['limit'], '200');
        expect(request.url.queryParameters['offset'], '0');
        return http.Response(
          jsonEncode([
            {
              'id': 'u-1',
              'email': 'a@srch.edu',
              'full_name': 'Ada',
              'roles': ['student'],
            },
          ]),
          200,
        );
      }),
    );
    final repository = TenancyAdminRepositoryImpl(api);

    final users = await repository.listUsers();
    expect(users, hasLength(1));
    expect(users[0].fullName, 'Ada');
    expect(users[0].roles, ['student']);
  });

  test('auditLogs sends limit/offset as query parameters', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/admin/audit-logs');
        expect(request.url.queryParameters['limit'], '50');
        expect(request.url.queryParameters['offset'], '10');
        return http.Response(
          jsonEncode([
            {
              'id': 'a-1',
              'actor_id': 'u-1',
              'action': 'department.created',
              'target_type': 'department',
              'target_id': 'd-1',
              'metadata': {},
              'ip_address': null,
              'created_at': '2026-07-22T00:00:00Z',
            },
          ]),
          200,
        );
      }),
    );
    final repository = TenancyAdminRepositoryImpl(api);

    final entries = await repository.auditLogs(limit: 50, offset: 10);
    expect(entries, hasLength(1));
    expect(entries[0].action, 'department.created');
  });
}
