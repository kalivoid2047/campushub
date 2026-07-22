import '../../../core/network/api_client.dart';
import '../domain/tenancy_admin_repository.dart';

/// Admin operations are always network-required, never cached — an admin
/// console showing stale storage/audit data is worse than one that fails
/// offline (mirrors attendance_repository_impl.dart's reasoning).
class TenancyAdminRepositoryImpl implements TenancyAdminRepository {
  TenancyAdminRepositoryImpl(this._api);

  final ApiClient _api;

  @override
  Future<List<AdminDepartment>> listDepartments() async {
    final rows = await _api.getJsonList('/api/v1/admin/departments');
    return [
      for (final row in rows) AdminDepartment.fromJson(row as Map<String, dynamic>)
    ];
  }

  @override
  Future<AdminDepartment> createDepartment({
    required String name,
    required String code,
  }) async {
    final json = await _api.postJson(
      '/api/v1/admin/departments',
      {'name': name, 'code': code},
    );
    return AdminDepartment.fromJson(json);
  }

  @override
  Future<List<AdminCourse>> listCourses() async {
    final rows = await _api.getJsonList('/api/v1/admin/courses');
    return [for (final row in rows) AdminCourse.fromJson(row as Map<String, dynamic>)];
  }

  @override
  Future<AdminCourse> createCourse({
    required String departmentId,
    required String name,
    required String code,
    required String term,
  }) async {
    final json = await _api.postJson('/api/v1/admin/courses', {
      'department_id': departmentId,
      'name': name,
      'code': code,
      'term': term,
    });
    return AdminCourse.fromJson(json);
  }

  @override
  Future<TenantUser> createUser({
    required String email,
    required String password,
    required String fullName,
    required String role,
  }) async {
    final json = await _api.postJson('/api/v1/admin/users', {
      'email': email,
      'password': password,
      'full_name': fullName,
      'role': role,
    });
    return TenantUser.fromJson(json);
  }

  @override
  Future<List<TenantUser>> listUsers({int limit = 200, int offset = 0}) async {
    final rows = await _api.getJsonList(
      '/api/v1/admin/users',
      query: {'limit': '$limit', 'offset': '$offset'},
    );
    return [for (final row in rows) TenantUser.fromJson(row as Map<String, dynamic>)];
  }

  @override
  Future<void> enrollUser({
    required String courseId,
    required String userId,
    required String role,
  }) async {
    await _api.postJson(
      '/api/v1/admin/courses/$courseId/enrollments',
      {'user_id': userId, 'role': role},
    );
  }

  @override
  Future<StorageUsage> storageUsage() async {
    final json = await _api.getJson('/api/v1/admin/storage/usage');
    return StorageUsage.fromJson(json);
  }

  @override
  Future<EngagementCounts> engagement() async {
    final json = await _api.getJson('/api/v1/admin/analytics/engagement');
    return EngagementCounts.fromJson(json);
  }

  @override
  Future<List<AdminAuditLogEntry>> auditLogs({int limit = 100, int offset = 0}) async {
    final rows = await _api.getJsonList(
      '/api/v1/admin/audit-logs',
      query: {'limit': '$limit', 'offset': '$offset'},
    );
    return [
      for (final row in rows) AdminAuditLogEntry.fromJson(row as Map<String, dynamic>)
    ];
  }
}
