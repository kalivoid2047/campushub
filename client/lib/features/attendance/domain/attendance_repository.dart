/// Attendance domain — per-course report (Epic E6, FR-ATT-2).
library;

class CourseAttendanceRow {
  const CourseAttendanceRow({
    required this.userId,
    required this.fullName,
    required this.email,
    required this.sessionsAttended,
    required this.totalSessions,
    required this.attendanceRate,
  });

  final String userId;
  final String fullName;
  final String email;
  final int sessionsAttended;
  final int totalSessions;
  final double attendanceRate;

  factory CourseAttendanceRow.fromJson(Map<String, dynamic> json) =>
      CourseAttendanceRow(
        userId: json['user_id'] as String,
        fullName: json['full_name'] as String,
        email: json['email'] as String,
        sessionsAttended: json['sessions_attended'] as int,
        totalSessions: json['total_sessions'] as int,
        attendanceRate: (json['attendance_rate'] as num).toDouble(),
      );
}

class CourseAttendanceReport {
  const CourseAttendanceReport(
      {required this.totalSessions, required this.rows});

  final int totalSessions;
  final List<CourseAttendanceRow> rows;

  factory CourseAttendanceReport.fromJson(Map<String, dynamic> json) =>
      CourseAttendanceReport(
        totalSessions: json['total_sessions'] as int,
        rows: [
          for (final row in json['rows'] as List<dynamic>)
            CourseAttendanceRow.fromJson(row as Map<String, dynamic>)
        ],
      );
}

/// The caller's own attendance in a course — a lighter view than
/// [CourseAttendanceReport] available to any enrolled member, not just
/// lecturers (beyond FR-ATT-2's spec, added because there was previously no
/// way for a student to check their own attendance at all).
class MyAttendance {
  const MyAttendance({
    required this.sessionsAttended,
    required this.totalSessions,
    required this.attendanceRate,
  });

  final int sessionsAttended;
  final int totalSessions;
  final double attendanceRate;

  factory MyAttendance.fromJson(Map<String, dynamic> json) => MyAttendance(
        sessionsAttended: json['sessions_attended'] as int,
        totalSessions: json['total_sessions'] as int,
        attendanceRate: (json['attendance_rate'] as num).toDouble(),
      );
}

abstract class AttendanceRepository {
  /// Lecturer-only server-side (docs/08 section 7 RBAC matrix); requires
  /// connectivity, not cached.
  Future<CourseAttendanceReport> courseReport(String courseId);

  /// Any enrolled member; requires connectivity, not cached.
  Future<MyAttendance> myAttendance(String courseId);
}
