import '../../../core/network/api_client.dart';
import '../domain/attendance_repository.dart';

class AttendanceRepositoryImpl implements AttendanceRepository {
  AttendanceRepositoryImpl(this._api);

  final ApiClient _api;

  @override
  Future<CourseAttendanceReport> courseReport(String courseId) async {
    final json = await _api.getJson('/api/v1/courses/$courseId/attendance');
    return CourseAttendanceReport.fromJson(json);
  }
}
