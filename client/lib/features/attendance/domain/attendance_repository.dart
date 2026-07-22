/// Attendance domain — per-course report (Epic E6, FR-ATT-2).
library;

class CourseAttendanceRow {
  const CourseAttendanceRow({
    required this.userId,
    required this.sessionsAttended,
    required this.totalSessions,
    required this.attendanceRate,
  });

  final String userId;
  final int sessionsAttended;
  final int totalSessions;
  final double attendanceRate;

  factory CourseAttendanceRow.fromJson(Map<String, dynamic> json) =>
      CourseAttendanceRow(
        userId: json['user_id'] as String,
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

abstract class AttendanceRepository {
  /// Lecturer-only server-side (docs/08 section 7 RBAC matrix); requires
  /// connectivity, not cached.
  Future<CourseAttendanceReport> courseReport(String courseId);
}
