import 'dart:convert';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/features/attendance/data/attendance_repository_impl.dart';
import 'package:campushub/features/virtual_classroom/data/virtual_classroom_repository_impl.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const _sessionJson = {
  'id': 's-1',
  'course_id': 'c-1',
  'title': 'Lecture 1',
  'status': 'scheduled',
  'scheduled_start': null,
  'scheduled_end': null,
  'actual_start': null,
  'actual_end': null,
  'created_by': 'u-1',
};

void main() {
  test('listSessions parses the course session list', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/courses/c-1/sessions');
        return http.Response(jsonEncode([_sessionJson]), 200);
      }),
    );
    final repository = VirtualClassroomRepositoryImpl(api);

    final sessions = await repository.listSessions('c-1');
    expect(sessions.single.id, 's-1');
    expect(sessions.single.status, 'scheduled');
  });

  test('createSession posts the title', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/courses/c-1/sessions');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['title'], 'Lecture 1');
        return http.Response(jsonEncode(_sessionJson), 201);
      }),
    );
    final repository = VirtualClassroomRepositoryImpl(api);

    final session = await repository.createSession('c-1', 'Lecture 1');
    expect(session.title, 'Lecture 1');
  });

  test('start/end/join/leave hit the right lifecycle endpoints', () async {
    final calledPaths = <String>[];
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        calledPaths.add(request.url.path);
        if (request.url.path.endsWith('/leave')) {
          return http.Response('', 204);
        }
        if (request.url.path.endsWith('/join')) {
          return http.Response(
            jsonEncode({
              'session_id': 's-1',
              'joined_at': '2026-07-16T00:00:00Z',
              'signaling_url': null,
              'sfu_token': null,
            }),
            200,
          );
        }
        return http.Response(
          jsonEncode({..._sessionJson, 'status': 'live'}),
          200,
        );
      }),
    );
    final repository = VirtualClassroomRepositoryImpl(api);

    await repository.start('s-1');
    final joinInfo = await repository.join('s-1');
    await repository.leave('s-1');
    await repository.end('s-1');

    expect(calledPaths, [
      '/api/v1/sessions/s-1/start',
      '/api/v1/sessions/s-1/join',
      '/api/v1/sessions/s-1/leave',
      '/api/v1/sessions/s-1/end',
    ]);
    expect(joinInfo.canOpenCall, isFalse); // LiveKit not configured
  });

  test('join returns a call-openable JoinInfo when LiveKit is configured',
      () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        return http.Response(
          jsonEncode({
            'session_id': 's-1',
            'joined_at': '2026-07-16T00:00:00Z',
            'signaling_url': 'wss://livekit.example.edu',
            'sfu_token': 'signed-jwt',
          }),
          200,
        );
      }),
    );
    final repository = VirtualClassroomRepositoryImpl(api);

    final joinInfo = await repository.join('s-1');
    expect(joinInfo.canOpenCall, isTrue);
    expect(joinInfo.signalingUrl, 'wss://livekit.example.edu');
    expect(joinInfo.sfuToken, 'signed-jwt');
  });

  test('startRecording/stopRecording hit the right endpoints', () async {
    final calledPaths = <String>[];
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        calledPaths.add(request.url.path);
        return http.Response(
          jsonEncode({
            'id': 'r-1',
            'status': request.url.path.endsWith('/stop') ? 'available' : 'processing',
            'duration_seconds': 90,
            'size_bytes': 12345,
            'created_at': '2026-07-16T00:00:00Z',
            'download_url':
                request.url.path.endsWith('/stop') ? 'https://s3.example/r-1.mp4' : null,
          }),
          200,
        );
      }),
    );
    final repository = VirtualClassroomRepositoryImpl(api);

    final started = await repository.startRecording('s-1');
    expect(started.status, 'processing');
    expect(started.downloadUrl, isNull);

    final stopped = await repository.stopRecording('s-1');
    expect(stopped.status, 'available');
    expect(stopped.downloadUrl, 'https://s3.example/r-1.mp4');

    expect(calledPaths, [
      '/api/v1/sessions/s-1/recording/start',
      '/api/v1/sessions/s-1/recording/stop',
    ]);
  });

  test('listRecordings parses the recordings list', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/sessions/s-1/recordings');
        return http.Response(
          jsonEncode([
            {
              'id': 'r-1',
              'status': 'available',
              'duration_seconds': 90,
              'size_bytes': 12345,
              'created_at': '2026-07-16T00:00:00Z',
              'download_url': 'https://s3.example/r-1.mp4',
            },
          ]),
          200,
        );
      }),
    );
    final repository = VirtualClassroomRepositoryImpl(api);

    final recordings = await repository.listRecordings('s-1');
    expect(recordings.single.id, 'r-1');
    expect(recordings.single.durationSeconds, 90);
  });

  test('courseReport parses the attendance report', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/courses/c-1/attendance');
        return http.Response(
          jsonEncode({
            'course_id': 'c-1',
            'total_sessions': 4,
            'rows': [
              {
                'user_id': 'u-1',
                'full_name': 'Ada Lovelace',
                'email': 'ada@campus.edu',
                'sessions_attended': 3,
                'total_sessions': 4,
                'attendance_rate': 0.75,
              },
            ],
          }),
          200,
        );
      }),
    );
    final repository = AttendanceRepositoryImpl(api);

    final report = await repository.courseReport('c-1');
    expect(report.totalSessions, 4);
    expect(report.rows.single.attendanceRate, 0.75);
    expect(report.rows.single.fullName, 'Ada Lovelace');
    expect(report.rows.single.email, 'ada@campus.edu');
  });

  test('myAttendance hits the self-service endpoint', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/api/v1/courses/c-1/attendance/me');
        return http.Response(
          jsonEncode({
            'course_id': 'c-1',
            'sessions_attended': 2,
            'total_sessions': 4,
            'attendance_rate': 0.5,
          }),
          200,
        );
      }),
    );
    final repository = AttendanceRepositoryImpl(api);

    final mine = await repository.myAttendance('c-1');
    expect(mine.sessionsAttended, 2);
    expect(mine.attendanceRate, 0.5);
  });
}
