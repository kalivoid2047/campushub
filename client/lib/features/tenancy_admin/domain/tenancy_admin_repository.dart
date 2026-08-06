/// Tenancy admin domain — departments, courses, enrollment, users, storage
/// quota, audit log, and basic engagement analytics (Epic E8,
/// docs/06-api-design.md section 6). All operations require an admin-tier
/// role server-side (docs/08-security-design.md section 7 RBAC matrix); this
/// client trusts the backend's 403 rather than re-implementing the role
/// matrix locally.
library;

class AdminDepartment {
  const AdminDepartment(
      {required this.id, required this.name, required this.code});

  final String id;
  final String name;
  final String code;

  factory AdminDepartment.fromJson(Map<String, dynamic> json) =>
      AdminDepartment(
        id: json['id'] as String,
        name: json['name'] as String,
        code: json['code'] as String,
      );
}

class AdminCourse {
  const AdminCourse({
    required this.id,
    required this.departmentId,
    required this.name,
    required this.code,
    required this.term,
  });

  final String id;
  final String departmentId;
  final String name;
  final String code;
  final String term;

  factory AdminCourse.fromJson(Map<String, dynamic> json) => AdminCourse(
        id: json['id'] as String,
        departmentId: json['department_id'] as String,
        name: json['name'] as String,
        code: json['code'] as String,
        term: json['term'] as String,
      );
}

class TenantUser {
  const TenantUser({
    required this.id,
    required this.email,
    required this.fullName,
    required this.roles,
  });

  final String id;
  final String email;
  final String fullName;
  final List<String> roles;

  factory TenantUser.fromJson(Map<String, dynamic> json) => TenantUser(
        id: json['id'] as String,
        email: json['email'] as String,
        fullName: json['full_name'] as String,
        roles: (json['roles'] as List<dynamic>).cast<String>(),
      );
}

class StorageUsage {
  const StorageUsage({
    required this.usedBytes,
    required this.quotaBytes,
    required this.percentUsed,
  });

  final int usedBytes;
  final int quotaBytes;
  final double percentUsed;

  factory StorageUsage.fromJson(Map<String, dynamic> json) => StorageUsage(
        usedBytes: json['used_bytes'] as int,
        quotaBytes: json['quota_bytes'] as int,
        percentUsed: (json['percent_used'] as num).toDouble(),
      );
}

class EngagementCounts {
  const EngagementCounts({
    required this.users,
    required this.resources,
    required this.messages,
    required this.submissions,
  });

  final int users;
  final int resources;
  final int messages;
  final int submissions;

  factory EngagementCounts.fromJson(Map<String, dynamic> json) =>
      EngagementCounts(
        users: json['users'] as int,
        resources: json['resources'] as int,
        messages: json['messages'] as int,
        submissions: json['submissions'] as int,
      );
}

class AdminAuditLogEntry {
  const AdminAuditLogEntry({
    required this.id,
    required this.actorId,
    required this.action,
    required this.targetType,
    required this.targetId,
    required this.createdAt,
  });

  final String id;
  final String? actorId;
  final String action;
  final String? targetType;
  final String? targetId;
  final DateTime createdAt;

  factory AdminAuditLogEntry.fromJson(Map<String, dynamic> json) =>
      AdminAuditLogEntry(
        id: json['id'] as String,
        actorId: json['actor_id'] as String?,
        action: json['action'] as String,
        targetType: json['target_type'] as String?,
        targetId: json['target_id'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

/// Course-enrollment role (docs/05 section 3.5) — distinct from the account
/// roles a user is created with (see [userRoles]).
const List<String> courseEnrollmentRoles = ['student', 'lecturer', 'ta'];

/// Account roles assignable via [TenancyAdminRepository.createUser]
/// (docs/06 section 6; super_admin is provisioned only via tenant creation).
const List<String> userRoles = [
  'student',
  'lecturer',
  'dept_admin',
  'institution_admin'
];

abstract class TenancyAdminRepository {
  Future<List<AdminDepartment>> listDepartments();

  Future<AdminDepartment> createDepartment(
      {required String name, required String code});

  Future<List<AdminCourse>> listCourses();

  Future<AdminCourse> createCourse({
    required String departmentId,
    required String name,
    required String code,
    required String term,
  });

  Future<TenantUser> createUser({
    required String email,
    required String password,
    required String fullName,
    required String role,
  });

  Future<List<TenantUser>> listUsers({int limit = 200, int offset = 0});

  Future<void> enrollUser({
    required String courseId,
    required String userId,
    required String role,
  });

  Future<StorageUsage> storageUsage();

  Future<EngagementCounts> engagement();

  Future<List<AdminAuditLogEntry>> auditLogs({int limit = 100, int offset = 0});
}
