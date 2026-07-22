import '../../../core/network/api_client.dart';
import '../domain/virtual_classroom_repository.dart';

class VirtualClassroomRepositoryImpl implements VirtualClassroomRepository {
  VirtualClassroomRepositoryImpl(this._api);

  final ApiClient _api;

  @override
  Future<List<ClassSessionSummary>> listSessions(String courseId) async {
    final rows = await _api.getJsonList('/api/v1/courses/$courseId/sessions');
    return [
      for (final row in rows)
        ClassSessionSummary.fromJson(row as Map<String, dynamic>)
    ];
  }

  @override
  Future<ClassSessionSummary> createSession(
      String courseId, String title) async {
    final json = await _api.postJson(
      '/api/v1/courses/$courseId/sessions',
      {'title': title},
    );
    return ClassSessionSummary.fromJson(json);
  }

  @override
  Future<ClassSessionSummary> start(String sessionId) async {
    final json =
        await _api.postJson('/api/v1/sessions/$sessionId/start', const {});
    return ClassSessionSummary.fromJson(json);
  }

  @override
  Future<ClassSessionSummary> end(String sessionId) async {
    final json =
        await _api.postJson('/api/v1/sessions/$sessionId/end', const {});
    return ClassSessionSummary.fromJson(json);
  }

  @override
  Future<JoinInfo> join(String sessionId) async {
    final json =
        await _api.postJson('/api/v1/sessions/$sessionId/join', const {});
    return JoinInfo.fromJson(json);
  }

  @override
  Future<void> leave(String sessionId) async {
    await _api.postJson('/api/v1/sessions/$sessionId/leave', const {});
  }
}
